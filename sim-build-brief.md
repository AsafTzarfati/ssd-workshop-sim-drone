# Build Brief — Drone Telemetry Simulator

> **For Claude Code.** This is a complete build brief. Read it end-to-end before writing any code. Acceptance criteria are at the bottom — your work is done when those pass.

---

## 1. Mission

Build a Python WebSocket service that simulates a single drone emitting realistic telemetry at 10 Hz. The simulator is the **black-box dependency** for a workshop where participants build an "AI Telemetry Watchdog" using GitHub SpecKit. They consume the sim. They never modify it.

The sim must:

1. Emit deterministic, seedable telemetry over WebSocket (`ws://localhost:8765`)
2. Inject realistic anomalies on a configurable schedule
3. Embed **five hidden patterns** in the data — not visible at a glance, but discoverable by analysis. The whole point of the workshop is building an agent that can find these.
4. Ship a sealed `ANSWER_KEY.md` that documents the patterns, ignored by participants until the workshop wrap-up

This brief is the spec. It is intentionally opinionated about *what* and lighter on *how* — make sane Python choices within the constraints below.

---

## 2. Hard Constraints

| | |
|---|---|
| **Python version** | 3.11+ |
| **Async runtime** | `asyncio` standard library only — no trio, no anyio |
| **WebSocket lib** | `websockets` (the `python-websockets/websockets` package). No FastAPI, no Starlette. |
| **Numerical** | `numpy` for path math and signal generation. No pandas. No scipy unless absolutely necessary (it isn't). |
| **Determinism** | Seeded by default. Same seed → identical sample sequence (modulo wall-clock timestamps, which use a virtual clock under test). |
| **Dependencies** | Keep the dep list under 5 packages total. Boring tech only. |
| **No I/O surprises** | No telemetry, no analytics, no calling out. The sim runs offline. |

**Do NOT:**
- Add a built-in plotter, dashboard, or visualization. Participants must analyze the data themselves; that's the point of the workshop.
- Add ML, anomaly detection, or alerting *inside* the sim — that's the Watchdog's job, built later.
- Add a database, a message broker, or persistence of any kind.
- Add Docker / K8s / cloud config. This is `python -m sim` and that's it.
- Make the schema "extensible" with plugin hooks. The schema is fixed.
- Use `time.sleep`. Anywhere. Period.

---

## 3. Stack & Layout

```
sim-drone/
├── pyproject.toml
├── Makefile
├── README.md                    # for participants — how to consume the sim
├── ANSWER_KEY.md                # SEALED — instructor only, ignored until wrap-up
├── src/
│   └── sim/
│       ├── __init__.py
│       ├── __main__.py          # CLI entry: `python -m sim`
│       ├── schema.py            # TelemetrySample, Anomaly types
│       ├── clock.py             # VirtualClock + RealClock
│       ├── server.py            # WebSocket server, broadcasts to all consumers
│       ├── drone.py             # Drone state machine; produces samples on the wire
│       ├── paths.py             # Geospatial path generators (flag, heart)
│       ├── incidents.py         # Real-event replay profiles (Apollo 11, Wright)
│       ├── anomalies.py         # Failure mode injectors
│       ├── encoding.py          # ASCII-in-motor-temp encoder/decoder
│       └── scenarios.py         # Compose patterns into named scenarios
└── tests/
    ├── test_schema.py
    ├── test_clock.py
    ├── test_paths.py
    ├── test_drone_determinism.py    # same seed → same bytes
    ├── test_anomalies.py
    ├── test_encoding.py             # ASCII round-trip
    ├── test_server.py               # WS handshake + first 10 samples
    └── test_scenarios.py            # each scenario boots and emits expected count
```

Use a `src/` layout. Use `pyproject.toml` with PEP 621 metadata. Pin Python ≥3.11.

---

## 4. The Wire Schema

Telemetry samples are JSON, one per WebSocket message, emitted at exactly 10 Hz (100ms cadence). The schema is **fixed** — do not extend it, do not add fields, do not bikeshed.

```python
# src/sim/schema.py
from typing import Literal, TypedDict

FlightMode = Literal["AUTO", "MANUAL", "RTL", "LAND", "MAINT"]

class TelemetrySample(TypedDict):
    drone_id: str          # always "uav-01" in the v1 sim
    seq: int               # monotonic, starts at 0, +1 per sample
    ts: float              # unix seconds, with millisecond precision
    altitude_m: float      # meters AGL, 0..200
    vertical_speed_mps: float   # +up / -down
    current_a: float       # amperes, ~15..40 nominal, spikes higher
    battery_pct: float     # 0..100, monotonically decreasing per scenario
    motor_temp_c: list[int]    # length 4, each 50..120, integers (NOT floats — see §6 pattern 5)
    lat: float             # WGS84
    lon: float             # WGS84
    flight_mode: FlightMode
```

**Notes for implementation:**

- `motor_temp_c` is `list[int]` not `list[float]` deliberately. Pattern 5 depends on this.
- `ts` uses the **virtual clock** under tests, real wall clock when running live. The drone state machine takes a `Clock` interface; both clocks expose `now() -> float` and `await sleep(seconds)`.
- `seq` is the only field that increments deterministically forever. Anomaly timing, lat/lon, etc. are all functions of `seq` and the seed — so determinism is reproducible *by sequence number*, not by wall-clock.

---

## 5. Drone State Machine

A single drone, modeled as an async coroutine that:

1. Starts at a scenario-defined origin, altitude 0
2. Takes off vertically to ~140m
3. Follows a scenario-defined waypoint path
4. Lands

Sample emission is **independent** of the state machine's update loop. The state machine ticks 10x/second (exactly), and each tick produces one sample appended to a broadcast queue. The WebSocket server fan-outs from the queue to all connected consumers.

**Key implementation requirements:**

- The drone's altitude/velocity profile **is the scenario's profile** — for `apollo11`, the profile *is* a scaled lunar descent curve, not a straight climb-and-cruise.
- `motor_temp_c` is modeled as a function of `current_a` plus correlated noise — see Pattern 4 below.
- `battery_pct` decays from 100 monotonically. Rate depends on `current_a` integrated over time.
- `flight_mode` defaults to `AUTO`. Transitions to `MAINT` only during scheduled MAINT windows (see Pattern 5).

**Lifecycle:** the drone runs to the end of its scenario (typically 60–180 seconds of telemetry), then closes the WebSocket cleanly. `--loop` flag restarts from `seq=0`.

---

## 6. The Five Hidden Patterns

These are the heart of the sim. Each pattern must be:

- **Detectable** by an agent with standard analytical tools (numpy, basic stats)
- **Not obvious** in the raw stream — has to be found by *looking* in the right way
- **Robust to noise** — the signal must survive the natural variability of the sim
- **Documented in `ANSWER_KEY.md`** — see §8

### Pattern 1 — Geospatial path (visual)

The lat/lon waypoints, when plotted, form a recognizable shape.

- Two scenarios ship: `flag` (Israeli flag, ~80 waypoints) and `heart` (parametric curve, ~60 waypoints)
- Path generator lives in `paths.py` and returns `list[tuple[float, float]]` — lat/lon pairs in WGS84, centered on the scenario origin
- The drone interpolates between waypoints at constant horizontal speed; resolution is ~600 samples per scenario (60s × 10Hz)

**Israeli flag construction (reference):**

- Two horizontal blue stripes (top and bottom of bounding box)
- Star of David in the middle (two overlapping equilateral triangles)
- Scale: ~500m × 333m bounding box (3:2 aspect)
- Drone visits all stripes and triangles in order, then closes the path

**Detection by an agent:** plot the lat/lon trajectory. Visual recognition by a human is trivial; an agent that reaches for `matplotlib` finds it in one step.

### Pattern 2 — Replay of a real event (narrative)

The altitude/velocity profile of a scenario *loosely models* a famous flight.

- Scenario `apollo11`: the descent profile from "high gate" (P63) through final touchdown, scaled to drone altitudes (15,000ft → 142m, 12 minutes → 120 seconds). Includes the famous **1202 alarm** moment — at the equivalent relative time, the sim injects a `current_spike` anomaly. Includes the late-stage manual takeover — flight mode flips `AUTO → MANUAL` at the equivalent of 500 ft AGL.
- Scenario `wright`: a 12-second hover at 3m, then landing. Tiny scenario, mostly for unit tests.

**Detection by an agent:** plot altitude vs time, observe the curve shape, recognize the descent profile. Or: notice the timing of the `MANUAL` mode transition matches the historical record. The agent doesn't need to *recognize* Apollo 11 — it just needs to recognize that the profile is a structured curve, not random.

### Pattern 3 — Temporal cadence (sequence math)

The *intervals between consecutive anomalies* form a Fibonacci sequence (in seconds): 1, 1, 2, 3, 5, 8, 13, 21.

- Anomalies fire at seq=10, 20, 40, 70, 120, 200, 330, 540 (assuming 10 Hz)
- The anomaly **types** rotate through a fixed list: `[battery_cliff, current_spike, gps_jump, motor_overheat, comm_loss, ...]`
- This pattern is **independent** of the geospatial / replay patterns — it composes on top

**Detection by an agent:** extract the sequence of anomaly timestamps from the alert log, compute deltas, check against known integer sequences. Fibonacci is one of the first things any agent checks.

### Pattern 4 — Cross-channel correlation (time-series statistics)

`motor_temp_c[0]` lags `current_a` by exactly **1.7 seconds** (17 samples). When `current_a` rises by Δ, `motor_temp_c[0]` rises by ~`0.3·Δ` exactly 17 samples later, plus N(0, 0.5) noise.

- Implement as a 17-sample ring buffer of recent `current_a` values; `motor_temp_c[0]` is computed from `buffer[-17]`
- The other three motor temps are independent noise around 65±5°C
- Determinism: noise is sampled from a `numpy.random.default_rng(seed)` so the lag is recoverable bit-exactly with the same seed

**Detection by an agent:** compute the cross-correlation of `current_a` and `motor_temp_c[0]` at varying lags. Peak at lag=17 is unmistakable. ~5 lines of numpy.

### Pattern 5 — Encoded ASCII (encoding, hides as anomalies)

This is the sneakiest pattern. It **masquerades as a sequence of motor overheat anomalies**, which the Watchdog is built to detect.

Mechanism:

- Every 30 seconds, the drone enters `MAINT` mode for exactly 10 samples (1 second)
- During that window, `motor_temp_c[3]` (the *fourth* motor) takes on values that are **valid ASCII bytes for printable letters** — i.e., between 65 ('A') and 122 ('z'), with each value matching one character of a hidden message
- The message: `HELLO COPILOT` (13 characters). With a 30s cadence and a 60–180s scenario, you'll get 2–6 characters per run — enough to hint at a pattern. Loop the scenario to recover the full message.
- The values 65–122°C ARE physically anomalous — they trigger a `motor_overheat` alert in any reasonable Watchdog. So the team will see the alerts. Only when they look at the *exact temperature values* during MAINT mode will they notice the values cluster in the printable-ASCII range.

**Detection by an agent:** when the Watchdog flags `motor_overheat` events, group by `flight_mode`. In MAINT-mode events, motor[3] values are integers in [65,122] — print them as ASCII bytes. The message reveals itself.

This pattern is intentionally **last to be discovered**. It's a wrap-up reveal.

---

## 7. Anomaly Injection (the "obvious" part)

Independent of the hidden patterns, the sim injects standard failure modes that the Watchdog is *meant* to catch:

| Anomaly | Symptom on the wire |
|---|---|
| `battery_cliff` | `battery_pct` drops 5 percentage points in <2 seconds |
| `current_spike` | `current_a` exceeds 35A for 3+ consecutive samples |
| `gps_jump` | `lat`/`lon` teleports >100m between adjacent samples |
| `motor_overheat` | Any `motor_temp_c[i]` > 90°C |
| `comm_loss` | Drone stops emitting for 5–30 seconds, then resumes (but `seq` continues, so consumers can detect the gap) |
| `freefall` | `vertical_speed_mps` < −8 sustained 1+ seconds |

Anomaly injection is driven by **Pattern 3's Fibonacci schedule**. Each anomaly modifies the underlying sample stream — it's not a separate event channel. The Watchdog has to *infer* anomalies from the telemetry; the sim never says "anomaly here."

---

## 8. CLI

```bash
# Default: israeli-flag scenario, seed=42, port 8765, no loop
python -m sim

# Pick a scenario
python -m sim --scenario apollo11
python -m sim --scenario heart
python -m sim --scenario wright

# Reproducibility
python -m sim --seed 7

# Networking
python -m sim --port 9000

# Looping for long demos
python -m sim --loop

# Speed (for tests/demos): emit at 10x real time
python -m sim --rate 100
```

Available scenarios: `flag` (default), `heart`, `apollo11`, `wright`.

CLI uses `argparse` standard library only — no `click`, no `typer`.

On startup, log a single line to stderr:
```
sim: scenario=flag seed=42 rate=10Hz port=8765 — listening
```

No other stderr output unless a connection error.

---

## 9. ANSWER_KEY.md

Ship this file with a giant **DO NOT OPEN UNTIL WORKSHOP WRAP-UP** banner at the top. Contents:

- One section per hidden pattern (5 sections)
- For each: what the pattern is, where it's encoded, the exact decode procedure, the expected output

Structure:

```markdown
# 🔒 ANSWER KEY — Sealed Until Workshop Wrap-Up

Stop. If you're a workshop participant, close this file.
Open it only after the instructor says so.

---

## Pattern 1 — Geospatial Path

**What it is:** The flight path traces the Israeli flag.
**Where to find it:** Plot all `lat`/`lon` samples in chronological order.
**Decode:** `matplotlib.pyplot.plot(lons, lats); plt.axis('equal'); plt.show()`
**Expected output:** Two horizontal stripes plus a Star of David hexagram.

## Pattern 2 — Apollo 11 Descent
[...]
```

Each pattern section ends with a one-liner Python snippet that recovers the signal — so the instructor can verify the pattern is present after any code change.

---

## 10. Acceptance Tests

The following must all pass before the build is done:

```bash
make verify   # runs all of:
  python -m pip install -e .
  pytest -q
  python -m sim --scenario flag --seed 42 --rate 1000 &
  sleep 0.5
  python -c "$(cat tests/_smoke_client.py)"   # connects, reads 50 samples, exits 0
  pkill -f 'python -m sim'
```

`tests/_smoke_client.py` (you write this) connects to the WS, reads 50 samples, asserts:
- All 50 are valid `TelemetrySample` shapes
- `seq` is contiguous from 0..49
- At least 4 distinct `lat`/`lon` pairs (drone is moving)
- `motor_temp_c` is `list[int]` of length 4

Unit-level acceptance:

| Test | Asserts |
|---|---|
| `test_schema` | TypedDict roundtrips through `json.dumps`/`loads` |
| `test_clock` | VirtualClock advances deterministically; `await sleep` resolves immediately under VirtualClock |
| `test_paths` | `paths.israeli_flag()` returns a closed polygon spanning expected bounding box |
| `test_drone_determinism` | Same seed → byte-identical first 100 samples (modulo `ts`, which uses VirtualClock) |
| `test_anomalies` | Fibonacci schedule fires anomalies at expected `seq` values |
| `test_encoding` | `encoding.encode("HELLO")` then `decode` round-trips; values fall in [65, 122] |
| `test_server` | WS handshake completes; first 10 frames are valid samples |
| `test_scenarios` | Each named scenario boots, emits ≥600 samples, closes cleanly |

`pytest` only. No async test framework other than `pytest-asyncio` (the one allowed extra dep beyond the runtime list).

---

## 11. Build Order

Build incrementally. Commit after each step. Don't move to the next step until tests for the current step pass.

1. **Skeleton** — `pyproject.toml`, `src/sim/__init__.py`, empty `__main__.py`, Makefile with `verify` target
2. **Schema + Clock** — `schema.py`, `clock.py`, their tests
3. **Path generators** — `paths.py` for `israeli_flag` and `heart`, with test that asserts the bounding box
4. **Drone state machine** — `drone.py` consuming a path, emitting samples to an `asyncio.Queue`, ticking on a `Clock`
5. **WebSocket server** — `server.py`, broadcast queue → all consumers
6. **CLI** — `__main__.py` with argparse, default scenario `flag`
7. **Anomaly injectors** — `anomalies.py`, applied to the sample stream
8. **Pattern 3 (Fibonacci schedule)** — drives the anomaly injector
9. **Pattern 4 (cross-channel correlation)** — added to drone's `motor_temp_c[0]` calculation
10. **Pattern 5 (ASCII encoding)** — `encoding.py` + MAINT-mode windows in `drone.py`
11. **Pattern 2 (Apollo 11 + Wright incidents)** — `incidents.py` + scenarios that compose them
12. **Scenarios** — `scenarios.py` ties paths + incidents + patterns into named scenarios
13. **ANSWER_KEY.md** — final pass, every pattern documented with verifying snippet
14. **README.md** — for participants, what they need to consume the sim
15. **Final `make verify`** — must pass clean from a fresh venv

---

## 12. README.md (Package Documentation Only)

Keep it short. This README is for anyone landing on the sim package — not the workshop participant onboarding (that lives in a separate `workshop-speckit` repo).

Include:

- One-liner: "WebSocket telemetry simulator. Black-box dependency for the SpecKit workshop."
- How to install: `pip install -e .` (or from a release tag)
- How to run: `python -m sim`
- The wire schema (copy from §4 of this brief)
- A 10-line Python WebSocket client snippet for ad-hoc consumers
- Version + changelog pointer

Do **not**:
- Mention the hidden patterns
- Reference the workshop pedagogically — this repo stands alone as a package
- Include participant onboarding instructions — those live in the workshop repo

---

## 13. Out of Scope (Things Not To Build)

- Multi-drone fleet (single drone only — `drone_id` is always `"uav-01"`)
- Authentication / TLS on the WebSocket
- Configuration files (YAML/TOML for scenarios) — scenarios are Python, period
- Plugin system / extensibility hooks
- Performance optimization beyond "doesn't fall behind 10Hz"
- Windows-specific tweaks (Linux/macOS only)
- A mock client / fake Watchdog for testing the sim against — the smoke client is enough

---

## 14. Done When

- `make verify` exits 0 from a fresh `git clone`
- All 8 unit test files pass
- Running `python -m sim` produces a working WebSocket stream that a `wscat` client can connect to and read JSON from
- Each of the 5 patterns is verifiable from `ANSWER_KEY.md`'s decode snippets
- README is participant-ready
- No TODO/FIXME comments left in the code

When all that's true, you're done. Don't add features. Don't refactor for elegance. Ship it.
