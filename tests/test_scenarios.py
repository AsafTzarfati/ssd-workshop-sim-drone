import asyncio

import pytest

from sim.anomalies import AnomalyInjector, fibonacci_schedule
from sim.clock import VirtualClock
from sim.drone import run_merged
from sim.scenarios import merged_scenarios


_SCENARIO_NAMES = ("apollo11", "flag", "heart", "wright")


async def _drive(seed: int = 42, rate_hz: int = 10) -> list[dict]:
    """Run the merged stream end-to-end and return all emitted frames."""
    clock = VirtualClock()
    queue: asyncio.Queue = asyncio.Queue()
    scenarios = merged_scenarios()
    injector = AnomalyInjector(
        fibonacci_schedule(rate_hz), rate_hz=rate_hz, seed=seed ^ 0xA17
    )
    task = asyncio.create_task(
        run_merged(
            clock=clock,
            queue=queue,
            scenarios=scenarios,
            seed=seed,
            rate_hz=rate_hz,
            injector=injector,
        )
    )
    out: list[dict] = []
    try:
        while True:
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


async def test_merged_emits_expected_count() -> None:
    samples = await _drive()
    # apollo11 = 120s × 10Hz = 1200; allow up to 50 dropped samples (comm_loss).
    assert len(samples) >= 1100


async def test_every_frame_has_all_four_sub_objects() -> None:
    samples = await _drive()
    for s in samples:
        for name in _SCENARIO_NAMES:
            assert name in s, f"sub-object '{name}' missing from frame seq={s['seq']}"
            sub = s[name]
            assert isinstance(sub, dict)
            assert isinstance(sub["motor_temp_c"], list) and len(sub["motor_temp_c"]) == 4
            assert sub["flight_mode"] in ("AUTO", "MANUAL", "RTL", "LAND")


async def test_no_maint_mode_in_any_subobject() -> None:
    """Pattern 5 (MAINT-window encoded ASCII) was removed from the sim."""
    samples = await _drive()
    for s in samples:
        for name in _SCENARIO_NAMES:
            assert s[name]["flight_mode"] != "MAINT", (
                f"MAINT mode appeared in '{name}' at seq={s['seq']} — "
                "pattern 5 was supposed to be removed"
            )


async def test_apollo11_subobject_altitude_curve() -> None:
    samples = await _drive()
    alts = [s["apollo11"]["altitude_m"] for s in samples]
    assert max(alts) > 130
    assert max(alts) < 155
    # End of apollo's natural cycle (120s = 1200 seq) should be near zero.
    final_seq = next(s for s in samples[::-1] if s["seq"] >= 1190)
    assert final_seq["apollo11"]["altitude_m"] < 10


async def test_apollo11_subobject_manual_takeover() -> None:
    samples = await _drive()
    modes = [s["apollo11"]["flight_mode"] for s in samples]
    assert "MANUAL" in modes
    first_manual_idx = next(i for i, m in enumerate(modes) if m == "MANUAL")
    # MANUAL fires at seq=1100 (110s × 10Hz). Allow some slop for comm_loss drops.
    assert samples[first_manual_idx]["seq"] >= 1050


async def test_flag_subobject_traces_israeli_flag_bbox() -> None:
    samples = await _drive()
    lats = [s["flag"]["lat"] for s in samples]
    lons = [s["flag"]["lon"] for s in samples]
    # The israeli_flag path is ~500m wide × ~333m tall (1m ≈ 1/111320° at this lat).
    bbox_w_m = (max(lons) - min(lons)) * 111_320 * 0.85  # cos(31.77°) ≈ 0.85
    bbox_h_m = (max(lats) - min(lats)) * 111_320
    assert bbox_w_m > 400
    assert bbox_h_m > 250


async def test_wright_subobject_max_altitude() -> None:
    samples = await _drive()
    alts = [s["wright"]["altitude_m"] for s in samples]
    # Wright hovers at ~3m. Each natural cycle is 12s; in 120s of merged
    # stream it loops 10 times.
    assert 2.0 < max(alts) < 5.0


async def test_window_sha_present_after_buffer_fill() -> None:
    samples = await _drive()
    # First 99 samples may have None; from sample 100 onwards, every emitted
    # frame carries a 64-char hex digest.
    later = [s for s in samples if s["seq"] >= 200]
    assert len(later) > 100
    for s in later[:100]:
        sha = s.get("window_sha256")
        assert sha is not None
        assert len(sha) == 64
        assert all(c in "0123456789abcdef" for c in sha)
