import asyncio

from sim.clock import VirtualClock
from sim.drone import run_drone
from sim.paths import israeli_flag


async def _collect_first_n(seed: int, n: int) -> list[dict]:
    clock = VirtualClock()
    queue: asyncio.Queue = asyncio.Queue()
    path = israeli_flag()
    task = asyncio.create_task(
        run_drone(clock=clock, path=path, queue=queue, seed=seed)
    )
    samples = []
    for _ in range(n):
        samples.append(await queue.get())
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    return samples


async def test_drone_determinism():
    a = await _collect_first_n(seed=42, n=100)
    b = await _collect_first_n(seed=42, n=100)
    assert a == b
    assert len(a) == 100
    assert a[0]["seq"] == 0
    assert a[-1]["seq"] == 99


async def test_drone_different_seeds_diverge():
    a = await _collect_first_n(seed=1, n=50)
    b = await _collect_first_n(seed=2, n=50)
    assert any(a[i]["current_a"] != b[i]["current_a"] for i in range(50))


async def test_drone_battery_monotonic():
    samples = await _collect_first_n(seed=7, n=200)
    for i in range(1, len(samples)):
        assert samples[i]["battery_pct"] <= samples[i - 1]["battery_pct"]


async def test_drone_sample_shape():
    samples = await _collect_first_n(seed=0, n=1)
    s = samples[0]
    assert s["drone_id"] == "uav-01"
    assert s["flight_mode"] == "AUTO"
    assert isinstance(s["motor_temp_c"], list)
    assert len(s["motor_temp_c"]) == 4
    assert all(isinstance(v, int) for v in s["motor_temp_c"])
