import asyncio

import pytest

from sim.anomalies import AnomalyInjector
from sim.clock import VirtualClock
from sim.drone import run_drone
from sim.scenarios import SCENARIOS, Scenario


async def _drive(sc: Scenario, n_samples: int | None = None, seed: int = 42) -> list[dict]:
    """Run the scenario; collect up to n_samples (or to completion if None)."""
    clock = VirtualClock()
    queue: asyncio.Queue = asyncio.Queue()
    injector = AnomalyInjector(
        sc.anomaly_schedule_factory(10), rate_hz=10, seed=seed ^ 0xA17
    )
    task = asyncio.create_task(
        run_drone(
            clock=clock,
            path=sc.path,
            queue=queue,
            seed=seed,
            injector=injector,
            duration_s=sc.duration_s,
            takeoff_duration_s=sc.takeoff_duration_s,
            landing_duration_s=sc.landing_duration_s,
            cruise_altitude_m=sc.cruise_altitude_m,
            altitude_profile=sc.altitude_profile,
            mode_schedule=sc.mode_schedule,
        )
    )
    out: list[dict] = []
    try:
        while n_samples is None or len(out) < n_samples:
            if task.done() and queue.empty():
                break
            try:
                out.append(await asyncio.wait_for(queue.get(), timeout=2.0))
            except asyncio.TimeoutError:
                if task.done():
                    break
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    return out


@pytest.mark.parametrize("name,min_samples", [
    ("flag", 540),    # 600 seq − up to 50 comm_loss suppressed + margin
    ("heart", 540),
    ("apollo11", 600),
    ("wright", 100),
])
async def test_scenario_emits_expected_count(name: str, min_samples: int) -> None:
    sc = SCENARIOS[name]()
    samples = await _drive(sc)
    assert len(samples) >= min_samples


async def test_apollo11_altitude_curve() -> None:
    sc = SCENARIOS["apollo11"]()
    samples = await _drive(sc)
    alts = [s["altitude_m"] for s in samples]
    assert max(alts) > 130, f"peak altitude too low: {max(alts)}"
    assert max(alts) < 155, f"peak altitude too high: {max(alts)}"
    assert alts[-1] < 10, f"did not descend to near-zero: {alts[-1]}"
    assert alts[0] > alts[-1], "altitude did not decrease over flight"
    # verify overall monotonic-ish descent: altitude at 25/50/75% waypoints decreases
    q25 = alts[len(alts) // 4]
    q50 = alts[len(alts) // 2]
    q75 = alts[3 * len(alts) // 4]
    assert alts[0] > q25 > q50 > q75 > alts[-1], "altitude not decreasing through quarters"


async def test_apollo11_manual_takeover() -> None:
    sc = SCENARIOS["apollo11"]()
    samples = await _drive(sc)
    modes = [s["flight_mode"] for s in samples]
    assert "MANUAL" in modes, "MANUAL mode never appeared"
    first_manual = next(i for i, m in enumerate(modes) if m == "MANUAL")
    assert first_manual >= 1050, f"MANUAL appeared too early at seq {first_manual}"


async def test_apollo11_1202_current_spike() -> None:
    sc = SCENARIOS["apollo11"]()
    samples = await _drive(sc)
    by_seq = {s["seq"]: s for s in samples}
    window = [by_seq[seq] for seq in range(595, 615) if seq in by_seq]
    assert any(s["current_a"] > 35 for s in window), (
        "no current spike found around seq 600 (1202 alarm)"
    )


async def test_wright_max_altitude() -> None:
    sc = SCENARIOS["wright"]()
    samples = await _drive(sc)
    alts = [s["altitude_m"] for s in samples]
    assert 2.0 < max(alts) < 5.0, f"wright max altitude unexpected: {max(alts)}"


async def test_all_scenarios_valid_schema() -> None:
    for name, factory in SCENARIOS.items():
        sc = factory()
        samples = await _drive(sc, 10)
        assert len(samples) >= 1, f"scenario {name} emitted no samples"
        for s in samples:
            assert s["drone_id"] == "uav-01"
            assert isinstance(s["motor_temp_c"], list)
            assert len(s["motor_temp_c"]) == 4
            assert all(isinstance(v, int) for v in s["motor_temp_c"])
            assert s["flight_mode"] in ("AUTO", "MANUAL", "RTL", "LAND", "MAINT")
