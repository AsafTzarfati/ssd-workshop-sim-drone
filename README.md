# sim-drone

WebSocket telemetry simulator. Black-box dependency for the SpecKit workshop.

## Install

```bash
pip install -e .
```

Requires Python ≥ 3.11.

## Run

```bash
# Default: flag scenario, seed 42, port 8765
python -m sim

# Options
python -m sim --scenario apollo11   # apollo11 | flag | heart | wright
python -m sim --seed 7
python -m sim --port 9000
python -m sim --rate 100            # emit at 100 Hz (10× real time, for tests)
python -m sim --loop                # restart indefinitely from seq=0
```

On startup the sim logs one line to stderr and begins broadcasting:

```
sim: scenario=flag seed=42 rate=10Hz port=8765 — listening
```

## Wire schema

One JSON object per WebSocket message, emitted at 10 Hz (`ws://localhost:8765`).

```python
class TelemetrySample(TypedDict):
    drone_id: str                    # always "uav-01"
    seq: int                         # monotonic, starts at 0
    ts: float                        # unix seconds, millisecond precision
    altitude_m: float                # metres AGL, 0..200
    vertical_speed_mps: float        # +up / -down
    current_a: float                 # amperes, ~15..40 nominal
    battery_pct: float               # 0..100, monotonically decreasing
    motor_temp_c: list[int]          # length 4, each 50..120
    lat: float                       # WGS84
    lon: float                       # WGS84
    flight_mode: Literal["AUTO", "MANUAL", "RTL", "LAND", "MAINT"]
```

## Example consumer

```python
import asyncio, json
import websockets

async def consume():
    async with websockets.connect("ws://localhost:8765") as ws:
        async for message in ws:
            sample = json.loads(message)
            print(sample["seq"], sample["altitude_m"], sample["flight_mode"])

asyncio.run(consume())
```

## Version

0.1.0 — see `pyproject.toml` for the changelog.
