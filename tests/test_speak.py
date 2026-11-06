import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "jarvis_ha_control", "app"))

import config  # noqa: E402
import httpx  # noqa: E402
from tools import speak as speak_mod  # noqa: E402


def capture(monkeypatch, status=200):
    sent = {}

    class Fake(httpx.AsyncClient):
        async def post(self, url, headers=None, json=None, **kw):
            sent.update(url=url, json=json)
            return httpx.Response(status, request=httpx.Request("POST", url), json=[])
    monkeypatch.setattr(speak_mod.httpx, "AsyncClient", Fake)
    return sent


def test_chime_tts_direct_payload_is_fully_explicit(monkeypatch):
    sent = capture(monkeypatch)
    monkeypatch.setattr(config, "SPEAK_SERVICE", "chime_tts.say")
    monkeypatch.setattr(config, "SPEAK_TARGETS", ["media_player.salle_a_manger"])
    monkeypatch.setattr(config, "SPEAK_TTS_PLATFORM", "tts.piper")
    monkeypatch.setattr(config, "SPEAK_LANGUAGE", "fr_FR")
    monkeypatch.setattr(config, "SPEAK_VOICE", "fr_FR-tom-medium")
    assert asyncio.run(speak_mod.speak("Bonjour"))["spoken"] is True
    assert sent["url"].endswith("/services/chime_tts/say")
    assert sent["json"] == {"message": "Bonjour", "tts_platform": "tts.piper", "language": "fr_FR",
                            "options": {"voice": "fr_FR-tom-medium"}, "entity_id": ["media_player.salle_a_manger"]}
    assert "tld" not in sent["json"]


def test_notify_services_keep_their_old_payload(monkeypatch):
    sent = capture(monkeypatch)
    monkeypatch.setattr(config, "SPEAK_SERVICE", "notify.jarvis")
    monkeypatch.setattr(config, "SPEAK_TARGETS", ["media_player.salle_a_manger"])
    asyncio.run(speak_mod.speak("Bonjour"))
    assert sent["json"] == {"message": "Bonjour", "target": ["media_player.salle_a_manger"]}


def test_failure_is_reported_not_raised(monkeypatch):
    capture(monkeypatch, status=500)
    monkeypatch.setattr(config, "SPEAK_SERVICE", "chime_tts.say")
    r = asyncio.run(speak_mod.speak("x"))
    assert r["spoken"] is False and "500" in r["reason"]
