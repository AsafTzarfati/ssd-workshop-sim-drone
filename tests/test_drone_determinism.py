import asyncio

from sim.clock import VirtualClock
from sim.drone import run_merged
from sim.scenarios import merged_scenarios


async def _collect_first_n(seed: int, n: int) -> list[dict]:
    clock = VirtualClock()
    queue: asyncio.Queue = asyncio.Queue()
    scenarios = merged_scenarios()
    task = asyncio.create_task(
        run_merged(clock=clock, queue=queue, scenarios=scenarios, seed=seed)
    )
    samples: list[dict] = []
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
    assert any(
        a[i]["flag"]["current_a"] != b[i]["flag"]["current_a"] for i in range(50)
    )


async def test_drone_battery_monotonic():
    """Each scenario's battery drains monotonically — checked per sub-object."""
    samples = await _collect_first_n(seed=7, n=200)
    for name in ("apollo11", "flag", "heart", "wright"):
        for i in range(1, len(samples)):
            assert (
                samples[i][name]["battery_pct"] <= samples[i - 1][name]["battery_pct"]
            ), f"battery not monotonic in '{name}' at seq {samples[i]['seq']}"


async def test_merged_frame_shape():
    samples = await _collect_first_n(seed=0, n=1)
    s = samples[0]
    assert s["drone_id"] == "uav-01"
    assert s["seq"] == 0
    for name in ("apollo11", "flag", "heart", "wright"):
        sub = s[name]
        assert sub["flight_mode"] in ("AUTO", "MANUAL", "RTL", "LAND")
        assert isinstance(sub["motor_temp_c"], list)
        assert len(sub["motor_temp_c"]) == 4
        assert all(isinstance(v, int) for v in sub["motor_temp_c"])
