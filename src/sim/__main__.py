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
    # Sample counts are pinned to the canonical rate (10Hz). One full cycle
    # = max scenario length × 10 samples (apollo's 1200). At rate=1000 this
    # cycle takes 1.2s wall-time; at rate=10 it takes 120s.
    total_samples = max(int(sc.duration_s * 10) for sc in scenarios)
    duration_s = total_samples / args.rate

    print(
        f"sim: merged stream "
        f"(scenarios={[sc.name for sc in scenarios]}, "
        f"seed={args.seed} rate={args.rate}Hz "
        f"samples={total_samples} wall_duration={duration_s:.2f}s "
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
