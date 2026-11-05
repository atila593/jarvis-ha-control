import asyncio
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "jarvis_ha_control", "app"))
sys.path.insert(0, os.path.dirname(__file__))

from autonomy import rules  # noqa: E402
from autonomy.engine import AutonomyEngine, Settings  # noqa: E402
from autonomy.store import Store  # noqa: E402
from autonomy.vision import Vision, VisionSettings  # noqa: E402
from test_vision import Rig  # noqa: E402

TZ = ZoneInfo("Europe/Brussels")


def run(c):
    return asyncio.run(c)


def build(tmp_path, now, handlers=None, vision=None):
    spoken, notified = [], []

    async def fetch():
        return []

    async def execute(*a):
        return "OK"

    async def speak(t):
        spoken.append(t)

    async def notify(a, b):
        notified.append(b)

    async def report():
        return ""

    async def local_now():
        return now
    e = AutonomyEngine(Store(str(tmp_path / "e.db")), Settings(), rules.Params(), fetch_states=fetch, execute=execute,
                       speak=speak, notify=notify, report=report, local_now=local_now, handlers=handlers, vision=vision)
    return e, spoken, notified


def test_proposal_dispatch_by_type_and_unknown_type_is_refused(tmp_path):
    calls = []

    async def h(action):
        calls.append(action["x"])
        return "OK : fait"
    e, _, _ = build(tmp_path, datetime.now(TZ), handlers={"config_change": h})
    ok = e.store.add_proposal("engineer", "automation.a", "Créer a", {"type": "config_change", "x": 1}, None)
    bad = e.store.add_proposal("engineer", "x", "?", {"type": "reformat_disk"}, None)
    boom = e.store.add_proposal("engineer", "y", "?", {"type": "config_change", "x": 2}, None)
    assert run(e.decide(ok, True, "o"))["status"] == "executed" and calls == [1]
    r = run(e.decide(bad, True, "o"))
    assert r["status"] == "failed" and "inconnu" in r["result"]
    assert e.store.get_proposal(bad)["status"] == "failed"

    async def crash(action):
        raise RuntimeError("kaboom")
    e.handlers["config_change"] = crash
    assert run(e.decide(boom, True, "o"))["status"] == "failed"          # une exception ne fait pas tomber le moteur


def test_vision_findings_are_announced_through_the_loop(tmp_path):
    day = datetime(2026, 11, 5, 14, 0, tzinfo=TZ)
    rig = Rig(tmp_path, day)
    rig.verdict = '{"who":"inconnu","threat":1,"summary":"Quelqu\'un regarde par la fenêtre."}'
    rig.ev(1)
    e, spoken, notified = build(tmp_path, day, vision=rig.v)
    run(e.tick())
    assert any("regarde par la fenêtre" in s for s in spoken) and notified
    assert any(j["kind"] == "vision" and j["severity"] == "important" for j in e.store.journal())


def test_vision_crash_does_not_stop_rules(tmp_path):
    day = datetime(2026, 11, 5, 14, 0, tzinfo=TZ)

    async def boom(*a):
        raise RuntimeError("frigate cassé")
    v = Vision(Store(str(tmp_path / "v.db")), VisionSettings(enabled=True, frigate_url="http://x"), rules.time(23), rules.time(7),
               get_json=boom, get_bytes=boom, describe=boom)
    v.poll = boom
    e, _, _ = build(tmp_path, day, vision=v)
    run(e.tick())
    assert e.last_tick is not None
