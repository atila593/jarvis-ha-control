import asyncio
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "jarvis_ha_control", "app"))
sys.path.insert(0, os.path.dirname(__file__))

import config  # noqa: E402
from assistant import gemini_engine as ge  # noqa: E402
from autonomy.vision import pause_for  # noqa: E402
from test_gemini_vision_key import Client, engine  # noqa: E402
from test_vision import DAY, Rig, poll  # noqa: E402

BODY_MINUTE = {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "message": "Quota exceeded for metric: requests per minute, limit: 5",
                         "details": [{"@type": "type.googleapis.com/google.rpc.QuotaFailure",
                                      "violations": [{"quotaMetric": "generate_content_free_tier_requests",
                                                      "quotaId": "GenerateRequestsPerMinutePerProjectPerModel-FreeTier"}]},
                                     {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "37s"}]}}
BODY_DAY = {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "message": "Quota exceeded: requests per day, limit: 20",
                      "details": [{"@type": "type.googleapis.com/google.rpc.QuotaFailure",
                                   "violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]}]}}


def test_quota_info_parses_google_429():
    retry, quota, msg = ge.quota_info(ge.errors.APIError(429, BODY_MINUTE))
    assert retry == 37 and "PerMinute" in quota and "per minute" in msg
    retry, quota, _ = ge.quota_info(ge.errors.APIError(429, BODY_DAY))
    assert retry is None and "PerDay" in quota
    assert ge.quota_info(ge.errors.APIError(500, {})) == (None, None, "")      # corps vide : jamais d'exception


def test_pause_depends_on_what_google_says():
    class E(Exception):
        pass
    mk = lambda **kw: type("X", (Exception,), kw)()  # noqa: E731
    assert pause_for(mk(quota="GenerateRequestsPerDayPerProjectPerModel-FreeTier", retry_after=5))[0] == 3600
    secs, label = pause_for(mk(quota="GenerateRequestsPerMinutePerProjectPerModel-FreeTier", retry_after=37))
    assert secs == 42 and "minute" in label
    assert pause_for(mk(quota=None, retry_after=1))[0] == 30           # plancher
    assert pause_for(mk(quota=None, retry_after=99999))[0] == 3600     # plafond
    assert pause_for(E())[0] == 600                                     # aucune info : 10 min


def test_error_reaches_the_exception_and_the_journal(tmp_path):
    err = ge.errors.APIError(429, BODY_DAY)
    cli = Client("v", fail_with=err)
    e = engine(Client("m"), cli)
    config.GEMINI_FALLBACK_MODEL = ""
    try:
        asyncio.run(e.describe_image(b"\xff\xd8x", "p"))
        raise AssertionError
    except ge.GeminiUnavailable as ex:
        assert "PerDay" in ex.quota and "limit: 20" in ex.detail
        captured = ex

    r = Rig(tmp_path, DAY); r.ev(1)

    async def describe(img, prompt):
        raise captured
    r.v.describe = describe
    assert poll(r) == []
    msg = [j["message"] for j in r.v.store.journal() if j["kind"] == "vision"][0]
    assert "quota JOURNALIER épuisé" in msg and "limit: 20" in msg and "Pause de 60 min" in msg
    assert r.v._pause_until - DAY.timestamp() == 3600


def test_vision_model_option_overrides_models(monkeypatch):
    monkeypatch.setattr(config, "VISION_MODEL", "gemini-lite-test")
    used = []
    cli = Client("v")
    orig = cli.aio.models.generate_content

    async def spy(**kw):
        used.append(kw["model"])
        return await orig(**kw)
    cli.aio.models.generate_content = spy
    asyncio.run(engine(Client("m"), cli).describe_image(b"\xff\xd8x", "p"))
    assert used == ["gemini-lite-test"]
    monkeypatch.setattr(config, "VISION_MODEL", "")
    used.clear()
    asyncio.run(engine(Client("m"), cli).describe_image(b"\xff\xd8x", "p"))
    assert used == [config.GEMINI_MODEL]            # sans option : modèle principal (puis secours si échec)
