import json

from sim.schema import TelemetrySample


def test_telemetry_sample_json_roundtrip():
    sample: TelemetrySample = {
        "drone_id": "uav-01",
        "seq": 0,
        "ts": 1_700_000_000.123,
        "altitude_m": 140.0,
        "vertical_speed_mps": 0.5,
        "current_a": 20.0,
        "battery_pct": 95.0,
        "motor_temp_c": [65, 66, 67, 68],
        "lat": 31.7683,
        "lon": 35.2137,
        "flight_mode": "AUTO",
    }
    back = json.loads(json.dumps(sample))
    assert back == sample
    assert isinstance(back["motor_temp_c"], list)
    assert len(back["motor_temp_c"]) == 4
    assert all(isinstance(v, int) for v in back["motor_temp_c"])
    assert back["flight_mode"] in {"AUTO", "MANUAL", "RTL", "LAND", "MAINT"}
