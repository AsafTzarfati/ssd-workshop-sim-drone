import asyncio
import json

import websockets


async def _main() -> None:
    async with websockets.connect("ws://localhost:8765") as ws:
        samples = [json.loads(await ws.recv()) for _ in range(50)]

    assert [s["seq"] for s in samples] == list(range(50)), "seq must be 0..49"
    assert len({(s["lat"], s["lon"]) for s in samples}) >= 4, "drone not moving"
    for s in samples:
        assert isinstance(s["drone_id"], str)
        assert isinstance(s["motor_temp_c"], list)
        assert len(s["motor_temp_c"]) == 4
        assert all(isinstance(v, int) for v in s["motor_temp_c"])

    print("smoke ok")


asyncio.run(_main())
