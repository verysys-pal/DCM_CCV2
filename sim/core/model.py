from __future__ import annotations

"""
Minimal thermal-capacitance simulator for Cryo Cooler cold head.

This is an intentionally simple first-order model to bootstrap
IOC/GUI integration. It will be refined as requirements evolve.
"""

from dataclasses import dataclass, field


@dataclass
class CryoPlant:
    """Three-node thermal model (cold head, T5, T6) with a simple controller.

    Cold head (tch) is controlled to a setpoint via a PI controller producing
    cooling power `qcool` (0..qmax). T5 (LN2 inlet) tracks the cold head via a
    heat-exchanger time constant. T6 (LN2 outlet) is driven above T5 by the
    DCM heat load q_dcm through an effective thermal conductance k_dcm.

    Cold head dynamics (first order):
        dTch/dt = (Tamb - Tch)/tau_env + (Qload - Qcool)/cap

    LN2 nodes (first order relaxation to targets):
        T5 -> Tch        with tau = tau_ln2_in
        T6 -> T5+Qdcm/k  with tau = tau_ln2_out

    Units are abstract; treat temperatures in Kelvin-equivalent scale.
    """

    # Cold head (primary) dynamics
    cap: float = 800.0          # 유효 열용량
        # cap=800이면 −2000/800 ≈ −2.5 K/s 수준의 “이론적 최대” 냉각 속도 구현
    tau_env: float = 120.0      # 환경으로 새는 열 경로의 시간상수(초)
    tamb: float = 300.0         # ambient temperature
    tch: float = 77.3
    # LN2 loop nodes
    t5: float = 300.0
    t6: float = 300.0
    tau_ln2_in: float = 10.0    # LN2 inlet (T5) time constant
    tau_ln2_out: float = 10.0   # LN2 outlet (T6) time constant
    # Subcooler (acts as minimum limit for LN2 loop)
    tsub: float = 77.3
    # Controller
    k_p: float = 10.0           # Tch−Tsp 오차를 냉각출력(W)으로 매핑
    k_i: float = 0.2            # 정상상태 오차 제거
    qmax: float = 2000.0        # max cooling power
    _ei: float = field(default=0.0, init=False, repr=False)
    # DCM load placed between T5 (inlet) and T6 (outlet)
    q_dcm: float = 100.0  # W (fixed per requirement)
    k_dcm: float = 20.0   # W/K base conductance (flow=0)
    k_flow: float = 1.0   # W/K per (L/min) of FT18 (conductance increases with flow)
    flow_ft18: float = 5.0  # L/min (can be updated externally)

    def reset(self, t0: float | None = None) -> None:
        if t0 is None:
            t0 = self.tamb
        base = float(t0)
        self.tch = base
        self.t5 = base
        self.t6 = base
        self._ei = 0.0

    # Backwards-compat for code that referenced .t
    @property
    def t(self) -> float:  # pragma: no cover - compatibility shim
        return self.tch

    def _controller(self, tsp: float, dt: float) -> float:
        """PI controller mapping error to cooling power with anti-windup."""
        err = self.tch - tsp
        ei = self._ei + err * dt
        u = self.k_p * err + self.k_i * ei
        u_sat = max(0.0, min(self.qmax, u))
        if self.k_i > 0:
            self._ei = ei + (u_sat - u) / self.k_i
        else:
            self._ei = ei
        return u_sat

    def step(self, tsp: float, qload: float, dt: float) -> float:
        # Cold head update
        qcool = self._controller(tsp, dt)
        dTch = (self.tamb - self.tch) / self.tau_env + (qload - qcool) / self.cap
        self.tch += dTch * dt

        # LN2 inlet (T5) relaxes towards subcooler temperature via HX time constant
        t5_target = self.tsub
        self.t5 += (t5_target - self.t5) * (dt / max(1e-6, self.tau_ln2_in))

        # LN2 outlet (T6) rises above T5 due to DCM heat load.
        # Effective conductance increases with FT18 flow, reducing ΔT.
        k_eff = self.k_dcm + self.k_flow * max(0.0, float(self.flow_ft18))
        deltaT_target = self.q_dcm / max(1e-6, k_eff)
        t6_target = self.t5 + deltaT_target
        self.t6 += (t6_target - self.t6) * (dt / max(1e-6, self.tau_ln2_out))

        # Enforce physical constraint: T5/T6 cannot go below subcooler temperature
        if self.t5 < self.tsub:
            self.t5 = self.tsub
        if self.t6 < self.tsub:
            self.t6 = self.tsub

        return self.tch
