from __future__ import annotations

"""
Operating/state-machine logic for the DCM Cryo-Cooler simulator.

정합성 안내:
- 본 모듈은 HMI 상위 로직(상태 전이, 밴드 판단, 단순 장치 파생)을 담당하고,
  물리/시퀀스 모델은 `sim/core/dcm_cryo_cooler_sim.py`가 맡습니다.
- GUI/DB와 일관성:
  - System control `CMD:MAIN` = {0:NONE, 1:START, 2:STOP, 3:HOLD, 4:RESUME, 5:EMERGENCY_STOP, 6:RESET}
  - Select Mode `CMD:MODE` = {0:NONE, 1:PURGE, 2:READY, 3:Cool-Down, 4:Warm-up, 5:Refill ON, 6:Refill OFF}
  - 본 모듈은 CMD:MODE를 저장만 하고 직접 사용하지 않습니다. 브리지(`tools/pv_bridge.py`)가
    CMD:MODE + CMD:MAIN=START 조합을 `CryoCoolerSim`의 자동 시퀀스 호출로 연결합니다.

Notes:
- pv_bridge에서 이 모듈이 선택적으로 로드되며, 미로드 시 브리지의 단순 로직을 사용합니다.
- 여기서는 EPICS IO가 아닌 "결정 규칙"만 제공합니다.
"""

from dataclasses import dataclass
from enum import IntEnum


@dataclass
class OperatingParams:
    # START 후 INIT 상태 유지 시간 (s)
    init_seconds: float = 2.0
    # PRECOOL → RUN 전이 시 목표온도 대비 허용 밴드 (K)
    precool_band: float = 5.0


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
    def __init__(self, params: OperatingParams) -> None:
        self.params = params
        self._t_init_left: float = params.init_seconds
        # 선택 모드(CMD:MODE)는 외부에서 관리/적용하며, 여기서는 저장만 제공
        self.mode: ModeCmd = ModeCmd.NONE

    @classmethod
    def from_yaml(cls, data: dict | None) -> "OperatingLogic":
        p = OperatingParams(
            init_seconds=float((data or {}).get("init_seconds", 2.0)),
            precool_band=float((data or {}).get("precool_band", 5.0)),
        )
        return cls(p)

    def reset(self) -> None:
        self._t_init_left = self.params.init_seconds

    def next_state(
        self,
        state: int,
        STATE: dict[str, int],
        CMD: dict[str, int],
        cmd_val: int,
        tsp: float,
        tch: float,
        dt: float,
    ) -> int:
        prev = state
        # React to command changes (CMD:MAIN 정의와 정합)
        if cmd_val == CMD.get("START", -1):
            state = STATE["INIT"]
            if prev != state:
                self._t_init_left = self.params.init_seconds
        elif cmd_val == CMD.get("STOP", -1):
            state = STATE["OFF"]
        elif cmd_val == CMD.get("HOLD", -1):
            state = STATE["HOLD"]
        elif cmd_val == CMD.get("RESUME", -1) and state == STATE["HOLD"]:
            state = STATE["RUN"]
        elif cmd_val == CMD.get("EMERGENCY_STOP", -1):
            state = STATE["SAFE_SHUTDOWN"]
        elif cmd_val == CMD.get("RESET", -1) and state == STATE["SAFE_SHUTDOWN"]:
            state = STATE["OFF"]

        # Timed INIT -> PRECOOL
        if state == STATE["INIT"]:
            self._t_init_left -= dt
            if self._t_init_left <= 0:
                state = STATE["PRECOOL"]

        # PRECOOL -> RUN when near setpoint (T_ch <= T_sp - band)
        if state == STATE["PRECOOL"]:
            if tch <= (tsp - self.params.precool_band):
                state = STATE["RUN"]

        # WARMUP -> OFF when near ambient (handled by bridge using model.tamb)
        return state

    # 추가: 측정/표시값 파생 로직
    # pv_bridge는 장치 상태/모델 값만 전달하고, 조건식은 여기서 적용한다.
    def derive_measurements(
        self,
        *,
        v9_open: int,
        v21_open: int,
        t5_model: float,
        pt1_base: float,
        tamb: float,
    ) -> tuple[float, float]:
        """운전 로직에 따른 T5/PT1 유효값을 산출한다.

        규칙:
        - V9 open일 때: 서브쿨러 LN2가 DCM으로 유입 → T5/PT1 모델/기저값 사용
        - V9 close이고 V21 open일 때: 대기 개방 → T5=tamb, PT1=1.0
        - 그 외: 모델/기저값 사용
        """
        if (not int(v9_open)) and int(v21_open):
            return float(tamb), 1.0
        return float(t5_model), float(pt1_base)

    # 컨트롤러 유효 목표 온도 (OFF/SAFE/WARMUP 시 주위온도 추종)
    def controller_target(self, *, state: int, STATE: dict[str, int], tsp: float, tamb: float) -> float:
        if state in (STATE.get("OFF", -1), STATE.get("SAFE_SHUTDOWN", -2), STATE.get("WARMUP", -3)):
            return float(tamb)
        return float(tsp)

    # 압력 파생 (간단한 함수 형태)
    def derive_pressures(self, *, tch: float, tamb: float) -> tuple[float, float]:
        pt1 = max(0.5, 1.5 - 0.002 * (float(tamb) - float(tch)))
        pt3 = max(0.5, 1.2 - 0.0015 * (float(tamb) - float(tch)))
        return float(pt1), float(pt3)

    # 콤프레서 상태 (상태 기반)
    def comp_status(self, *, state: int, STATE: dict[str, int]) -> tuple[int, str]:
        running = int(state in (STATE.get("INIT", -1), STATE.get("PRECOOL", -1), STATE.get("RUN", -1), STATE.get("HOLD", -1)))
        return running, ("RUNNING" if running else "OFF")

    # 펌프/히터 출력 파생 (명령 기반 단순 맵핑)
    def device_actuators(
        self,
        *,
        pump_cmd: int,
        heat_cmd: int,
        pump_freq_on: float,
        pump_freq_off: float,
        heater_power_on: float,
        heater_power_off: float,
    ) -> tuple[int, float, int, float]:
        pump_run = int(pump_cmd)
        pump_freq = float(pump_freq_on) if pump_run else float(pump_freq_off)
        heat_run = int(heat_cmd)
        heat_power = float(heater_power_on) if heat_run else float(heater_power_off)
        return pump_run, pump_freq, heat_run, heat_power

    # 밸브 개도/유량 파생 (간단 모델)
    def valve_flows(self, *, v17_cmd: int, v10_cmd: int) -> tuple[float, float, float]:
        v17_pos = 100.0 if int(v17_cmd) else 0.0
        flow_v17 = 0.08 * v17_pos  # 약 8 L/min @ 100%
        flow_v10 = 6.0 if int(v10_cmd) else 0.0
        return float(v17_pos), float(flow_v17), float(flow_v10)

    # 외부에서 선택 모드(CMD:MODE)를 저장해둘 수 있는 훅
    def set_mode(self, mode_value: int) -> None:
        try:
            self.mode = ModeCmd(int(mode_value))
        except Exception:
            self.mode = ModeCmd.NONE
