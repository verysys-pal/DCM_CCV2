"""
Physics-inspired discrete-time simulator for a Bruker-type DCM Cryo-Cooler.

This file mirrors docs/logic/dcm_cryo_cooler_sim.py so that runtime code under
`sim/` provides the full simulator implementation, while `docs/logic` remains
as reference material.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


@dataclass
class Controls:
    V9: bool
    V11: bool
    V19: bool
    V15: bool
    V21: bool
    V10: float
    V17: float
    V20: float
    pump_hz: float
    press_ctrl_on: bool
    press_sp_bar: float
    _heater_u: float = 0.0


@dataclass
class State:
    T5: float
    T6: float
    PT1: float
    PT3: float
    LT19: float
    LT23: float
    FT18: float = 0.0
    ready: bool = False
    mode: str = 'IDLE'


class AutoKind(Enum):
    NONE = 0
    COOL_DOWN = auto()
    WARM_UP = auto()
    REFILL_HV = auto()
    REFILL_SUB = auto()


class CryoCoolerSim:
    """ 
    Simple physics-inspired discrete-time simulator for a Bruker-type DCM Cryo-Cooler.
    """
    Q80 = 15.0                  # Max flow rate at 80Hz, L/min      
    rho = 800.0                 # LN₂의 유효 밀도 [kg/m³]. 질량유량 ṁ 계산(ṁ = ρ·Q_eff/60·1e-3)에 사용.
    cp = 2000.0                 # LN₂의 유효 비열 [J/(kg·K)].열부하 반영 T6 = T5 + Power/(ṁ·c_p)에 사용.
    ambK = 280.0                # 주변 온도 [K]. 퍼지/격리 시 T5가 복귀하는 목표 온도
    delta_subcool = 6.0         # 서브쿨 여유(과냉도) [K]. T_supply = max(77, T_boil(PT1) − Δ_subcool·R_SC)에서 사용.
    k_tau = 120.0               # 냉각 1차시정수 계수 [s·(L/min)]. τ_cool = k_tau / Q_eff. 유량이 클수록 응답 빠름.
    tau_warm0 = 180.0           # 퍼지/가열 시 기본 시정수 [s]. 잔냉량(LT19)·펌프에 의해 자동 가중.
    Kh = 0.5                    # HV 히터 → PT3 가압 이득 [bar/s] (@히터출력 1).
    Kc = 0.4                    # PT3 → PT1 결합 이득 [1/s]. 베셀 압력이 루프 압력으로 전달되는 정도.
    kv17 = 0.5                  # 루프 벤트(V17)의 감압 계수 [1/s]. PT1을 1 bar로 내리는 속도 결정.
    kv20 = 0.5                  # HV 벤트(V20)의 감압 계수 [1/s]. PT3를 내리는 속도.
    kv21 = 0.8                  # 퍼지(V21)가 열릴 때 루프 감압 효과 [1/s]. PT1 저감 항에 가중.
    leak = 0.02                 # HV 압력의 누설/자연감압 계수 [1/s]. PT3가 1 bar로 서서히 복귀하는 경향.
    base_cons_Lps = 3.0 / 3600.0            # 기본 LN₂ 소비량 [L/s](≈3 L/h). 순수 유지·기본 손실.
    cons_coeff_Lps_perW = 0.023 / 3600.0    # 열부하 100 W당 약 2.3 L/h 추가 소비 항의 계수 [(L/s)/W].
    gamma_vent_Lps_per_Lpm = 0.004 / 60.0   # 오픈루프(벤트 경로)로 손실되는 추가 소비 계수 [(L/s)/(L/min)]. 
    Vsub_L = 200.0              # 서브쿨러 유효 용량 [L]. 레벨 %↔절대량 변환에 사용.
    Vhv_L = 20.0                # 히터 베셀 유효 용량 [L]. LT23 변화 속도에 영향.
    PSV_open_bar = 5.0          # 안전밸브(PSV) 작동 압력 [bar(g)]. 모델은 PSV−0.5로 클램핑.
    max_bar = 5.0               # 시뮬레이터 상 한계 압력 [bar(g)]. 수치적 안전 클램프.

    def __init__(self, state: State, controls: Controls):
        self.state = state
        self.controls = controls
        self.auto: AutoKind = AutoKind.NONE
        self.paused: bool = False
        self.stage: int = 0
        self.stage_timer: float = 0.0
        self._pulse_timer: float = 0.0
        self._pulse_state: bool = False
        # --- Tunable level dynamics (can be overridden via YAML through pv_bridge) ---
        # Subcooler (LT19) fill flow when V19 is OPEN [L/s]
        self.fill_Lps_v19: float = 1.0 / 60.0
        # HV tank (LT23) refill/drain rates in percentage per second [%/s]
        # Defaults reflect current accelerated test tuning
        self.refill_rate_pctps: float = 10.0 / 60.0
        self.drain_rate_pctps: float = 1.0 / 60.0
        # HV tank consumption terms (percentage per second) — adjustable via YAML through pv_bridge
        self.hv_base_cons_pctps: float = 0.0            # base consumption when system running
        self.hv_power_cons_pctps_perW: float = 0.0      # additional per-W power consumption
        self.hv_heater_cons_pctps_max: float = 0.0      # additional when press control ON (scaled by heater_u)
        self.hv_vent_gamma_pctps: float = 0.0           # additional when HV vent (V20) open (scaled by V20)

    @staticmethod
    def clamp(v, lo, hi):
        return max(lo, min(hi, v))

    def T_boil(self, pt_bar: float) -> float:
        return 77.0 + 3.8 * self.clamp(pt_bar, 0.0, 5.0)

    def _flow_base(self) -> float:
        u = self.controls
        v10 = self.clamp(u.V10, 0.0, 1.0)
        return self.Q80 * (self.clamp(u.pump_hz, 0.0, 80.0) / 80.0) * (0.4 + 0.6 * v10)

    def flow_loop_and_eff(self):
        u = self.controls
        base = self._flow_base()
        Q_loop = base if (u.V9 and u.V11) else 0.0
        Q_eff = base if (u.V9 and (u.V11 or u.V17 > 0.01)) else 0.0
        return Q_loop, Q_eff

    def _rsc(self) -> float:
        return self.clamp(self.state.LT19 / 40.0, 0.0, 1.0)

    def auto_cool_down(self):
        self.auto = AutoKind.COOL_DOWN
        self.stage = 0
        self.stage_timer = 0.0
        self.state.mode = 'COOLING'

    def auto_warm_up(self):
        self.auto = AutoKind.WARM_UP
        self.stage = 0
        self.stage_timer = 0.0
        self.state.mode = 'WARMUP'

    def auto_refill_hv(self):
        self.auto = AutoKind.REFILL_HV
        self.stage = 0
        self.stage_timer = 0.0

    def auto_refill_subcooler(self):
        """서브쿨러(LT19) 보충 자동 시퀀스.

        간단한 정책:
        - V19 OPEN으로 충전 시작
        - 목표치(예: 50%) 도달 시 V19 CLOSE 후 종료
        다른 밸브/제어는 변경하지 않음(현재 상태 유지)
        """
        self.auto = AutoKind.REFILL_SUB
        self.stage = 0
        self.stage_timer = 0.0

    def stop(self):
        u = self.controls
        # 기본 상태로 복귀: 모든 밸브 CLOSE, 단 V10=100% OPEN
        u.V9 = False
        u.V11 = False
        u.V15 = False
        u.V19 = False
        u.V21 = False
        u.V17 = 0.0
        u.V20 = 0.0
        u.V10 = 1.0
        u.pump_hz = 0.0
        u.press_ctrl_on = False
        self.state.ready = False
        self.state.mode = 'STOP'

    def off(self):
        self.stop()
        u = self.controls
        u.V17 = 1.0
        u.V20 = 1.0
        self.state.mode = 'OFF'

    def _update_auto(self, dt: float):
        u, s = self.controls, self.state
        # HOLD 모드에서는 자동 시퀀스 진행만 일시 정지
        if self.paused:
            return
        if self.auto == AutoKind.NONE:
            return
        self.stage_timer += dt

        if self.auto == AutoKind.COOL_DOWN:
            """
            쿨다운 시퀀스(stage) 진행 기준
            Stage 0: 초기 purge/보충(60초 등)
            Stage 1: HV 보충(PT3 제어 off)
            Stage 2: V9 on, V17=1.0 유지, T6 < 200 K 도달 시 다음
            Stage 3: V17=0.35, V11 on, T6 < 90 K 도달 시 다음
            Stage 4: V17=0.0, T6 < 82 K 도달 시 다음
            Stage 5: 압력 제어 on(press_ctrl_on=True), PT3를 SP(기본 2.0 bar)로 맞추고 READY로 수렴
            """
            if self.stage == 0:
                u.V10 = 0.6
                u.pump_hz = max(u.pump_hz, 30.0)
                u.V17 = 0.0
                u.V20 = 0.0
                u.V21 = False
                u.V9 = False
                u.V11 = False
                u.V19 = True
                if self.stage_timer >= 3.0:
                    u.V19 = False
                    self.stage += 1
                    self.stage_timer = 0.0
            elif self.stage == 1:
                u.press_ctrl_on = False
                u.V15 = True
                self._pulse_timer += dt
                if self._pulse_timer >= 1.0:
                    self._pulse_state = not self._pulse_state
                    self._pulse_timer = 0.0
                u.V20 = 1.0 if self._pulse_state else 0.0
                if s.LT23 >= 90.0:
                    u.V15 = False
                    u.V20 = 0.0
                    self.stage += 1
                    self.stage_timer = 0.0
            elif self.stage == 2:
                u.V9 = True
                u.V17 = 1.0
                if s.T6 < 200.0:
                    self.stage += 1
                    self.stage_timer = 0.0
            elif self.stage == 3:
                u.V17 = 0.35
                u.V11 = True
                if s.T6 < 90.0:
                    self.stage += 1
                    self.stage_timer = 0.0
            elif self.stage == 4:
                u.V17 = 0.0
                if s.T6 < 82.0:
                    self.stage += 1
                    self.stage_timer = 0.0
            elif self.stage == 5:
                u.press_ctrl_on = True
                u.press_sp_bar = max(u.press_sp_bar, 2.0)
                if s.LT23 > 30.0:
                    u.V17 = 0.3
                elif s.LT23 < 25.0:
                    u.press_ctrl_on = False
                    u.V15 = True
                    self._pulse_timer += dt
                    if self._pulse_timer >= 1.0:
                        self._pulse_state = not self._pulse_state
                        self._pulse_timer = 0.0
                    u.V20 = 1.0 if self._pulse_state else 0.0
                    if s.LT23 >= 45.0:
                        u.V15 = False
                        u.V20 = 0.0
                        u.press_ctrl_on = True
                else:
                    u.V17 = 0.0
                    if self._is_ready():
                        self.state.mode = 'READY'
                        self.auto = AutoKind.NONE
                        self.stage = 0
                        self.stage_timer = 0.0
        elif self.auto == AutoKind.WARM_UP:
            if self.stage == 0:
                u.V9 = False
                u.V11 = False
                u.V10 = 1.0
                u.V17 = 0.4
                u.pump_hz = max(u.pump_hz, 30.0)
                u.press_ctrl_on = False
                if s.PT1 < 1.0:
                    self.stage += 1
                    self.stage_timer = 0.0
            elif self.stage == 1:
                u.V21 = True
                if s.T6 >= 280.0:
                    u.V21 = False
                    u.V17 = 0.0
                    self.auto = AutoKind.NONE
                    self.stage = 0
                    self.state.mode = 'IDLE'
        elif self.auto == AutoKind.REFILL_HV:
            if self.stage == 0:
                u.press_ctrl_on = False
                u.V15 = True
                self.stage += 1
                self.stage_timer = 0.0
            elif self.stage == 1:
                self._pulse_timer += dt
                if self._pulse_timer >= 1.0:
                    self._pulse_state = not self._pulse_state
                    self._pulse_timer = 0.0
                u.V20 = 1.0 if self._pulse_state else 0.0
                if self.state.LT23 >= 25.0:
                    u.V15 = False
                    u.V20 = 0.0
                    u.press_ctrl_on = True
                    self.auto = AutoKind.NONE
                    self.stage = 0
        elif self.auto == AutoKind.REFILL_SUB:
            if self.stage == 0:
                # 서브쿨러 보충 시작
                u.V19 = True
                self.stage += 1
                self.stage_timer = 0.0
            elif self.stage == 1:
                # 목표 레벨 도달 시 종료
                if self.state.LT19 >= 50.0:
                    u.V19 = False
                    self.auto = AutoKind.NONE
                    self.stage = 0

    def _is_ready(self) -> bool:
        s, u = self.state, self.controls
        ready = (
            u.V9
            and u.V11
            and u.pump_hz > 0.0
            and u.press_ctrl_on
            and abs(s.PT3 - u.press_sp_bar) < 0.05
            and abs(s.PT1 - u.press_sp_bar) < 0.1
            and s.LT23 > 20.0
            and s.T5 < 80.0
        )
        return ready

    def _update_pressures(self, dt: float):
        s, u = self.state, self.controls
        if u.press_ctrl_on:
            err = u.press_sp_bar - s.PT3
            u._heater_u = self.clamp(u._heater_u + 0.8 * err * dt + 0.02 * err, 0.0, 1.0)
        else:
            u._heater_u = 0.0
        dPT3 = self.Kh * u._heater_u - self.kv20 * u.V20 * max(s.PT3 - 1.0, 0.0) - self.leak * max(s.PT3 - 1.0, 0.0)
        s.PT3 = self.clamp(s.PT3 + dPT3 * dt, 0.0, self.max_bar)
        dPT1 = (
            self.Kc * (s.PT3 - s.PT1)
            - self.kv17 * u.V17 * max(s.PT1 - 1.0, 0.0)
            - self.kv21 * (1.0 if u.V21 else 0.0) * max(s.PT1 - 1.0, 0.0)
        )
        s.PT1 = self.clamp(s.PT1 + dPT1 * dt, 0.0, self.max_bar)
        s.PT1 = min(s.PT1, self.PSV_open_bar - 0.5)
        s.PT3 = min(s.PT3, self.PSV_open_bar - 0.5)

    def _update_temperatures(self, dt: float, power_W: float):
        s, u = self.state, self.controls
        Q_loop, Q_eff = self.flow_loop_and_eff()
        s.FT18 = Q_loop
        Rsc = self._rsc()
        T_supply_star = max(77.0, self.T_boil(s.PT1) - self.delta_subcool * Rsc)
        if u.V21 and s.PT1 <= 1.05:
            tau = self.tau_warm0 / (1.0 + 0.3 * Rsc + (0.3 if u.pump_hz > 0 else 0.0))
            s.T5 += (self.ambK - s.T5) / tau * dt
        elif Q_eff > 1e-6:
            tau = self.k_tau / max(Q_eff, 1e-6)
            s.T5 += (T_supply_star - s.T5) / tau * dt
        else:
            tau_iso = 1200.0
            s.T5 += (self.ambK - s.T5) / tau_iso * dt
        mdot = self.rho * (Q_eff / 60.0) * 1e-3
        dT_load = (power_W / (mdot * self.cp)) if mdot > 1e-6 else 0.0
        s.T6 = s.T5 + dT_load

    def _update_levels(self, dt: float, power_W: float):
        s, u = self.state, self.controls
        Q_loop, Q_eff = self.flow_loop_and_eff()
        cons_Lps = (
            self.base_cons_Lps + self.cons_coeff_Lps_perW * power_W + self.gamma_vent_Lps_per_Lpm * max(Q_eff - Q_loop, 0.0) * 60.0
        )
        fill_Lps = float(self.fill_Lps_v19) if u.V19 else 0.0
        dLT19 = (fill_Lps - cons_Lps) / self.Vsub_L * 100.0
        s.LT19 = self.clamp(s.LT19 + dLT19 * dt, 0.0, 100.0)
        if u.V15:
            s.LT23 = self.clamp(s.LT23 + float(self.refill_rate_pctps) * dt, 0.0, 100.0)
        # Existing drain via loop vent proportional to V17
        s.LT23 = self.clamp(s.LT23 - float(self.drain_rate_pctps) * u.V17 * dt, 0.0, 100.0)
        # Additional HV consumption: base + power + heater activity + HV vent contribution
        hv_cons_pctps = float(self.hv_base_cons_pctps) + float(self.hv_power_cons_pctps_perW) * float(power_W)
        if u.press_ctrl_on:
            hv_cons_pctps += float(self.hv_heater_cons_pctps_max) * self.clamp(getattr(u, '_heater_u', 0.0), 0.0, 1.0)
        hv_cons_pctps += float(self.hv_vent_gamma_pctps) * float(self.clamp(u.V20, 0.0, 1.0))
        if hv_cons_pctps > 0.0:
            s.LT23 = self.clamp(s.LT23 - hv_cons_pctps * dt, 0.0, 100.0)
        # 자동 시퀀스 진행 중에만 LT19 자동 보충 히스테리시스 적용
        if (self.auto != AutoKind.NONE) and (not getattr(self, 'paused', False)):
            if s.LT19 < 80.0:
                u.V19 = True
            if s.LT19 > 90.0:
                u.V19 = False
        if s.LT23 < 5.0:
            self.stop()

    def step(self, dt: float = 1.0, power_W: float = 0.0):
        self._update_auto(dt)
        self._update_pressures(dt)
        self._update_temperatures(dt, power_W)
        self._update_levels(dt, power_W)
        self.state.ready = self._is_ready()
        return self.state


if __name__ == '__main__':
    s = State(T5=280.0, T6=280.0, PT1=1.0, PT3=1.0, LT19=40.0, LT23=30.0)
    u = Controls(
        V9=False,
        V11=False,
        V19=False,
        V15=False,
        V21=False,
        V10=0.6,
        V17=0.0,
        V20=0.0,
        pump_hz=0.0,
        press_ctrl_on=False,
        press_sp_bar=2.0,
    )
    sim = CryoCoolerSim(s, u)
    sim.auto_cool_down()
    for t in range(0, 7200):
        sim.step(dt=1.0, power_W=300.0)
        if sim.state.ready:
            break
    print(
        f't={t}s, mode={sim.state.mode}, ready={sim.state.ready}, '
        f'T5={sim.state.T5:.1f}K, T6={sim.state.T6:.1f}K, '
        f'PT1={sim.state.PT1:.2f}bar, PT3={sim.state.PT3:.2f}bar, '
        f'LT19={sim.state.LT19:.1f}%, LT23={sim.state.LT23:.1f}%, '
        f'FT18={sim.state.FT18:.1f} L/min'
    )
