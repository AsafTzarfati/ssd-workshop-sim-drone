import asyncio

from sim.anomalies import AnomalyInjector, fibonacci_schedule
from sim.clock import VirtualClock
from sim.drone import run_merged
from sim.scenarios import merged_scenarios

_SEED = 42
_RATE = 10


async def _collect_with_injector() -> dict[int, dict]:
    """Run the merged stream and index frames by top-level seq.

    Pattern 3 (Fibonacci anomalies) is anchored on the `flag` sub-object,
    so all assertions below read from `f["flag"][...]`."""
    clock = VirtualClock()
    queue: asyncio.Queue = asyncio.Queue()
    scenarios = merged_scenarios()
    injector = AnomalyInjector(
        fibonacci_schedule(_RATE), rate_hz=_RATE, seed=_SEED ^ 0xA17
    )
    await run_merged(
        clock=clock,
        queue=queue,
        scenarios=scenarios,
        seed=_SEED,
        rate_hz=_RATE,
        injector=injector,
    )
    result: dict[int, dict] = {}
    while not queue.empty():
        s = queue.get_nowait()
        result[s["seq"]] = s
    return result


async def test_battery_cliff_at_seq10():
    samples = await _collect_with_injector()
    drop = samples[9]["flag"]["battery_pct"] - samples[10]["flag"]["battery_pct"]
    assert drop > 4.0


async def test_current_spike_at_seq20():
    samples = await _collect_with_injector()
    for seq in range(20, 24):
        assert samples[seq]["flag"]["current_a"] > 35.0


async def test_gps_jump_at_seq40():
    samples = await _collect_with_injector()
    delta = abs(samples[40]["flag"]["lat"] - samples[39]["flag"]["lat"]) + abs(
        samples[40]["flag"]["lon"] - samples[39]["flag"]["lon"]
    )
    assert delta > 0.0005


async def test_motor_overheat_at_seq70():
    samples = await _collect_with_injector()
    assert max(samples[70]["flag"]["motor_temp_c"]) > 90


async def test_comm_loss_drops_50_samples_at_seq120():
    """comm_loss suppresses the entire merged frame, not just the flag sub-object."""
    samples = await _collect_with_injector()
    for seq in range(120, 170):
        assert seq not in samples
    assert 170 in samples


async def test_freefall_at_seq200():
    samples = await _collect_with_injector()
    for seq in range(200, 212):
        assert samples[seq]["flag"]["vertical_speed_mps"] < -8.0
