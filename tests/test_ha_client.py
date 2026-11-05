import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "jarvis_ha_control", "app"))

import pytest  # noqa: E402
import websockets  # noqa: E402

from autonomy.ha import HaClient, HaError  # noqa: E402


async def fake_ha(sock):
    await sock.send(json.dumps({"type": "auth_required"}))
    auth = json.loads(await sock.recv())
    if auth.get("access_token") != "good":
        await sock.send(json.dumps({"type": "auth_invalid"}))
        return
    await sock.send(json.dumps({"type": "auth_ok"}))
    cmd = json.loads(await sock.recv())
    await sock.send(json.dumps({"type": "event", "id": 99}))                      # bruit à ignorer
    if cmd["type"] == "boom":
        await sock.send(json.dumps({"id": cmd["id"], "type": "result", "success": False, "error": {"message": "refusé"}}))
    else:
        await sock.send(json.dumps({"id": cmd["id"], "type": "result", "success": True, "result": {"echo": cmd}}))


async def _with_server(fn):
    async with websockets.serve(fake_ha, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        return await fn(f"ws://127.0.0.1:{port}")


def test_ws_roundtrip_and_errors():
    async def go(url):
        ok = await HaClient("http://x", url, "good").ws("config/entity_registry/get", entity_id="sensor.a")
        assert ok["echo"]["entity_id"] == "sensor.a"
        with pytest.raises(HaError, match="refusé"):
            await HaClient("http://x", url, "good").ws("boom")
        with pytest.raises(HaError, match="Authentification"):
            await HaClient("http://x", url, "bad").ws("x")
    asyncio.run(_with_server(go))
