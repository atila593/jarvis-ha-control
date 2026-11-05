import asyncio
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "jarvis_ha_control", "app"))

from autonomy import rules  # noqa: E402
from autonomy.store import Store  # noqa: E402
from autonomy.vision import Vision, VisionSettings, parse_verdict, severity_for  # noqa: E402

TZ = ZoneInfo("Europe/Brussels")
NIGHT = datetime(2026, 11, 5, 2, 30, tzinfo=TZ)
DAY = datetime(2026, 11, 5, 14, 0, tzinfo=TZ)
Q = (rules.time(23, 0), rules.time(7, 0))


def run(c):
    return asyncio.run(c)


class Rig:
    def __init__(self, tmp_path, now, **kw):
        self.events, self.calls, self.verdict, self.down = [], [], '{"who":"inconnu","threat":0,"summary":"Un homme passe."}', False
        self.now = now
        s = VisionSettings(enabled=True, frigate_url="http://frigate:5000", **kw)
        self.v = Vision(Store(str(tmp_path / "v.db")), s, *Q, get_json=self.get_json, get_bytes=self.get_bytes, describe=self.describe)

    async def get_json(self, url, params):
        if self.down:
            raise ConnectionError("injoignable")
        return [e for e in self.events if e["start_time"] > params["after"]]

    async def get_bytes(self, url):
        return b"\xff\xd8img"

    async def describe(self, img, prompt):
        self.calls.append(prompt)
        return self.verdict

    def ev(self, i, cam="porte_entree", label="person", t=None, **kw):
        t = t or (self.now.timestamp() - 60 + i)
        self.events.append({"id": f"e{i}", "camera": cam, "label": label, "start_time": t, **kw})


def poll(r):
    return run(r.v.poll(r.now))


def test_parse_verdict_tolerates_noise():
    assert parse_verdict('```json\n{"who":"livreur","threat":0,"summary":"Livraison"}\n```')["who"] == "livreur"
    assert parse_verdict("n'importe quoi")["threat"] == 1                    # illisible -> à vérifier, jamais « tout va bien »
    assert parse_verdict('{"threat": 9, "summary": "x"}')["threat"] == 2     # borné


def test_severity_mapping():
    v = lambda who, t: {"who": who, "threat": t}  # noqa: E731
    assert severity_for(v("livreur", 0), night=False) == "minor"
    assert severity_for(v("inconnu", 0), night=False) == "minor"
    assert severity_for(v("inconnu", 0), night=True) == "important"
    assert severity_for(v("inconnu", 1), night=False) == "important"
    assert severity_for(v("inconnu", 2), night=False) == "important"        # jamais d'urgence de jour sur la foi d'une IA
    assert severity_for(v("inconnu", 2), night=True) == "urgent"


def test_event_analysed_once_and_not_replayed(tmp_path):
    r = Rig(tmp_path, DAY); r.ev(1)
    out = poll(r)
    assert len(out) == 1 and out[0].severity == "minor" and "Un homme passe" in out[0].message
    assert poll(r) == [] and len(r.calls) == 1                               # déjà vu


def test_known_person_costs_no_quota(tmp_path):
    r = Rig(tmp_path, DAY); r.ev(1, sub_label=["Sarah", 0.93])
    out = poll(r)
    assert out[0].severity == "minor" and "Sarah" in out[0].message
    assert r.calls == [] and r.v.used_today(DAY) == 0


def test_labels_and_cameras_filter(tmp_path):
    r = Rig(tmp_path, DAY, cameras=["porte_entree"]); r.ev(1, label="car"); r.ev(2, cam="garage"); r.ev(3)
    out = poll(r)
    assert len(out) == 1 and len(r.calls) == 1


def test_cooldown_per_camera(tmp_path):
    r = Rig(tmp_path, DAY, cooldown_min=5); r.ev(1); r.ev(2)                 # 1 s d'écart, même caméra
    assert len(poll(r)) == 1 and len(r.calls) == 1


def test_daily_budget_stops_analyses_and_logs_once(tmp_path):
    r = Rig(tmp_path, DAY, daily_budget=2, cooldown_min=0)
    for i in range(1, 6):
        r.ev(i, cam=f"cam{i}")
    out = poll(r)
    assert len(out) == 2 and len(r.calls) == 2
    logs = [j for j in r.v.store.journal() if "Budget" in j["message"]]
    assert len(logs) == 1


def test_night_unknown_is_important_and_prompt_forbids_face_id(tmp_path):
    r = Rig(tmp_path, NIGHT); r.ev(1)
    out = poll(r)
    assert out[0].severity == "important"
    assert "identifier une personne par son visage" in r.calls[0]


def test_frigate_down_is_logged_once_then_recovers(tmp_path):
    r = Rig(tmp_path, DAY); r.down = True
    assert poll(r) == [] and poll(r) == []
    assert len([j for j in r.v.store.journal() if "injoignable" in j["message"]]) == 1
    r.down = False; r.ev(1)
    assert len(poll(r)) == 1
    assert any("de nouveau joignable" in j["message"] for j in r.v.store.journal())


def test_disabled_does_nothing(tmp_path):
    r = Rig(tmp_path, DAY); r.v.s.enabled = False; r.ev(1)
    assert poll(r) == [] and r.calls == []
