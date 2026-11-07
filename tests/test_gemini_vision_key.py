import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "jarvis_ha_control", "app"))

import config  # noqa: E402
from assistant import gemini_engine as ge  # noqa: E402


class Resp:
    text = '{"who":"autre","threat":0,"summary":"ok"}'


class Client:
    def __init__(self, name, fail_with=None):
        self.name, self.fail_with, self.calls = name, fail_with, 0
        outer = self

        class Models:
            async def generate_content(self, **kw):
                outer.calls += 1
                if outer.fail_with:
                    raise outer.fail_with
                return Resp()
        self.aio = type("Aio", (), {"models": Models()})()


def engine(main_client, vision_client=None):
    e = ge.JarvisEngine()
    e.client, e.vision_client = main_client, vision_client
    return e


def test_vision_uses_its_own_key_when_set():
    main, vis = Client("main"), Client("vision")
    asyncio.run(engine(main, vis).describe_image(b"\xff\xd8x", "prompt"))
    assert vis.calls == 1 and main.calls == 0                    # quota séparé : Jarvis n'est pas affamé


def test_vision_falls_back_to_main_key():
    main = Client("main")
    asyncio.run(engine(main).describe_image(b"\xff\xd8x", "prompt"))
    assert main.calls == 1


def test_vision_does_not_retry_on_429(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_FALLBACK_MODEL", "")
    err = ge.errors.APIError(429, {"error": {"message": "quota", "status": "RESOURCE_EXHAUSTED"}})
    vis = Client("vision", fail_with=err)
    try:
        asyncio.run(engine(Client("main"), vis).describe_image(b"\xff\xd8x", "p"))
        raise AssertionError("aurait dû lever GeminiUnavailable")
    except ge.GeminiUnavailable:
        pass
    assert vis.calls == 1                                        # un seul essai (avant : 3 par modèle)


def test_chat_still_retries(monkeypatch):
    async def nosleep(_):
        return None
    monkeypatch.setattr(ge.asyncio, "sleep", nosleep)
    monkeypatch.setattr(config, "GEMINI_FALLBACK_MODEL", "")
    err = ge.errors.APIError(503, {"error": {"message": "busy", "status": "UNAVAILABLE"}})
    main = Client("main", fail_with=err)
    try:
        asyncio.run(engine(main).ask("bonjour"))
    except ge.GeminiUnavailable:
        pass
    assert main.calls == ge.ATTEMPTS                             # le chat garde ses réessais
