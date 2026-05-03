"""Generate the canonical expected_shas.json shipped with the leaderboard.

Drives the merged-stream sim at the locked default (seed=42, rate=10Hz)
through `run_merged`, captures every non-None `window_sha256` emitted, and
writes the deduped sorted list to JSON. Re-run after any change to the
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

from sim.anomalies import AnomalyInjector, fibonacci_schedule
from sim.clock import VirtualClock
from sim.drone import run_merged
from sim.scenarios import merged_scenarios

SEED = 42
RATE_HZ = 10


async def _collect_shas() -> list[str]:
    queue: asyncio.Queue = asyncio.Queue()
    clock = VirtualClock()
    injector = AnomalyInjector(
        fibonacci_schedule(RATE_HZ),
        rate_hz=RATE_HZ,
        seed=SEED ^ 0xA17,
    )
    await run_merged(
        clock=clock,
        queue=queue,
        scenarios=merged_scenarios(),
        seed=SEED,
        rate_hz=RATE_HZ,
        injector=injector,
    )
    shas: list[str] = []
    while not queue.empty():
        sample = queue.get_nowait()
        sha = sample.get("window_sha256")
        if sha is not None:
            shas.append(sha)
    return shas


async def _main(out_path: Path) -> None:
    shas = await _collect_shas()
    unique = sorted(set(shas))
    out_path.write_text(json.dumps(unique, indent=0) + "\n")
    print(
        f"wrote {len(unique)} unique SHAs (out of {len(shas)} emitted) to {out_path}",
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
