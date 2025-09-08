from __future__ import annotations

"""
Minimal thermal-capacitance simulator for Cryo Cooler cold head.

This is an intentionally simple first-order model to bootstrap
IOC/GUI integration. It will be refined as requirements evolve.
"""

from dataclasses import dataclass, field


@dataclass
class CryoPlant:
    """Simple first-order thermal model with a naive controller.

    dT/dt = (Tamb - T)/tau_env + (Qload - Qcool)/cap

    Units are abstracted; treat temperatures in Kelvin-equivalent scale.
    """

    cap: float = 800.0  # effective thermal capacity
    tau_env: float = 120.0  # environmental time constant (s)
    tamb: float = 300.0  # ambient temperature
    t: float = 300.0  # current temperature
    k_p: float = 10.0
    k_i: float = 0.2
    qmax: float = 2000.0
    _ei: float = field(default=0.0, init=False, repr=False)

    def reset(self, t0: float | None = None) -> None:
        if t0 is None:
            t0 = self.tamb
        self.t = float(t0)
        self._ei = 0.0

    def _controller(self, tsp: float, dt: float) -> float:
        """PI controller mapping error to cooling power with anti-windup.

        Returns cooling power Qcool (arbitrary unit). Saturated in [0, qmax].
        """
        err = self.t - tsp
        # Integrate error
        ei = self._ei + err * dt
        u = self.k_p * err + self.k_i * ei
        # Saturate
        u_sat = max(0.0, min(self.qmax, u))
        # Anti-windup: if saturated, don't accumulate integral further in the saturating direction
        if self.k_i > 0:
            self._ei = ei + (u_sat - u) / self.k_i
        else:
            self._ei = ei
        return u_sat

    def step(self, tsp: float, qload: float, dt: float) -> float:
        qcool = self._controller(tsp, dt)
        dT = (self.tamb - self.t) / self.tau_env + (qload - qcool) / self.cap
        self.t += dT * dt
        return self.t
