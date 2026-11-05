import asyncio
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "jarvis_ha_control", "app"))

from autonomy.engineer import Engineer, SIGNATURE, validate  # noqa: E402
from autonomy.store import Store  # noqa: E402


def run(c):
    return asyncio.run(c)


class FakeHa:
    """Simule HA : configs UI, entités chargées après écriture, WebSocket minimal."""

    def __init__(self):
        self.configs = {}
        self.states = [
            {"entity_id": "light.salon", "state": "on", "attributes": {}, "last_changed": "2026-11-01T00:00:00+00:00"},
            {"entity_id": "cover.porte_garage", "state": "open", "attributes": {}, "last_changed": "2026-11-01T00:00:00+00:00"},
            {"entity_id": "sensor.fantome", "state": "unavailable", "attributes": {"restored": True}, "last_changed": "2026-10-01T00:00:00+00:00"},
            {"entity_id": "sensor.utilise", "state": "unavailable", "attributes": {"restored": True}, "last_changed": "2026-10-01T00:00:00+00:00"},
            {"entity_id": "automation.user", "state": "on", "attributes": {"id": "u1"}, "last_changed": "2026-11-01T00:00:00+00:00"},
        ]
        self.configs["config/automation/config/u1"] = {"alias": "Ma auto", "description": "", "actions": [{"action": "light.turn_on", "target": {"entity_id": "sensor.utilise"}}]}
        self.removed, self.dashboards = [], {None: {"views": []}}
        self.fail_post = False

    async def get(self, path):
        if path == "states":
            return self.states
        return self.configs.get(path)

    async def post(self, path, payload):
        if self.fail_post:
            raise RuntimeError("500")
        self.configs[path] = payload
        _, kind, _, oid = path.split("/")
        if kind == "automation":
            self.states = [s for s in self.states if s["attributes"].get("id") != oid]
            self.states.append({"entity_id": f"automation.{oid}", "state": "unavailable" if payload.get("_broken") else "on",
                                "attributes": {"id": oid}, "last_changed": "2026-11-05T00:00:00+00:00"})

    async def delete(self, path):
        self.configs.pop(path, None)
        oid = path.split("/")[-1]
        self.states = [s for s in self.states if s["attributes"].get("id") != oid]

    async def ws(self, t, **kw):
        if t == "lovelace/dashboards/list":
            return []
        if t == "lovelace/config":
            return self.dashboards[None]
        if t == "config/entity_registry/get":
            return {"entity_id": kw["entity_id"]}
        if t == "config/entity_registry/remove":
            self.removed.append(kw["entity_id"])
            self.states = [s for s in self.states if s["entity_id"] != kw["entity_id"]]
            return None


async def nosleep(_):
    return None


def make(tmp_path, **kw):
    ha = FakeHa()
    return Engineer(Store(str(tmp_path / "e.db")), ha, sleep=nosleep, **kw), ha


GOOD = {"alias": "Fermer le garage", "triggers": [{"trigger": "time", "at": "23:00:00"}],
        "actions": [{"action": "cover.close_cover", "target": {"entity_id": "cover.porte_garage"}}]}


def test_validate_rejects_dangerous_and_unknown():
    known = {"light.salon"}
    bad = {"alias": "x", "triggers": [{"trigger": "time", "at": "1:00"}],
           "actions": [{"action": "lock.unlock", "target": {"entity_id": "lock.porte"}}, {"action": "shell_command.rm"},
                       {"action": "light.turn_on", "target": {"entity_id": "light.inconnue"}}]}
    msg = " ".join(validate("automation", bad, known))
    assert "lock.unlock" in msg and "shell_command.rm" in msg and "light.inconnue" in msg
    assert validate("automation", {"alias": "ok", "triggers": [1], "actions": [{"action": "light.turn_on", "target": {"entity_id": "light.salon"}}]}, known) == []
    assert any("alias" in p for p in validate("automation", {"triggers": [1], "actions": [1]}, known))
    assert any("séquence" in p for p in validate("script", {"alias": "s"}, known))


def test_templates_are_not_flagged_as_entities():
    cfg = {"alias": "t", "triggers": [1], "actions": [{"action": "light.turn_on", "target": {"entity_id": "{{ states('input_text.x') }}"}}]}
    assert validate("automation", cfg, set()) == []


def test_create_flow_apply_and_undo(tmp_path):
    e, ha = make(tmp_path)
    r = run(e.propose_change("automation", "create", json.dumps(GOOD), reason="sécurité"))
    assert r["ok"] and "Créer automation" in r["summary"]
    prop = e.store.get_proposal(r["id"])
    act = prop["action"]
    assert act["config"]["alias"].startswith("[Jarvis]") and SIGNATURE in act["config"]["description"]
    out = run(e.apply_change(act))
    assert out.startswith("OK")
    oid = act["object_id"]
    assert f"config/automation/config/{oid}" in ha.configs
    ch = e.store.last_applied_change()
    assert ch["before"] is None
    assert run(e.undo(ch["id"])).startswith("OK")
    assert f"config/automation/config/{oid}" not in ha.configs          # supprimée : retour à l'état d'avant
    assert run(e.undo(ch["id"])).startswith("ERREUR")                    # pas deux fois


def test_broken_config_is_rolled_back_automatically(tmp_path):
    e, ha = make(tmp_path)
    cfg = dict(GOOD, _broken=True)
    r = run(e.propose_change("automation", "create", json.dumps(cfg)))
    out = run(e.apply_change(e.store.get_proposal(r["id"])["action"]))
    assert out.startswith("ERREUR") and "Retour arrière" in out
    assert not [k for k in ha.configs if "jarvis_" in k]
    assert e.store.changes()[0]["status"] == "rolled_back"


def test_write_refused_keeps_previous_state(tmp_path):
    e, ha = make(tmp_path)
    r = run(e.propose_change("automation", "create", json.dumps(GOOD)))
    ha.fail_post = True
    assert run(e.apply_change(e.store.get_proposal(r["id"])["action"])).startswith("ERREUR")
    assert e.store.changes()[0]["status"] == "failed"


def test_cannot_touch_user_automations_by_default(tmp_path):
    e, ha = make(tmp_path)
    r = run(e.propose_change("automation", "delete", object_id="u1"))
    assert not r["ok"] and "créé" in r["error"]


def test_edit_existing_when_allowed_and_undo_restores_original(tmp_path):
    e, ha = make(tmp_path, edit_existing=True)
    new = {"alias": "Ma auto améliorée", "triggers": [1], "actions": [{"action": "light.turn_on", "target": {"entity_id": "light.salon"}}]}
    r = run(e.propose_change("automation", "update", json.dumps(new), object_id="u1"))
    assert r["ok"]
    original = json.loads(json.dumps(ha.configs["config/automation/config/u1"]))
    assert run(e.apply_change(e.store.get_proposal(r["id"])["action"])).startswith("OK")
    assert ha.configs["config/automation/config/u1"]["alias"] == "Ma auto améliorée"
    run(e.undo_last())
    assert ha.configs["config/automation/config/u1"] == original


def test_proposal_cap(tmp_path):
    e, _ = make(tmp_path)
    for _ in range(10):
        assert run(e.propose_change("automation", "create", json.dumps(GOOD)))["ok"]
    assert not run(e.propose_change("automation", "create", json.dumps(GOOD)))["ok"]


def test_remove_entity_refuses_if_referenced_or_alive(tmp_path):
    e, ha = make(tmp_path)
    r = run(e.propose_remove_entity("sensor.utilise"))
    assert not r["ok"] and "automation Ma auto" in r["error"]               # citée par une automation
    assert not run(e.propose_remove_entity("light.salon"))["ok"]            # vivante
    ha.dashboards[None] = {"views": [{"cards": [{"entity": "sensor.fantome"}]}]}
    assert not run(e.propose_remove_entity("sensor.fantome"))["ok"]         # citée par un dashboard
    ha.dashboards[None] = {"views": []}
    r = run(e.propose_remove_entity("sensor.fantome", "fantôme"))
    assert r["ok"] and "irréversible" in r["summary"]
    assert run(e.remove_entity(e.store.get_proposal(r["id"])["action"])).startswith("OK")
    assert ha.removed == ["sensor.fantome"]


def test_stale_entities(tmp_path):
    e, _ = make(tmp_path)
    out = run(e.stale_entities(7, datetime(2026, 11, 5, tzinfo=timezone.utc)))
    assert [x["entity_id"] for x in out] == ["sensor.fantome", "sensor.utilise"]
