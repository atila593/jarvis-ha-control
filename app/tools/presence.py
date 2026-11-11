"""Présence par zones, lue directement sur le radar ESPHome (HLK-LD2450, ex. Apollo MTR-1).

L'appareil ESPHome expose, pour chaque zone :
  - sensor.<prefix>_zone_<n>_all_target_count   (nombre de cibles dans la zone)
  - number.<prefix>_zone_<n>_x1 / y1 / x2 / y2  (rectangle ; une zone à 0 ou plate n'est pas utilisée)
  - select.<prefix>_zone_type                   ("Disabled" = zones désactivées)
Détection automatique du préfixe. Options : presence_prefix (si plusieurs radars) et
presence_zone_names (noms dans l'ordre : zone 1, zone 2...). hidden_entities masque une zone.
"""
import asyncio
import re

import httpx

import config

COUNT_RE = re.compile(r"^sensor\.(.+)_zone_(\d+)_all_target_count$")
BAD_STATES = ("", "unknown", "unavailable", "None")

# entity_id du compteur -> nom d'affichage ; rempli par zones(), utilisé par fast()
_cache: dict = {}


def _int(state) -> int:
    try:
        return int(float(state))
    except (TypeError, ValueError):
        return 0


def _float(state):
    try:
        return float(state)
    except (TypeError, ValueError):
        return None


def _configured(by_id: dict, prefix: str, n: int) -> bool:
    """Faux si le rectangle de la zone est vide (zone non utilisée sur le radar)."""
    vals = [_float((by_id.get(f"number.{prefix}_zone_{n}_{k}") or {}).get("state"))
            for k in ("x1", "y1", "x2", "y2")]
    if any(v is None for v in vals):
        return True  # entités absentes ou indisponibles : on ne cache pas la zone
    x1, y1, x2, y2 = vals
    return x1 != x2 and y1 != y2


def _name(n: int) -> str:
    names = config.PRESENCE_ZONE_NAMES
    return (names[n - 1].strip() if n - 1 < len(names) and names[n - 1].strip() else f"Zone {n}")


def _make(entity_id: str, name: str, state: dict | None) -> dict:
    raw = str((state or {}).get("state", "unavailable"))
    count = _int(raw)
    return {
        "entity_id": entity_id,
        "name": name,
        "known": raw not in BAD_STATES,
        "occupied": count > 0,
        "count": count,
    }


def zones(states: list) -> list:
    """Liste des zones du radar : name, entity_id, known, occupied, count."""
    by_id = {s.get("entity_id"): s for s in states}
    hidden = set(config.HIDDEN_ENTITIES)
    out = []
    for eid, s in by_id.items():
        m = COUNT_RE.match(eid or "")
        if not m or eid in hidden:
            continue
        prefix, n = m.group(1), int(m.group(2))
        if config.PRESENCE_PREFIX and prefix != config.PRESENCE_PREFIX:
            continue
        if (by_id.get(f"select.{prefix}_zone_type") or {}).get("state") == "Disabled":
            continue
        if not _configured(by_id, prefix, n):
            continue
        out.append((prefix, n, _make(eid, _name(n), s)))
    out.sort(key=lambda t: (t[0], t[1]))
    _cache.clear()
    _cache.update({z["entity_id"]: z["name"] for _, _, z in out})
    return [z for _, _, z in out]


def describe(z: dict) -> str:
    if not z["known"]:
        return "Indisponible"
    if not z["occupied"]:
        return "Libre"
    return "Occupé" + (f" ({z['count']} personnes)" if z["count"] > 1 else "")


def items(zs: list) -> list:
    """Éléments du groupe « presence » du HUD."""
    return [{
        "entity_id": z["entity_id"], "name": z["name"].capitalize(),
        "state": "on" if z["occupied"] else "off" if z["known"] else "unavailable",
        "display": describe(z), "level": "ok" if z["known"] else "warn", "kind": "other",
    } for z in zs]


async def fast() -> list:
    """Rafraîchissement rapide : ne relit que les compteurs de zones déjà découverts."""
    names = dict(_cache)
    if not names:
        return []
    headers = {"Authorization": f"Bearer {config.SUPERVISOR_TOKEN}"}

    async def one(http, eid):
        try:
            res = await http.get(f"{config.HA_API_URL}/states/{eid}", headers=headers)
            res.raise_for_status()
            return eid, res.json()
        except Exception:
            return eid, None

    async with httpx.AsyncClient(timeout=4) as http:
        got = await asyncio.gather(*(one(http, e) for e in names))
    return items([_make(eid, names[eid], s) for eid, s in got])


def context_block(zs: list) -> str:
    """Bloc ajouté au contexte envoyé à Gemini."""
    if not zs:
        return ""
    lines = ["[Présence — radar mmWave : il ne couvre que les zones ci-dessous et ne dit rien des autres pièces]"]
    for z in zs:
        if not z["known"]:
            lines.append(f"- {z['name']} : indisponible")
        elif z["occupied"]:
            lines.append(f"- {z['name']} : occupée, {z['count']} personne{'s' if z['count'] > 1 else ''}")
        else:
            lines.append(f"- {z['name']} : libre")
    return "\n".join(lines)


def spoken(items_: list) -> str:
    """Phrase pour le rapport vocal. `items_` = éléments du groupe « presence » du statut."""
    known = [i for i in items_ if i["state"] in ("on", "off")]
    if not known:
        return ""
    busy = [i["name"].strip() for i in known if i["state"] == "on"]
    if busy:
        return "Présence détectée : " + ", ".join(busy) + "."
    return "Aucune présence dans les zones surveillées : " + ", ".join(i["name"].strip() for i in known) + "."
