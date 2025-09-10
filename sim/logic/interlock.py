from __future__ import annotations

"""
Interlock evaluation logic for the simulator.

Optional module: when configured, pv_bridge uses this to set safety/interlock
and alarm severity PVs based on thresholds.
"""

from dataclasses import dataclass
from typing import Tuple, Dict


@dataclass
class InterlockThresholds:
    t_high_minor: float = 250.0
    t_high_major: float = 300.0
    lt19_low: float = 10.0
    lt23_low: float = 10.0
    flow_ft18_min: float = 0.5


class InterlockLogic:
    def __init__(self, th: InterlockThresholds) -> None:
        self.th = th

    @classmethod
    def from_yaml(cls, data: dict | None) -> "InterlockLogic":
        d = data or {}
        th = InterlockThresholds(
            t_high_minor=float(d.get("t_high_minor", 250.0)),
            t_high_major=float(d.get("t_high_major", 300.0)),
            lt19_low=float(d.get("lt19_low", 10.0)),
            lt23_low=float(d.get("lt23_low", 10.0)),
            flow_ft18_min=float(d.get("flow_ft18_min", 0.5)),
        )
        return cls(th)

    def evaluate(self, signals: Dict[str, float]) -> Tuple[int, bool]:
        """Return (severity, safety_interlock) based on thresholds.

        severity: 0=NO_ALARM, 1=MINOR, 2=MAJOR
        safety_interlock: True triggers safety stop logic upstream.
        """
        sev = 0
        safe = False
        tch = float(signals.get("tch", 0.0))
        lt19 = float(signals.get("lt19", 100.0))
        lt23 = float(signals.get("lt23", 100.0))
        ft18 = float(signals.get("ft18", 10.0))

        # Temperature high
        if tch >= self.th.t_high_major:
            sev = max(sev, 2)
            safe = True
        elif tch >= self.th.t_high_minor:
            sev = max(sev, 1)

        # Low levels
        if lt19 <= self.th.lt19_low or lt23 <= self.th.lt23_low:
            sev = max(sev, 1)

        # Flow too low
        if ft18 < self.th.flow_ft18_min:
            sev = max(sev, 1)
            # If flow collapsed near ambient we could trip; keep simple

        return sev, safe
