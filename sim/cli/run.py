#!/usr/bin/env python3
"""
Lightweight CLI loop to run the CryoPlant model and print temperature.

Example:
  python -m sim.cli.run --tsp 80 --qload 50 --dt 0.1 --seconds 30
"""

import argparse
import sys
import time
from sim.core.model import CryoPlant


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run CryoPlant simulator loop")
    p.add_argument("--tsp", type=float, default=80.0, help="Temperature setpoint")
    p.add_argument("--qload", type=float, default=50.0, help="Heat load")
    p.add_argument("--dt", type=float, default=0.1, help="Step time (s)")
    p.add_argument(
        "--seconds", type=float, default=10.0, help="Total simulated seconds"
    )
    p.add_argument("--realtime", action="store_true", help="Sleep to realtime")
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    model = CryoPlant()
    model.reset()

    steps = int(args.seconds / args.dt)
    t_sim = 0.0
    print("# time_s, T")
    for _ in range(steps):
        T = model.step(args.tsp, args.qload, args.dt)
        t_sim += args.dt
        print(f"{t_sim:.2f}, {T:.2f}")
        if args.realtime:
            time.sleep(max(0.0, args.dt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

