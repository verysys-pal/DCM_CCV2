import math
import pytest

from sim.core.model import CryoPlant


def run_to_seconds(model: CryoPlant, tsp: float, qload: float, dt: float, seconds: float) -> float:
    steps = int(seconds / dt)
    T = model.t
    for _ in range(steps):
        T = model.step(tsp, qload, dt)
    return T


@pytest.mark.parametrize("tsp,qload", [
    (80.0, 50.0),
    (100.0, 20.0),
    (60.0, 80.0),
])
def test_converges_within_band(tsp: float, qload: float):
    model = CryoPlant()
    model.reset()
    # Simulate longer horizon to allow settling
    final_T = run_to_seconds(model, tsp, qload, dt=0.1, seconds=600.0)
    assert abs(final_T - tsp) < 10.0


def test_temperature_trends_towards_setpoint():
    model = CryoPlant()
    model.reset(300.0)
    tsp = 80.0
    qload = 50.0
    dt = 0.1
    T_prev = model.t
    # Over early horizon, temperature should move downwards (towards tsp)
    for _ in range(50):  # 5 seconds
        T = model.step(tsp, qload, dt)
        assert T <= T_prev + 1e-6  # non-increasing
        T_prev = T


def test_stability_no_divergence():
    model = CryoPlant()
    model.reset(250.0)
    tsp = 200.0
    qload = 100.0
    dt = 0.05
    T = run_to_seconds(model, tsp, qload, dt, seconds=300.0)
    assert math.isfinite(T)
    # Should not overshoot too far below setpoint
    assert T > (tsp - 30.0)
