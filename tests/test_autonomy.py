import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

os.environ["JARVIS_DEV"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "jarvis_ha_control", "app"))

import pytest  # noqa: E402

from autonomy import rules  # noqa: E402
from autonomy.engine import AutonomyEngine, Settings  # noqa: E402
from autonomy.store import Store  # noqa: E402

TZ = ZoneInfo("Europe/Brussels")
NIGHT = datetime(2026, 11, 4, 2, 30, tzinfo=TZ)
DAY = datetime(2026, 11, 4, 14, 0, tzinfo=TZ)


def st(eid, state, minutes_ago=0, now=NIGHT, **attrs):
    ts = (now.astimezone(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()
    return {"entity_id": eid, "state": state, "last_changed": ts, "attributes": attrs}


def test_window_wraps_midnight():
    s, e = rules.time(23, 0), rules.time(7, 0)
    assert rules.in_window(rules.time(2, 0), s, e)
    assert rules.in_window(rules.time(23, 30), s, e)
    assert not rules.in_window(rules.time(12, 0), s, e)


def test_garage_open_night_vs_day():
    garage = st("cover.porte_garage", "open", 15, friendly_name="Porte garage")
    assert [f.rule for f in rules.evaluate([garage], NIGHT, rules.Params())] == ["garage_open"]
    # 15 min ouverte en journée : normal (seuil 60 min)
    day_garage = st("cover.porte_garage", "open", 15, now=DAY, friendly_name="Porte garage")
    assert rules.evaluate([day_garage], DAY, rules.Params()) == []
    day_long = st("cover.porte_garage", "open", 90, now=DAY, friendly_name="Porte garage")
    f = rules.evaluate([day_long], DAY, rules.Params())[0]
    assert f.action == {"domain": "cover", "service": "close_cover", "entity_id": "cover.porte_garage"}
    assert f.severity == "important"


def test_safety_sensor_is_urgent_and_has_no_action():
    s = st("binary_sensor.fuite_cuisine", "on", device_class="moisture", friendly_name="Fuite cuisine")
    f = rules.evaluate([s], DAY, rules.Params())[0]
    assert f.severity == "urgent" and f.action is None and "fuite d'eau" in f.message


def test_system_high_ignores_swap_and_battery():
    states = [
        st("sensor.localhost_utilisation_disque_data", "97", unit_of_measurement="%", friendly_name="Disque"),
        st("sensor.localhost_utilisation_de_l_espace_d_echange", "99", unit_of_measurement="%"),
        st("sensor.localhost_batterie", "99", unit_of_measurement="%", device_class="battery"),
        st("sensor.localhost_temperature_package_id_0", "88", unit_of_measurement="°C", friendly_name="CPU"),
    ]
    got = sorted(f.entity_id for f in rules.evaluate(states, DAY, rules.Params()))
    assert got == ["sensor.localhost_temperature_package_id_0", "sensor.localhost_utilisation_disque_data"]


def test_hidden_and_disabled_rules():
    s = st("binary_sensor.fumee", "on", device_class="smoke", friendly_name="Fumée")
    assert rules.evaluate([s], DAY, rules.Params(hidden=["binary_sensor.fumee"])) == []
    assert rules.evaluate([s], DAY, rules.Params(enabled=["garage_open"])) == []


def test_watched_unavailable_only_after_delay():
    p = rules.Params(watched=["light.cuisine"])
    assert rules.evaluate([st("light.cuisine", "unavailable", 5, now=DAY)], DAY, p) == []
    f = rules.evaluate([st("light.cuisine", "unavailable", 45, now=DAY)], DAY, p)[0]
    assert f.severity == "minor"


# ---------------------------------------------------------------- moteur
class Fake:
    def __init__(self):
        self.states, self.spoken, self.notified, self.executed = [], [], [], []
        self.now = NIGHT
        self.exec_result = "OK : cover.close_cover exécuté."

    async def fetch(self):
        return self.states

    async def execute(self, d, s, e):
        self.executed.append((d, s, e))
        return self.exec_result

    async def speak(self, t):
        self.spoken.append(t)

    async def notify(self, title, msg):
        self.notified.append((title, msg))

    async def report(self):
        return "Tout est nominal."

    async def local_now(self):
        return self.now


def make(tmp_path, fake, **kw):
    settings = Settings(enabled=True, **kw)
    return AutonomyEngine(Store(str(tmp_path / "t.db")), settings, rules.Params(), fetch_states=fake.fetch,
                          execute=fake.execute, speak=fake.speak, notify=fake.notify, report=fake.report,
                          local_now=fake.local_now)


def run(coro):
    return asyncio.run(coro)


def garage_open(now, minutes=20):
    return st("cover.porte_garage", "open", minutes, now=now, friendly_name="Porte garage")


def test_important_creates_one_proposal_and_stays_quiet_at_night(tmp_path):
    f = Fake(); f.states = [garage_open(NIGHT)]
    e = make(tmp_path, f)
    run(e.tick()); run(e.tick()); run(e.tick())          # 3 passages : une seule proposition, une seule annonce
    assert len(e.store.proposals("pending")) == 1
    assert f.spoken == []                                 # nuit : important ne parle pas
    assert len(f.notified) == 1                           # mais notifie
    assert f.executed == []                               # jamais d'action sans validation


def test_important_speaks_in_daytime(tmp_path):
    f = Fake(); f.now = DAY; f.states = [garage_open(DAY, 90)]
    e = make(tmp_path, f); run(e.tick())
    assert len(f.spoken) == 1 and "valide" in f.spoken[0].lower()


def test_approve_executes_and_checks_state(tmp_path):
    f = Fake(); f.states = [garage_open(NIGHT)]
    e = make(tmp_path, f, approvers=["Olivier"]); run(e.tick())
    pid = e.store.proposals("pending")[0]["id"]
    assert run(e.decide(pid, True, "Sarah"))["code"] == 403          # seul Olivier
    assert f.executed == []
    res = run(e.decide(pid, True, "olivier"))
    assert res["status"] == "executed" and f.executed == [("cover", "close_cover", "cover.porte_garage")]
    assert run(e.decide(pid, True, "Olivier"))["code"] == 409        # pas deux fois


def test_proposal_becomes_obsolete_if_state_changed(tmp_path):
    f = Fake(); f.states = [garage_open(NIGHT)]
    e = make(tmp_path, f); run(e.tick())
    pid = e.store.proposals("pending")[0]["id"]
    f.states = [st("cover.porte_garage", "closed", 1, friendly_name="Porte garage")]   # refermée entre-temps
    assert run(e.decide(pid, True, "x"))["status"] == "obsolete"
    assert f.executed == []


def test_reject(tmp_path):
    f = Fake(); f.states = [garage_open(NIGHT)]
    e = make(tmp_path, f); run(e.tick())
    pid = e.store.proposals("pending")[0]["id"]
    assert run(e.decide(pid, False, "Olivier"))["status"] == "rejected"
    assert f.executed == []


def test_urgent_always_speaks_and_reminds_then_resolves(tmp_path):
    f = Fake()
    f.states = [st("binary_sensor.fumee", "on", device_class="smoke", friendly_name="Détecteur salon")]
    e = make(tmp_path, f); run(e.tick())
    assert len(f.spoken) == 1                             # parle même la nuit
    f.now = NIGHT + timedelta(minutes=11); run(e.tick())
    assert len(f.spoken) == 2 and f.spoken[1].startswith("Rappel")
    f.states = []; run(e.tick())                          # situation terminée
    assert e.active == {}
    assert any(j["kind"] == "resolu" for j in e.store.journal())


def test_urgent_acts_alone_only_if_rule_in_auto_rules(tmp_path, monkeypatch):
    f = Fake(); f.states = [st("binary_sensor.fumee", "on", device_class="smoke", friendly_name="Détecteur")]
    real = rules.evaluate

    def with_action(states, now, p):
        out = real(states, now, p)
        for x in out:
            x.action = {"domain": "light", "service": "turn_on", "entity_id": "light.couloir"}
        return out
    monkeypatch.setattr(rules, "evaluate", with_action)
    e = make(tmp_path, f); run(e.tick())
    assert f.executed == []                               # par défaut : jamais seul
    f3 = Fake(); f3.states = f.states
    sub = tmp_path / "b"; sub.mkdir()
    e3 = make(sub, f3, auto_rules=["safety_sensor"]); run(e3.tick())
    assert f3.executed == [("light", "turn_on", "light.couloir")]


def test_active_survives_restart_without_reannouncing(tmp_path):
    f = Fake(); f.states = [garage_open(NIGHT)]
    e = make(tmp_path, f); run(e.tick())
    e2 = make(tmp_path, f); run(e2.tick())
    assert len(f.notified) == 1 and len(e2.store.proposals("pending")) == 1


def test_proposals_expire(tmp_path):
    base = datetime.now(TZ)                                # horloge réelle : la base y est calée
    f = Fake(); f.now = base; f.states = [garage_open(base, 90)]
    e = make(tmp_path, f, proposal_ttl_min=30); run(e.tick())
    assert len(e.store.proposals("pending")) == 1
    f.now = base + timedelta(minutes=45); run(e.tick())
    assert e.store.proposals("pending") == [] and e.store.proposals("expired")


def test_daily_report_once_per_day(tmp_path):
    f = Fake(); f.now = datetime(2026, 11, 4, 8, 5, tzinfo=TZ)
    e = make(tmp_path, f, daily_report_time="08:00")
    run(e.tick()); run(e.tick())
    assert len(f.spoken) == 1 and "Tout est nominal" in f.spoken[0]
    f.now = f.now + timedelta(days=1); run(e.tick())
    assert len(f.spoken) == 2
