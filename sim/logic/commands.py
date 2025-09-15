from __future__ import annotations

"""
Shared enums and mappings used across logic modules.

Includes:
- MainCmd: system-level commands
- ModeCmd: sequence selection modes
- OperState: operating state values aligned with IOC mbbi
- mode_to_auto(): mapping ModeCmd → Sequencer.AutoKind
"""

from enum import IntEnum
from .sequencer import AutoKind


class MainCmd(IntEnum):
    NONE = 0
    START = 1
    STOP = 2
    HOLD = 3
    RESUME = 4
    OFF = 5
    RESET = 6


class ModeCmd(IntEnum):
    NONE = 0
    PURGE = 1
    READY = 2
    COOL_DOWN = 3
    WARM_UP = 4
    REFILL_HETER_ON = 5
    REFILL_HETER_OFF = 6
    REFILL_SBCOL_ON = 7
    REFILL_SBCOL_OFF = 8


class OperState(IntEnum):
    OFF = 0
    INIT = 1
    PRECOOL = 2
    RUN = 3
    HOLD = 4
    WARMUP = 5
    SAFE_SHUTDOWN = 6
    ALARM = 7
    READY = 8


def mode_to_auto(mode: int | ModeCmd) -> AutoKind | None:
    """Translate a ModeCmd value to a Sequencer AutoKind.

    Returns None when the mode is not an automatic sequence selection
    (e.g., READY, PURGE, or explicit *_OFF modes).
    """
    try:
        m = ModeCmd(int(mode))
    except Exception:
        return None

    if m is ModeCmd.COOL_DOWN:
        return AutoKind.COOL_DOWN
    if m is ModeCmd.WARM_UP:
        return AutoKind.WARM_UP
    if m is ModeCmd.REFILL_HETER_ON:
        return AutoKind.REFILL_HV
    if m is ModeCmd.REFILL_SBCOL_ON:
        return AutoKind.REFILL_SUB
    return None
