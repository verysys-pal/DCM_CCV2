from __future__ import annotations

"""
Operating logic focused on Main/Mode commands.

- MainCmd: 시스템 제어 명령 집합 (START/STOP/HOLD/RESUME/EMERGENCY_STOP/RESET)
- ModeCmd: 시퀀스 선택 모드 (PURGE/READY/COOL_DOWN/WARM_UP/REFILL_ON/REFILL_OFF)

본 모듈은 EPICS I/O를 수행하지 않으며, 브리지(tools/pv_bridge.py)가 필요 시 이 로직을 호출합니다.
현재 브리지는 시퀀스 트리거를 자체 처리하므로 이 모듈은 최소한의 전이 규칙과 모드 저장만 제공합니다.
"""

from dataclasses import dataclass
from enum import IntEnum


class MainCmd(IntEnum):
    NONE = 0
    START = 1
    STOP = 2
    HOLD = 3
    RESUME = 4
    EMERGENCY_STOP = 5
    RESET = 6


class ModeCmd(IntEnum):
    NONE = 0
    PURGE = 1
    READY = 2
    COOL_DOWN = 3
    WARM_UP = 4
    REFILL_ON = 5
    REFILL_OFF = 6


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
        CMD: dict[str, int],
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
        - EMERGENCY_STOP → SAFE_SHUTDOWN, RESET(SAFE에서만) → OFF
        """
        prev = state
        # Command-driven transitions
        if cmd_val == CMD.get("START", -1):
            if int(mode_val) == ModeCmd.WARM_UP:
                state = STATE.get("WARMUP", state)
            else:
                state = STATE.get("INIT", state)
            if prev != state:
                self._t_init_left = self.params.init_seconds
        elif cmd_val == CMD.get("STOP", -1):
            state = STATE.get("OFF", state)
        elif cmd_val == CMD.get("HOLD", -1):
            state = STATE.get("HOLD", state)
        elif cmd_val == CMD.get("RESUME", -1) and prev == STATE.get("HOLD", -999):
            state = STATE.get("RUN", state)
        elif cmd_val == CMD.get("EMERGENCY_STOP", -1):
            state = STATE.get("SAFE_SHUTDOWN", state)
        elif cmd_val == CMD.get("RESET", -1) and prev == STATE.get("SAFE_SHUTDOWN", -999):
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
    def apply_mode_action(self, sim, *, cmd_val: int, mode_val: int, CMD: dict[str, int]) -> None:
        if cmd_val == CMD.get("START", -1):
            if int(mode_val) == ModeCmd.COOL_DOWN:
                sim.auto_cool_down()
            elif int(mode_val) == ModeCmd.WARM_UP:
                sim.auto_warm_up()
            elif int(mode_val) == ModeCmd.REFILL_ON:
                sim.auto_refill_hv()
            elif int(mode_val) == ModeCmd.READY:
                # 간단한 Ready 유지 세팅
                sim.controls.V9 = True
                sim.controls.V11 = True
                sim.controls.V17 = 0.0
                sim.controls.pump_hz = max(sim.controls.pump_hz, 40.0)
                sim.controls.press_ctrl_on = True
                sim.state.mode = 'READY'
            elif int(mode_val) == ModeCmd.PURGE:
                sim.controls.V9 = False
                sim.controls.V11 = False
                sim.controls.V17 = 0.4
                sim.controls.V21 = True
                sim.controls.pump_hz = 20.0
                sim.state.mode = 'PURGE'
        elif cmd_val == CMD.get("STOP", -1):
            sim.stop()
        elif cmd_val == CMD.get("HOLD", -1):
            # 자동 시퀀스를 중단하여 수동 조작 허용
            try:
                sim.auto = type(sim.auto).NONE
            except Exception:
                pass
        elif cmd_val == CMD.get("EMERGENCY_STOP", -1):
            sim.off()
