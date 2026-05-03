import asyncio
import re

from sim.clock import VirtualClock
from sim.drone import run_merged
from sim.scenarios import merged_scenarios
from sim.window import WINDOW_SIZE, WindowHasher


HEX_64 = re.compile(r"^[a-f0-9]{64}$")


def _stub_subframe(seq_offset: int) -> dict:
    return {
        "altitude_m": 140.0 + seq_offset * 0.01,
        "vertical_speed_mps": 0.0,
        "current_a": 22.0,
        "battery_pct": 80.0,
        "motor_temp_c": [70, 71, 72, 73],
        "lat": 31.77,
        "lon": 35.21,
        "flight_mode": "AUTO",
    }


def _stub_merged(seq: int) -> dict:
    return {
        "drone_id": "uav-01",
        "seq": seq,
        "ts": 0.123456789,
        "apollo11": _stub_subframe(seq),
        "flag": _stub_subframe(seq + 1),
        "heart": _stub_subframe(seq + 2),
        "wright": _stub_subframe(seq + 3),
    }


def test_hasher_returns_none_until_window_full():
    h = WindowHasher()
    for i in range(WINDOW_SIZE - 1):
        assert h.update(_stub_merged(i)) is None
    digest = h.update(_stub_merged(WINDOW_SIZE - 1))
    assert digest is not None
    assert HEX_64.match(digest)


def test_hasher_independent_of_ts():
    a = WindowHasher()
    b = WindowHasher()
    for i in range(WINDOW_SIZE):
        s_a = _stub_merged(i)
        s_b = _stub_merged(i)
        s_b["ts"] = 999_999.0
        digest_a = a.update(s_a)
        digest_b = b.update(s_b)
    assert digest_a is not None
    assert digest_a == digest_b


def test_hasher_changes_when_nested_payload_changes():
    a = WindowHasher()
    b = WindowHasher()
    for i in range(WINDOW_SIZE):
        s_a = _stub_merged(i)
        s_b = _stub_merged(i)
        if i == WINDOW_SIZE - 1:
            s_b["flag"]["altitude_m"] = 1000.0
        digest_a = a.update(s_a)
        digest_b = b.update(s_b)
    assert digest_a != digest_b


async def _emit_n_with_hasher(seed: int, n: int) -> list[dict]:
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


async def test_drone_emits_window_sha_after_window_size():
    samples = await _emit_n_with_hasher(seed=42, n=WINDOW_SIZE + 5)
    for i in range(WINDOW_SIZE - 1):
        assert samples[i]["window_sha256"] is None
    for i in range(WINDOW_SIZE - 1, len(samples)):
        sha = samples[i]["window_sha256"]
        assert sha is not None
        assert HEX_64.match(sha)


async def test_drone_window_sha_deterministic_across_runs():
    a = await _emit_n_with_hasher(seed=42, n=WINDOW_SIZE + 10)
    b = await _emit_n_with_hasher(seed=42, n=WINDOW_SIZE + 10)
    a_shas = [s["window_sha256"] for s in a if s["window_sha256"] is not None]
    b_shas = [s["window_sha256"] for s in b if s["window_sha256"] is not None]
    assert a_shas == b_shas
    assert len(a_shas) > 0
