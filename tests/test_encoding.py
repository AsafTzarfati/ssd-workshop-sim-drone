import asyncio

from sim.clock import VirtualClock
from sim.encoding import HIDDEN_MESSAGE, encode, decode
from sim.paths import israeli_flag


def test_encode_round_trip():
    values = encode("HELLO")
    assert decode(values) == "HELLO"


def test_encode_range():
    for v in encode(HIDDEN_MESSAGE):
        assert 65 <= v <= 122


def test_hidden_message_length():
    assert len(HIDDEN_MESSAGE) == 13


async def test_drone_emits_maint_window_with_encoded_char():
    from sim.drone import run_drone

    clock = VirtualClock()
    queue: asyncio.Queue = asyncio.Queue()
    path = israeli_flag()

    # Run just past the first MAINT window (seq 300..309 at 10 Hz = 31 s)
    await run_drone(
        clock=clock,
        path=path,
        queue=queue,
        seed=42,
        duration_s=31.5,
        rate_hz=10,
    )

    samples: dict[int, dict] = {}
    while not queue.empty():
        s = queue.get_nowait()
        samples[s["seq"]] = s

    expected_char = encode(HIDDEN_MESSAGE)[0]  # ord('H') == 72

    # Sample just before the window should still be AUTO
    assert samples[299]["flight_mode"] == "AUTO"

    # All 10 samples in the first MAINT window
    for seq in range(300, 310):
        assert samples[seq]["flight_mode"] == "MAINT"
        assert samples[seq]["motor_temp_c"][3] == expected_char

    # Sample right after the window should be back to AUTO
    assert samples[310]["flight_mode"] == "AUTO"
