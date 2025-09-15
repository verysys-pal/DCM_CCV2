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
    """Controls staged operating sequences by driving `sim.controls`.

    The plant (`sim`) remains responsible only for physics updates.

    External control API (used by OperatingLogic and bridges):
    - start_cool_down(), start_warm_up(), start_refill_hv(), start_refill_subcooler()
    - stop(), off(), hold(), resume()
    - update(dt): advance stages and actuate controls
    """

    def __init__(self, sim) -> None:
        self.sim = sim
        self.auto: AutoKind = AutoKind.NONE
        self.paused: bool = False
        self.stage: int = 0
        self._t = _Timers()

    # --- External control API ---
    def start_cool_down(self) -> None:
        self.auto = AutoKind.COOL_DOWN
        self.stage = 0
        self._t = _Timers()

    def start_warm_up(self) -> None:
        self.auto = AutoKind.WARM_UP
        self.stage = 0
        self._t = _Timers()

    def start_refill_hv(self) -> None:
        self.auto = AutoKind.REFILL_HV
        self.stage = 0
        self._t = _Timers()

    def start_refill_subcooler(self) -> None:
        self.auto = AutoKind.REFILL_SUB
        self.stage = 0
        self._t = _Timers()

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
        """Advance stage machine and drive controls. Call before plant.step()."""
        if self.paused or self.auto == AutoKind.NONE:
            return
        u, s = self.sim.controls, self.sim.state
        self._t.stage_timer += dt

        if self.auto == AutoKind.COOL_DOWN:
            # Overlay HV refill when LT23 is low
            if s.LT23 < 25.0:
                u.V15 = True
                # Suspend pressure control while refilling low LT23
                if self.stage >= 5:
                    u.press_ctrl_on = False
                self._t.pulse_timer += dt
                if self._t.pulse_timer >= 1.0:
                    self._t.pulse_state = not self._t.pulse_state
                    self._t.pulse_timer = 0.0
                u.V20 = 1.0 if self._t.pulse_state else 0.0
            elif u.V15 and s.LT23 >= 45.0:
                u.V15 = False
                u.V20 = 0.0
                if self.stage >= 5:
                    u.press_ctrl_on = True

            if self.stage == 0:
                u.V10 = 0.6
                u.pump_hz = max(u.pump_hz, 30.0)
                u.V17 = 0.0
                u.V20 = 0.0
                u.V21 = False
                u.V9 = False
                u.V11 = False
                u.V19 = True
                if self._t.stage_timer >= 3.0:
                    u.V19 = False
                    self.stage += 1
                    self._t.stage_timer = 0.0
            elif self.stage == 1:
                u.press_ctrl_on = False
                u.V15 = True
                self._t.pulse_timer += dt
                if self._t.pulse_timer >= 1.0:
                    self._t.pulse_state = not self._t.pulse_state
                    self._t.pulse_timer = 0.0
                u.V20 = 1.0 if self._t.pulse_state else 0.0
                if s.LT23 >= 90.0:
                    u.V15 = False
                    u.V20 = 0.0
                    self.stage += 1
                    self._t.stage_timer = 0.0
            elif self.stage == 2:
                u.V9 = True
                u.V17 = 1.0
                if s.T6 < 200.0:
                    self.stage += 1
                    self._t.stage_timer = 0.0
            elif self.stage == 3:
                u.V17 = 0.35
                u.V11 = True
                if s.T6 < 90.0:
                    self.stage += 1
                    self._t.stage_timer = 0.0
            elif self.stage == 4:
                u.V17 = 0.0
                if s.T6 < 82.0:
                    self.stage += 1
                    self._t.stage_timer = 0.0
            elif self.stage == 5:
                u.press_ctrl_on = True
                u.press_sp_bar = max(u.press_sp_bar, 2.0)
                if s.LT23 > 30.0:
                    u.V17 = 0.3
                elif s.LT23 < 25.0:
                    u.press_ctrl_on = False
                    u.V15 = True
                    self._t.pulse_timer += dt
                    if self._t.pulse_timer >= 1.0:
                        self._t.pulse_state = not self._t.pulse_state
                        self._t.pulse_timer = 0.0
                    u.V20 = 1.0 if self._t.pulse_state else 0.0
                    if s.LT23 >= 45.0:
                        u.V15 = False
                        u.V20 = 0.0
                        u.press_ctrl_on = True
                else:
                    u.V17 = 0.0
                    # Use plant's readiness check
                    if getattr(self.sim, '_is_ready', None) and self.sim._is_ready():
                        self.sim.state.mode = 'READY'
                        self.auto = AutoKind.NONE
                        self.stage = 0
                        self._t = _Timers()

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
                    self._t.stage_timer = 0.0
            elif self.stage == 1:
                # Let it warm towards ambient, then finish
                if s.T5 >= (getattr(self.sim, 'ambK', 280.0) - 2.0):
                    self.auto = AutoKind.NONE
                    self.stage = 0
                    self._t = _Timers()

        elif self.auto == AutoKind.REFILL_HV:
            if self.stage == 0:
                u.V15 = True
                u.press_ctrl_on = False
                self._t.pulse_timer += dt
                if self._t.pulse_timer >= 1.0:
                    self._t.pulse_state = not self._t.pulse_state
                    self._t.pulse_timer = 0.0
                u.V20 = 1.0 if self._t.pulse_state else 0.0
                if s.LT23 >= 90.0:
                    self.stage += 1
                    self._t.stage_timer = 0.0
            elif self.stage == 1:
                u.V15 = False
                u.V20 = 0.0
                self.auto = AutoKind.NONE
                self.stage = 0
                self._t = _Timers()

        elif self.auto == AutoKind.REFILL_SUB:
            if self.stage == 0:
                u.V19 = True
                if s.LT19 >= 90.0:
                    self.stage += 1
                    self._t.stage_timer = 0.0
            elif self.stage == 1:
                u.V19 = False
                self.auto = AutoKind.NONE
                self.stage = 0
                self._t = _Timers()

        # LT19 auto refill hysteresis during any auto sequence
        if self.auto != AutoKind.NONE:
            if s.LT19 >= 90.0:
                u.V19 = False
            if s.LT19 < 80.0 and not self.paused:
                u.V19 = True
