import asyncio
import json

import websockets

from sim.anomalies import AnomalyInjector, fibonacci_schedule
from sim.clock import Clock
from sim.drone import run_merged


async def serve(
    *,
    host: str = "localhost",
    port: int = 8765,
    clock: Clock,
    scenarios: list,
    seed: int,
    rate_hz: int = 10,
    duration_s: float | None = None,
    anomaly_schedule: list | None = None,
) -> None:
    """Serve a merged telemetry stream over WebSocket.

    All connected clients receive the same broadcast. The drone loop only
    advances while at least one client is connected (the server pauses
    between scenarios so reconnecting clients pick up from seq=0)."""
    queue: asyncio.Queue = asyncio.Queue()
    clients: set = set()
    has_client = asyncio.Event()

    async def handler(ws) -> None:
        clients.add(ws)
        has_client.set()
        try:
            await ws.wait_closed()
        finally:
            clients.discard(ws)
            if not clients:
                has_client.clear()

    async def broadcast() -> None:
        while True:
            await has_client.wait()
            sample = await queue.get()
            if not clients:
                continue
            msg = json.dumps(sample)
            for ws in list(clients):
                try:
                    await ws.send(msg)
                except websockets.ConnectionClosed:
                    clients.discard(ws)

    async with websockets.serve(handler, host, port):
        bcast_task = asyncio.create_task(broadcast())
        try:
            schedule = (
                anomaly_schedule
                if anomaly_schedule is not None
                else fibonacci_schedule(rate_hz)
            )
            injector = AnomalyInjector(schedule, rate_hz=rate_hz, seed=seed ^ 0xA17)
            await run_merged(
                clock=clock,
                queue=queue,
                scenarios=scenarios,
                seed=seed,
                rate_hz=rate_hz,
                duration_s=duration_s,
                injector=injector,
            )
        finally:
            bcast_task.cancel()
