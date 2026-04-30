# 🔒 ANSWER KEY — Sealed Until Workshop Wrap-Up

```
╔══════════════════════════════════════════════════════════════╗
║  STOP.  If you are a workshop participant, close this file.  ║
║  Open it only after the instructor says so.                  ║
╚══════════════════════════════════════════════════════════════╝
```

---

## Pattern 1 — Geospatial Path

**What it is:** The flight path, when plotted as latitude vs longitude, traces a recognisable shape.

- Scenario `flag`: two horizontal stripes (top and bottom) plus a Star of David hexagram — the Israeli flag, over a ~500 m × 333 m bounding box centred near Jerusalem (31.77 °N, 35.21 °E).
- Scenario `heart`: a parametric cardioid heart curve.

**Where to find it:** All `lat` / `lon` fields in chronological sample order.

**Decode:**

```python
# Run: python -m sim --scenario flag --seed 42 --rate 1000 &
# Collect samples with any WS client, then:
import json, matplotlib.pyplot as plt
samples = [json.loads(line) for line in open("samples.jsonl")]
lats = [s["lat"] for s in samples]
lons = [s["lon"] for s in samples]
plt.plot(lons, lats); plt.axis("equal"); plt.title("Pattern 1"); plt.show()
```

**Expected output:** Two horizontal lines plus a six-pointed star (flag) or a heart shape.

**Verify (no plot needed):**

```python
from sim.paths import israeli_flag, heart
pts = israeli_flag()
lats, lons = zip(*pts)
assert max(lats) - min(lats) > 0.002   # ~220 m latitude span
assert max(lons) - min(lons) > 0.003   # ~290 m longitude span
print("P1 flag bounding box OK")
```

---

## Pattern 2 — Replay of a Real Event

**What it is:** The `apollo11` scenario's altitude profile *loosely models* the Apollo 11 lunar descent (P63 "high gate" to touchdown), scaled to drone altitudes.

- Peak altitude: **142 m** (scaled from ~4600 m high gate).
- Descent curve: `alt(f) = 142 · (1 − f)² · (1 + 0.4·f)` where `f = seq / total` — a slightly steepened parabola, not a straight ramp.
- **1202 alarm moment:** at `seq = 600` (60 s into the 120 s scenario), a `current_spike` anomaly is injected — mirroring the famous program alarm Armstrong's computer raised at the same relative point in the real descent.
- **Manual takeover:** at `seq = 1100` (110 s), `flight_mode` flips to `MANUAL` — mirroring Aldrin's manual takeover at ~500 ft AGL.
- Scenario `wright`: 10 s hover at 3 m followed by a 2 s descent — the Wright Flyer's first flight profile.

**Where to find it:** `altitude_m`, `flight_mode`, `current_a` in the `apollo11` scenario stream.

**Decode:**

```python
# Collect apollo11 samples, then:
import json, matplotlib.pyplot as plt
samples = [json.loads(line) for line in open("apollo11.jsonl")]
alts = [s["altitude_m"] for s in samples]
modes = [s["flight_mode"] for s in samples]
plt.plot([i/10 for i in range(len(alts))], alts)
plt.xlabel("time (s)"); plt.ylabel("altitude (m)")
manual_t = next(i/10 for i, m in enumerate(modes) if m == "MANUAL")
plt.axvline(manual_t, color="red", label=f"MANUAL at {manual_t}s"); plt.legend(); plt.show()
```

**Verify:**

```python
import asyncio, json
from sim.scenarios import SCENARIOS
from sim.clock import VirtualClock
from sim.drone import run_drone
from sim.anomalies import AnomalyInjector

async def _collect():
    sc = SCENARIOS["apollo11"]()
    q = asyncio.Queue()
    clk = VirtualClock()
    inj = AnomalyInjector(sc.anomaly_schedule_factory(10), rate_hz=10, seed=42)
    await run_drone(clock=clk, path=sc.path, queue=q, seed=42, injector=inj,
                    duration_s=sc.duration_s, takeoff_duration_s=sc.takeoff_duration_s,
                    landing_duration_s=sc.landing_duration_s, cruise_altitude_m=sc.cruise_altitude_m,
                    altitude_profile=sc.altitude_profile, mode_schedule=sc.mode_schedule)
    return [q.get_nowait() for _ in range(q.qsize())]

samples = asyncio.run(_collect())
assert samples[0]["altitude_m"] > 130, "starts high"
assert samples[-1]["altitude_m"] < 5,  "ends near ground"
assert samples[1100]["flight_mode"] == "MANUAL", "MANUAL at seq 1100"
assert samples[600]["current_a"] > 35,  "1202 current spike at seq 600"
print("P2 apollo11 profile OK")
```

---

## Pattern 3 — Temporal Cadence (Fibonacci)

**What it is:** The intervals (in seconds) between consecutive anomalies form a Fibonacci sequence: **1, 1, 2, 3, 5, 8, 13, 21**.

At 10 Hz, anomalies fire at cumulative seq numbers: **10, 20, 40, 70, 120, 200, 330, 540**.

Anomaly kinds rotate through: `battery_cliff → current_spike → gps_jump → motor_overheat → comm_loss → freefall → battery_cliff → current_spike`.

**Where to find it:** Any channel that changes abruptly at those exact seq values — `battery_pct` drops, `current_a` spikes, `lat`/`lon` jumps, `motor_temp_c[0]` peaks, missing samples (`seq` gap), `vertical_speed_mps` plunges.

**Detection hint:** Build a list of seq values where any channel shows an out-of-range reading, then compute the inter-event gaps.

**Decode:**

```python
import numpy as np
# anomaly_seqs = sorted list of seq numbers where you detected anomalies
anomaly_seqs = [10, 20, 40, 70, 120, 200, 330, 540]
gaps_s = np.diff(anomaly_seqs) / 10   # → [1, 2, 3, 5, 8, 13, 21]
# Each gap is the sum of the two preceding ones → Fibonacci
print("gaps (s):", gaps_s)
```

**Verify:**

```python
from sim.anomalies import fibonacci_schedule
sched = fibonacci_schedule(rate_hz=10)
seqs = [s for s, _ in sched]
import numpy as np
gaps = np.diff(seqs) / 10
fib = [1, 2, 3, 5, 8, 13, 21]
assert list(gaps.astype(int)) == fib, gaps
print("P3 Fibonacci schedule OK:", seqs)
```

---

## Pattern 4 — Cross-Channel Correlation (1.7 s lag)

**What it is:** `motor_temp_c[0]` is a *lagged, scaled echo* of `current_a` — specifically:

```
motor_temp_c[0] ≈ 65 + 0.3 · current_a[seq − 17] + N(0, 0.5)
```

The lag is **17 samples = 1.7 seconds** at 10 Hz. The other three motor temperatures are independent noise around 65 ± 2 °C and carry no signal.

**Where to find it:** `current_a` and `motor_temp_c[0]` across any scenario.

**Detection hint:** Compute the cross-correlation between `current_a` and `motor_temp_c[0]` at lags 0–40 samples. The peak is unambiguous at lag 17.

**Decode:**

```python
import numpy as np
# current = np.array of current_a values
# motor0  = np.array of motor_temp_c[0] values (same length)
lags = range(1, 40)
corrs = [np.corrcoef(current[:-L], motor0[L:])[0, 1] for L in lags]
best_lag = lags[int(np.argmax(corrs))]
print(f"Peak cross-correlation at lag={best_lag} samples ({best_lag/10:.1f} s)")
# → Peak cross-correlation at lag=17 samples (1.7 s)
```

**Verify:**

```python
import asyncio, numpy as np
from sim.scenarios import SCENARIOS
from sim.clock import VirtualClock
from sim.drone import run_drone

async def _collect():
    sc = SCENARIOS["flag"]()
    q = asyncio.Queue()
    await run_drone(clock=VirtualClock(), path=sc.path, queue=q, seed=42,
                    duration_s=sc.duration_s, takeoff_duration_s=sc.takeoff_duration_s,
                    landing_duration_s=sc.landing_duration_s, cruise_altitude_m=sc.cruise_altitude_m)
    return [q.get_nowait() for _ in range(q.qsize())]

samples = asyncio.run(_collect())
current = np.array([s["current_a"] for s in samples])
motor0  = np.array([s["motor_temp_c"][0] for s in samples])
lags = range(1, 40)
corrs = [np.corrcoef(current[:-L], motor0[L:])[0, 1] for L in lags]
assert lags[int(np.argmax(corrs))] == 17
print("P4 lag-17 correlation OK")
```

---

## Pattern 5 — Encoded ASCII Message

**What it is:** Hidden inside the `motor_temp_c[3]` field during `MAINT` mode windows is an ASCII-encoded message: **`HELLO COPILOT`**.

**Mechanism:**

1. Every 30 seconds (every 300 samples at 10 Hz), the drone enters `MAINT` mode for exactly **10 samples**.
2. During those 10 samples, `motor_temp_c[3]` takes on a single ASCII byte value (65–122) that encodes one character of the hidden message.
3. The message cycles character-by-character with each successive MAINT window.

**Encoding note:** The space character (ASCII 32) falls outside [65, 122], so it is substituted with `_` (ASCII 95). The raw decoded string is `HELLO_COPILOT`; replace `_` with a space to recover the true message.

**The disguise:** Values 65–122 °C are genuinely anomalous motor temperatures — any reasonable Watchdog will flag them as `motor_overheat`. The pattern only becomes visible when you *group those alerts by `flight_mode`* and inspect the exact integer temperatures during `MAINT` windows.

**Detection path:**

1. Watchdog flags many `motor_overheat` events.
2. Group by `flight_mode` → MAINT-mode events cluster.
3. During MAINT, all four `motor_temp_c` values are suspicious — but `motor_temp_c[3]` is always a *specific* integer in [65, 122], while the others are noisy.
4. Take the first sample of each MAINT window, read `motor_temp_c[3]`, call `chr()`.

**Decode:**

```python
# samples = list of TelemetrySample dicts from a --loop run (need ≥ 13 MAINT windows = ~390 s)
maint_samples = [s for s in samples if s["flight_mode"] == "MAINT"]
# One sample per block (all 10 in a window are identical for motor_temp_c[3])
seen_blocks = set()
chars = []
for s in maint_samples:
    block = s["seq"] // 300
    if block not in seen_blocks:
        seen_blocks.add(block)
        chars.append(chr(s["motor_temp_c"][3]))
message = "".join(chars).replace("_", " ")
print("Hidden message:", message)
# → Hidden message: HELLO COPILOT
```

**Verify:**

```python
from sim.encoding import encode, decode, HIDDEN_MESSAGE
encoded = encode(HIDDEN_MESSAGE)
assert all(65 <= v <= 122 for v in encoded), "all values in [65,122]"
raw = decode(encoded)
assert raw.replace("_", " ") == HIDDEN_MESSAGE
print(f"P5 encoding OK: {encoded} → {raw!r} → {raw.replace('_', ' ')!r}")
```

---

*End of answer key. Ship this file with the repo but mark it in `.gitignore` or rename it for participant distribution — whichever the workshop logistics require.*
