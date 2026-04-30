import argparse
import asyncio
import sys

from sim.clock import RealClock
from sim.scenarios import SCENARIOS
from sim.server import serve


def main() -> None:
    parser = argparse.ArgumentParser(prog="sim")
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), default="flag")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--rate", type=int, default=10)
    parser.add_argument("--loop", action="store_true")
    args = parser.parse_args()

    print(
        f"sim: scenario={args.scenario} seed={args.seed} "
        f"rate={args.rate}Hz port={args.port} — listening",
        file=sys.stderr,
    )

    sc = SCENARIOS[args.scenario]()
    factor = 10.0 / args.rate

    async def _run() -> None:
        while True:
            await serve(
                host="localhost",
                port=args.port,
                clock=RealClock(),
                path=sc.path,
                seed=args.seed,
                rate_hz=args.rate,
                duration_s=sc.duration_s * factor,
                takeoff_duration_s=sc.takeoff_duration_s * factor,
                landing_duration_s=sc.landing_duration_s * factor,
                cruise_altitude_m=sc.cruise_altitude_m,
                altitude_profile=sc.altitude_profile,
                mode_schedule=sc.mode_schedule,
                anomaly_schedule=sc.anomaly_schedule_factory(args.rate),
            )
            if not args.loop:
                break

    asyncio.run(_run())


if __name__ == "__main__":
    main()
