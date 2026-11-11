"""Règles d'autonomie : états HA -> constats (gravité + action éventuelle).

Fonctions pures, sans réseau : faciles à tester. Le moteur décide ensuite quoi en faire
(agir, proposer, noter) selon la gravité.
"""
from dataclasses import dataclass, field
from datetime import datetime, time, timezone

SAFETY_CLASSES = {
    "smoke": "de la fumée",
    "gas": "du gaz",
    "carbon_monoxide": "du monoxyde de carbone",
    "moisture": "une fuite d'eau",
    "safety": "un danger",
}
# Uniquement ce qui sature vraiment : espace disque et mémoire. Jamais les CPU (somme sur plusieurs cœurs : 222 % est normal).
SYSTEM_METRIC_KEYS = ("stockage", "storage", "disk", "disque", "memoire", "memory", "nas")
SYSTEM_EXCLUDE = ("echange", "swap", "conteneur", "container", "processeur", "cpu")
BAD_ALERT = {"rouge": "rouge", "red": "rouge", "orange": "orange"}

ALL_RULES = (
    "safety_sensor",
    "garage_open",
    "vacuum_error",
    "system_high",
    "weather_alert",
    "watched_unavailable",
)


@dataclass
class Params:
    quiet_start: time = time(23, 0)
    quiet_end: time = time(7, 0)
    garage_night_min: int = 10
    garage_day_min: int = 60
    vacuum_error_min: int = 2
    unavailable_min: int = 30
    watched: list = field(default_factory=list)   # entités surveillées (extra_entities)
    hidden: list = field(default_factory=list)
    enabled: list = field(default_factory=list)   # vide = toutes les règles


@dataclass
class Finding:
    rule: str
    entity_id: str
    severity: str            # urgent | important | minor
    message: str             # phrase courte, lisible à voix haute
    action: dict | None = None   # {"domain","service","entity_id"} : ce que Jarvis ferait
    expect_state: str | None = None  # état attendu au moment d'agir (sinon proposition obsolète)

    @property
    def key(self) -> str:
        return f"{self.rule}:{self.entity_id}"


def parse_time(value: str, default: time) -> time:
    try:
        hh, mm = str(value).strip().split(":")
        return time(int(hh), int(mm))
    except Exception:
        return default


def in_window(now: time, start: time, end: time) -> bool:
    """Vrai si `now` est dans [start, end[ ; gère la fenêtre qui passe minuit (23:00 -> 07:00)."""
    if start <= end:
        return start <= now < end
    return now >= start or now < end


def _minutes_since(state: dict, now_utc: datetime) -> float:
    raw = state.get("last_changed") or ""
    try:
        ts = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return max(0.0, (now_utc - ts).total_seconds() / 60)
    except Exception:
        return 0.0


def _name(state: dict) -> str:
    return (state.get("attributes") or {}).get("friendly_name") or state.get("entity_id", "")


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_garage(eid: str, name: str) -> bool:
    low = f"{eid} {name}".lower()
    return "garage" in low or "rideau" in low


def evaluate(states: list, now_local: datetime, p: Params) -> list[Finding]:
    now_utc = now_local.astimezone(timezone.utc)
    night = in_window(now_local.time(), p.quiet_start, p.quiet_end)
    on = lambda r: not p.enabled or r in p.enabled  # noqa: E731
    out: list[Finding] = []

    for s in states:
        eid = s.get("entity_id", "")
        if not eid or eid in p.hidden:
            continue
        domain = eid.split(".")[0]
        state = str(s.get("state", ""))
        attrs = s.get("attributes") or {}
        dclass = attrs.get("device_class")
        name = _name(s)

        # 1. Capteurs de sécurité (fumée, gaz, CO, fuite d'eau) -> urgence
        if on("safety_sensor") and domain == "binary_sensor" and dclass in SAFETY_CLASSES and state == "on":
            out.append(Finding("safety_sensor", eid, "urgent",
                               f"Alerte : {name} détecte {SAFETY_CLASSES[dclass]}."))

        # 2. Porte de garage ouverte (longtemps, ou la nuit)
        if on("garage_open") and domain == "cover" and state == "open" and _is_garage(eid, name):
            mins = _minutes_since(s, now_utc)
            limit = p.garage_night_min if night else p.garage_day_min
            if mins >= limit:
                when = "en pleine nuit" if night else f"depuis {int(mins)} minutes"
                out.append(Finding("garage_open", eid, "important",
                                   f"{name} est ouverte {when}.",
                                   action={"domain": "cover", "service": "close_cover", "entity_id": eid},
                                   expect_state="open"))

        # 3. Aspirateur en erreur
        if on("vacuum_error") and domain == "vacuum" and state == "error" and _minutes_since(s, now_utc) >= p.vacuum_error_min:
            out.append(Finding("vacuum_error", eid, "important", f"{name} est en erreur."))

        # 4. Serveur : disque / mémoire presque pleins, processeur trop chaud
        if on("system_high") and domain == "sensor":
            v, unit = _num(state), attrs.get("unit_of_measurement")
            low = eid.lower()
            if v is not None and unit == "%" and dclass != "battery" and any(k in low for k in SYSTEM_METRIC_KEYS) \
                    and not any(x in low for x in SYSTEM_EXCLUDE) and v >= 95:
                out.append(Finding("system_high", eid, "important", f"{name} est à {v:.0f} pour cent."))
            elif v is not None and "temperature_package" in low and v >= 85:
                out.append(Finding("system_high", eid, "important", f"Le processeur chauffe : {v:.0f} degrés."))

        # 5. Alerte météo rouge ou orange
        if on("weather_alert") and domain == "sensor" and "weather_alert" in eid and state.lower() in BAD_ALERT:
            out.append(Finding("weather_alert", eid, "important",
                               f"Vigilance météo {BAD_ALERT[state.lower()]} en cours."))

        # 6. Entité surveillée indisponible depuis longtemps -> simple note
        if on("watched_unavailable") and eid in p.watched and state == "unavailable" \
                and _minutes_since(s, now_utc) >= p.unavailable_min:
            out.append(Finding("watched_unavailable", eid, "minor", f"{name} est indisponible."))

    return out
