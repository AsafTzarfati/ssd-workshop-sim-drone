import asyncio

from sim.anomalies import AnomalyInjector, fibonacci_schedule
from sim.clock import VirtualClock
from sim.drone import run_drone
from sim.paths import israeli_flag

_SEED = 42
_RATE = 10


async def _collect_with_injector() -> dict[int, dict]:
    clock = VirtualClock()
    queue: asyncio.Queue = asyncio.Queue()
    path = israeli_flag()
    injector = AnomalyInjector(
        fibonacci_schedule(_RATE), rate_hz=_RATE, seed=_SEED ^ 0xA17
    )
    await run_drone(
        clock=clock,
        path=path,
        queue=queue,
        seed=_SEED,
        injector=injector,
        duration_s=60.0,
        rate_hz=_RATE,
    )
    result: dict[int, dict] = {}
    while not queue.empty():
        s = queue.get_nowait()
        result[s["seq"]] = s
    return result


async def test_battery_cliff_at_seq10():
    samples = await _collect_with_injector()
    assert samples[9]["battery_pct"] - samples[10]["battery_pct"] > 4.0


async def test_current_spike_at_seq20():
    samples = await _collect_with_injector()
    for seq in range(20, 24):
        assert samples[seq]["current_a"] > 35.0


async def test_gps_jump_at_seq40():
    samples = await _collect_with_injector()
    delta = abs(samples[40]["lat"] - samples[39]["lat"]) + abs(
        samples[40]["lon"] - samples[39]["lon"]
    )
    assert delta > 0.0005


async def test_motor_overheat_at_seq70():
    samples = await _collect_with_injector()
    assert max(samples[70]["motor_temp_c"]) > 90


async def test_comm_loss_drops_50_samples_at_seq120():
    samples = await _collect_with_injector()
    for seq in range(120, 170):
        assert seq not in samples
    assert 170 in samples


async def test_freefall_at_seq200():
    samples = await _collect_with_injector()
    for seq in range(200, 212):
        assert samples[seq]["vertical_speed_mps"] < -8.0
