from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from sim.anomalies import fibonacci_schedule
from sim.incidents import (
    APOLLO11_PEAK_ALT_M,
    WRIGHT_HOVER_ALT_M,
    AltProfile,
    apollo11_altitude_profile,
    apollo11_anomaly_overlay,
    apollo11_mode_schedule,
    wright_altitude_profile,
)
from sim.paths import heart, israeli_flag
from sim.schema import AnomalyKind, FlightMode


@dataclass
class Scenario:
    name: str
    path: list[tuple[float, float]]
    duration_s: float
    takeoff_duration_s: float
    landing_duration_s: float
    cruise_altitude_m: float
    altitude_profile: AltProfile | None
    mode_schedule: dict[int, FlightMode] | None
    anomaly_schedule_factory: Callable[[int], list[tuple[int, AnomalyKind]]]


def _flag() -> Scenario:
    return Scenario(
        name="flag",
        path=israeli_flag(),
        duration_s=60.0,
        takeoff_duration_s=1.0,
        landing_duration_s=1.0,
        cruise_altitude_m=140.0,
        altitude_profile=None,
        mode_schedule=None,
        anomaly_schedule_factory=fibonacci_schedule,
    )


def _heart() -> Scenario:
    return Scenario(
        name="heart",
        path=heart(),
        duration_s=60.0,
        takeoff_duration_s=1.0,
        landing_duration_s=1.0,
        cruise_altitude_m=140.0,
        altitude_profile=None,
        mode_schedule=None,
        anomaly_schedule_factory=fibonacci_schedule,
    )


def _apollo11() -> Scenario:
    canonical_total = 1200  # 120s × 10Hz
    path = [
        (31.7683, 35.2137),
        (31.7684, 35.2137),
        (31.7684, 35.2138),
        (31.7683, 35.2137),
    ]
    return Scenario(
        name="apollo11",
        path=path,
        duration_s=120.0,
        takeoff_duration_s=0.0,
        landing_duration_s=0.0,
        cruise_altitude_m=APOLLO11_PEAK_ALT_M,
        altitude_profile=apollo11_altitude_profile(canonical_total, 10),
        mode_schedule=apollo11_mode_schedule(10),
        anomaly_schedule_factory=lambda hz: apollo11_anomaly_overlay(fibonacci_schedule(hz), hz),
    )


def _wright() -> Scenario:
    canonical_total = 120  # 12s × 10Hz
    path = [(41.1, -75.0), (41.1001, -75.0)]
    return Scenario(
        name="wright",
        path=path,
        duration_s=12.0,
        takeoff_duration_s=0.0,
        landing_duration_s=0.0,
        cruise_altitude_m=WRIGHT_HOVER_ALT_M,
        altitude_profile=wright_altitude_profile(canonical_total, 10),
        mode_schedule=None,
        anomaly_schedule_factory=fibonacci_schedule,
    )


SCENARIOS: dict[str, Callable[[], Scenario]] = {
    "apollo11": _apollo11,
    "flag": _flag,
    "heart": _heart,
    "wright": _wright,
}
