#!/usr/bin/env python3
"""
EPICS PV bridge for the CryoCooler simulator.

Reads setpoint/commands from PVs and publishes simulated temperatures and state.
Requires: pyepics

Usage:
  python tools/pv_bridge.py --dt 0.1 --q_dcm 200

Primary PVs (must exist in IOC DB):
  - BL:DCM:CRYO:STATE:MAIN (mbbi)
  - BL:DCM:CRYO:STATE:TEXT (stringin)
  - BL:DCM:CRYO:CMD:MAIN (mbbo)
  - BL:DCM:CRYO:TEMP:SETPOINT (ao)
  - BL:DCM:CRYO:TEMP:T5 (ai)
  - BL:DCM:CRYO:TEMP:T6 (ai)
  - BL:DCM:CRYO:PRESS:PT1 (ai)
  - BL:DCM:CRYO:PRESS:PT3 (ai)
  - BL:DCM:CRYO:FLOW:FT18 (ai)
  - BL:DCM:CRYO:TIME (ai)
  - BL:DCM:CRYO:LEVEL:LT19 (ai)
  - BL:DCM:CRYO:LEVEL:LT23 (ai)
  - BL:DCM:CRYO:ALARM:MAX_SEVERITY (mbbi)

Commands:
  - CMD:MAIN (system control): 0 NONE, 1 START, 2 STOP, 3 HOLD, 4 RESUME, 5 OFF, 6 RESET
  - CMD:MODE (sequence select): 0 NONE, 1 PURGE, 2 READY, 3 Cool-Down, 4 Warm-up,
    5 Refill HV ON, 6 Refill HV OFF, 7 Refill SUB ON, 8 Refill SUB OFF
  - Start semantics: START + MODE triggers simulator sequence (e.g., MODE=3 -> auto_cool_down)

Devices and auxiliaries mirrored by the bridge:
  - COMP:RUNNING (bi), COMP:STATUS (stringin)
  - VALVE:V9/V15/V17/V19:CMD (bo) -> STATUS (bi)
  - VALVE:V11/V20:CMD (bo) -> STATUS (bi)
  - VALVE:V10/VALVE:V21 STATUS held CLOSED (bi)
  - VALVE:V17 (ao position 0-100%) and FLOW:V17 (ai) synthesized from CMD
  - PUMP:CMD (bo) -> RUNNING (bi) and PUMP:FREQ (ao)
  - HEATER:CMD (bo) -> RUNNING (bi) and HEATER:POWER (ao)
  - Historical arrays under BL:DCM:CRYO:HIST:* (waveform)
Notes:
  - TEMP:T5 is the primary cold-region temperature used for GUI/trends.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from typing import Optional
from collections import deque
from pathlib import Path

# Ensure project root is on sys.path when executed as a script
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from epics import PV
    import numpy as np
    import yaml
except Exception as exc:  # pragma: no cover - import diagnostic
    print("[pv_bridge] pyepics import failed. Please `pip install pyepics`.")
    print(f"reason: {exc}")
    sys.exit(2)

from sim.core import CryoCoolerSim, State as SimState, Controls as SimControls
from sim.logic import OperatingLogic, InterlockLogic, Sequencer, AutoKind, MainCmd, OperState


PV_STATE = "BL:DCM:CRYO:STATE:MAIN"
PV_CMD = "BL:DCM:CRYO:CMD:MAIN"
PV_MODE = "BL:DCM:CRYO:CMD:MODE"
PV_TSP = "BL:DCM:CRYO:TEMP:SETPOINT"
PV_T5 = "BL:DCM:CRYO:TEMP:T5"
PV_T6 = "BL:DCM:CRYO:TEMP:T6"
PV_PT1 = "BL:DCM:CRYO:PRESS:PT1"
PV_PT3 = "BL:DCM:CRYO:PRESS:PT3"
PV_PT3_SP = "BL:DCM:CRYO:PRESS:PT3:SP"
PV_FT18 = "BL:DCM:CRYO:FLOW:FT18"
PV_TSUB = "BL:DCM:CRYO:TEMP:SUBCOOLER"
PV_STATE_TEXT = "BL:DCM:CRYO:STATE:TEXT"
PV_COMP_RUN = "BL:DCM:CRYO:COMP:RUNNING"
PV_COMP_STATUS = "BL:DCM:CRYO:COMP:STATUS"
PV_V9_CMD = "BL:DCM:CRYO:VALVE:V9:CMD"
PV_V9_STATUS = "BL:DCM:CRYO:VALVE:V9:STATUS"
PV_V15_CMD = "BL:DCM:CRYO:VALVE:V15:CMD"
PV_V15_STATUS = "BL:DCM:CRYO:VALVE:V15:STATUS"
PV_V17_CMD = "BL:DCM:CRYO:VALVE:V17:CMD"
PV_V17_STATUS = "BL:DCM:CRYO:VALVE:V17:STATUS"
PV_V19_CMD = "BL:DCM:CRYO:VALVE:V19:CMD"
PV_V19_STATUS = "BL:DCM:CRYO:VALVE:V19:STATUS"
PV_V11_CMD = "BL:DCM:CRYO:VALVE:V11:CMD"
PV_V11_STATUS = "BL:DCM:CRYO:VALVE:V11:STATUS"
PV_V20_CMD = "BL:DCM:CRYO:VALVE:V20:CMD"
PV_V20_STATUS = "BL:DCM:CRYO:VALVE:V20:STATUS"
PV_V10_STATUS = "BL:DCM:CRYO:VALVE:V10:STATUS"
PV_V21_STATUS = "BL:DCM:CRYO:VALVE:V21:STATUS"
PV_V10_CMD = "BL:DCM:CRYO:VALVE:V10:CMD"
PV_V21_CMD = "BL:DCM:CRYO:VALVE:V21:CMD"
PV_PUMP_CMD = "BL:DCM:CRYO:PUMP:CMD"
PV_PUMP_RUN = "BL:DCM:CRYO:PUMP:RUNNING"
PV_PUMP_FREQ = "BL:DCM:CRYO:PUMP:FREQ"
PV_HEAT_CMD = "BL:DCM:CRYO:HEATER:CMD"
PV_HEAT_RUN = "BL:DCM:CRYO:HEATER:RUNNING"
PV_HEAT_POWER = "BL:DCM:CRYO:HEATER:POWER"
PV_TIME = "BL:DCM:CRYO:TIME"
PV_LT19 = "BL:DCM:CRYO:LEVEL:LT19"
PV_LT23 = "BL:DCM:CRYO:LEVEL:LT23"
PV_ALARM_MAX = "BL:DCM:CRYO:ALARM:MAX_SEVERITY"
PV_SAFETY_ILK = "BL:DCM:CRYO:SAFETY:INTERLOCK"
PV_V17_POS = "BL:DCM:CRYO:VALVE:V17"
PV_FLOW_V17 = "BL:DCM:CRYO:FLOW:V17"
PV_FLOW_V10 = "BL:DCM:CRYO:FLOW:V10"
PV_DCM_POWER = "BL:DCM:CRYO:DCM:POWER"

# Optional live-tuning PVs (existence optional in IOC DB)
PV_TUNE_LT19_FILL_LPS = "BL:DCM:CRYO:TUNE:LT19:FILL_LPS"
PV_TUNE_LT19_BASE_CONS_LPS = "BL:DCM:CRYO:TUNE:LT19:BASE_CONS_LPS"
PV_TUNE_LT19_POWER_CONS_LPS_PERW = "BL:DCM:CRYO:TUNE:LT19:POWER_CONS_LPS_PERW"
PV_TUNE_LT19_VENT_GAMMA_LPS_PERLPM = "BL:DCM:CRYO:TUNE:LT19:VENT_GAMMA_LPS_PERLPM"
PV_TUNE_LT23_REFILL_RATE_PCTPS = "BL:DCM:CRYO:TUNE:LT23:REFILL_RATE_PCTPS"
PV_TUNE_LT23_DRAIN_RATE_PCTPS = "BL:DCM:CRYO:TUNE:LT23:DRAIN_RATE_PCTPS"
PV_TUNE_LT23_BASE_CONS_PCTPS = "BL:DCM:CRYO:TUNE:LT23:BASE_CONS_PCTPS"
PV_TUNE_LT23_POWER_CONS_PCTPS_PERW = "BL:DCM:CRYO:TUNE:LT23:POWER_CONS_PCTPS_PERW"
PV_TUNE_LT23_HEATER_CONS_PCTPS_MAX = "BL:DCM:CRYO:TUNE:LT23:HEATER_CONS_PCTPS_MAX"
PV_TUNE_LT23_VENT_GAMMA_PCTPS = "BL:DCM:CRYO:TUNE:LT23:VENT_GAMMA_PCTPS"

# Historical arrays (waveforms)
PV_HIST_TIME = "BL:DCM:CRYO:HIST:TIME"
PV_HIST_T5 = "BL:DCM:CRYO:HIST:TEMP:T5"
PV_HIST_T6 = "BL:DCM:CRYO:HIST:TEMP:T6"
PV_HIST_PT1 = "BL:DCM:CRYO:HIST:PRESS:PT1"
PV_HIST_PT3 = "BL:DCM:CRYO:HIST:PRESS:PT3"
PV_HIST_FT18 = "BL:DCM:CRYO:HIST:FLOW:FT18"
PV_HIST_FLOW_V17 = "BL:DCM:CRYO:HIST:FLOW:V17"
PV_HIST_FLOW_V10 = "BL:DCM:CRYO:HIST:FLOW:V10"
PV_HIST_PUMP_FREQ = "BL:DCM:CRYO:HIST:PUMP:FREQ"


# Operating state values derived from shared enum
STATE = {name: enum.value for name, enum in OperState.__members__.items()}

# Commands are compared against `MainCmd` enum values.


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="PV bridge for CryoCooler simulator")
    p.add_argument("--dt", type=float, default=0.1, help="step time (s)")
    p.add_argument("--q_dcm", type=float, default=200.0, help="DCM heat load (W)")
    p.add_argument("--log-interval", type=float, default=0.0, help="주기 로그 간격(seconds). 0이면 비활성화")
    # 상태 전이/제어 밴드는 OperatingLogic에서 관리
    p.add_argument(
        "--init-config",
        type=str,
        default="",
        help="초기 PV 값을 적용할 YAML 파일 경로 (예: tools/pv_init.yaml)",
    )
    p.add_argument("--verbose", action="store_true", help="Print debug info")
    return p.parse_args(argv)


class PVBridge:
    def __init__(self, dt: float, q_dcm: float, verbose: bool = False, init_config: str | None = None, log_interval: float = 0.0) -> None:
        # Initialize full CryoCooler simulator
        self.sim = CryoCoolerSim(
            SimState(T5=280.0, T6=280.0, PT1=1.0, PT3=1.0, LT19=40.0, LT23=30.0),
            SimControls(
                V9=False, V11=False, V19=False, V15=False, V21=False,
                V10=0.6, V17=0.0, V20=0.0, pump_hz=0.0,
                press_ctrl_on=False, press_sp_bar=2.0,
            ),
        )
        self.dt = dt
        self.q_dcm = q_dcm
        self.verbose = verbose
        self.init_config = init_config or ""
        # Configurable runtime defaults (can be overridden by YAML)
        self.alarm_t_high = 250.0
        self.pump_freq_on = 60.0
        self.pump_freq_off = 0.0
        self.heater_power_on = 30.0
        self.heater_power_off = 0.0
        self._last_transition_log = 0.0
        self.log_interval = float(log_interval or 0.0)
        self._log_elapsed = 0.0
        # Event tracing helpers (AUTO/Stage changes)
        self._last_auto_name: str | None = None
        self._last_stage: int | None = None
        # Live-tuning PV registry (connected ones only)
        self._tune_pvs: dict[str, PV] = {}

        # EPICS PVs
        self.pv_state = PV(PV_STATE, auto_monitor=True)
        self.pv_cmd = PV(PV_CMD, auto_monitor=True)
        self.pv_mode = PV(PV_MODE, auto_monitor=True)
        self.pv_tsp = PV(PV_TSP, auto_monitor=True)
        self.pv_t5 = PV(PV_T5, auto_monitor=False)
        self.pv_t6 = PV(PV_T6, auto_monitor=False)
        self.pv_tsub = PV(PV_TSUB, auto_monitor=True)
        self.pv_state_text = PV(PV_STATE_TEXT, auto_monitor=False)
        self.pv_comp_run = PV(PV_COMP_RUN, auto_monitor=False)
        self.pv_comp_status = PV(PV_COMP_STATUS, auto_monitor=False)
        self.pv_v9_cmd = PV(PV_V9_CMD, auto_monitor=True)
        self.pv_v9_status = PV(PV_V9_STATUS, auto_monitor=False)
        self.pv_v15_cmd = PV(PV_V15_CMD, auto_monitor=True)
        self.pv_v15_status = PV(PV_V15_STATUS, auto_monitor=False)
        self.pv_v17_cmd = PV(PV_V17_CMD, auto_monitor=True)
        self.pv_v17_status = PV(PV_V17_STATUS, auto_monitor=False)
        self.pv_v19_cmd = PV(PV_V19_CMD, auto_monitor=True)
        self.pv_v19_status = PV(PV_V19_STATUS, auto_monitor=False)
        self.pv_v11_cmd = PV(PV_V11_CMD, auto_monitor=True)
        self.pv_v11_status = PV(PV_V11_STATUS, auto_monitor=False)
        self.pv_v20_cmd = PV(PV_V20_CMD, auto_monitor=True)
        self.pv_v20_status = PV(PV_V20_STATUS, auto_monitor=False)
        self.pv_v10_status = PV(PV_V10_STATUS, auto_monitor=False)
        self.pv_v21_status = PV(PV_V21_STATUS, auto_monitor=False)
        self.pv_v10_cmd = PV(PV_V10_CMD, auto_monitor=True)
        self.pv_v21_cmd = PV(PV_V21_CMD, auto_monitor=True)
        self.pv_pump_cmd = PV(PV_PUMP_CMD, auto_monitor=True)
        self.pv_pump_run = PV(PV_PUMP_RUN, auto_monitor=False)
        self.pv_pump_freq = PV(PV_PUMP_FREQ, auto_monitor=False)
        self.pv_heat_cmd = PV(PV_HEAT_CMD, auto_monitor=True)
        self.pv_heat_run = PV(PV_HEAT_RUN, auto_monitor=False)
        self.pv_heat_power = PV(PV_HEAT_POWER, auto_monitor=False)
        self.pv_time = PV(PV_TIME, auto_monitor=False)
        self.pv_lt19 = PV(PV_LT19, auto_monitor=True)
        self.pv_lt23 = PV(PV_LT23, auto_monitor=True)
        self.pv_alarm_max = PV(PV_ALARM_MAX, auto_monitor=False)
        self.pv_safety_ilk = PV(PV_SAFETY_ILK, auto_monitor=False)
        # Additional process PVs for plotting
        self.pv_pt1 = PV(PV_PT1, auto_monitor=False)
        self.pv_pt3 = PV(PV_PT3, auto_monitor=False)
        self.pv_pt3_sp = PV(PV_PT3_SP, auto_monitor=True)
        self.pv_ft18 = PV(PV_FT18, auto_monitor=False)
        self.pv_v17_pos = PV(PV_V17_POS, auto_monitor=True)
        self.pv_flow_v17 = PV(PV_FLOW_V17, auto_monitor=False)
        self.pv_flow_v10 = PV(PV_FLOW_V10, auto_monitor=False)
        self.pv_dcm_power = PV(PV_DCM_POWER, auto_monitor=False)
        # Historical arrays (waveforms)
        self.pv_hist_time = PV(PV_HIST_TIME, auto_monitor=False)
        self.pv_hist_t5 = PV(PV_HIST_T5, auto_monitor=False)
        self.pv_hist_t6 = PV(PV_HIST_T6, auto_monitor=False)
        self.pv_hist_pt1 = PV(PV_HIST_PT1, auto_monitor=False)
        self.pv_hist_pt3 = PV(PV_HIST_PT3, auto_monitor=False)
        self.pv_hist_ft18 = PV(PV_HIST_FT18, auto_monitor=False)
        self.pv_hist_flow_v17 = PV(PV_HIST_FLOW_V17, auto_monitor=False)
        self.pv_hist_flow_v10 = PV(PV_HIST_FLOW_V10, auto_monitor=False)
        self.pv_hist_pump_freq = PV(PV_HIST_PUMP_FREQ, auto_monitor=False)

        # Local state
        self.state: int = OperState.OFF.value
        self._last_cmd_val: int = 0
        self._last_mode_val: int = 0
        # 사용자가 최근에 선택했던 유효 모드(0이 아닌 값) 기억: START 펄스와 모드 갱신 간 타이밍 이슈 보완
        self._last_nonzero_mode: int = 0
        self._held: bool = False
        # 브리지 상태 보조값은 불필요
        # History buffers (seconds window ~ maxlen * dt)
        self.hist_len = min(2048, max(120, int(600.0 / self.dt)))
        self.hist_time = deque(maxlen=self.hist_len)
        self.hist_t5 = deque(maxlen=self.hist_len)
        self.hist_t6 = deque(maxlen=self.hist_len)
        self.hist_pt1 = deque(maxlen=self.hist_len)
        self.hist_pt3 = deque(maxlen=self.hist_len)
        self.hist_ft18 = deque(maxlen=self.hist_len)
        self.hist_flow_v17 = deque(maxlen=self.hist_len)
        self.hist_flow_v10 = deque(maxlen=self.hist_len)
        self.hist_pump_freq = deque(maxlen=self.hist_len)

        # Verify connections
        conns = [
            (PV_STATE, self.pv_state),
            (PV_CMD, self.pv_cmd),
            (PV_MODE, self.pv_mode),
            (PV_TSP, self.pv_tsp),
            (PV_T5, self.pv_t5),
            (PV_T6, self.pv_t6),
            (PV_TSUB, self.pv_tsub),
            (PV_STATE_TEXT, self.pv_state_text),
            (PV_COMP_RUN, self.pv_comp_run),
            (PV_COMP_STATUS, self.pv_comp_status),
            (PV_V9_CMD, self.pv_v9_cmd),
            (PV_V9_STATUS, self.pv_v9_status),
            (PV_V15_CMD, self.pv_v15_cmd),
            (PV_V15_STATUS, self.pv_v15_status),
            (PV_V17_CMD, self.pv_v17_cmd),
            (PV_V17_STATUS, self.pv_v17_status),
            (PV_V19_CMD, self.pv_v19_cmd),
            (PV_V19_STATUS, self.pv_v19_status),
            (PV_V11_CMD, self.pv_v11_cmd),
            (PV_V11_STATUS, self.pv_v11_status),
            (PV_V20_CMD, self.pv_v20_cmd),
            (PV_V20_STATUS, self.pv_v20_status),
            (PV_V10_STATUS, self.pv_v10_status),
            (PV_V21_STATUS, self.pv_v21_status),
            (PV_V10_CMD, self.pv_v10_cmd),
            (PV_V21_CMD, self.pv_v21_cmd),
            (PV_PUMP_CMD, self.pv_pump_cmd),
            (PV_PUMP_RUN, self.pv_pump_run),
            (PV_PUMP_FREQ, self.pv_pump_freq),
            (PV_HEAT_CMD, self.pv_heat_cmd),
            (PV_HEAT_RUN, self.pv_heat_run),
            (PV_HEAT_POWER, self.pv_heat_power),
            (PV_TIME, self.pv_time),
            (PV_LT19, self.pv_lt19),
            (PV_LT23, self.pv_lt23),
            (PV_ALARM_MAX, self.pv_alarm_max),
            (PV_SAFETY_ILK, self.pv_safety_ilk),
            (PV_PT3_SP, self.pv_pt3_sp),
            (PV_HIST_TIME, self.pv_hist_time),
            (PV_HIST_T5, self.pv_hist_t5),
            (PV_HIST_T6, self.pv_hist_t6),
            (PV_HIST_PT1, self.pv_hist_pt1),
            (PV_HIST_PT3, self.pv_hist_pt3),
            (PV_V17_POS, self.pv_v17_pos),
            (PV_FLOW_V17, self.pv_flow_v17),
            (PV_FLOW_V10, self.pv_flow_v10),
            (PV_DCM_POWER, self.pv_dcm_power),
        ]
        failed = []
        for name, obj in conns:
            if not obj.wait_for_connection(timeout=1.0):
                failed.append(name)
        if self.verbose:
            print(f"[pv_bridge] connected={len(conns)-len(failed)}/{len(conns)}")
            if failed:
                print("[pv_bridge] missing:", ", ".join(failed))
        if failed:
            # We continue, but warn that some PVs are missing
            pass

    def _read(self, pv: PV, default: float) -> float:
        v = pv.get(timeout=0.2)
        return float(v) if v is not None else float(default)

    def _read_bool(self, pv: PV, default: bool = False) -> bool:
        """Robust boolean read from bo/bi PVs.

        Accepts numeric 0/1, numpy scalars, or enum strings like 'OPEN'/'CLOSE', 'ON'/'OFF'.
        """
        try:
            v = pv.get(timeout=0.2)
        except Exception:
            return bool(default)
        if v is None:
            return bool(default)
        # Numeric-like
        try:
            return int(v) != 0  # handles numpy scalars too
        except Exception:
            pass
        # String-like
        try:
            s = str(v).strip().upper()
            if s in ("", "0", "OFF", "CLOSE", "FALSE", "NO"):
                return False
            if s in ("1", "ON", "OPEN", "TRUE", "YES"):
                return True
        except Exception:
            pass
        return bool(default)

    def _write_int(self, pv: PV, val: int) -> None:
        pv.put(int(val), wait=False)

    def _write_float(self, pv: PV, val: float) -> None:
        pv.put(float(val), wait=False)

    def _state_name(self, s: Optional[int] = None) -> str:
        if s is None:
            s = self.state
        try:
            return OperState(int(s)).name
        except Exception:
            return f"UNKNOWN({s})"

    # 상태 전이는 OperatingLogic이 담당하므로 브리지 내 로직 없음

    def loop(self) -> None:
        # Initialize PVs
        tsp = self._read(self.pv_tsp, default=80.0)
        
        # Initialize PT3 setpoint PV with current model value
        try:
            self._write_float(self.pv_pt3_sp, float(self.sim.controls.press_sp_bar))
        except Exception:
            pass

        self._write_int(self.pv_state, self.state)
        self.pv_state_text.put(self._state_name(), wait=False)
        self._write_float(self.pv_t5, self.sim.state.T5)
        self._write_float(self.pv_t6, self.sim.state.T6)
        self._write_float(self.pv_time, 0.0)
        
        # Subcooler default
        try:
            # Initialize SUBCOOLER to 77.3 K
            self._write_float(self.pv_tsub, 77.3)
        except Exception:
            pass
        # LT19/LT23는 IOC 현재값을 신뢰하여 시뮬레이터 상태에 반영한다(초기 시드 동기화).
        try:
            self.sim.state.LT19 = float(self._read(self.pv_lt19, self.sim.state.LT19))
            self.sim.state.LT23 = float(self._read(self.pv_lt23, self.sim.state.LT23))
        except Exception:
            pass
        self._write_int(self.pv_alarm_max, 0)
        # Initialize auxiliaries
        self._write_int(self.pv_pump_run, 0)
        self._write_float(self.pv_pump_freq, 0.0)
        self._write_int(self.pv_heat_run, 0)
        self._write_float(self.pv_heat_power, 0.0)
        self._write_int(self.pv_v9_status, 0)
        self._write_int(self.pv_v11_status, 0)
        self._write_int(self.pv_v15_status, 0)
        self._write_int(self.pv_v17_status, 0)
        self._write_int(self.pv_v19_status, 0)
        self._write_int(self.pv_v20_status, 0)
        self._write_int(self.pv_v10_status, 0)
        self._write_int(self.pv_v21_status, 0)
        self._write_float(self.pv_v17_pos, 0.0)
        self._write_float(self.pv_flow_v17, 0.0)
        self._write_float(self.pv_flow_v10, 0.0)
        # DCM power PV는 입력으로 사용(초기값은 pv_init.yaml로 시드 가능)
        try:
            # 표시 목적 및 일관성 확보를 위해 초기 q_dcm 값을 PV에도 반영해 둔다
            self._write_float(self.pv_dcm_power, float(self.q_dcm))
        except Exception:
            pass
        # Interlock defaults
        try:
            self._write_int(self.pv_safety_ilk, 0)
        except Exception:
            pass
        # Optional external logic configs
        self._load_operating_interlock()

        # Create sequencer/controller bound to simulator
        try:
            self.seq = Sequencer(self.sim)
        except Exception:
            self.seq = None  # fallback; should not happen

        # YAML 초기값 적용(있으면 기본값을 덮어씀)
        self._apply_init_from_yaml()
        # 튜닝 PV 초기화(있을 시 현재 파라메타 게시)
        try:
            self._init_tuning_pvs()
        except Exception:
            pass
        # YAML이 PV를 갱신했을 수 있으므로 다시 동기화
        try:
            self.sim.state.LT19 = float(self._read(self.pv_lt19, self.sim.state.LT19))
            self.sim.state.LT23 = float(self._read(self.pv_lt23, self.sim.state.LT23))
        except Exception:
            pass
        
        # Seed history with first sample
        self.hist_time.clear()
        self.hist_t5.clear()
        self.hist_t6.clear()
        self.hist_pt1.clear()
        self.hist_pt3.clear()
        self.hist_time.append(0.0)
        self.hist_t5.append(self.sim.state.T5)
        self.hist_t6.append(self.sim.state.T6)
        self.hist_pt1.append(1.0)
        self.hist_pt3.append(1.0)
        self.hist_ft18.append(0.0)
        self.hist_flow_v17.append(0.0)
        self.hist_flow_v10.append(0.0)
        self.hist_pump_freq.append(0.0)
        self._publish_history()

        if self.verbose:
            print(f"[pv_bridge] loop start dt={self.dt} q_dcm={self.q_dcm}")
        while True:
            tsp = self._read(self.pv_tsp, default=tsp)
            # Live-tuning PV 값 반영
            try:
                self._apply_tuning_from_pvs()
            except Exception:
                pass
            mode_val = int(self.pv_mode.get() or 0)
            # 최근 유효 모드(latched) 갱신 및 OperatingLogic에 반영 (0은 무시하여 래칭 유지)
            mode_changed = (mode_val != self._last_mode_val)
            if mode_val != 0:
                self._last_nonzero_mode = mode_val
                if mode_changed and (self.oper_logic is not None):
                    try:
                        self.oper_logic.set_mode(mode_val)
                    except Exception:
                        pass
            cmd_val = int(self.pv_cmd.get() or 0)
            cmd_changed = (cmd_val != self._last_cmd_val)
            # START/STOP 등 MainCmd 변화시에만 시퀀스 액션 호출
            eff_mode_val = (self.oper_logic.mode if getattr(self, 'oper_logic', None) is not None else 0) or (self._last_nonzero_mode or 0)
            if cmd_changed:
                try:
                    if self.oper_logic is not None:
                        target = self.seq if (getattr(self, 'seq', None) is not None) else self.sim
                        self.oper_logic.apply_mode_action(target, cmd_val=cmd_val, mode_val=eff_mode_val)
                except Exception as e:
                    if self.verbose:
                        print(f"[pv_bridge] operating.apply_mode_action error: {e}")
                # Update hold flag from command
                if cmd_val == MainCmd.HOLD.value:
                    self._held = True
                elif cmd_val in (
                    MainCmd.RESUME.value, MainCmd.START.value, MainCmd.STOP.value, MainCmd.OFF.value, MainCmd.RESET.value
                ):
                    self._held = False
                # STOP/OFF 직후 수동모드로 전환: 현재 강제 상태를 PV CMD에 반영해 동기화
                try:
                    if cmd_val in (MainCmd.STOP.value, MainCmd.OFF.value):
                        self._sync_manual_cmd_pvs_from_sim()
                except Exception:
                    pass
                self._last_cmd_val = cmd_val
                self._last_mode_val = mode_val

            # Simulator step and publish
            self._apply_manual_actuators_if_allowed()
            # Apply PT3 setpoint from PV
            try:
                self.sim.controls.press_sp_bar = float(self._read(self.pv_pt3_sp, default=self.sim.controls.press_sp_bar))
            except Exception:
                pass
            # Update sequencer (operating controller) before physics
            try:
                if self.seq is not None:
                    self.seq.update(self.dt)
            except Exception:
                pass
            self.sim.step(self.dt, power_W=self.q_dcm)
            self._write_float(self.pv_t5, self.sim.state.T5)
            self._write_float(self.pv_t6, self.sim.state.T6)
            self._write_float(self.pv_pt1, self.sim.state.PT1)
            self._write_float(self.pv_pt3, self.sim.state.PT3)
            self._write_float(self.pv_ft18, self.sim.state.FT18)
            self._write_float(self.pv_time, (self.pv_time.get() or 0.0) + self.dt)
            # Publish levels to PVs so HMI (caget) reflects simulator state
            self._write_float(self.pv_lt19, self.sim.state.LT19)
            self._write_float(self.pv_lt23, self.sim.state.LT23)
            # Pre-compute derived flows before history append
            # (fix: ensure flow_v17/flow_v10 are defined before use)
            v17_pos = float(self.sim.controls.V17) * 100.0
            flow_v17 = 0.08 * v17_pos
            flow_v10 = 6.0 if int(self.sim.controls.V10 > 0.5) else 0.0

            # Update history arrays
            tnext = (self.hist_time[-1] if self.hist_time else 0.0) + self.dt
            self.hist_time.append(tnext)
            self.hist_t5.append(self.sim.state.T5)
            self.hist_t6.append(self.sim.state.T6)
            self.hist_pt1.append(self.sim.state.PT1)
            self.hist_pt3.append(self.sim.state.PT3)
            self.hist_ft18.append(self.sim.state.FT18)
            self.hist_flow_v17.append(flow_v17)
            self.hist_flow_v10.append(flow_v10)
            self.hist_pump_freq.append(self.sim.controls.pump_hz)
            self._publish_history()
            # State transition managed by OperatingLogic
            try:
                if self.oper_logic is not None:
                    # START와 같은 레벨 명령은 변경 시점에만 유효하도록 펄스 처리
                    cmd_for_transition = cmd_val if cmd_changed else 0
                    new_state = self.oper_logic.next_state(
                        state=self.state,
                        STATE=STATE,
                        cmd_val=cmd_for_transition,
                        mode_val=eff_mode_val,
                        tsp=tsp,
                        t5=self.sim.state.T5,
                        tamb=getattr(self.sim, 'ambK', 280.0),
                        dt=self.dt,
                    )
                    if int(new_state) != int(self.state):
                        self.state = int(new_state)
                        self._write_int(self.pv_state, self.state)
                        self.pv_state_text.put(self._state_name(), wait=False)
                else:
                    # Fallback: keep state as-is
                    pass
            except Exception as e:
                if self.verbose:
                    print(f"[pv_bridge] operating.next_state error: {e}")
            comp_on = 1 if (self.sim.controls.pump_hz > 0.0 or self.sim.controls.press_ctrl_on) else 0
            self._write_int(self.pv_comp_run, comp_on)
            self.pv_comp_status.put("RUNNING" if comp_on else "OFF", wait=False)

            # One-shot event logs when AUTO or STAGE changes
            try:
                cur_auto_name = getattr(self.seq, 'auto', None).name if getattr(self, 'seq', None) is not None else 'NA'
                cur_stage = int(getattr(self.seq, 'stage', -1))
                if (cur_auto_name != self._last_auto_name) or (cur_stage != self._last_stage):
                    self._last_auto_name = cur_auto_name
                    self._last_stage = cur_stage
                    if self.verbose:
                        #ts2 = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                        ts2 = datetime.now().strftime('%H:%M')
                        print(
                            "[event]",
                            ts2,
                            f"AUTO={cur_auto_name}",
                            f"STAGE={cur_stage}",
                            #f"T6={self.sim.state.T6:.1f}K",
                            #f"PT1={self.sim.state.PT1:.2f}bar",
                            #f"PT3={self.sim.state.PT3:.2f}bar",
                        )
            except Exception:
                pass

            # Mirror valve statuses from commands
            self._mirror_status_from_sim()
            self._write_float(self.pv_v17_pos, v17_pos)
            self._write_float(self.pv_flow_v17, flow_v17)
            self._write_float(self.pv_flow_v10, flow_v10)
            self._write_int(self.pv_pump_run, 1 if self.sim.controls.pump_hz > 0.0 else 0)
            self._write_float(self.pv_pump_freq, float(self.sim.controls.pump_hz))
            self._write_int(self.pv_heat_run, 1 if self.sim.controls.press_ctrl_on else 0)
            self._write_float(self.pv_heat_power, float(self.sim.controls._heater_u) * 100.0)

            # Interlock evaluation (if configured), else fallback simple rule
            if self.ilk_logic is not None:
                sev, safe = self.ilk_logic.evaluate(
                    {
                        "tch": float('nan'),
                        "lt19": float(self._read(self.pv_lt19, 50.0)),
                        "lt23": float(self._read(self.pv_lt23, 70.0)),
                        "ft18": float(self.sim.state.FT18),
                    }
                )
                self._write_int(self.pv_alarm_max, int(sev))
                self._write_int(self.pv_safety_ilk, 1 if safe else 0)
            else:
                self._write_int(self.pv_alarm_max, 1 if self.sim.state.T6 > float(self.alarm_t_high) else 0)
            # Read DCM power from PV as input (operator-set heat load)
            try:
                self.q_dcm = float(self._read(self.pv_dcm_power, default=self.q_dcm))
            except Exception:
                pass

            # 주기 로그(모드/메인 명령 및 핵심 상태) 출력
            if self.log_interval > 0.0:
                self._log_elapsed += self.dt
                if self._log_elapsed >= self.log_interval:
                    self._log_elapsed = 0.0
                    try:
                        ts = datetime.now().strftime('%H:%M')
                    except Exception:
                        ts = f"t={self.pv_time.get() or 0.0:.1f}s"
                    try:
                        print(
                            "[trace]",
                            ts,
                            f"CMD={int(cmd_val)}",
                            f"MODE={int(mode_val)}",
                            f"effMODE={int(eff_mode_val)}",
                            f"STATE={self._state_name()}",
                            f"AUTO={getattr(self.seq, 'auto', None).name if getattr(self, 'seq', None) is not None else 'NA'}",
                            f"STAGE={int(getattr(self.seq, 'stage', -1))}",
                            #f"V10={'OPEN' if (self.sim.controls.V10 > 0.5) else 'CLOSE'}",
                            #f"V17={'OPEN' if (self.sim.controls.V17 > 0.5) else 'CLOSE'}",
                            #f"V20={'OPEN' if (self.sim.controls.V20 > 0.5) else 'CLOSE'}",
                            #f"V15={'OPEN' if self.sim.controls.V15 else 'CLOSE'}",
                            #f"V19={'OPEN' if self.sim.controls.V19 else 'CLOSE'}",
                            #f"LT23={self.sim.state.LT23:.1f}%",
                            #f"LT19={self.sim.state.LT19:.1f}%",
                        )
                    except Exception:
                        pass

            # Done updating derived PVs (suppress per-iteration verbose prints)

            time.sleep(self.dt)

    def _publish_history(self) -> None:
        try:
            self.pv_hist_time.put(np.asarray(self.hist_time, dtype=float), wait=False)
            self.pv_hist_t5.put(np.asarray(self.hist_t5, dtype=float), wait=False)
            self.pv_hist_t6.put(np.asarray(self.hist_t6, dtype=float), wait=False)
            self.pv_hist_pt1.put(np.asarray(self.hist_pt1, dtype=float), wait=False)
            self.pv_hist_pt3.put(np.asarray(self.hist_pt3, dtype=float), wait=False)
            self.pv_hist_ft18.put(np.asarray(self.hist_ft18, dtype=float), wait=False)
            self.pv_hist_flow_v17.put(np.asarray(self.hist_flow_v17, dtype=float), wait=False)
            self.pv_hist_flow_v10.put(np.asarray(self.hist_flow_v10, dtype=float), wait=False)
            self.pv_hist_pump_freq.put(np.asarray(self.hist_pump_freq, dtype=float), wait=False)
        except Exception as e:
            if self.verbose:
                print(f"[pv_bridge] history publish error: {e}")

    # --- Live tuning PVs (optional) ---
    def _init_tuning_pvs(self) -> None:
        """튜닝용 PV들을 연결하고, 연결 시 현재 파라메타 값을 게시한다."""
        def _try_bind(name: str, value: float) -> None:
            try:
                pv = PV(name, auto_monitor=True)
                if pv.wait_for_connection(timeout=0.2):
                    pv.put(float(value), wait=False)
                    self._tune_pvs[name] = pv
            except Exception:
                pass
        # Subcooler (LT19)
        _try_bind(PV_TUNE_LT19_FILL_LPS, getattr(self.sim, 'fill_Lps_v19', 1.0/60.0))
        _try_bind(PV_TUNE_LT19_BASE_CONS_LPS, getattr(self.sim, 'base_cons_Lps', 3.0/3600.0))
        _try_bind(PV_TUNE_LT19_POWER_CONS_LPS_PERW, getattr(self.sim, 'cons_coeff_Lps_perW', 0.023/3600.0))
        _try_bind(PV_TUNE_LT19_VENT_GAMMA_LPS_PERLPM, getattr(self.sim, 'gamma_vent_Lps_per_Lpm', 0.004/60.0))
        # HV tank (LT23)
        _try_bind(PV_TUNE_LT23_REFILL_RATE_PCTPS, getattr(self.sim, 'refill_rate_pctps', 10.0/60.0))
        _try_bind(PV_TUNE_LT23_DRAIN_RATE_PCTPS, getattr(self.sim, 'drain_rate_pctps', 1.0/60.0))
        _try_bind(PV_TUNE_LT23_BASE_CONS_PCTPS, getattr(self.sim, 'hv_base_cons_pctps', 0.0))
        _try_bind(PV_TUNE_LT23_POWER_CONS_PCTPS_PERW, getattr(self.sim, 'hv_power_cons_pctps_perW', 0.0))
        _try_bind(PV_TUNE_LT23_HEATER_CONS_PCTPS_MAX, getattr(self.sim, 'hv_heater_cons_pctps_max', 0.0))
        _try_bind(PV_TUNE_LT23_VENT_GAMMA_PCTPS, getattr(self.sim, 'hv_vent_gamma_pctps', 0.0))

    def _apply_tuning_from_pvs(self) -> None:
        """튜닝 PV 값이 연결되어 있으면 읽어와 합리적 범위로 클램프 후 적용한다."""
        def _get(name: str) -> Optional[float]:
            pv = self._tune_pvs.get(name)
            if pv is None:
                return None
            try:
                val = pv.get()
                return float(val) if val is not None else None
            except Exception:
                return None
        def clamp(v: float, lo: float, hi: float) -> float:
            return max(lo, min(hi, v))
        v = _get(PV_TUNE_LT19_FILL_LPS)
        if v is not None:
            self.sim.fill_Lps_v19 = clamp(v, 0.0, 10.0)
        v = _get(PV_TUNE_LT19_BASE_CONS_LPS)
        if v is not None:
            self.sim.base_cons_Lps = clamp(v, 0.0, 1.0)
        v = _get(PV_TUNE_LT19_POWER_CONS_LPS_PERW)
        if v is not None:
            self.sim.cons_coeff_Lps_perW = clamp(v, 0.0, 0.01)
        v = _get(PV_TUNE_LT19_VENT_GAMMA_LPS_PERLPM)
        if v is not None:
            self.sim.gamma_vent_Lps_per_Lpm = clamp(v, 0.0, 0.5)
        v = _get(PV_TUNE_LT23_REFILL_RATE_PCTPS)
        if v is not None:
            self.sim.refill_rate_pctps = clamp(v, 0.0, 100.0)
        v = _get(PV_TUNE_LT23_DRAIN_RATE_PCTPS)
        if v is not None:
            self.sim.drain_rate_pctps = clamp(v, 0.0, 100.0)
        v = _get(PV_TUNE_LT23_BASE_CONS_PCTPS)
        if v is not None:
            self.sim.hv_base_cons_pctps = clamp(v, 0.0, 100.0)
        v = _get(PV_TUNE_LT23_POWER_CONS_PCTPS_PERW)
        if v is not None:
            self.sim.hv_power_cons_pctps_perW = clamp(v, 0.0, 1.0)
        v = _get(PV_TUNE_LT23_HEATER_CONS_PCTPS_MAX)
        if v is not None:
            self.sim.hv_heater_cons_pctps_max = clamp(v, 0.0, 100.0)
        v = _get(PV_TUNE_LT23_VENT_GAMMA_PCTPS)
        if v is not None:
            self.sim.hv_vent_gamma_pctps = clamp(v, 0.0, 100.0)

    def _load_operating_interlock(self) -> None:
        """Load optional operating/interlock YAMLs to configure external logic."""
        self.oper_logic = None
        self.ilk_logic = None
        try:
            oper_path = _ROOT / "tools" / "operating.yaml"
            data = {}
            if oper_path.exists():
                import yaml
                with open(oper_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
            # 운영 로직은 선택적 사용
            self.oper_logic = OperatingLogic.from_yaml(data)
        except Exception:
            # 실패 시에도 기본 파라미터로 생성
            self.oper_logic = OperatingLogic.from_yaml({})
        try:
            ilk_path = _ROOT / "tools" / "interlock.yaml"
            if ilk_path.exists():
                import yaml

                with open(ilk_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                self.ilk_logic = InterlockLogic.from_yaml(data)
        except Exception:
            self.ilk_logic = None

    # --- Helpers for CryoCoolerSim integration ---
    

    def _apply_manual_actuators_if_allowed(self) -> None:
        # 수동 조작은 자동 시퀀스 진행 중이 아닐 때 허용한다.
        try:
            if (getattr(self, 'seq', None) is not None) and (self.seq.auto != AutoKind.NONE):
                return
        except Exception:
            return
        try:
            self.sim.controls.V9 = self._read_bool(self.pv_v9_cmd, False)
            self.sim.controls.V11 = self._read_bool(self.pv_v11_cmd, False)
            self.sim.controls.V15 = self._read_bool(self.pv_v15_cmd, False)
            self.sim.controls.V19 = self._read_bool(self.pv_v19_cmd, False)
            self.sim.controls.V20 = 1.0 if self._read_bool(self.pv_v20_cmd, False) else 0.0
            self.sim.controls.V17 = 1.0 if self._read_bool(self.pv_v17_cmd, False) else 0.0
            self.sim.controls.V10 = 1.0 if self._read_bool(self.pv_v10_cmd, False) else 0.0
            self.sim.controls.V21 = self._read_bool(self.pv_v21_cmd, False)
            self.sim.controls.pump_hz = 60.0 if self._read_bool(self.pv_pump_cmd, False) else 0.0
            self.sim.controls.press_ctrl_on = self._read_bool(self.pv_heat_cmd, False)
        except Exception:
            pass

    def _sync_manual_cmd_pvs_from_sim(self) -> None:
        """STOP/OFF 직후 수동 모드로의 전환을 원활히 하기 위해
        현재 시뮬레이터 강제 상태를 PV 명령(CMD)과 동기화한다.
        이렇게 하면 다음 루프부터 수동 조작이 즉시 일관되게 반영된다.
        """
        try:
            self._write_int(self.pv_v9_cmd, 1 if self.sim.controls.V9 else 0)
        except Exception:
            pass
        try:
            self._write_int(self.pv_v11_cmd, 1 if self.sim.controls.V11 else 0)
        except Exception:
            pass
        try:
            self._write_int(self.pv_v15_cmd, 1 if self.sim.controls.V15 else 0)
        except Exception:
            pass
        try:
            self._write_int(self.pv_v19_cmd, 1 if self.sim.controls.V19 else 0)
        except Exception:
            pass
        try:
            self._write_int(self.pv_v20_cmd, 1 if self.sim.controls.V20 > 0.5 else 0)
        except Exception:
            pass
        try:
            self._write_int(self.pv_v17_cmd, 1 if self.sim.controls.V17 > 0.5 else 0)
        except Exception:
            pass
        try:
            self._write_int(self.pv_v10_cmd, 1 if self.sim.controls.V10 > 0.5 else 0)
        except Exception:
            pass
        try:
            self._write_int(self.pv_v21_cmd, 1 if self.sim.controls.V21 else 0)
        except Exception:
            pass
        try:
            self._write_int(self.pv_pump_cmd, 1 if self.sim.controls.pump_hz > 0.0 else 0)
        except Exception:
            pass
        try:
            self._write_int(self.pv_heat_cmd, 1 if self.sim.controls.press_ctrl_on else 0)
        except Exception:
            pass

    def _mirror_status_from_sim(self) -> None:
        self._write_int(self.pv_v9_status, 1 if self.sim.controls.V9 else 0)
        self._write_int(self.pv_v11_status, 1 if self.sim.controls.V11 else 0)
        self._write_int(self.pv_v15_status, 1 if self.sim.controls.V15 else 0)
        self._write_int(self.pv_v17_status, 1 if self.sim.controls.V17 > 0.5 else 0)
        self._write_int(self.pv_v19_status, 1 if self.sim.controls.V19 else 0)
        self._write_int(self.pv_v20_status, 1 if self.sim.controls.V20 > 0.5 else 0)
        self._write_int(self.pv_v10_status, 1 if self.sim.controls.V10 > 0.5 else 0)
        self._write_int(self.pv_v21_status, 1 if self.sim.controls.V21 else 0)

    

    def _apply_init_from_yaml(self) -> None:
        """선택적 YAML 설정 파일에서 초기 설정과 PV 값을 적용한다.

        형식 예시 (tools/pv_init.yaml):
        config:
          dt: 0.1
          tsub: 77.3
          q_dcm: 100.0
        pvs:
          BL:DCM:CRYO:TEMP:SETPOINT: 80
          BL:DCM:CRYO:TEMP:SUBCOOLER: 77.3
          BL:DCM:CRYO:FLOW:FT18: 5.0
          BL:DCM:CRYO:PUMP:CMD: 0
        """
        try:
            cfg_path = self.init_config
            if not cfg_path:
                default_path = _ROOT / "tools" / "pv_init.yaml"
                if default_path.exists():
                    cfg_path = str(default_path)
            if not cfg_path:
                return
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            # Optional overlay (tools/tuning.yaml) to override config/pvs
            try:
                overlay_path = _ROOT / "tools" / "tuning.yaml"
                if overlay_path.exists():
                    with open(overlay_path, "r", encoding="utf-8") as f:
                        overlay = yaml.safe_load(f) or {}
                    if isinstance(overlay, dict):
                        if isinstance(overlay.get("config"), dict):
                            base_cfg = data.get("config") or {}
                            if not isinstance(base_cfg, dict):
                                base_cfg = {}
                            base_cfg.update(overlay["config"])  # type: ignore[index]
                            data["config"] = base_cfg
                        if isinstance(overlay.get("pvs"), dict):
                            base_pvs = data.get("pvs") or {}
                            if not isinstance(base_pvs, dict):
                                base_pvs = {}
                            base_pvs.update(overlay["pvs"])  # type: ignore[index]
                            data["pvs"] = base_pvs
            except Exception:
                pass
            # 1) config 섹션: dt, q_dcm, tsub 등 런타임 파라미터 적용
            cfg = data.get("config", {}) if isinstance(data, dict) else {}
            if isinstance(cfg, dict):
                self._apply_config_with_validation(cfg)
            pvs = data.get("pvs", {}) if isinstance(data, dict) else {}
            if not isinstance(pvs, dict):
                if self.verbose:
                    print("[pv_bridge] init-config: 'pvs' 키가 dict 형식이 아님")
                return
            for name, val in pvs.items():
                try:
                    pv = PV(str(name), auto_monitor=False)
                    if not pv.wait_for_connection(timeout=0.5):
                        if self.verbose:
                            print(f"[pv_bridge] init-config: 연결 실패: {name}")
                        continue
                    pv.put(val, wait=False)
                except Exception as e:
                    if self.verbose:
                        print(f"[pv_bridge] init-config 적용 오류 {name}: {e}")
        except FileNotFoundError:
            if self.verbose:
                print(f"[pv_bridge] init-config 파일 없음: {self.init_config}")
        except Exception as e:
            if self.verbose:
                print(f"[pv_bridge] init-config 로드 오류: {e}")

    def _apply_config_with_validation(self, cfg: dict) -> None:
        """YAML config 키를 검증/클램프하여 안전하게 적용한다."""
        def clamp(v: float, lo: float, hi: float) -> float:
            return max(lo, min(hi, v))
        # Basic run params
        if "dt" in cfg:
            try:
                self.dt = clamp(float(cfg["dt"]), 0.01, 5.0)
            except Exception:
                pass
        if "q_dcm" in cfg:
            try:
                self.q_dcm = clamp(float(cfg["q_dcm"]), 0.0, 5000.0)
            except Exception:
                pass
        if "tsub" in cfg:
            try:
                self._write_float(self.pv_tsub, float(cfg["tsub"]))
            except Exception:
                pass
        # Derived runtime params (used by bridge only)
        for k, lo, hi in (
            ("alarm_t_high", 0.0, 1000.0),
            ("pump_freq_on", 0.0, 80.0),
            ("pump_freq_off", 0.0, 80.0),
            ("heater_power_on", 0.0, 100.0),
            ("heater_power_off", 0.0, 100.0),
        ):
            if k in cfg:
                try:
                    setattr(self, k, clamp(float(cfg[k]), lo, hi))
                except Exception:
                    pass
        # Level dynamics
        if "lt19_fill_lps" in cfg:
            try:
                self.sim.fill_Lps_v19 = clamp(float(cfg["lt19_fill_lps"]), 0.0, 10.0)
            except Exception:
                pass
        if "lt23_refill_rate_pctps" in cfg:
            try:
                self.sim.refill_rate_pctps = clamp(float(cfg["lt23_refill_rate_pctps"]), 0.0, 100.0)
            except Exception:
                pass
        if "lt23_drain_rate_pctps" in cfg:
            try:
                self.sim.drain_rate_pctps = clamp(float(cfg["lt23_drain_rate_pctps"]), 0.0, 100.0)
            except Exception:
                pass
        # SubTank consumption sensitivity
        if "lt19_base_cons_lps" in cfg:
            try:
                self.sim.base_cons_Lps = clamp(float(cfg["lt19_base_cons_lps"]), 0.0, 1.0)
            except Exception:
                pass
        if "lt19_power_cons_lps_perW" in cfg:
            try:
                self.sim.cons_coeff_Lps_perW = clamp(float(cfg["lt19_power_cons_lps_perW"]), 0.0, 0.01)
            except Exception:
                pass
        if "lt19_vent_gamma_lps_perLpm" in cfg:
            try:
                self.sim.gamma_vent_Lps_per_Lpm = clamp(float(cfg["lt19_vent_gamma_lps_perLpm"]), 0.0, 0.5)
            except Exception:
                pass
        # Initial levels
        if "lt19_init_pct" in cfg:
            try:
                v = clamp(float(cfg["lt19_init_pct"]), 0.0, 100.0)
                self.sim.state.LT19 = v
                self._write_float(self.pv_lt19, v)
            except Exception:
                pass
        if "lt23_init_pct" in cfg:
            try:
                v = clamp(float(cfg["lt23_init_pct"]), 0.0, 100.0)
                self.sim.state.LT23 = v
                self._write_float(self.pv_lt23, v)
            except Exception:
                pass
        # HV tank consumption sensitivity
        if "lt23_base_cons_pctps" in cfg:
            try:
                self.sim.hv_base_cons_pctps = clamp(float(cfg["lt23_base_cons_pctps"]), 0.0, 100.0)
            except Exception:
                pass
        if "lt23_power_cons_pctps_perW" in cfg:
            try:
                self.sim.hv_power_cons_pctps_perW = clamp(float(cfg["lt23_power_cons_pctps_perW"]), 0.0, 1.0)
            except Exception:
                pass
        if "lt23_heater_cons_pctps_max" in cfg:
            try:
                self.sim.hv_heater_cons_pctps_max = clamp(float(cfg["lt23_heater_cons_pctps_max"]), 0.0, 100.0)
            except Exception:
                pass
        if "lt23_vent_gamma_pctps" in cfg:
            try:
                self.sim.hv_vent_gamma_pctps = clamp(float(cfg["lt23_vent_gamma_pctps"]), 0.0, 100.0)
            except Exception:
                pass


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    bridge = PVBridge(
        args.dt,
        args.q_dcm,
        verbose=args.verbose,
        init_config=args.init_config,
        log_interval=args.log_interval,
    )
    try:
        bridge.loop()
    except KeyboardInterrupt:
        print("\n[pv_bridge] stopped by user")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
