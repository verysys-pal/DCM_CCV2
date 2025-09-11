# dcm_cryo_cooler_sim.py
# Physics-inspired discrete-time simulator for a Bruker-type DCM Cryo-Cooler.
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

@dataclass
class Controls:
    V9: bool
    V11: bool
    V19: bool
    V15: bool
    V21: bool
    V10: float
    V17: float
    V20: float
    pump_hz: float
    press_ctrl_on: bool
    press_sp_bar: float
    _heater_u: float = 0.0

@dataclass
class State:
    T5: float
    T6: float
    PT1: float
    PT3: float
    LT19: float
    LT23: float
    FT18: float = 0.0
    ready: bool = False
    mode: str = 'IDLE'

class AutoKind(Enum):
    NONE = 0
    COOL_DOWN = auto()
    WARM_UP = auto()
    REFILL_HV = auto()

class CryoCoolerSim:
    Q80 = 15.0
    rho = 800.0
    cp = 2000.0
    ambK = 280.0
    delta_subcool = 6.0
    k_tau = 120.0
    tau_warm0 = 180.0
    Kh = 0.5
    Kc = 0.4
    kv17 = 0.5
    kv20 = 0.5
    kv21 = 0.8
    leak = 0.02
    base_cons_Lps = 3.0/3600.0
    cons_coeff_Lps_perW = 0.023/3600.0
    gamma_vent_Lps_per_Lpm = 0.004/60.0
    Vsub_L = 200.0
    Vhv_L = 20.0
    PSV_open_bar = 5.0
    max_bar = 5.0

    def __init__(self, state: State, controls: Controls):
        self.state = state
        self.controls = controls
        self.auto: AutoKind = AutoKind.NONE
        self.stage: int = 0
        self.stage_timer: float = 0.0
        self._pulse_timer: float = 0.0
        self._pulse_state: bool = False

    @staticmethod
    def clamp(v, lo, hi):
        return max(lo, min(hi, v))

    def T_boil(self, pt_bar: float) -> float:
        return 77.0 + 3.8*self.clamp(pt_bar, 0.0, 5.0)

    def _flow_base(self) -> float:
        u = self.controls
        v10 = self.clamp(u.V10, 0.0, 1.0)
        return self.Q80*(self.clamp(u.pump_hz,0.0,80.0)/80.0)*(0.4 + 0.6*v10)

    def flow_loop_and_eff(self):
        u = self.controls
        base = self._flow_base()
        Q_loop = base if (u.V9 and u.V11) else 0.0
        Q_eff  = base if (u.V9 and (u.V11 or u.V17>0.01)) else 0.0
        return Q_loop, Q_eff

    def _rsc(self) -> float:
        return self.clamp(self.state.LT19/40.0, 0.0, 1.0)

    def auto_cool_down(self):
        self.auto = AutoKind.COOL_DOWN
        self.stage = 0
        self.stage_timer = 0.0
        self.state.mode = 'COOLING'

    def auto_warm_up(self):
        self.auto = AutoKind.WARM_UP
        self.stage = 0
        self.stage_timer = 0.0
        self.state.mode = 'WARMUP'

    def auto_refill_hv(self):
        self.auto = AutoKind.REFILL_HV
        self.stage = 0
        self.stage_timer = 0.0

    def stop(self):
        u = self.controls
        u.V9 = False; u.V11 = False; u.V10 = 1.0
        u.pump_hz = 0.0; u.press_ctrl_on = False
        self.state.ready = False
        self.state.mode = 'STOP'

    def off(self):
        self.stop()
        u = self.controls
        u.V17 = 1.0; u.V20 = 1.0
        self.state.mode = 'OFF'

    def _update_auto(self, dt: float):
        u, s = self.controls, self.state
        if self.auto == AutoKind.NONE:
            return
        self.stage_timer += dt
        if self.auto == AutoKind.COOL_DOWN:
            if self.stage == 0:
                u.V10 = 0.6; u.pump_hz = max(u.pump_hz, 30.0)
                u.V17 = 0.0; u.V20 = 0.0; u.V21 = False
                u.V9 = False; u.V11 = False
                u.V19 = True
                if self.stage_timer >= 60.0:
                    u.V19 = False
                    self.stage += 1; self.stage_timer = 0.0
            elif self.stage == 1:
                u.press_ctrl_on = False
                u.V15 = True
                self._pulse_timer += dt
                if self._pulse_timer >= 1.0:
                    self._pulse_state = not self._pulse_state
                    self._pulse_timer = 0.0
                u.V20 = 1.0 if self._pulse_state else 0.0
                if s.LT23 >= 90.0:
                    u.V15 = False; u.V20 = 0.0
                    self.stage += 1; self.stage_timer = 0.0
            elif self.stage == 2:
                u.V9 = True; u.V17 = 1.0
                if s.T6 < 200.0:
                    self.stage += 1; self.stage_timer = 0.0
            elif self.stage == 3:
                u.V17 = 0.35; u.V11 = True
                if s.T6 < 90.0:
                    self.stage += 1; self.stage_timer = 0.0
            elif self.stage == 4:
                u.V17 = 0.0
                if s.T6 < 82.0:
                    self.stage += 1; self.stage_timer = 0.0
            elif self.stage == 5:
                u.press_ctrl_on = True
                u.press_sp_bar = max(u.press_sp_bar, 2.0)
                if s.LT23 > 30.0:
                    u.V17 = 0.3
                elif s.LT23 < 25.0:
                    u.press_ctrl_on = False
                    u.V15 = True
                    self._pulse_timer += dt
                    if self._pulse_timer >= 1.0:
                        self._pulse_state = not self._pulse_state
                        self._pulse_timer = 0.0
                    u.V20 = 1.0 if self._pulse_state else 0.0
                    if s.LT23 >= 45.0:
                        u.V15 = False; u.V20 = 0.0; u.press_ctrl_on = True
                else:
                    u.V17 = 0.0
                    if self._is_ready():
                        self.state.mode = 'READY'
                        self.auto = AutoKind.NONE
                        self.stage = 0; self.stage_timer = 0.0
        elif self.auto == AutoKind.WARM_UP:
            if self.stage == 0:
                u.V9 = False; u.V11 = False; u.V10 = 1.0
                u.V17 = 0.4; u.pump_hz = max(u.pump_hz, 30.0)
                u.press_ctrl_on = False
                if s.PT1 < 1.0:
                    self.stage += 1; self.stage_timer = 0.0
            elif self.stage == 1:
                u.V21 = True
                if s.T6 >= 280.0:
                    u.V21 = False; u.V17 = 0.0
                    self.auto = AutoKind.NONE; self.stage = 0
                    self.state.mode = 'IDLE'
        elif self.auto == AutoKind.REFILL_HV:
            if self.stage == 0:
                u.press_ctrl_on = False
                u.V15 = True
                self.stage += 1; self.stage_timer = 0.0
            elif self.stage == 1:
                self._pulse_timer += dt
                if self._pulse_timer >= 1.0:
                    self._pulse_state = not self._pulse_state
                    self._pulse_timer = 0.0
                u.V20 = 1.0 if self._pulse_state else 0.0
                if self.state.LT23 >= 25.0:
                    u.V15 = False; u.V20 = 0.0; u.press_ctrl_on = True
                    self.auto = AutoKind.NONE; self.stage = 0

    def _is_ready(self) -> bool:
        s, u = self.state, self.controls
        ready = (
            u.V9 and u.V11 and u.pump_hz > 0.0 and u.press_ctrl_on
            and abs(s.PT3 - u.press_sp_bar) < 0.05
            and abs(s.PT1 - u.press_sp_bar) < 0.1
            and s.LT23 > 20.0 and s.T5 < 80.0
        )
        return ready

    def _update_pressures(self, dt: float):
        s, u = self.state, self.controls
        if u.press_ctrl_on:
            err = u.press_sp_bar - s.PT3
            u._heater_u = self.clamp(u._heater_u + 0.8*err*dt + 0.02*err, 0.0, 1.0)
        else:
            u._heater_u = 0.0
        dPT3 = self.Kh*u._heater_u - self.kv20*u.V20*max(s.PT3-1.0, 0.0) - self.leak*max(s.PT3-1.0, 0.0)
        s.PT3 = self.clamp(s.PT3 + dPT3*dt, 0.0, self.max_bar)
        dPT1 = self.Kc*(s.PT3 - s.PT1) - self.kv17*u.V17*max(s.PT1-1.0, 0.0) - self.kv21*(1.0 if u.V21 else 0.0)*max(s.PT1-1.0, 0.0)
        s.PT1 = self.clamp(s.PT1 + dPT1*dt, 0.0, self.max_bar)
        s.PT1 = min(s.PT1, self.PSV_open_bar - 0.5)
        s.PT3 = min(s.PT3, self.PSV_open_bar - 0.5)

    def _update_temperatures(self, dt: float, power_W: float):
        s, u = self.state, self.controls
        Q_loop, Q_eff = self.flow_loop_and_eff()
        s.FT18 = Q_loop
        Rsc = self._rsc()
        T_supply_star = max(77.0, self.T_boil(s.PT1) - self.delta_subcool * Rsc)
        if u.V21 and s.PT1 <= 1.05:
            tau = self.tau_warm0/(1.0 + 0.3*Rsc + (0.3 if u.pump_hz>0 else 0.0))
            s.T5 += (self.ambK - s.T5)/tau * dt
        elif Q_eff > 1e-6:
            tau = self.k_tau/max(Q_eff, 1e-6)
            s.T5 += (T_supply_star - s.T5)/tau * dt
        else:
            tau_iso = 1200.0
            s.T5 += (self.ambK - s.T5)/tau_iso * dt
        mdot = self.rho*(Q_eff/60.0)*1e-3
        dT_load = (power_W/(mdot*self.cp)) if mdot>1e-6 else 0.0
        s.T6 = s.T5 + dT_load

    def _update_levels(self, dt: float, power_W: float):
        s, u = self.state, self.controls
        Q_loop, Q_eff = self.flow_loop_and_eff()
        cons_Lps = self.base_cons_Lps + self.cons_coeff_Lps_perW*power_W + self.gamma_vent_Lps_per_Lpm*max(Q_eff - Q_loop, 0.0)*60.0
        fill_Lps = 1.0/60.0 if u.V19 else 0.0
        dLT19 = (fill_Lps - cons_Lps)/self.Vsub_L * 100.0
        s.LT19 = self.clamp(s.LT19 + dLT19*dt, 0.0, 100.0)
        refill_rate_pctps = 0.5/60.0
        drain_rate_pctps  = 0.3/60.0
        if u.V15:
            s.LT23 = self.clamp(s.LT23 + refill_rate_pctps*dt, 0.0, 100.0)
        s.LT23 = self.clamp(s.LT23 - drain_rate_pctps*u.V17*dt, 0.0, 100.0)
        if s.LT19 < 30.0:
            u.V19 = True
        if s.LT19 > 40.0:
            u.V19 = False
        if s.LT23 < 5.0:
            self.stop()

    def step(self, dt: float = 1.0, power_W: float = 0.0):
        self._update_auto(dt)
        self._update_pressures(dt)
        self._update_temperatures(dt, power_W)
        self._update_levels(dt, power_W)
        self.state.ready = self._is_ready()
        return self.state

if __name__ == '__main__':
    s = State(T5=280.0, T6=280.0, PT1=1.0, PT3=1.0, LT19=40.0, LT23=30.0)
    u = Controls(V9=False, V11=False, V19=False, V15=False, V21=False,
                 V10=0.6, V17=0.0, V20=0.0, pump_hz=0.0, press_ctrl_on=False, press_sp_bar=2.0)
    sim = CryoCoolerSim(s, u)
    sim.auto_cool_down()
    for t in range(0, 7200):
        sim.step(dt=1.0, power_W=300.0)
        if sim.state.ready:
            break
    print(f't={t}s, mode={sim.state.mode}, ready={sim.state.ready}, '
          f'T5={sim.state.T5:.1f}K, T6={sim.state.T6:.1f}K, '
          f'PT1={sim.state.PT1:.2f}bar, PT3={sim.state.PT3:.2f}bar, '
          f'LT19={sim.state.LT19:.1f}%, LT23={sim.state.LT23:.1f}%, '
          f'FT18={sim.state.FT18:.1f} L/min')
