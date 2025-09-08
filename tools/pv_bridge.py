#!/usr/bin/env python3
"""
EPICS PV bridge for the CryoPlant simulator.

Reads setpoint/commands from PVs and publishes simulated temperatures and state.
Requires: pyepics

Usage:
  python tools/pv_bridge.py --dt 0.1 --qload 50

PVs used (must exist in IOC DB):
  - BL:DCM:CRYO:TEMP:SETPOINT (ao)
  - BL:DCM:CRYO:TEMP:COLDHEAD (ai)
  - BL:DCM:CRYO:TEMP:T5 (ai)
  - BL:DCM:CRYO:STATE:MAIN (mbbi)
  - BL:DCM:CRYO:CMD:MAIN (mbbo)
"""

from __future__ import annotations

import argparse
import sys
import time
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
except Exception as exc:  # pragma: no cover - import diagnostic
    print("[pv_bridge] pyepics import failed. Please `pip install pyepics`.")
    print(f"reason: {exc}")
    sys.exit(2)

from sim.core.model import CryoPlant


PV_STATE = "BL:DCM:CRYO:STATE:MAIN"
PV_CMD = "BL:DCM:CRYO:CMD:MAIN"
PV_TSP = "BL:DCM:CRYO:TEMP:SETPOINT"
PV_TCH = "BL:DCM:CRYO:TEMP:COLDHEAD"
PV_T5 = "BL:DCM:CRYO:TEMP:T5"
PV_T6 = "BL:DCM:CRYO:TEMP:T6"
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
PV_PUMP_CMD = "BL:DCM:CRYO:PUMP:CMD"
PV_PUMP_RUN = "BL:DCM:CRYO:PUMP:RUNNING"
PV_HEAT_CMD = "BL:DCM:CRYO:HEATER:CMD"
PV_HEAT_RUN = "BL:DCM:CRYO:HEATER:RUNNING"
PV_TIME = "BL:DCM:CRYO:TIME"
PV_LT19 = "BL:DCM:CRYO:LEVEL:LT19"
PV_LT23 = "BL:DCM:CRYO:LEVEL:LT23"
PV_ALARM_MAX = "BL:DCM:CRYO:ALARM:MAX_SEVERITY"


STATE = {
    "OFF": 0,
    "INIT": 1,
    "PRECOOL": 2,
    "RUN": 3,
    "HOLD": 4,
    "WARMUP": 5,
    "SAFE_SHUTDOWN": 6,
    "ALARM": 7,
}

CMD = {
    "NONE": 0,
    "START": 1,
    "STOP": 2,
    "HOLD": 3,
    "RESUME": 4,
    "EMERGENCY_STOP": 5,
    "RESET": 6,
    "WARMUP": 7,
}


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="PV bridge for CryoPlant simulator")
    p.add_argument("--dt", type=float, default=0.1, help="step time (s)")
    p.add_argument("--qload", type=float, default=50.0, help="heat load")
    p.add_argument("--init-seconds", type=float, default=2.0, help="INIT dwell")
    p.add_argument("--precool-band", type=float, default=5.0, help="Run target band (K)")
    p.add_argument("--verbose", action="store_true", help="Print debug info")
    return p.parse_args(argv)


class PVBridge:
    def __init__(self, dt: float, qload: float, init_seconds: float, band: float, verbose: bool = False) -> None:
        self.model = CryoPlant()
        self.model.reset()
        self.dt = dt
        self.qload = qload
        self.band = band
        self.init_seconds = init_seconds
        self.verbose = verbose
        self._rev_state = {v: k for k, v in STATE.items()}

        # EPICS PVs
        self.pv_state = PV(PV_STATE, auto_monitor=True)
        self.pv_cmd = PV(PV_CMD, auto_monitor=True)
        self.pv_tsp = PV(PV_TSP, auto_monitor=True)
        self.pv_tch = PV(PV_TCH, auto_monitor=False)
        self.pv_t5 = PV(PV_T5, auto_monitor=False)
        self.pv_t6 = PV(PV_T6, auto_monitor=False)
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
        self.pv_pump_cmd = PV(PV_PUMP_CMD, auto_monitor=True)
        self.pv_pump_run = PV(PV_PUMP_RUN, auto_monitor=False)
        self.pv_heat_cmd = PV(PV_HEAT_CMD, auto_monitor=True)
        self.pv_heat_run = PV(PV_HEAT_RUN, auto_monitor=False)
        self.pv_time = PV(PV_TIME, auto_monitor=False)
        self.pv_lt19 = PV(PV_LT19, auto_monitor=False)
        self.pv_lt23 = PV(PV_LT23, auto_monitor=False)
        self.pv_alarm_max = PV(PV_ALARM_MAX, auto_monitor=False)
        # Additional process PVs for plotting
        self.pv_pt1 = PV("BL:DCM:CRYO:PRESS:PT1", auto_monitor=False)
        self.pv_pt3 = PV("BL:DCM:CRYO:PRESS:PT3", auto_monitor=False)
        self.pv_ft18 = PV("BL:DCM:CRYO:FLOW:FT18", auto_monitor=False)
        # Historical arrays (waveforms)
        self.pv_hist_time = PV("BL:DCM:CRYO:HIST:TIME", auto_monitor=False)
        self.pv_hist_tch = PV("BL:DCM:CRYO:HIST:TEMP:COLDHEAD", auto_monitor=False)
        self.pv_hist_t5 = PV("BL:DCM:CRYO:HIST:TEMP:T5", auto_monitor=False)
        self.pv_hist_t6 = PV("BL:DCM:CRYO:HIST:TEMP:T6", auto_monitor=False)
        self.pv_hist_pt1 = PV("BL:DCM:CRYO:HIST:PRESS:PT1", auto_monitor=False)
        self.pv_hist_pt3 = PV("BL:DCM:CRYO:HIST:PRESS:PT3", auto_monitor=False)

        # Local state
        self.state: int = STATE["OFF"]
        self.cmd_last: Optional[int] = None
        self.t_init_left = 0.0
        # History buffers (seconds window ~ maxlen * dt)
        self.hist_len = min(2048, max(120, int(600.0 / self.dt)))
        self.hist_time = deque(maxlen=self.hist_len)
        self.hist_tch = deque(maxlen=self.hist_len)
        self.hist_t5 = deque(maxlen=self.hist_len)
        self.hist_t6 = deque(maxlen=self.hist_len)
        self.hist_pt1 = deque(maxlen=self.hist_len)
        self.hist_pt3 = deque(maxlen=self.hist_len)

        # Verify connections
        conns = [
            (PV_STATE, self.pv_state),
            (PV_CMD, self.pv_cmd),
            (PV_TSP, self.pv_tsp),
            (PV_TCH, self.pv_tch),
            (PV_T5, self.pv_t5),
            (PV_T6, self.pv_t6),
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
            (PV_PUMP_CMD, self.pv_pump_cmd),
            (PV_PUMP_RUN, self.pv_pump_run),
            (PV_HEAT_CMD, self.pv_heat_cmd),
            (PV_HEAT_RUN, self.pv_heat_run),
            (PV_TIME, self.pv_time),
            (PV_LT19, self.pv_lt19),
            (PV_LT23, self.pv_lt23),
            (PV_ALARM_MAX, self.pv_alarm_max),
            ("BL:DCM:CRYO:HIST:TIME", self.pv_hist_time),
            ("BL:DCM:CRYO:HIST:TEMP:COLDHEAD", self.pv_hist_tch),
            ("BL:DCM:CRYO:HIST:TEMP:T5", self.pv_hist_t5),
            ("BL:DCM:CRYO:HIST:TEMP:T6", self.pv_hist_t6),
            ("BL:DCM:CRYO:HIST:PRESS:PT1", self.pv_hist_pt1),
            ("BL:DCM:CRYO:HIST:PRESS:PT3", self.pv_hist_pt3),
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

    def _write_int(self, pv: PV, val: int) -> None:
        pv.put(int(val), wait=False)

    def _write_float(self, pv: PV, val: float) -> None:
        pv.put(float(val), wait=False)

    def _state_name(self, s: Optional[int] = None) -> str:
        if s is None:
            s = self.state
        return self._rev_state.get(int(s), f"UNKNOWN({s})")

    def _maybe_transition(self, tsp: float) -> None:
        prev = self.state
        cmd = self.pv_cmd.get() or 0
        if cmd != self.cmd_last:
            self.cmd_last = cmd
            if cmd == CMD["START"]:
                self.state = STATE["INIT"]
                self.t_init_left = self.init_seconds
            elif cmd == CMD["STOP"]:
                self.state = STATE["OFF"]
            elif cmd == CMD["HOLD"]:
                self.state = STATE["HOLD"]
            elif cmd == CMD["RESUME"] and self.state == STATE["HOLD"]:
                self.state = STATE["RUN"]
            elif cmd == CMD["WARMUP"]:
                self.state = STATE["WARMUP"]
            elif cmd == CMD["EMERGENCY_STOP"]:
                self.state = STATE["SAFE_SHUTDOWN"]
            elif cmd == CMD["RESET"] and self.state == STATE["SAFE_SHUTDOWN"]:
                self.state = STATE["OFF"]

        # timed INIT -> PRECOOL
        if self.state == STATE["INIT"]:
            self.t_init_left -= self.dt
            if self.t_init_left <= 0:
                self.state = STATE["PRECOOL"]

        # PRECOOL -> RUN when near setpoint
        if self.state == STATE["PRECOOL"]:
            if (self.model.t) <= (tsp - self.band):
                self.state = STATE["RUN"]

        # WARMUP -> OFF when near ambient
        if self.state == STATE["WARMUP"]:
            if (self.model.t) >= (self.model.tamb - self.band):
                self.state = STATE["OFF"]

        if self.verbose and prev != self.state:
            print(f"[pv_bridge] transition {self._state_name(prev)} -> {self._state_name(self.state)}")

    def loop(self) -> None:
        # Initialize PVs
        tsp = self._read(self.pv_tsp, default=80.0)
        self._write_int(self.pv_state, self.state)
        self.pv_state_text.put(self._state_name(), wait=False)
        self._write_float(self.pv_tch, self.model.t)
        self._write_float(self.pv_t5, self.model.t)
        self._write_float(self.pv_t6, self.model.t)
        self._write_float(self.pv_time, 0.0)
        self._write_float(self.pv_lt19, 50.0)
        self._write_float(self.pv_lt23, 70.0)
        self._write_int(self.pv_alarm_max, 0)
        # Seed history with first sample
        self.hist_time.clear(); self.hist_tch.clear(); self.hist_t5.clear(); self.hist_t6.clear(); self.hist_pt1.clear(); self.hist_pt3.clear()
        self.hist_time.append(0.0)
        self.hist_tch.append(self.model.t)
        self.hist_t5.append(self.model.t)
        self.hist_t6.append(self.model.t)
        self.hist_pt1.append(1.0)
        self.hist_pt3.append(1.0)
        self._publish_history()

        if self.verbose:
            print(f"[pv_bridge] loop start dt={self.dt} qload={self.qload}")
        while True:
            tsp = self._read(self.pv_tsp, default=tsp)
            # Adjust controller target based on state
            effective_tsp = tsp
            if self.state in (STATE["OFF"], STATE["SAFE_SHUTDOWN"], STATE["WARMUP"]):
                # No active cooling during OFF/WARMUP/SAFE; controller will output low Qcool
                effective_tsp = self.model.tamb

            self._maybe_transition(tsp)

            T = self.model.step(effective_tsp, self.qload, self.dt)
            # Publish temperatures and time
            self._write_float(self.pv_tch, T)
            self._write_float(self.pv_t5, T)
            self._write_float(self.pv_t6, T)
            self._write_float(self.pv_time, (self.pv_time.get() or 0.0) + self.dt)

            # Derived signals for trending
            pt1 = max(0.5, 1.5 - 0.002 * (self.model.tamb - T))
            pt3 = max(0.5, 1.2 - 0.0015 * (self.model.tamb - T))
            self._write_float(self.pv_pt1, pt1)
            self._write_float(self.pv_pt3, pt3)
            self._write_float(self.pv_ft18, 5.0)
            # Update history arrays
            tnext = (self.hist_time[-1] if self.hist_time else 0.0) + self.dt
            self.hist_time.append(tnext)
            self.hist_tch.append(T)
            self.hist_t5.append(T)
            self.hist_t6.append(T)
            self.hist_pt1.append(pt1)
            self.hist_pt3.append(pt3)
            self._publish_history()
            self._write_int(self.pv_state, self.state)
            self.pv_state_text.put(self._state_name(), wait=False)

            # Compressor status derived from state
            comp_on = int(self.state in (STATE["INIT"], STATE["PRECOOL"], STATE["RUN"], STATE["HOLD"]))
            self._write_int(self.pv_comp_run, comp_on)
            self.pv_comp_status.put("RUNNING" if comp_on else "OFF", wait=False)

            # Mirror valve statuses from commands
            v9_cmd = int(self.pv_v9_cmd.get() or 0)
            self._write_int(self.pv_v9_status, v9_cmd)
            self._write_int(self.pv_v15_status, int(self.pv_v15_cmd.get() or 0))
            self._write_int(self.pv_v17_status, int(self.pv_v17_cmd.get() or 0))
            self._write_int(self.pv_v19_status, int(self.pv_v19_cmd.get() or 0))

            # Mirror pump/heater RUNNING from CMD
            self._write_int(self.pv_pump_run, int(self.pv_pump_cmd.get() or 0))
            self._write_int(self.pv_heat_run, int(self.pv_heat_cmd.get() or 0))

            # Simple alarm max severity heuristic: 0 normally, 1 if T > 250K
            self._write_int(self.pv_alarm_max, 1 if T > 250 else 0)

            # Done updating derived PVs

            if self.verbose:
                print(
                    f"[pv_bridge] T={T:.2f}K, state={self._state_name()}({self.state}), tsp={tsp:.1f}"
                )

            time.sleep(self.dt)

    def _publish_history(self) -> None:
        try:
            self.pv_hist_time.put(np.asarray(self.hist_time, dtype=float), wait=False)
            self.pv_hist_tch.put(np.asarray(self.hist_tch, dtype=float), wait=False)
            self.pv_hist_t5.put(np.asarray(self.hist_t5, dtype=float), wait=False)
            self.pv_hist_t6.put(np.asarray(self.hist_t6, dtype=float), wait=False)
            self.pv_hist_pt1.put(np.asarray(self.hist_pt1, dtype=float), wait=False)
            self.pv_hist_pt3.put(np.asarray(self.hist_pt3, dtype=float), wait=False)
        except Exception as e:
            if self.verbose:
                print(f"[pv_bridge] history publish error: {e}")


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    bridge = PVBridge(
        args.dt,
        args.qload,
        args.init_seconds,
        args.precool_band,
        verbose=args.verbose,
    )
    try:
        bridge.loop()
    except KeyboardInterrupt:
        print("\n[pv_bridge] stopped by user")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
