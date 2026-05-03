import argparse
import asyncio
import sys

from sim.clock import RealClock
from sim.scenarios import merged_scenarios
from sim.server import serve


def main() -> None:
    parser = argparse.ArgumentParser(prog="sim")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--rate", type=int, default=10)
    parser.add_argument("--loop", action="store_true")
    args = parser.parse_args()

    scenarios = merged_scenarios()
    duration_s = max(sc.duration_s for sc in scenarios)

    print(
        f"sim: merged stream "
        f"(scenarios={[sc.name for sc in scenarios]}, "
        f"seed={args.seed} rate={args.rate}Hz duration={duration_s}s "
        f"port={args.port}) — listening",
        file=sys.stderr,
    )

    async def _run() -> None:
        while True:
            await serve(
                host="localhost",
                port=args.port,
                clock=RealClock(),
                scenarios=scenarios,
                seed=args.seed,
                rate_hz=args.rate,
                duration_s=duration_s,
            )
            if not args.loop:
                break

    asyncio.run(_run())


if __name__ == "__main__":
    main()
