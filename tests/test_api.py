import os
import sys
import tempfile

os.environ["OPTIONS_PATH"] = "/nonexistent.json"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "jarvis_ha_control", "app"))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402


def test_approval_endpoints():
    with TestClient(main.app) as c:
        e = main.autonomy
        e.s.approvers = ["Olivier"]
        done = []

        async def fetch():
            return [{"entity_id": "cover.porte_garage", "state": "open", "attributes": {}}]

        async def execute(d, s, ent):
            done.append((d, s, ent))
            return "OK : fait."
        e.fetch_states, e.execute = fetch, execute

        pid = e.store.add_proposal("garage_open", "cover.porte_garage", "Porte ouverte",
                                   {"domain": "cover", "service": "close_cover", "entity_id": "cover.porte_garage"}, "open")
        assert c.get("/api/proposals").json()["items"][0]["id"] == pid

        # sans identité / mauvaise identité -> 403, rien n'est exécuté
        assert c.post(f"/api/proposals/{pid}/approve").status_code == 403
        assert c.post(f"/api/proposals/{pid}/approve", headers={"X-Remote-User-Name": "sarah"}).status_code == 403
        assert done == []

        r = c.post(f"/api/proposals/{pid}/approve", headers={"X-Remote-User-Name": "olivier"})
        assert r.status_code == 200 and r.json()["status"] == "executed"
        assert done == [("cover", "close_cover", "cover.porte_garage")]
        assert c.post(f"/api/proposals/{pid}/approve", headers={"X-Remote-User-Name": "olivier"}).status_code == 409
        assert c.post("/api/proposals/999/reject", headers={"X-Remote-User-Name": "olivier"}).status_code == 404

        j = c.get("/api/journal").json()["items"]
        assert any("validée par" in x["message"] for x in j)
        assert c.get("/api/autonomy").json()["enabled"] is False   # désactivé par défaut


def test_untrusted_source_is_refused_when_approvers_set(monkeypatch):
    monkeypatch.delenv("JARVIS_DEV")
    with TestClient(main.app) as c:                    # client "testclient" != IP du proxy Ingress
        main.autonomy.s.approvers = ["Olivier"]
        pid = main.autonomy.store.add_proposal("x", "light.a", "m", {"domain": "light", "service": "turn_off", "entity_id": "light.a"}, None)
        r = c.post(f"/api/proposals/{pid}/approve", headers={"X-Remote-User-Name": "olivier"})
        assert r.status_code == 403                    # en-tête forgé depuis un autre conteneur : refusé
