import time

from sim.clock import RealClock, VirtualClock


async def test_virtual_clock_advances_deterministically():
    c = VirtualClock()
    assert c.now() == 0.0
    await c.sleep(1.5)
    await c.sleep(0.25)
    assert c.now() == 1.75


async def test_virtual_clock_sleep_returns_immediately():
    c = VirtualClock()
    wall_start = time.monotonic()
    await c.sleep(60.0)
    elapsed = time.monotonic() - wall_start
    assert elapsed < 0.05
    assert c.now() == 60.0


async def test_real_clock_now_is_wall_time():
    c = RealClock()
    assert abs(c.now() - time.time()) < 0.1
