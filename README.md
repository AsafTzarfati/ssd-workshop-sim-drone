# sim-drone

WebSocket telemetry simulator. Black-box dependency for the SpecKit workshop.

## Install

```bash
pip install -e .
```

Requires Python ≥ 3.11.

## Run

```bash
python -m sim
```

The sim runs all 4 internal scenarios (`apollo11`, `flag`, `heart`, `wright`)
multiplexed into a **single merged stream**. Each WebSocket message contains
the current state of every scenario simultaneously, nested under per-scenario
keys. Students no longer need to pick a scenario.

```bash
# Options
python -m sim --seed 7
python -m sim --port 9000
python -m sim --rate 100            # emit at 100 Hz (10× real time, for tests)
python -m sim --loop                # restart indefinitely from seq=0
```

On startup the sim logs one line to stderr and begins broadcasting:

```
sim: merged stream (scenarios=['apollo11', 'flag', 'heart', 'wright'], seed=42 rate=10Hz duration=120.0s port=8765) — listening
```

The merged stream's total length is the longest scenario (`apollo11` = 120s
@ 10Hz = 1200 samples). Shorter scenarios loop internally so every frame
carries fresh data for all four.

## Wire schema

One JSON object per WebSocket message. Top-level fields plus 4 per-scenario
sub-objects:

```python
class ScenarioSample(TypedDict):
    altitude_m: float                # metres AGL, 0..200
    vertical_speed_mps: float        # +up / -down
    current_a: float                 # amperes, ~15..40 nominal
    battery_pct: float               # 0..100, monotonically decreasing
    motor_temp_c: list[int]          # length 4, each 50..120
    lat: float                       # WGS84
    lon: float                       # WGS84
    flight_mode: Literal["AUTO", "MANUAL", "RTL", "LAND"]


class MergedTelemetrySample(TypedDict):
    drone_id: str                    # always "uav-01"
    seq: int                         # monotonic, starts at 0
    ts: float                        # unix seconds, millisecond precision
    apollo11: ScenarioSample
    flag: ScenarioSample
    heart: ScenarioSample
    wright: ScenarioSample
    window_sha256: str | None        # SHA over the last 100 frames; None until buffer fills
```

Example frame:

```json
{
  "drone_id": "uav-01",
  "seq": 137,
  "ts": 1714.7,
  "apollo11": {
    "altitude_m": 134.0, "vertical_speed_mps": -2.1,
    "lat": 31.7700, "lon": 35.2100,
    "flight_mode": "AUTO", "current_a": 17.4, "battery_pct": 86.4,
    "motor_temp_c": [78, 80, 79, 77]
  },
  "flag":   { "altitude_m": 60.0, "lat": 31.7714, "lon": 35.2087, ... },
  "heart":  { ... },
  "wright": { ... },
  "window_sha256": "865c90e2..."
}
```

## Example consumer

```python
import asyncio, json
import websockets

async def consume():
    async with websockets.connect("ws://localhost:8765") as ws:
        async for message in ws:
            f = json.loads(message)
            print(f["seq"], f["apollo11"]["altitude_m"], f["flag"]["lat"], f["flag"]["lon"])

asyncio.run(consume())
```

## Version

0.2.0 — merged-stream rewrite. See `pyproject.toml` for the changelog.
