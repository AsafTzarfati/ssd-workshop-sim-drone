import asyncio
import json

import websockets

from sim.anomalies import AnomalyInjector, fibonacci_schedule
from sim.clock import Clock
from sim.drone import run_drone


async def serve(
    *,
    host: str = "localhost",
    port: int = 8765,
    clock: Clock,
    path: list[tuple[float, float]],
    seed: int,
    anomaly_schedule: list | None = None,
    **drone_kwargs,
) -> None:
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
            rate_hz = drone_kwargs.get("rate_hz", 10)
            schedule = anomaly_schedule if anomaly_schedule is not None else fibonacci_schedule(rate_hz)
            injector = AnomalyInjector(
                schedule, rate_hz=rate_hz, seed=seed ^ 0xA17
            )
            await run_drone(
                clock=clock, path=path, queue=queue, seed=seed, injector=injector, **drone_kwargs
            )
        finally:
            bcast_task.cancel()
