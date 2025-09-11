#!/usr/bin/env python3
"""
Simple scenario runner using pyepics.

Plan YAML example:

steps:
  - set: { pv: BL:DCM:CRYO:TEMP:SETPOINT, value: 80 }
  - set: { pv: BL:DCM:CRYO:CMD:MAIN, value: 1 }
  - wait: { pv: BL:DCM:CRYO:STATE:MAIN, equals: 2, timeout: 60 }
  - wait: { pv: BL:DCM:CRYO:STATE:MAIN, equals: 3, timeout: 600 }
  - assert: { pv: BL:DCM:CRYO:TEMP:T5, max: 85 }
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Dict

# Ensure project root on path when run directly
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    import yaml
except Exception:
    print("Please `pip install pyyaml` to use the runner.")
    sys.exit(2)

try:
    from epics import PV
except Exception:
    print("Please `pip install pyepics` to use the runner.")
    sys.exit(2)


def load_plan(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def pv_get(pvname: str, timeout: float = 1.0) -> float:
    pv = PV(pvname, auto_monitor=True)
    v = pv.get(timeout=timeout)
    if v is None:
        raise RuntimeError(f"PV get timeout: {pvname}")
    return float(v)


def pv_put(pvname: str, value: float) -> None:
    pv = PV(pvname)
    ok = pv.put(value, wait=False)
    if not ok:
        raise RuntimeError(f"PV put failed: {pvname}")


def run_step(step: Dict[str, Any]) -> None:
    if "set" in step:
        s = step["set"]
        pv_put(s["pv"], s["value"])
        return
    if "sleep" in step:
        secs = float(step["sleep"]) or 0.0
        time.sleep(secs)
        return
    if "wait" in step:
        w = step["wait"]
        pvname = w["pv"]
        timeout = float(w.get("timeout", 10.0))
        t0 = time.monotonic()
        while True:
            val = pv_get(pvname, timeout=1.0)
            ok = True
            if "equals" in w:
                ok = ok and (int(val) == int(w["equals"]))
            if "min" in w:
                ok = ok and (val >= float(w["min"]))
            if "max" in w:
                ok = ok and (val <= float(w["max"]))
            if ok:
                return
            if (time.monotonic() - t0) > timeout:
                raise TimeoutError(f"wait timeout for {pvname}, last={val}")
            time.sleep(0.2)
        return
    if "assert" in step:
        a = step["assert"]
        val = pv_get(a["pv"], timeout=1.0)
        if "equals" in a:
            assert int(val) == int(a["equals"]), f"assert equals failed: {val} != {a['equals']}"
        if "min" in a:
            assert val >= float(a["min"]), f"assert min failed: {val} < {a['min']}"
        if "max" in a:
            assert val <= float(a["max"]), f"assert max failed: {val} > {a['max']}"
        return
    raise ValueError(f"Unknown step: {step}")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Run EPICS scenario plan")
    ap.add_argument("--plan", required=True, help="YAML plan path")
    args = ap.parse_args(argv)
    plan = load_plan(args.plan)

    steps = plan.get("steps") or []
    print(f"[runner] steps={len(steps)} plan={args.plan}")
    for i, step in enumerate(steps, 1):
        print(f"[runner] step {i}: {list(step.keys())[0]}")
        run_step(step)
    print("[runner] completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
