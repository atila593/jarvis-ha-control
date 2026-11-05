import json
import os
import sys
import tempfile

os.environ["OPTIONS_PATH"] = "/nonexistent.json"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "jarvis_ha_control", "app"))
sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
from autonomy import access  # noqa: E402
from test_engineer import FakeHa, nosleep, GOOD  # noqa: E402


def boot(c, pin="1234"):
    e = main.autonomy
    e.s.approvers = ["Olivier"]
    main.ROLES.update({"olivier": "admin", "sarah": "member"})
    main.engineer.ha = FakeHa()
    main.engineer.sleep = nosleep
    main.gate = access.VoiceGate(e, main.engineer, pin, True)
    seen = {}

    async def fake_cmd(prompt, who=None, role="admin", toolbox=None, facts=None):
        seen.update(prompt=prompt, who=who, role=role, tools=[t.__name__ for t in toolbox.tools()] if toolbox else [], facts=facts)
        return "ok", []
    main.jarvis.process_command = fake_cmd
    return e, seen


def test_command_identity_and_toolbox():
    with TestClient(main.app) as c:
        e, seen = boot(c)
        main.config.MEMORY_ENABLED = main.config.ENGINEER_ENABLED = True
        e.store.add_fact("Sarah", "Aime le chauffage à 20 degrés")
        c.post("/api/command", json={"prompt": "salut", "who": "Sarah"})
        assert seen["role"] == "member" and seen["tools"] == ["remember"] and seen["facts"] == ["Aime le chauffage à 20 degrés"]
        c.post("/api/command", json={"prompt": "salut", "who": "Inconnu"})
        assert seen["role"] == "guest" and seen["tools"] == []
        c.post("/api/command", json={"prompt": "salut"}, headers={"X-Remote-User-Display-Name": "Olivier"})   # panneau (Ingress)
        assert seen["role"] == "admin" and "propose_automation" in seen["tools"]
        main.config.MEMORY_ENABLED = main.config.ENGINEER_ENABLED = False


def test_voice_endpoint_approves_engineer_proposal_then_undoes_it():
    with TestClient(main.app) as c:
        e, _ = boot(c)
        r = c.post("/api/voice/ask", json={"text": "oui", "who": "Olivier"}).json()
        assert "Il n'y a rien" in r["response"] or "code" in r["response"].lower()

        out = main.asyncio.run(main.engineer.propose_change("automation", "create", json.dumps(GOOD), reason="test"))
        pid = out["id"]
        assert c.post("/api/voice/ask", json={"text": "oui 1234", "who": "Sarah"}).json()["response"].startswith("Seul")
        assert "incorrect" in c.post("/api/voice/ask", json={"text": "oui 0000", "who": "Olivier"}).json()["response"]
        assert c.post("/api/voice/ask", json={"text": "oui 1234", "who": "Olivier"}).json()["response"] == "C'est fait."

        ch = c.get("/api/changes").json()["items"][0]
        assert ch["status"] == "applied" and ch["kind"] == "automation"
        assert any(k.startswith("config/automation/config/jarvis_") for k in main.engineer.ha.configs)

        assert c.post(f"/api/changes/{ch['id']}/undo").status_code == 403                    # pas d'identité approbateur
        assert "annulée" in c.post("/api/voice/ask", json={"text": "annule ça 1234", "who": "Olivier"}).json()["response"]
        assert not any(k.startswith("config/automation/config/jarvis_") for k in main.engineer.ha.configs)
        assert c.get("/api/changes").json()["items"][0]["status"] == "undone"


def test_undo_endpoint_with_approver_header():
    with TestClient(main.app) as c:
        e, _ = boot(c)
        out = main.asyncio.run(main.engineer.propose_change("automation", "create", json.dumps(GOOD)))
        main.asyncio.run(e.decide(out["id"], True, "Olivier"))
        cid = c.get("/api/changes").json()["items"][0]["id"]
        assert c.post(f"/api/changes/{cid}/undo", headers={"X-Remote-User-Name": "sarah"}).status_code == 403
        assert c.post(f"/api/changes/{cid}/undo", headers={"X-Remote-User-Name": "olivier"}).status_code == 200
        assert c.post(f"/api/changes/{cid}/undo", headers={"X-Remote-User-Name": "olivier"}).status_code == 409


def test_memory_endpoints_and_hygiene():
    with TestClient(main.app) as c:
        e, _ = boot(c)
        fid = e.store.add_fact("Olivier", "Préfère les réponses courtes")
        assert [f["fact"] for f in c.get("/api/memory").json()["items"]][0] == "Préfère les réponses courtes"
        assert c.delete(f"/api/memory/{fid}").status_code == 200
        assert c.delete(f"/api/memory/{fid}").status_code == 404
        h = c.get("/api/hygiene").json()
        assert h["count"] == 2 and h["items"][0]["entity_id"] == "sensor.fantome"
