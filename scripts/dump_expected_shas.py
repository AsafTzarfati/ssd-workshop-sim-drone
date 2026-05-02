"""Generate the canonical expected_shas.json shipped with the leaderboard.

Drives every workshop scenario at the locked default (seed=42, rate=10Hz)
through `run_drone`, captures every non-None `window_sha256` emitted, and
writes the deduped sorted union to JSON. Re-run after any change to the
sim that would alter telemetry content.

  python scripts/dump_expected_shas.py [--out path]

The output should be copied into:
  - ssd-speckit-workshop/specs/expected_shas.json (canonical)
  - sdd-workshop-leaderboard/server/expected_shas.json
  - sdd-workshop-leaderboard/worker/expected_shas.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from sim.anomalies import AnomalyInjector
from sim.clock import VirtualClock
from sim.drone import run_drone
from sim.scenarios import SCENARIOS

SEED = 42
RATE_HZ = 10


async def _collect_shas_for(scenario_name: str) -> list[str]:
    sc = SCENARIOS[scenario_name]()
    queue: asyncio.Queue = asyncio.Queue()
    clock = VirtualClock()
    injector = AnomalyInjector(
        sc.anomaly_schedule_factory(RATE_HZ),
        rate_hz=RATE_HZ,
        seed=SEED ^ 0xA17,
    )
    await run_drone(
        clock=clock,
        path=sc.path,
        queue=queue,
        seed=SEED,
        injector=injector,
        rate_hz=RATE_HZ,
        duration_s=sc.duration_s,
        takeoff_duration_s=sc.takeoff_duration_s,
        landing_duration_s=sc.landing_duration_s,
        cruise_altitude_m=sc.cruise_altitude_m,
        altitude_profile=sc.altitude_profile,
        mode_schedule=sc.mode_schedule,
    )
    shas: list[str] = []
    while not queue.empty():
        sample = queue.get_nowait()
        sha = sample.get("window_sha256")
        if sha is not None:
            shas.append(sha)
    return shas


async def _main(out_path: Path) -> None:
    union: set[str] = set()
    per_scenario: dict[str, int] = {}
    for name in sorted(SCENARIOS):
        shas = await _collect_shas_for(name)
        per_scenario[name] = len(shas)
        union.update(shas)
        print(f"  {name}: {len(shas)} SHAs", file=sys.stderr)
    sorted_union = sorted(union)
    out_path.write_text(json.dumps(sorted_union, indent=0) + "\n")
    print(
        f"wrote {len(sorted_union)} unique SHAs to {out_path} "
        f"(per-scenario: {per_scenario})",
        file=sys.stderr,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("expected_shas.json"),
        help="output JSON path (default: expected_shas.json in cwd)",
    )
    args = parser.parse_args()
    asyncio.run(_main(args.out))


if __name__ == "__main__":
    main()
