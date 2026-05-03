import json

from sim.schema import MergedTelemetrySample, ScenarioSample


def _scenario_sample() -> ScenarioSample:
    return {
        "altitude_m": 140.0,
        "vertical_speed_mps": 0.5,
        "current_a": 20.0,
        "battery_pct": 95.0,
        "motor_temp_c": [65, 66, 67, 68],
        "lat": 31.7683,
        "lon": 35.2137,
        "flight_mode": "AUTO",
    }


def test_merged_sample_json_roundtrip():
    sample: MergedTelemetrySample = {
        "drone_id": "uav-01",
        "seq": 0,
        "ts": 1_700_000_000.123,
        "apollo11": _scenario_sample(),
        "flag": _scenario_sample(),
        "heart": _scenario_sample(),
        "wright": _scenario_sample(),
    }
    back = json.loads(json.dumps(sample))
    assert back == sample
    for name in ("apollo11", "flag", "heart", "wright"):
        sub = back[name]
        assert isinstance(sub["motor_temp_c"], list)
        assert len(sub["motor_temp_c"]) == 4
        assert all(isinstance(v, int) for v in sub["motor_temp_c"])
        assert sub["flight_mode"] in {"AUTO", "MANUAL", "RTL", "LAND"}
