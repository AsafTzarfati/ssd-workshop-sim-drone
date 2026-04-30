import math

from sim.anomalies import KINDS_ROTATION, AnomalyInjector, fibonacci_schedule
from sim.schema import TelemetrySample


def _baseline_sample(seq: int) -> TelemetrySample:
    return {
        "drone_id": "uav-01",
        "seq": seq,
        "ts": 0.0,
        "altitude_m": 140.0,
        "vertical_speed_mps": 0.0,
        "current_a": 22.0,
        "battery_pct": 80.0,
        "motor_temp_c": [65, 65, 65, 65],
        "lat": 32.0,
        "lon": 35.0,
        "flight_mode": "AUTO",
    }


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(
        math.radians(lat2)
    ) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _apply_n(
    injector: AnomalyInjector, n: int
) -> list[TelemetrySample | None]:
    return [injector.apply(_baseline_sample(seq)) for seq in range(n)]


def test_fibonacci_schedule_seqs_at_10hz():
    sched = fibonacci_schedule(rate_hz=10)
    assert [seq for seq, _ in sched] == [10, 20, 40, 70, 120, 200, 330, 540]


def test_fibonacci_schedule_kinds_rotation():
    sched = fibonacci_schedule(rate_hz=10)
    expected = [
        "battery_cliff", "current_spike", "gps_jump", "motor_overheat",
        "comm_loss", "freefall", "battery_cliff", "current_spike",
    ]
    assert [kind for _, kind in sched] == expected


def test_fibonacci_schedule_scales_with_rate():
    sched = fibonacci_schedule(rate_hz=100)
    assert sched[0] == (100, "battery_cliff")


def test_battery_cliff_drops_5pp():
    injector = AnomalyInjector([(10, "battery_cliff")], rate_hz=10)
    results = _apply_n(injector, 30)
    for seq in range(10, 30):
        assert results[seq] is not None
        assert results[seq]["battery_pct"] <= 75.0


def test_current_spike_three_consecutive():
    injector = AnomalyInjector([(10, "current_spike")], rate_hz=10)
    results = _apply_n(injector, 20)
    for seq in range(10, 14):
        assert results[seq] is not None
        assert results[seq]["current_a"] > 35.0


def test_gps_jump_over_100m():
    injector = AnomalyInjector([(10, "gps_jump")], rate_hz=10, seed=0)
    results = _apply_n(injector, 15)
    pre = results[9]
    jump = results[10]
    assert pre is not None and jump is not None
    dist = _haversine_m(pre["lat"], pre["lon"], jump["lat"], jump["lon"])
    assert dist > 100.0


def test_motor_overheat_above_90():
    injector = AnomalyInjector([(10, "motor_overheat")], rate_hz=10)
    results = _apply_n(injector, 15)
    assert results[10] is not None
    assert max(results[10]["motor_temp_c"]) > 90


def test_comm_loss_drops_samples_for_5s():
    injector = AnomalyInjector([(10, "comm_loss")], rate_hz=10)
    results = _apply_n(injector, 100)
    for seq in range(10, 60):
        assert results[seq] is None
    for seq in list(range(10)) + list(range(60, 100)):
        assert results[seq] is not None


def test_freefall_sustained_1s():
    injector = AnomalyInjector([(10, "freefall")], rate_hz=10)
    results = _apply_n(injector, 30)
    # rate_hz + 2 = 12 ticks → seqs 10..21 all have vertical_speed < -8
    for seq in range(10, 22):
        assert results[seq] is not None
        assert results[seq]["vertical_speed_mps"] < -8.0


def test_apply_returns_unmodified_when_no_anomaly_active():
    injector = AnomalyInjector([], rate_hz=10)
    sample = _baseline_sample(0)
    result = injector.apply(sample)
    assert result is not None
    assert result["battery_pct"] == 80.0
    assert result["current_a"] == 22.0


def test_full_fibonacci_schedule_fires_each_kind():
    schedule = fibonacci_schedule(rate_hz=10)
    injector = AnomalyInjector(schedule, rate_hz=10, seed=1)
    results = _apply_n(injector, 600)

    assert results[10] is not None and results[10]["battery_pct"] <= 75.0
    assert results[20] is not None and results[20]["current_a"] > 35.0
    assert results[40] is not None and (
        results[40]["lat"] != 32.0 or results[40]["lon"] != 35.0
    )
    assert results[70] is not None and max(results[70]["motor_temp_c"]) > 90
    assert results[120] is None  # comm_loss
    assert results[200] is not None and results[200]["vertical_speed_mps"] < -8.0
    assert results[330] is not None and results[330]["battery_pct"] <= 70.0
    assert results[540] is not None and results[540]["current_a"] > 35.0
