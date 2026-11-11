"""Rôles, mémoire et validation vocale.

Rôles : admin (valide, crée des automations), member (commandes courantes + mémoire), guest (lecture seule).
Validation vocale : désactivée tant que `voice_pin` est vide. Exige le code ET le rôle admin :
sans reconnaissance du locuteur, un simple « oui » dit à voix haute ne doit jamais suffire.
"""
import hmac
import re
import time
import unicodedata

ROLES = ("admin", "member", "guest")
SECRET_RE = re.compile(r"mot de passe|password|\bpin\b|\bcode\b.*\d|iban|carte (bancaire|bleue)|cvv", re.I)
PIN_RE = re.compile(r"\b(\d{4,8})\b")
LOCK_AFTER = 5
LOCK_SECONDS = 300


def norm(text: str) -> str:
    t = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9' ]", " ", t)).strip()


def parse_roles(items: list) -> dict:
    out = {}
    for it in items or []:
        name, _, role = str(it).partition(":")
        if name.strip() and role.strip().lower() in ROLES:
            out[name.strip().lower()] = role.strip().lower()
    return out


def role_of(name: str | None, roles: dict, default: str = "guest") -> str:
    return roles.get((name or "").strip().lower(), default)


APPROVE = {"oui", "valide", "approuve", "vas y", "fais le", "c'est bon", "ok", "d'accord", "go"}
REJECT = {"non", "refuse", "laisse tomber", "ne le fais pas", "annule la proposition"}
UNDO_WORDS = ("annule ca", "annule la derniere", "annule cette modification", "reviens en arriere", "annule tout ca")
LIST_WORDS = ("quelles propositions", "qu'est ce que tu proposes", "propositions en attente", "tu proposes quoi")


def extract_pin(text: str) -> str | None:
    m = PIN_RE.search(text or "")
    return m.group(1) if m else None


def classify(text: str) -> tuple[str | None, int | None]:
    """(intention, numéro de proposition éventuel). Strict : une phrase de conversation ne doit jamais valider quoi que ce soit."""
    t = norm(PIN_RE.sub(" ", text or ""))
    t = re.sub(r"\b(jarvis|code|mon code est|le code)\b", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    num = None
    m = re.search(r"\b(?:numero|proposition|la)\s*(\d{1,3})\b", t)
    if m:
        num = int(m.group(1))
        t = re.sub(r"\b(?:numero|proposition|la)\s*\d{1,3}\b", " ", t).strip()
    if any(w in t for w in UNDO_WORDS):
        return "undo", None
    if any(w in t for w in LIST_WORDS):
        return "list", None
    if t in APPROVE:
        return "approve", num
    if t in REJECT:
        return "reject", num
    return None, None


class VoiceGate:
    def __init__(self, engine, engineer, pin: str, enabled: bool):
        self.engine, self.engineer = engine, engineer
        self.pin, self.enabled = (pin or "").strip(), enabled
        self._fails: list = []

    def _locked(self) -> bool:
        now = time.time()
        self._fails = [t for t in self._fails if now - t < LOCK_SECONDS]
        return len(self._fails) >= LOCK_AFTER

    async def handle(self, text: str, who: str | None, role: str) -> str | None:
        """Texte à dire si la phrase est une commande de validation ; None -> conversation normale."""
        if not self.enabled:
            return None
        intent, num = classify(text)
        if not intent:
            return None
        pending = self.engine.store.proposals("pending")
        if intent == "list":
            if not pending:
                return "Aucune proposition en attente."
            return f"{len(pending)} proposition(s) : " + " ; ".join(f"numéro {p['id']}, {p['message']}" for p in pending[:5])

        if not self.pin:
            return "La validation vocale est désactivée : utilise le panneau Jarvis."
        if role != "admin":
            return "Seul un administrateur peut valider par la voix."
        if self._locked():
            return "Trop d'essais de code. Réessaie dans quelques minutes."
        given = extract_pin(text)
        if not given:
            return "Dis aussi ton code pour valider."          # pas d'essai décompté : « oui » peut être de la conversation
        if not hmac.compare_digest(given, self.pin):
            self._fails.append(time.time())
            return "Code incorrect."

        if intent == "undo":
            return (await self.engineer.undo_last()).removeprefix("OK : ").removeprefix("ERREUR : ")
        if not pending:
            return "Il n'y a rien à valider."
        if num is None:
            if len(pending) > 1:
                return f"Il y a {len(pending)} propositions, dis le numéro : " + ", ".join(str(p["id"]) for p in pending[:5]) + "."
            num = pending[0]["id"]
        res = await self.engine.decide(num, intent == "approve", who)
        if not res["ok"]:
            return res["detail"]
        return {"executed": "C'est fait.", "obsolete": "La situation a changé, je n'ai rien fait.",
                "rejected": "Proposition refusée.", "failed": "L'action a échoué."}.get(res["status"], res["status"])
