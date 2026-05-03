import asyncio
import json
import socket

import websockets

from sim.clock import RealClock
from sim.scenarios import merged_scenarios
from sim.server import serve


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def _connect_with_retry(url: str, attempts: int = 40, delay: float = 0.025):
    last: Exception | None = None
    for _ in range(attempts):
        try:
            return await websockets.connect(url)
        except (OSError, ConnectionRefusedError) as e:
            last = e
            await asyncio.sleep(delay)
    raise RuntimeError(f"could not connect to {url}: {last}")


async def test_ws_handshake_and_first_10_merged_frames():
    port = _free_port()
    server_task = asyncio.create_task(
        serve(
            host="127.0.0.1",
            port=port,
            clock=RealClock(),
            scenarios=merged_scenarios(),
            seed=42,
            rate_hz=1000,
            duration_s=2.0,
        )
    )
    try:
        ws = await _connect_with_retry(f"ws://127.0.0.1:{port}")
        try:
            samples = [json.loads(await ws.recv()) for _ in range(10)]
        finally:
            await ws.close()

        assert [s["seq"] for s in samples] == list(range(10))
        for s in samples:
            assert s["drone_id"] == "uav-01"
            for name in ("apollo11", "flag", "heart", "wright"):
                sub = s[name]
                assert sub["flight_mode"] in ("AUTO", "MANUAL", "RTL", "LAND")
                assert isinstance(sub["motor_temp_c"], list)
                assert len(sub["motor_temp_c"]) == 4
                assert isinstance(sub["lat"], float)
                assert isinstance(sub["lon"], float)
    finally:
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass


async def test_seq_contiguous_after_buffered_start():
    """Client connects after server has been running; buffered samples replay from seq=0."""
    port = _free_port()
    server_task = asyncio.create_task(
        serve(
            host="127.0.0.1",
            port=port,
            clock=RealClock(),
            scenarios=merged_scenarios(),
            seed=1,
            rate_hz=1000,
            duration_s=2.0,
        )
    )
    try:
        await asyncio.sleep(0.1)
        ws = await _connect_with_retry(f"ws://127.0.0.1:{port}")
        try:
            samples = [json.loads(await ws.recv()) for _ in range(50)]
        finally:
            await ws.close()
        assert [s["seq"] for s in samples] == list(range(50))
    finally:
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass
