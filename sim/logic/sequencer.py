from __future__ import annotations

"""
Sequencer/Controller for CryoCooler operation stages.

Separates operating sequences (AUTO, stage, timers) from the plant physics
(`sim/core/dcm_cryo_cooler_sim.py`).
"""

from dataclasses import dataclass
from enum import Enum, auto


class AutoKind(Enum):
    NONE = 0
    COOL_DOWN = auto()
    WARM_UP = auto()
    REFILL_HV = auto()
    REFILL_SUB = auto()


@dataclass
class _Timers:
    stage_timer: float = 0.0
    pulse_timer: float = 0.0
    pulse_state: bool = False


class Sequencer:
    """규칙 기반(Independent Valve Rules) CryoCooler 시퀀서.

    - 각 규칙은 하나의 밸브만 제어하며, 공통 조건은 헬퍼 함수가 판정한다.
    - 물리 갱신은 `sim.step()`이 담당하고, 본 시퀀서는 `sim.controls`만 변경한다.

    External API (브리지/운영 로직에서 사용):
    - start_cool_down(), start_warm_up(), start_refill_hv(), start_refill_subcooler()
    - stop(), off(), hold(), resume()
    - update(dt): 규칙 실행 및 내부 상태 갱신
    """

    def __init__(self, sim) -> None:
        self.sim = sim
        self.auto: AutoKind = AutoKind.NONE
        self.paused: bool = False
        self.stage: int = 0  # 호환성 유지(이제는 사용하지 않음)
        self._t = _Timers()
        # 내부 상태/히스테리시스
        self._last_auto: AutoKind = AutoKind.NONE
        # HV
        self._hv_initial_done: bool = False
        self._hv_recharge_active: bool = False
        self._hv_pulse_period: float = 1.0
        # SC
        self._sc_initial_done: bool = False
        self._sc_recharge_active: bool = False

    # --- External control API ---
    def start_cool_down(self) -> None:
        self.auto = AutoKind.COOL_DOWN
        self._on_auto_changed(reset_pulses=True)

    def start_warm_up(self) -> None:
        self.auto = AutoKind.WARM_UP
        self._on_auto_changed(reset_pulses=True)

    def start_refill_hv(self) -> None:
        self.auto = AutoKind.REFILL_HV
        self._on_auto_changed(reset_pulses=True)

    def start_refill_subcooler(self) -> None:
        self.auto = AutoKind.REFILL_SUB
        self._on_auto_changed(reset_pulses=False)

    def stop(self) -> None:
        # Equivalent to previous plant.stop()
        u = self.sim.controls
        u.V9 = False
        u.V11 = False
        u.V15 = False
        u.V19 = False
        u.V20 = 0.0
        u.V17 = 0.0
        u.V10 = 0.0
        u.V21 = False
        u.pump_hz = 0.0
        u.press_ctrl_on = False
        self.sim.state.ready = False
        self.sim.state.mode = 'STOP'
        self.auto = AutoKind.NONE
        self.stage = 0
        self._t = _Timers()
        self._reset_internal()

    def off(self) -> None:
        # Equivalent to previous plant.off()
        self.stop()
        u = self.sim.controls
        u.V17 = 1.0
        u.V20 = 1.0
        self.sim.state.mode = 'OFF'

    def hold(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False

    # --- Periodic update ---
    def update(self, dt: float) -> None:
        """규칙 실행 순서에 따라 밸브/구동을 갱신한다.

        NOTE: AUTO가 NONE이어도 READY 판정은 항상 갱신하여
        READY 모드(수동 프리셋)에서 START 시 즉시 READY 표시가 가능하도록 한다.
        """
        # READY 플래그는 항상 계산(모드와 무관)
        try:
            self.sim.state.ready = bool(self._is_ready())
            if self.auto == AutoKind.NONE and self.sim.state.ready:
                # 수동 READY 프리셋(operating.apply_mode_action)과 연동
                self.sim.state.mode = 'READY'
        except Exception:
            pass
        if self.paused or self.auto == AutoKind.NONE:
            return
        u, s = self.sim.controls, self.sim.state
        self._t.stage_timer += dt

        # 1) Baseline
        self.rule_pump_v10_baseline()
        # 2) DCM loop supply/return
        self.rule_v9_dcm_supply()
        self.rule_v11_dcm_return()
        # 3) Loop vent
        self.rule_v17_loop_vent()
        # 4) HV pulse vent
        self.rule_v20_hv_pulse_vent(dt)
        # 5) HV refill
        self.rule_v15_hv_refill()
        # 6) SubCooler refill
        self.rule_v19_subcool_fill()
        # 7) Purge
        self.rule_v21_purge()
        # 8) Pressure/heater control
        self.rule_press_heater()

        # READY 플래그 갱신 및 상태 전이 보조(자동 진행 중에도 확인)
        try:
            self.sim.state.ready = bool(self._is_ready())
        except Exception:
            pass
        # 상태 전이 보조: READY 조건 충족 시 자동 종료
        if self.auto == AutoKind.COOL_DOWN:
            try:
                if self._is_ready():
                    self.sim.state.mode = 'READY'
                    self.auto = AutoKind.NONE
                    self.stage = 0
                    self._t = _Timers()
            except Exception:
                pass

    # --- Helpers & internal state ---
    def _on_auto_changed(self, *, reset_pulses: bool) -> None:
        self.stage = 0
        self._t = _Timers()
        if reset_pulses:
            self._t.pulse_timer = 0.0
            self._t.pulse_state = False
        # Auto 전환 시 초기/재보충 플래그 리셋
        if self.auto == AutoKind.COOL_DOWN:
            self._hv_initial_done = False
            self._hv_recharge_active = False
            self._sc_initial_done = False
            self._sc_recharge_active = False
        elif self.auto == AutoKind.REFILL_HV:
            # 전용 모드에서는 초기/재보충 개념 없음
            pass
        elif self.auto == AutoKind.REFILL_SUB:
            pass
        self._last_auto = self.auto

    def _reset_internal(self) -> None:
        self._last_auto = AutoKind.NONE
        self._hv_initial_done = False
        self._hv_recharge_active = False
        self._sc_initial_done = False
        self._sc_recharge_active = False
        self._t = _Timers()

    def _dcm_loop_on(self) -> bool:
        u = self.sim.controls
        return bool(u.V9 and u.V11 and (not u.V21))

    def _is_ready(self) -> bool:
        """READY 판정: 루프 성립+압력안정+온도/레벨 조건."""
        s, u = self.sim.state, self.sim.controls
        try:
            return (
                bool(u.V9)
                and bool(u.V11)
                and float(u.pump_hz) > 0.0
                and bool(u.press_ctrl_on)
                and abs(float(s.PT3) - float(u.press_sp_bar)) < 0.05
                and abs(float(s.PT1) - float(u.press_sp_bar)) < 0.1
                and float(s.LT23) > 20.0
                and float(s.T5) < 80.0
            )
        except Exception:
            return False

    def _hv_refill_active(self) -> bool:
        s = self.sim.state
        if self.auto == AutoKind.REFILL_HV:
            return s.LT23 < 90.0
        if self.auto == AutoKind.COOL_DOWN:
            # 초기 보충: 90% 도달 전까지 1회 활성
            if not self._hv_initial_done:
                if s.LT23 >= 90.0:
                    self._hv_initial_done = True
                    return False
                return True
            # 재보충: 히스테리시스 39↔41
            if not self._hv_recharge_active and s.LT23 < 39.0:
                self._hv_recharge_active = True
            if self._hv_recharge_active and s.LT23 >= 41.0:
                self._hv_recharge_active = False
            return self._hv_recharge_active
        return False

    def _hv_refill_gating_ok(self) -> bool:
        u = self.sim.controls
        # COOL_DOWN 재보충 시: V9 OPEN, V17>0, V20 토글(최근 1주기 내 변경)
        if self.auto == AutoKind.COOL_DOWN and self._hv_initial_done:
            return bool(u.V9 and (u.V17 > 0.0) and (u.V20 > 0.0))
        # REFILL_HV 또는 초기 보충: 게이팅 불필요
        return True

    def _sc_refill_active(self) -> bool:
        s = self.sim.state
        if self.auto == AutoKind.REFILL_SUB:
            return s.LT19 < 90.0
        if self.auto == AutoKind.COOL_DOWN:
            if not self._sc_initial_done:
                if s.LT19 >= 90.0:
                    self._sc_initial_done = True
                    return False
                return True
            if not self._sc_recharge_active and s.LT19 < 49.0:
                self._sc_recharge_active = True
            if self._sc_recharge_active and s.LT19 >= 51.0:
                self._sc_recharge_active = False
            return self._sc_recharge_active
        return False

    # --- Independent valve rules ---
    def rule_pump_v10_baseline(self) -> None:
        u = self.sim.controls
        u.pump_hz = max(u.pump_hz, 30.0)
        u.V10 = max(u.V10, 0.6)

    def rule_v9_dcm_supply(self) -> None:
        u = self.sim.controls
        # 냉각 의도: COOL_DOWN 동안 루프 성립 목표
        if self.auto == AutoKind.COOL_DOWN:
            u.V9 = True
            u.V21 = False
        elif self.auto in (AutoKind.WARM_UP, AutoKind.REFILL_HV, AutoKind.REFILL_SUB):
            # 전용 리필/웜업 중에는 공급 경로를 강제하지 않음 (기존 상태 유지)
            pass

    def rule_v11_dcm_return(self) -> None:
        u = self.sim.controls
        if self.auto == AutoKind.COOL_DOWN:
            u.V11 = True
        elif self.auto in (AutoKind.WARM_UP, AutoKind.REFILL_HV, AutoKind.REFILL_SUB):
            pass

    def rule_v21_purge(self) -> None:
        # PURGE 모드는 OperatingLogic.apply_mode_action이 직접 제어
        # 자동 시퀀스 중에는 닫힘 유지
        if self.auto != AutoKind.NONE:
            self.sim.controls.V21 = False

    def rule_v15_hv_refill(self) -> None:
        u, s = self.sim.controls, self.sim.state
        active = self._hv_refill_active()
        gating_ok = self._hv_refill_gating_ok()
        if active and gating_ok:
            u.V15 = True
            # 목표 90% 도달 시 종료
            if s.LT23 >= 90.0:
                u.V15 = False
                if self.auto == AutoKind.COOL_DOWN:
                    self._hv_initial_done = True
                if self.auto == AutoKind.REFILL_HV:
                    # 단독 리필 모드는 완료 후 종료
                    self.auto = AutoKind.NONE
                    self.stage = 0
                    self._t = _Timers()
        else:
            u.V15 = False

    def rule_v20_hv_pulse_vent(self, dt: float) -> None:
        u = self.sim.controls
        if self._hv_refill_active():
            self._t.pulse_timer += dt
            if self._t.pulse_timer >= self._hv_pulse_period:
                self._t.pulse_timer -= self._hv_pulse_period
                self._t.pulse_state = not self._t.pulse_state
            u.V20 = 1.0 if self._t.pulse_state else 0.0
        else:
            # 비활성 시 0으로 고정 및 위상 리셋
            u.V20 = 0.0
            self._t.pulse_timer = 0.0
            self._t.pulse_state = False

    def rule_v17_loop_vent(self) -> None:
        u, s = self.sim.controls, self.sim.state
        # 냉각 진행도 기반 간단한 3단계 제어
        if self.auto == AutoKind.COOL_DOWN and self._dcm_loop_on():
            if s.T6 > 200.0:
                u.V17 = max(u.V17, 1.0)
            elif s.T6 > 90.0:
                u.V17 = max(u.V17, 0.35)
            else:
                # 재보충 게이팅 중이면 최소 개도 보장
                if self._hv_initial_done and self._hv_recharge_active:
                    u.V17 = max(u.V17, 0.35)
                else:
                    u.V17 = 0.0
        else:
            # 기타 모드에서는 변경하지 않음(웜업은 다른 규칙에서 처리 가능)
            pass

    def rule_v19_subcool_fill(self) -> None:
        u = self.sim.controls
        if self._sc_refill_active():
            u.V19 = True
            # 90% 도달 후 종료 처리
            if self.sim.state.LT19 >= 90.0:
                u.V19 = False
                if self.auto == AutoKind.REFILL_SUB:
                    self.auto = AutoKind.NONE
                    self.stage = 0
                    self._t = _Timers()
        else:
            u.V19 = False

    def rule_press_heater(self) -> None:
        u = self.sim.controls
        # HV 보충 중에는 압력 제어 일시 비활성화 허용
        if self._hv_refill_active():
            u.press_ctrl_on = False
        else:
            u.press_ctrl_on = True
            u.press_sp_bar = max(u.press_sp_bar, 2.0)
