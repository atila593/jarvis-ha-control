"""Présence par zones, lue depuis Radar Map Manager (RMM).

RMM crée, pour chaque zone de détection dessinée sur le plan :
  - binary_sensor.rmm_<carte>_<zone>_occupancy   (zone occupée ou non)
  - sensor.rmm_<carte>_<zone>_count              (nombre de personnes, attribut zone_name)
Détection automatique : rien à configurer. Une entité listée dans hidden_entities est ignorée.
"""
import re

import config

OCC_RE = re.compile(r"^binary_sensor\.(rmm_.+)_occupancy$")
NAME_CLEAN_RE = re.compile(r"(?i)^rmm\s+\S+\s+|\s+occupancy$")


def _int(state) -> int:
    try:
        return int(float(state))
    except (TypeError, ValueError):
        return 0


def zones(states: list) -> list:
    """Liste des zones RMM : name, entity_id, known, occupied, count."""
    by_id = {s.get("entity_id"): s for s in states}
    hidden = set(config.HIDDEN_ENTITIES)
    out = []
    for eid, s in by_id.items():
        m = OCC_RE.match(eid or "")
        if not m or eid in hidden:
            continue
        counter = by_id.get(f"sensor.{m.group(1)}_count") or {}
        cattrs = counter.get("attributes") or {}
        attrs = s.get("attributes") or {}
        name = cattrs.get("zone_name") or NAME_CLEAN_RE.sub("", attrs.get("friendly_name", eid)).strip() or eid
        state = str(s.get("state"))
        occupied = state == "on"
        out.append({
            "entity_id": eid,
            "name": name,
            "known": state in ("on", "off"),
            "occupied": occupied,
            "count": max(_int(counter.get("state")), 1) if occupied else 0,
        })
    out.sort(key=lambda z: z["name"])
    return out


def describe(z: dict) -> str:
    if not z["known"]:
        return "Indisponible"
    if not z["occupied"]:
        return "Libre"
    return "Occupé" + (f" ({z['count']} personnes)" if z["count"] > 1 else "")


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


def spoken(items: list) -> str:
    """Phrase pour le rapport vocal. `items` = éléments du groupe « presence » du statut."""
    known = [i for i in items if i["state"] in ("on", "off")]
    if not known:
        return ""
    busy = [i["name"].strip() for i in known if i["state"] == "on"]
    if busy:
        return "Présence détectée : " + ", ".join(busy) + "."
    return "Aucune présence dans les zones surveillées : " + ", ".join(i["name"].strip() for i in known) + "."
