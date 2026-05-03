from typing import Literal, NotRequired, TypedDict

FlightMode = Literal["AUTO", "MANUAL", "RTL", "LAND"]

AnomalyKind = Literal[
    "battery_cliff",
    "current_spike",
    "gps_jump",
    "motor_overheat",
    "comm_loss",
    "freefall",
]


class TelemetrySample(TypedDict):
    """Per-scenario flat sample. Used by the anomaly injector and as the
    intermediate shape during a merged tick before assembly."""
    drone_id: str
    seq: int
    ts: float
    altitude_m: float
    vertical_speed_mps: float
    current_a: float
    battery_pct: float
    motor_temp_c: list[int]
    lat: float
    lon: float
    flight_mode: FlightMode
    window_sha256: NotRequired[str | None]


class ScenarioSample(TypedDict):
    """One scenario's sub-object inside a merged frame."""
    altitude_m: float
    vertical_speed_mps: float
    current_a: float
    battery_pct: float
    motor_temp_c: list[int]
    lat: float
    lon: float
    flight_mode: FlightMode


class MergedTelemetrySample(TypedDict):
    drone_id: str
    seq: int
    ts: float
    apollo11: ScenarioSample
    flag: ScenarioSample
    heart: ScenarioSample
    wright: ScenarioSample
    window_sha256: NotRequired[str | None]


class Anomaly(TypedDict):
    kind: AnomalyKind
    seq: int
