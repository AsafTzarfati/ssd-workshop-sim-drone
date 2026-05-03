from __future__ import annotations

import asyncio
from collections import deque
from typing import Callable

import numpy as np

from sim.anomalies import AnomalyInjector
from sim.clock import Clock
from sim.schema import FlightMode, ScenarioSample, TelemetrySample
from sim.window import WindowHasher


def _interpolate_path(
    path: list[tuple[float, float]], fraction: float
) -> tuple[float, float]:
    if fraction >= 1.0:
        fraction = 1.0 - 1e-9
    i = fraction * (len(path) - 1)
    a = int(i)
    t = i - a
    p0, p1 = path[a], path[a + 1]
    return (p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t)


class _ScenarioState:
    """Per-scenario per-tick state. Each merged stream owns 4 of these.

    Scenarios with a shorter natural duration loop in place: at the merged
    seq `s`, the scenario evaluates its path/altitude/mode at `s % natural`.
    State that should flow continuously across loops (battery, RNG, lag
    buffer) lives on the instance and never resets."""

    def __init__(
        self,
        *,
        name: str,
        path: list[tuple[float, float]],
        natural_total: int,
        natural_takeoff: int,
        natural_landing: int,
        cruise_altitude_m: float,
        rate_hz: int,
        seed: int,
        altitude_profile: Callable[[int, int], tuple[float, float]] | None,
        mode_schedule: dict[int, FlightMode] | None,
    ) -> None:
        self.name = name
        self.path = path
        self.natural_total = natural_total
        self.natural_takeoff = natural_takeoff
        self.natural_landing = natural_landing
        self.natural_cruise = max(0, natural_total - natural_takeoff - natural_landing)
        self.cruise_altitude_m = cruise_altitude_m
        self.rate_hz = rate_hz
        self.dt = 1.0 / rate_hz
        self.altitude_profile = altitude_profile
        self.mode_schedule = mode_schedule

        self.rng = np.random.default_rng(seed)
        self.battery_pct = 100.0
        self._capacity_constant = 50.0  # A·s per %
        self.current_lag_buffer: deque[float] = deque(maxlen=17)

        self.climb_rate = (
            cruise_altitude_m / (natural_takeoff * self.dt) if natural_takeoff > 0 else 0.0
        )
        self.descent_rate = (
            cruise_altitude_m / (natural_landing * self.dt) if natural_landing > 0 else 0.0
        )

    def tick(self, merged_seq: int) -> ScenarioSample:
        """Advance one tick. Loops the natural pattern via merged_seq % natural_total."""
        seq = merged_seq % self.natural_total
        rng = self.rng
        path = self.path

        if self.altitude_profile is not None:
            altitude, v_speed = self.altitude_profile(seq, self.natural_total)
            altitude += float(rng.normal(0, 0.3))
            v_speed += float(rng.normal(0, 0.2))
            current = 22.0 + float(rng.normal(0, 1.5))
            fraction = seq / max(1, self.natural_total - 1)
            lat, lon = _interpolate_path(path, fraction)
        elif seq < self.natural_takeoff:
            altitude = self.climb_rate * (seq + 1) * self.dt
            v_speed = self.climb_rate + float(rng.normal(0, 0.3))
            current = 33.0 + float(rng.normal(0, 1.5))
            lat, lon = path[0]
        elif seq < self.natural_takeoff + self.natural_cruise:
            altitude = self.cruise_altitude_m + float(rng.normal(0, 0.5))
            v_speed = float(rng.normal(0, 0.3))
            current = 22.0 + float(rng.normal(0, 1.5))
            fraction = (seq - self.natural_takeoff) / max(1, self.natural_cruise)
            lat, lon = _interpolate_path(path, fraction)
        else:
            k = seq - (self.natural_takeoff + self.natural_cruise)
            altitude = max(0.0, self.cruise_altitude_m - self.descent_rate * (k + 1) * self.dt)
            v_speed = -self.descent_rate + float(rng.normal(0, 0.3))
            current = 18.0 + float(rng.normal(0, 1.5))
            lat, lon = path[-1]

        self.battery_pct = max(
            0.0, self.battery_pct - current * self.dt / self._capacity_constant
        )
        lagged_current = self.current_lag_buffer[0] if self.current_lag_buffer else current
        motor0 = int(round(65 + 0.3 * lagged_current + float(rng.normal(0, 0.5))))
        motor_temp = [motor0] + [
            int(round(65 + float(rng.normal(0, 2)))) for _ in range(3)
        ]
        self.current_lag_buffer.append(current)

        flight_mode: FlightMode = "AUTO"
        if self.mode_schedule:
            for k in sorted(self.mode_schedule):
                if seq >= k:
                    flight_mode = self.mode_schedule[k]

        return {
            "altitude_m": float(altitude),
            "vertical_speed_mps": float(v_speed),
            "current_a": float(current),
            "battery_pct": float(self.battery_pct),
            "motor_temp_c": motor_temp,
            "lat": float(lat),
            "lon": float(lon),
            "flight_mode": flight_mode,
        }


def make_scenario_states(
    scenarios: list, *, rate_hz: int, seed: int
) -> list[_ScenarioState]:
    """Build the per-scenario state objects with deterministic seed offsets.

    The order of `scenarios` determines the seed offset (i-th scenario uses
    `seed + i + 1`), so adding a new scenario at the tail won't shift seeds
    for the existing ones."""
    states: list[_ScenarioState] = []
    for i, sc in enumerate(scenarios):
        natural_total = int(sc.duration_s * rate_hz)
        states.append(
            _ScenarioState(
                name=sc.name,
                path=sc.path,
                natural_total=natural_total,
                natural_takeoff=int(sc.takeoff_duration_s * rate_hz),
                natural_landing=int(sc.landing_duration_s * rate_hz),
                cruise_altitude_m=sc.cruise_altitude_m,
                rate_hz=rate_hz,
                seed=seed + i + 1,
                altitude_profile=sc.altitude_profile,
                mode_schedule=sc.mode_schedule,
            )
        )
    return states


# Pattern-3 anomalies (Fibonacci) anchor on the `flag` sub-object.
_ANOMALY_ANCHOR = "flag"


async def run_merged(
    *,
    clock: Clock,
    queue: asyncio.Queue,
    scenarios: list,
    seed: int,
    rate_hz: int = 10,
    duration_s: float | None = None,
    drone_id: str = "uav-01",
    injector: AnomalyInjector | None = None,
) -> None:
    """Drive all scenarios in lockstep, emit one merged frame per tick.

    Each frame contains a top-level (drone_id, seq, ts, window_sha256) plus
    one nested sub-object per scenario carrying its tick fields. Pattern-3
    anomalies (the optional injector) apply to the `flag` sub-object only.
    """
    if duration_s is None:
        duration_s = max(sc.duration_s for sc in scenarios)
    total = int(duration_s * rate_hz)
    dt = 1.0 / rate_hz

    states = make_scenario_states(scenarios, rate_hz=rate_hz, seed=seed)
    name_to_state = {s.name: s for s in states}
    if injector is not None and _ANOMALY_ANCHOR not in name_to_state:
        raise ValueError(f"injector requires the '{_ANOMALY_ANCHOR}' scenario")

    hasher = WindowHasher()

    for seq in range(total):
        sub_frames: dict[str, ScenarioSample] = {}
        for st in states:
            sub_frames[st.name] = st.tick(seq)

        if injector is not None:
            # Build a flat sample for the injector — anomalies need seq
            # and operate on TelemetrySample-shaped dicts.
            anchor = sub_frames[_ANOMALY_ANCHOR]
            flat: TelemetrySample = {
                "drone_id": drone_id,
                "seq": seq,
                "ts": clock.now(),
                **anchor,  # type: ignore[misc]
            }
            mutated = injector.apply(flat)
            if mutated is None:
                # comm_loss suppresses the entire merged frame — skip this tick.
                await clock.sleep(dt)
                continue
            # Copy mutated channel fields back into the anchor sub-object.
            for k in (
                "altitude_m",
                "vertical_speed_mps",
                "current_a",
                "battery_pct",
                "motor_temp_c",
                "lat",
                "lon",
                "flight_mode",
            ):
                anchor[k] = mutated[k]  # type: ignore[literal-required]

        frame = {
            "drone_id": drone_id,
            "seq": seq,
            "ts": clock.now(),
            **sub_frames,
        }
        frame["window_sha256"] = hasher.update(frame)
        await queue.put(frame)
        await clock.sleep(dt)
