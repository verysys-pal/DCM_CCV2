from __future__ import annotations

"""
Sequencer/Controller for CryoCooler operation stages.

Separates operating sequences (AUTO, stage, timers) from the plant physics
(`sim/core/dcm_cryo_cooler_sim.py`).
"""

from dataclasses import dataclass, fields
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


@dataclass
class _ManualOverrides:
    V9: bool | None = None
    V11: bool | None = None
    V15: bool | None = None
    V17: float | None = None
    V19: bool | None = None
    V20: float | None = None
    V10: float | None = None
    V21: bool | None = None
    pump_hz: float | None = None
    press_ctrl_on: bool | None = None

    def clear_all(self) -> None:
        for f in fields(self):
            setattr(self, f.name, None)

    def clear(self, *keys: str) -> None:
        for key in keys:
            if hasattr(self, key):
                setattr(self, key, None)

    def update(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if not hasattr(self, key):
                raise AttributeError(f"unknown manual override '{key}'")
            setattr(self, key, value)


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
        self._t = _Timers()
        self._manual = _ManualOverrides()
        # 내부 상태/히스테리시스
        self._last_auto: AutoKind = AutoKind.NONE
        # HV
        self._hv_initial_done: bool = False
        self._hv_recharge_active: bool = False
        self._hv_pulse_period: float = 1.0
        # SC
        self._sc_initial_done: bool = False
        self._sc_recharge_active: bool = False

    def _manual_set(self, **kwargs) -> None:
        self._manual.update(**kwargs)

    def _manual_clear_all(self) -> None:
        self._manual.clear_all()

    def _manual_override(self, key: str):
        return getattr(self._manual, key)

    # --- External control API ---
    def start_cool_down(self) -> None:
        self.auto = AutoKind.COOL_DOWN
        try:
            self.sim.state.mode = 'COOL'
        except Exception:
            pass
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

    # Preset/auxiliary operations (manual presets or one-shot helpers)
    '''
    reset_ready와 preset_purge는 HMI 버튼 대신 모드 명령을 통해 호출됩니다.
    OperatingLogic.plan_action()이 ModeCmd.READY 또는 ModeCmd.PURGE 상태에서
    MainCmd.START 펄스를 받으면 각각 ActionType.PRESET_READY/PRESET_PURGE를 반환하고
    tools/pv_bridge.py가 이를 받아 시퀀서의 프리셋 API를 호출합니다.
    '''
    def preset_ready(self) -> None:
        u = self.sim.controls
        try:
            current = float(getattr(u, 'pump_hz', 0.0))
        except Exception:
            current = 0.0

        pump_target = current if current >= 40.0 else 40.0
        self._manual_set(V9=True, V11=True, V17=0.0, pump_hz=pump_target, press_ctrl_on=True)
        self.sim.state.mode = 'READY'
        self.update(0.0)

    def preset_purge(self) -> None:
        self._manual_set(V9=False, V11=False, V17=0.4, V21=True, pump_hz=20.0)
        self.sim.state.mode = 'PURGE'
        self.update(0.0)

    '''
    aux_off는 REFILL 해제 모드 전환용입니다.
    모드가 ModeCmd.REFILL_HETER_OFF나 ModeCmd.REFILL_SBCOL_OFF로 설정되면
    plan_action()이 aux 목록에 해당 문자열을 담고,
    브리지가 이를 iterate 하면서 Sequencer.aux_off()를 호출해 해당 밸브만 수동으로 닫습니다.
    '''
    def aux_off(self, kind: str) -> None:
        if kind == 'REFILL_HETER_OFF':
            self._manual_set(V15=False, V20=0.0)
            self.auto = AutoKind.NONE
        elif kind == 'REFILL_SBCOL_OFF':
            self._manual_set(V19=False)
            self.auto = AutoKind.NONE
        self.update(0.0)

    def set_press_sp(self, value: float) -> None:
        try:
            self.sim.controls.press_sp_bar = float(value)
        except Exception:
            pass

    def apply_manual_commands(
        self,
        *,
        v9: bool,
        v11: bool,
        v15: bool,
        v19: bool,
        v20: bool,
        v17: bool,
        v10: bool,
        v21: bool,
        pump: bool,
        heat: bool,
    ) -> None:
        """
        수동 CMD PV를 기반으로 현재 제어 상태를 강제한다.
        브리지에서는 값을 판독만 하고, 실제 조작은 시퀀서가 담당한다.
        """
        self._manual_set(
            V9=bool(v9),
            V11=bool(v11),
            V15=bool(v15),
            V19=bool(v19),
            V20=1.0 if bool(v20) else 0.0,
            V17=1.0 if bool(v17) else 0.0,
            V10=1.0 if bool(v10) else 0.0,
            V21=bool(v21),
            pump_hz=60.0 if bool(pump) else 0.0,
            press_ctrl_on=bool(heat),
        )
        self.update(0.0)

    def snapshot_status(self) -> dict:
        """제어 상태 스냅샷을 제공(브리지가 PV로 게시하는 데 사용)."""
        u = self.sim.controls
        return {
            'V9': bool(u.V9),
            'V11': bool(u.V11),
            'V15': bool(u.V15),
            'V17': float(u.V17),
            'V19': bool(u.V19),
            'V20': float(u.V20),
            'V10': float(u.V10),
            'V21': bool(u.V21),
            'pump_hz': float(u.pump_hz),
            'press_ctrl_on': bool(u.press_ctrl_on),
            'press_sp_bar': float(getattr(u, 'press_sp_bar', 0.0)),
            'heater_u': float(getattr(u, '_heater_u', 0.0)),
        }

    def stop(self) -> None:
        # Equivalent to previous plant.stop()
        self.sim.state.ready = False
        self.sim.state.mode = 'STOP'
        self.auto = AutoKind.NONE
        self._t = _Timers()
        self._reset_internal()
        self._manual_set(
            V9=False,
            V11=False,
            V15=False,
            V19=False,
            V20=0.0,
            V17=0.0,
            V10=0.0,
            V21=False,
            pump_hz=0.0,
            press_ctrl_on=False,
        )
        self.update(0.0)

    def off(self) -> None:
        # Equivalent to previous plant.off()
        self.stop()
        self._manual_set(V17=1.0, V20=1.0)
        self.sim.state.mode = 'OFF'
        self.update(0.0)

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
        manual_mode = self.auto == AutoKind.NONE
        if manual_mode:
            self._run_rules(0.0)
            try:
                self.sim.state.ready = bool(self._is_ready())
                if self.sim.state.ready:
                    self.sim.state.mode = 'READY'
            except Exception:
                pass
            return

        if self.paused:
            return

        self._t.stage_timer += dt
        self._run_rules(dt)

        # READY 사후계산: 규칙 적용 결과 반영 + 자동 종료 판정
        try:
            self.sim.state.ready = bool(self._is_ready())
        except Exception:
            pass
        if self.auto == AutoKind.COOL_DOWN:
            try:
                if self._is_ready():
                    self.sim.state.mode = 'READY'
                    #self.auto = AutoKind.NONE
                    self._t = _Timers()
            except Exception:
                pass

    def _run_rules(self, dt: float) -> None:
        # 1) Baseline
        self.rule_pump_baseline()
        self.rule_v10_mode()
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

    # --- Helpers & internal state ---
    def _on_auto_changed(self, *, reset_pulses: bool) -> None:
        self._t = _Timers()
        self._manual_clear_all()
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
            return s.LT23 < 45.0
        if self.auto == AutoKind.COOL_DOWN:
            # 초기 보충: 90% 도달 전까지 1회 활성
            if not self._hv_initial_done:
                if s.LT23 >= 85.0:
                    self._hv_initial_done = True
                    return False
                return True
            # 재보충: 히스테리시스 39↔41
            if not self._hv_recharge_active and s.LT23 < 25.0:
                self._hv_recharge_active = True
            if self._hv_recharge_active and s.LT23 >= 50.0:
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
            return s.LT19 < 85.0
        if self.auto == AutoKind.COOL_DOWN:
            if not self._sc_initial_done:
                if s.LT19 >= 85.0:
                    self._sc_initial_done = True
                    return False
                return True
            if not self._sc_recharge_active and s.LT19 < 40.0:
                self._sc_recharge_active = True
            if self._sc_recharge_active and s.LT19 >= 80.0:
                self._sc_recharge_active = False
            return self._sc_recharge_active
        return False

    # --- Independent valve rules ---
    def rule_pump_baseline(self) -> None:
        """
        펌프 베이스라인: 최소 유량 보장.
        비-밸브 구동은 전용 규칙에서 처리하여 밸브 규칙과 분리.
        """
        u = self.sim.controls
        override = self._manual_override('pump_hz')
        if override is not None:
            try:
                u.pump_hz = float(override)
            except Exception:
                pass
            return
        if self.auto == AutoKind.COOL_DOWN:
            u.pump_hz = max(u.pump_hz, 30.0)
        elif self.auto in (AutoKind.WARM_UP, AutoKind.REFILL_HV, AutoKind.REFILL_SUB):
            u.pump_hz = 1.0

    def rule_v10_mode(self) -> None:
        """
        V10 전용 규칙: 모드 기반 개도 설정.
        - COOL_DOWN: 60% 개도
        - OFF, PURGE: 100% 개도
        - 그 외: 0% (닫힘)
        - 다른 밸브/구동에는 영향을 주지 않는다.
        """
        u = self.sim.controls
        override = self._manual_override('V10')
        if override is not None:
            try:
                u.V10 = float(override)
            except Exception:
                pass
            return

        if self.auto == AutoKind.COOL_DOWN:
            u.V10 = 0.6
            return

        try:
            mode = str(self.sim.state.mode).upper()
        except Exception:
            mode = ''

        if mode in ('OFF', 'PURGE'):
            u.V10 = 1.0
        elif self.auto != AutoKind.NONE:
            u.V10 = 0.0

    def rule_v9_dcm_supply(self) -> None:
        u = self.sim.controls
        override = self._manual_override('V9')
        if override is not None:
            u.V9 = bool(override)
            return
        # 냉각 의도: COOL_DOWN 동안 루프 성립 목표
        if self.auto == AutoKind.COOL_DOWN:
            u.V9 = True
        elif self.auto in (AutoKind.WARM_UP, AutoKind.REFILL_HV, AutoKind.REFILL_SUB):
            # 전용 리필/웜업 중에는 공급 경로를 강제하지 않음 (기존 상태 유지)
            pass

    def rule_v11_dcm_return(self) -> None:
        u = self.sim.controls
        override = self._manual_override('V11')
        if override is not None:
            u.V11 = bool(override)
            return
        if self.auto == AutoKind.COOL_DOWN:
            u.V11 = True
        elif self.auto in (AutoKind.WARM_UP, AutoKind.REFILL_HV, AutoKind.REFILL_SUB):
            pass

    def rule_v21_purge(self) -> None:
        # PURGE 제어 경로 설명:
        # - 브리지(tools/pv_bridge.py)가 OperatingLogic.plan_action 결과로
        #   Sequencer.preset_purge()를 호출하여 직접 V21 오버라이드를 설정한다.
        # - AUTO가 NONE인 상태에서도 규칙이 실행되므로, 오버라이드가 없더라도
        #   모드가 PURGE이면 기본적으로 개방한다.
        # - 자동 시퀀스 중(AUTO != NONE)에는 안전을 위해 V21을 항상 닫힘으로 유지한다.
        override = self._manual_override('V21')
        if override is not None:
            self.sim.controls.V21 = bool(override)
            return
        # 모드가 PURGE로 표시되면 수동 프리셋 없이도 기본적으로 개방한다.
        try:
            mode = str(self.sim.state.mode).upper()
        except Exception:
            mode = ''

        if self.auto != AutoKind.NONE:
            self.sim.controls.V21 = False
            return

        if mode == 'PURGE':
            self.sim.controls.V21 = True
        else:
            # 수동 명령이 없고 모드가 PURGE가 아니면 안전상 닫힘 유지
            self.sim.controls.V21 = False

    def rule_v15_hv_refill(self) -> None:
        u = self.sim.controls
        s = self.sim.state
        override = self._manual_override('V15')
        if override is not None:
            u.V15 = bool(override)
            return
        if self.auto == AutoKind.NONE:
            return

        active = self._hv_refill_active()
        gating_ok = self._hv_refill_gating_ok()
        if active and gating_ok:
            u.V15 = True
            # 목표 85% 도달 시 종료
            if s.LT23 >= 85.0:
                u.V15 = False
                if self.auto == AutoKind.COOL_DOWN:
                    self._hv_initial_done = True
                if self.auto == AutoKind.REFILL_HV:
                    # 단독 리필 모드는 완료 후 종료
                    self.auto = AutoKind.NONE
                    self._t = _Timers()
        else:
            u.V15 = False

    def rule_v20_hv_pulse_vent(self, dt: float) -> None:
        u = self.sim.controls
        override = self._manual_override('V20')
        if override is not None:
            try:
                u.V20 = float(override)
            except Exception:
                pass
            return
        if self.auto == AutoKind.NONE:
            return
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
        override = self._manual_override('V17')
        if override is not None:
            try:
                u.V17 = float(override)
            except Exception:
                pass
            return
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
        override = self._manual_override('V19')
        if override is not None:
            u.V19 = bool(override)
            return
        if self.auto == AutoKind.NONE:
            return
        if self._sc_refill_active():
            u.V19 = True
            # 90% 도달 후 종료 처리
            if self.sim.state.LT19 >= 90.0:
                u.V19 = False
                if self.auto == AutoKind.REFILL_SUB:
                    self.auto = AutoKind.NONE
                    self._t = _Timers()
        else:
            u.V19 = False

    def rule_press_heater(self) -> None:
        u = self.sim.controls
        override = self._manual_override('press_ctrl_on')
        if override is not None:
            u.press_ctrl_on = bool(override)
            return
        if self.auto == AutoKind.NONE:
            return
        # HV 보충 중에는 압력 제어 일시 비활성화 허용
        if self._hv_refill_active():
            u.press_ctrl_on = False
        else:
            u.press_ctrl_on = True
            u.press_sp_bar = max(u.press_sp_bar, 2.0)
