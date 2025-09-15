from __future__ import annotations

"""
Operating logic focused on Main/Mode commands.

- MainCmd: 시스템 제어 명령 집합 (START/STOP/HOLD/RESUME/OFF/RESET)
- ModeCmd: 시퀀스 선택 모드 (PURGE/READY/COOL_DOWN/WARM_UP/
           REFILL_HETER_ON/REFILL_HETER_OFF/REFILL_SBCOL_ON/REFILL_SBCOL_OFF)

본 모듈은 EPICS I/O를 수행하지 않으며, 브리지(tools/pv_bridge.py)가 필요 시 이 로직을 호출합니다.
현재 브리지는 시퀀스 트리거를 자체 처리하므로 이 모듈은 최소한의 전이 규칙과 모드 저장만 제공합니다.
"""

from dataclasses import dataclass
from .commands import MainCmd, ModeCmd, mode_to_auto


"""Command policy: transitions and mapping to sequencer autos.

This module intentionally avoids any EPICS I/O. It consumes primitive
values and returns/acts on pure Python state to keep unit tests simple.
"""


class OperatingLogic:
    @dataclass
    class Params:
        init_seconds: float = 2.0
        precool_band: float = 5.0

    def __init__(self, params: "OperatingLogic.Params" | None = None) -> None:
        self.params = params or OperatingLogic.Params()
        self._t_init_left: float = self.params.init_seconds
        self.mode: ModeCmd = ModeCmd.NONE

    @classmethod
    def from_yaml(cls, data: dict | None) -> "OperatingLogic":
        d = data or {}
        p = OperatingLogic.Params(
            init_seconds=float(d.get("init_seconds", 2.0)),
            precool_band=float(d.get("precool_band", 5.0)),
        )
        return cls(p)

    def set_mode(self, mode_value: int) -> None:
        try:
            self.mode = ModeCmd(int(mode_value))
        except Exception:
            self.mode = ModeCmd.NONE

    def next_state(
        self,
        *,
        state: int,
        STATE: dict[str, int],
        cmd_val: int,
        mode_val: int,
        tsp: float,
        t5: float,
        tamb: float,
        dt: float,
    ) -> int:
        """MainCmd/ModeCmd 기반 상태 전이 정책.

        - START → INIT (Warm-up 모드에서는 WARMUP로 표시)
        - INIT (시간 경과) → PRECOOL
        - PRECOOL (T5 <= TSP - band) → RUN
        - WARMUP (T5 >= tamb - 1K 근접) → OFF
        - STOP → OFF, HOLD → HOLD, RESUME(HOLD에서만) → RUN
        - OFF → OFF (STOP과 동일, 단 시뮬레이터에서 V17/V20 추가 개방)
        - RESET(SAFE에서만) → OFF
        """
        prev = state
        try:
            cmd = MainCmd(int(cmd_val))
        except Exception:
            cmd = MainCmd.NONE
        # Command-driven transitions
        if cmd is MainCmd.START:
            if int(mode_val) == ModeCmd.WARM_UP:
                state = STATE.get("WARMUP", state)
            else:
                state = STATE.get("INIT", state)
            if prev != state:
                self._t_init_left = self.params.init_seconds
        elif cmd is MainCmd.STOP:
            state = STATE.get("OFF", state)
        elif cmd is MainCmd.HOLD:
            state = STATE.get("HOLD", state)
        elif cmd is MainCmd.RESUME and prev == STATE.get("HOLD", -999):
            state = STATE.get("RUN", state)
        elif cmd is MainCmd.OFF:
            state = STATE.get("OFF", state)
        elif cmd is MainCmd.RESET and prev == STATE.get("SAFE_SHUTDOWN", -999):
            state = STATE.get("OFF", state)

        # Timed INIT -> PRECOOL
        if state == STATE.get("INIT", -1):
            self._t_init_left -= dt
            if self._t_init_left <= 0:
                state = STATE.get("PRECOOL", state)

        # PRECOOL -> RUN near setpoint
        try:
            if state == STATE.get("PRECOOL", -1):
                if float(t5) <= (float(tsp) - float(self.params.precool_band)):
                    state = STATE.get("RUN", state)
        except Exception:
            pass

        # WARMUP -> OFF near ambient
        try:
            if state == STATE.get("WARMUP", -1):
                if float(t5) >= (float(tamb) - 1.0):
                    state = STATE.get("OFF", state)
        except Exception:
            pass

        return int(state)

    # 시퀀스/모드 액션 적용 (브리지가 전달하는 시뮬레이터 인스턴스를 조작)
    def apply_mode_action(self, seq, *, cmd_val: int, mode_val: int) -> None:
        """Drive the Sequencer (and occasionally direct control presets).

        Uses centralized mapping between ModeCmd and AutoKind to keep
        responsibilities separated and prevent drift.
        """
        sim = getattr(seq, 'sim', None)
        try:
            cmd = MainCmd(int(cmd_val))
        except Exception:
            cmd = MainCmd.NONE
        if cmd is MainCmd.START:
            auto = mode_to_auto(mode_val)
            if auto is not None:
                # Pre-sequence side effects for certain modes
                if auto.name == 'REFILL_HV' and sim is not None:
                    try:
                        sim.controls.V15 = True
                        sim.controls.press_ctrl_on = False
                    except Exception:
                        pass
                # Dispatch to sequencer start methods
                if auto.name == 'COOL_DOWN':
                    seq.start_cool_down()
                elif auto.name == 'WARM_UP':
                    seq.start_warm_up()
                elif auto.name == 'REFILL_HV':
                    seq.start_refill_hv()
                elif auto.name == 'REFILL_SUB':
                    try:
                        seq.start_refill_subcooler()
                    except Exception:
                        if sim is not None:
                            sim.controls.V19 = True
            elif int(mode_val) == ModeCmd.READY and sim is not None:
                # Simple ready preset
                sim.controls.V9 = True
                sim.controls.V11 = True
                sim.controls.V17 = 0.0
                sim.controls.pump_hz = max(sim.controls.pump_hz, 40.0)
                sim.controls.press_ctrl_on = True
                sim.state.mode = 'READY'
            elif int(mode_val) == ModeCmd.PURGE and sim is not None:
                sim.controls.V9 = False
                sim.controls.V11 = False
                sim.controls.V17 = 0.4
                sim.controls.V21 = True
                sim.controls.pump_hz = 20.0
                sim.state.mode = 'PURGE'
        elif cmd is MainCmd.STOP:
            seq.stop()
            seq.paused = False
        elif cmd is MainCmd.HOLD:
            seq.hold()
        elif cmd is MainCmd.RESUME:
            seq.resume()
        elif cmd is MainCmd.OFF:
            seq.off()
            seq.paused = False
        # Auxiliary OFF-like modes
        try:
            if int(mode_val) == ModeCmd.REFILL_HETER_OFF and sim is not None:
                sim.controls.V15 = False
                sim.controls.V20 = 0.0
                seq.auto = type(seq.auto).NONE
            elif int(mode_val) == ModeCmd.REFILL_SBCOL_OFF and sim is not None:
                sim.controls.V19 = False
                seq.auto = type(seq.auto).NONE
        except Exception:
            pass
