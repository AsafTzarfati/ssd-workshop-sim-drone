from __future__ import annotations

import asyncio
from collections import deque
from typing import Callable

import numpy as np

from sim.anomalies import AnomalyInjector
from sim.clock import Clock
from sim.encoding import HIDDEN_MESSAGE, MAINT_INTERVAL_S, MAINT_WINDOW_SAMPLES, encode
from sim.schema import FlightMode, TelemetrySample
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


async def run_drone(
    *,
    clock: Clock,
    path: list[tuple[float, float]],
    queue: asyncio.Queue,
    seed: int,
    injector: AnomalyInjector | None = None,
    drone_id: str = "uav-01",
    duration_s: float = 60.0,
    rate_hz: int = 10,
    cruise_altitude_m: float = 140.0,
    takeoff_duration_s: float = 5.0,
    landing_duration_s: float = 5.0,
    altitude_profile: Callable[[int, int], tuple[float, float]] | None = None,
    mode_schedule: dict[int, FlightMode] | None = None,
) -> None:
    rng = np.random.default_rng(seed)
    dt = 1.0 / rate_hz

    encoded_msg = encode(HIDDEN_MESSAGE)
    maint_period = int(MAINT_INTERVAL_S * rate_hz)
    maint_window = MAINT_WINDOW_SAMPLES

    total = int(duration_s * rate_hz)
    n_takeoff = int(takeoff_duration_s * rate_hz)
    n_landing = int(landing_duration_s * rate_hz)
    n_cruise = total - n_takeoff - n_landing
    if altitude_profile is None and n_cruise <= 0:
        raise ValueError("duration_s too short for takeoff + landing budget")

    climb_rate = cruise_altitude_m / takeoff_duration_s if takeoff_duration_s > 0 else 0.0
    descent_rate = cruise_altitude_m / landing_duration_s if landing_duration_s > 0 else 0.0

    battery_pct = 100.0
    capacity_constant = 50.0  # A·s per %
    current_lag_buffer: deque[float] = deque(maxlen=17)
    hasher = WindowHasher()

    for seq in range(total):
        if altitude_profile is not None:
            altitude, v_speed = altitude_profile(seq, total)
            altitude += float(rng.normal(0, 0.3))
            v_speed += float(rng.normal(0, 0.2))
            current = 22.0 + float(rng.normal(0, 1.5))
            fraction = seq / max(1, total - 1)
            lat, lon = _interpolate_path(path, fraction)
        elif seq < n_takeoff:
            altitude = climb_rate * (seq + 1) * dt
            v_speed = climb_rate + float(rng.normal(0, 0.3))
            current = 33.0 + float(rng.normal(0, 1.5))
            lat, lon = path[0]
        elif seq < n_takeoff + n_cruise:
            altitude = cruise_altitude_m + float(rng.normal(0, 0.5))
            v_speed = float(rng.normal(0, 0.3))
            current = 22.0 + float(rng.normal(0, 1.5))
            fraction = (seq - n_takeoff) / n_cruise
            lat, lon = _interpolate_path(path, fraction)
        else:
            k = seq - (n_takeoff + n_cruise)
            altitude = max(0.0, cruise_altitude_m - descent_rate * (k + 1) * dt)
            v_speed = -descent_rate + float(rng.normal(0, 0.3))
            current = 18.0 + float(rng.normal(0, 1.5))
            lat, lon = path[-1]

        battery_pct = max(0.0, battery_pct - current * dt / capacity_constant)
        lagged_current = current_lag_buffer[0] if current_lag_buffer else current
        motor0 = int(round(65 + 0.3 * lagged_current + float(rng.normal(0, 0.5))))
        motor_temp = [motor0] + [int(round(65 + float(rng.normal(0, 2)))) for _ in range(3)]
        current_lag_buffer.append(current)

        flight_mode: FlightMode = "AUTO"
        if mode_schedule:
            for k in sorted(mode_schedule):
                if seq >= k:
                    flight_mode = mode_schedule[k]
        if seq >= maint_period:
            block = seq // maint_period
            offset = seq - block * maint_period
            if offset < maint_window:
                flight_mode = "MAINT"
                motor_temp[3] = encoded_msg[(block - 1) % len(encoded_msg)]

        sample: TelemetrySample = {
            "drone_id": drone_id,
            "seq": seq,
            "ts": clock.now(),
            "altitude_m": float(altitude),
            "vertical_speed_mps": float(v_speed),
            "current_a": float(current),
            "battery_pct": float(battery_pct),
            "motor_temp_c": motor_temp,
            "lat": float(lat),
            "lon": float(lon),
            "flight_mode": flight_mode,
        }
        if injector is not None:
            out = injector.apply(sample)
            if out is None:
                await clock.sleep(dt)
                continue
            sample = out
        sample["window_sha256"] = hasher.update(sample)
        await queue.put(sample)
        await clock.sleep(dt)
