import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "jarvis_ha_control", "app"))

from autonomy import access, rules  # noqa: E402
from autonomy.engine import AutonomyEngine, Settings  # noqa: E402
from autonomy.store import Store  # noqa: E402
from tools.toolbox import Toolbox  # noqa: E402


def run(c):
    return asyncio.run(c)


def test_classify_is_strict():
    assert access.classify("oui 1234") == ("approve", None)
    assert access.classify("Jarvis, oui, mon code est 1234") == ("approve", None)
    assert access.classify("valide la 7 code 4321") == ("approve", 7)
    assert access.classify("non merci")[0] is None                       # phrase de conversation : jamais une validation
    assert access.classify("oui je veux bien du café")[0] is None
    assert access.classify("annule ça code 1234")[0] == "undo"
    assert access.classify("quelles propositions")[0] == "list"
    assert access.classify("allume le salon")[0] is None


def test_parse_roles():
    r = access.parse_roles(["Olivier:admin", "sarah:Member", "bad", "x:chef"])
    assert r == {"olivier": "admin", "sarah": "member"}
    assert access.role_of("OLIVIER", r) == "admin" and access.role_of("inconnu", r) == "guest"


class Eng:
    def __init__(self, tmp):
        self.executed, self.undone = [], []

        async def execute(d, s, e):
            self.executed.append((d, s, e))
            return "OK : fait"

        async def fetch():
            return [{"entity_id": "cover.g", "state": "open", "attributes": {}}]

        async def noop(*a):
            return None

        async def rep():
            return ""

        async def now():
            from datetime import datetime
            return datetime.now()
        self.e = AutonomyEngine(Store(str(tmp / "a.db")), Settings(approvers=["Olivier"]), rules.Params(), fetch_states=fetch,
                                execute=execute, speak=noop, notify=noop, report=rep, local_now=now)
        self.e.store.add_proposal("garage_open", "cover.g", "Garage ouvert",
                                  {"domain": "cover", "service": "close_cover", "entity_id": "cover.g"}, "open")


class FakeEngineer:
    async def undo_last(self):
        return "OK : modification #3 annulée."


def gate(tmp, pin="1234", enabled=True):
    h = Eng(tmp)
    return h, access.VoiceGate(h.e, FakeEngineer(), pin, enabled)


def test_voice_approve_requires_pin_and_admin(tmp_path):
    h, g = gate(tmp_path)
    assert run(g.handle("allume le salon", "Olivier", "admin")) is None                       # conversation
    assert "code" in run(g.handle("oui", "Olivier", "admin")).lower() and h.executed == []     # pas de code
    assert "administrateur" in run(g.handle("oui 1234", "Sarah", "member"))
    assert run(g.handle("oui 9999", "Olivier", "admin")) == "Code incorrect." and h.executed == []
    assert run(g.handle("oui 1234", "Olivier", "admin")) == "C'est fait."
    assert h.executed == [("cover", "close_cover", "cover.g")]


def test_voice_disabled_without_pin_or_flag(tmp_path):
    h, g = gate(tmp_path, pin="")
    assert "désactivée" in run(g.handle("oui", "Olivier", "admin")) and h.executed == []
    assert access.VoiceGate(h.e, FakeEngineer(), "1234", False)  # drapeau coupé
    assert run(access.VoiceGate(h.e, FakeEngineer(), "1234", False).handle("oui 1234", "Olivier", "admin")) is None


def test_lockout_after_wrong_codes_but_plain_yes_does_not_count(tmp_path):
    h, g = gate(tmp_path)
    for _ in range(10):
        run(g.handle("oui", "Olivier", "admin"))                  # « oui » de conversation : jamais décompté
    assert run(g.handle("oui 1234", "Olivier", "admin")) == "C'est fait."
    for _ in range(5):
        run(g.handle("oui 0000", "Olivier", "admin"))
    assert "Trop d'essais" in run(g.handle("oui 1234", "Olivier", "admin"))


def test_voice_undo_and_list(tmp_path):
    h, g = gate(tmp_path)
    assert "Garage ouvert" in run(g.handle("quelles propositions", "Sarah", "guest"))         # lecture ouverte à tous
    assert "annulée" in run(g.handle("annule ça 1234", "Olivier", "admin"))
    assert "code" in run(g.handle("annule ça", "Olivier", "admin")).lower()


def test_toolbox_by_role_and_secret_filter(tmp_path):
    st = Store(str(tmp_path / "t.db"))
    tb = lambda role, who="Olivier", **kw: Toolbox(FakeEngineer(), st, who, role, **{"engineer_on": True, "memory_on": True, **kw})  # noqa: E731
    names = lambda t: sorted(f.__name__ for f in t.tools())  # noqa: E731
    assert "propose_automation" in names(tb("admin")) and "remember" in names(tb("admin"))
    assert names(tb("member")) == ["remember"]                                   # un membre ne crée pas d'automation
    assert names(tb("guest")) == []
    assert names(tb("admin", engineer_on=False)) == ["remember"]
    assert names(tb("admin", memory_on=False)).count("remember") == 0
    t = tb("admin")
    assert run(t.remember("Aime la lumière chaude le soir")) == "Retenu."
    assert run(t.remember("Mon mot de passe wifi est abc")).startswith("REFUSÉ")
    assert run(t.remember("le code est 1234")).startswith("REFUSÉ")
    assert [f["fact"] for f in st.facts("Olivier")] == ["Aime la lumière chaude le soir"]
    run(t.remember("aime la lumière chaude le soir"))                            # doublon ignoré
    assert len(st.facts("Olivier")) == 1
