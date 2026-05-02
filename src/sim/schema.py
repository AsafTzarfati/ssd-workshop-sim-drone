from typing import Literal, NotRequired, TypedDict

FlightMode = Literal["AUTO", "MANUAL", "RTL", "LAND", "MAINT"]

AnomalyKind = Literal[
    "battery_cliff",
    "current_spike",
    "gps_jump",
    "motor_overheat",
    "comm_loss",
    "freefall",
]


class TelemetrySample(TypedDict):
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


class Anomaly(TypedDict):
    kind: AnomalyKind
    seq: int
