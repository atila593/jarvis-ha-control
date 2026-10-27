import html
import logging
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

import config

logger = logging.getLogger("JarvisStatus")

MAP_RE = re.compile(r"carte|map", re.I)
LEVEL_LABEL = {"ok": "OK", "warn": "ATTENTION", "ko": "KO"}
OVERALL_LABEL = {"ok": "TOUT EST NOMINAL", "warn": "ATTENTION", "ko": "ALERTE"}
KIND_ORDER = {"vacuum": 0, "cover": 1, "light": 2, "plug": 3, "other": 4}
GROUPS = [("modules", "Modules domotiques"), ("network", "Réseau & caméras"), ("system", "Serveur & services")]

STATE_FR = {
    "docked": "À la base", "cleaning": "Nettoyage", "returning": "Retour à la base", "idle": "Inactif",
    "paused": "En pause", "error": "Erreur", "recording": "Enregistre", "streaming": "Flux actif",
    "locked": "Verrouillée", "unlocked": "Déverrouillée", "jammed": "Bloquée",
    "open": "Ouvert", "closed": "Fermé", "opening": "Ouverture", "closing": "Fermeture",
    "unavailable": "Indisponible", "unknown": "Inconnu",
}


def _kind(domain: str) -> str:
    if domain in ("vacuum", "cover", "light"):
        return domain
    return "plug" if domain in ("switch", "fan") else "other"


def _is_garage(eid: str, name: str) -> bool:
    return "garage" in eid.lower() or "garage" in name.lower() or "rideau" in eid.lower()


def _num(state: str):
    try:
        return float(state)
    except (TypeError, ValueError):
        return None


def _level(domain, dclass, state, attrs, eid, name) -> str:
    if state == "unavailable":
        return "ko"
    if state == "unknown":
        return "warn"
    if domain == "vacuum":
        return "ko" if state == "error" else "ok"
    if domain == "lock":
        return "ko" if state == "jammed" else "ok"
    if domain == "camera":
        return "ok" if state in ("idle", "recording", "streaming") else "warn"
    if domain == "cover":
        return "warn" if (state == "open" and _is_garage(eid, name)) else "ok"
    if domain == "update":
        return "warn" if state == "on" else "ok"
    if domain == "binary_sensor":
        if dclass == "problem":
            return "ko" if state == "on" else "ok"
        if dclass in ("connectivity", "running"):
            return "ko" if state == "off" else "ok"
    if domain == "sensor":
        v, unit = _num(state), attrs.get("unit_of_measurement")
        if v is not None and unit == "%" and dclass != "battery":
            return "ko" if v >= 95 else "warn" if v >= 85 else "ok"
        if v is not None and (dclass == "temperature" or unit == "°C") and "temperature" in eid.lower() and "localhost" in eid.lower():
            return "ko" if v >= 85 else "warn" if v >= 75 else "ok"
    return "ok"


def _display(domain, dclass, state, attrs) -> str:
    if state in ("unavailable", "unknown"):
        return STATE_FR[state]
    if domain == "light":
        return {"on": "Allumé", "off": "Éteint"}.get(state, state)
    if domain in ("switch", "fan"):
        return {"on": "Actif", "off": "Arrêté"}.get(state, state)
    if domain == "update":
        return "Mise à jour disponible" if state == "on" else "À jour"
    if domain == "binary_sensor":
        if dclass == "problem":
            return "Problème" if state == "on" else "RAS"
        if dclass == "connectivity":
            return "Connecté" if state == "on" else "Déconnecté"
        if dclass == "running":
            return "En marche" if state == "on" else "Arrêté"
    if domain == "sensor":
        unit = attrs.get("unit_of_measurement")
        return f"{state} {unit}" if unit else state
    return STATE_FR.get(state, state)


def _item(s: dict) -> dict:
    eid = s["entity_id"]
    domain = eid.split(".")[0]
    attrs = s.get("attributes", {}) or {}
    state = str(s.get("state"))
    dclass = attrs.get("device_class") or ""
    name = attrs.get("friendly_name", eid)
    return {
        "entity_id": eid,
        "name": name,
        "state": state,
        "display": _display(domain, dclass, state, attrs),
        "level": _level(domain, dclass, state, attrs, eid, name),
        "kind": _kind(domain),
    }


def _group_for(s: dict) -> str:
    eid = s["entity_id"]
    domain = eid.split(".")[0]
    attrs = s.get("attributes", {}) or {}
    dclass = attrs.get("device_class") or ""
    if domain == "camera":
        return "network"
    if domain == "update":
        return "system"
    if domain == "binary_sensor":
        return {"connectivity": "network", "problem": "modules"}.get(dclass, "system")
    if domain == "sensor":
        return "system"
    return "modules"


def classify(states: list) -> list:
    hidden = set(config.HIDDEN_ENTITIES)
    by_id = {s.get("entity_id"): s for s in states}
    out = {gid: [] for gid, _ in GROUPS}
    seen = set()

    def place(gid, s):
        if s["entity_id"] in seen:
            return
        seen.add(s["entity_id"])
        out[gid].append(_item(s))

    # 1. Entités surveillées explicitement (option extra_entities)
    for eid in config.EXTRA_ENTITIES:
        if eid in hidden or eid in seen:
            continue
        s = by_id.get(eid)
        if s:
            place(_group_for(s), s)
        else:
            seen.add(eid)
            domain = eid.split(".")[0]
            out["network" if domain == "camera" else "modules"].append(
                {"entity_id": eid, "name": eid, "state": "missing", "display": "Introuvable", "level": "warn", "kind": _kind(domain)})

    # 2. Découverte automatique (désactivable avec auto_discover: false)
    if config.AUTO_DISCOVER:
        power, cams = 0, 0
        for s in states:
            eid = s.get("entity_id", "")
            if eid in hidden:
                continue
            domain = eid.split(".")[0]
            attrs = s.get("attributes", {}) or {}
            dclass = attrs.get("device_class") or ""
            name = attrs.get("friendly_name", eid)
            if domain == "camera":
                if not MAP_RE.search(name) and not MAP_RE.search(eid) and cams < 12:
                    cams += 1
                    place("network", s)
            elif domain == "binary_sensor" and dclass == "connectivity":
                place("network", s)
            elif domain in ("vacuum", "lock") or (domain == "binary_sensor" and dclass == "problem"):
                place("modules", s)
            elif domain == "sensor" and dclass == "power" and power < 6:
                power += 1
                place("modules", s)

    out["modules"].sort(key=lambda it: KIND_ORDER.get(it["kind"], 9))
    return [{"id": gid, "title": title, "items": out[gid]} for gid, title in GROUPS]


async def _ha_get(path: str):
    headers = {"Authorization": f"Bearer {config.SUPERVISOR_TOKEN}"}
    async with httpx.AsyncClient(timeout=8) as http:
        res = await http.get(f"{config.HA_API_URL}/{path}", headers=headers)
    res.raise_for_status()
    return res.json()


async def _now_str() -> str:
    tz = "UTC"
    try:
        tz = (await _ha_get("config")).get("time_zone") or "UTC"
    except Exception:
        pass
    try:
        return datetime.now(ZoneInfo(tz)).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")


async def build_status(diagnose) -> dict:
    core = await diagnose.check_system_health()
    ha_ok = True
    try:
        states = await _ha_get("states")
    except Exception as e:
        logger.warning("États HA indisponibles: %s", e)
        states, ha_ok = [], False

    groups = classify(states)
    counts = {"ok": 0, "warn": 0, "ko": 0}
    for g in groups:
        for it in g["items"]:
            counts[it["level"]] += 1
    if not core.get("healthy") or not ha_ok or counts["ko"]:
        overall = "ko"
    elif counts["warn"]:
        overall = "warn"
    else:
        overall = "ok"
    return {
        "generated": await _now_str(),
        "core": core,
        "ha_ok": ha_ok,
        "overall": overall,
        "overall_label": OVERALL_LABEL[overall],
        "counts": counts,
        "groups": groups,
        "gemini_configured": bool(config.GEMINI_API_KEY),
        "speak_configured": bool(config.SPEAK_SERVICE),
    }


def build_report(status: dict, analysis: str | None) -> dict:
    anomalies = [it for g in status["groups"] for it in g["items"] if it["level"] != "ok"]
    return {**status, "anomalies": anomalies, "analysis": analysis}


def render_txt(r: dict) -> str:
    core = r["core"]
    lines = [
        "JARVIS — RAPPORT DE DIAGNOSTIC",
        f"Généré le : {r['generated']}",
        f"Statut global : {r['overall_label']}",
        "Home Assistant Core : " + (f"OK · {core.get('version')}" if core.get("healthy") else "INJOIGNABLE"),
        f"Entités : {r['counts']['ok']} OK · {r['counts']['warn']} attention · {r['counts']['ko']} KO",
        "",
    ]
    for g in r["groups"]:
        lines.append(f"[{g['title']}]")
        if not g["items"]:
            lines.append("  (aucune entité détectée)")
        for it in g["items"]:
            lines.append(f"  [{LEVEL_LABEL[it['level']]}] {it['name']} : {it['display']}  ({it['entity_id']})")
        lines.append("")
    if r["anomalies"]:
        lines.append("ANOMALIES")
        lines += [f"  - {a['name']} : {a['display']}" for a in r["anomalies"]]
    else:
        lines.append("Aucune anomalie détectée.")
    if r.get("analysis"):
        lines += ["", "ANALYSE JARVIS", r["analysis"]]
    return "\n".join(lines) + "\n"


def render_html(r: dict) -> str:
    e = html.escape
    color = {"ok": "#0a9d58", "warn": "#e08a00", "ko": "#d93025"}
    core = r["core"]
    rows = ""
    for g in r["groups"]:
        rows += f"<h2>{e(g['title'])}</h2><table>"
        for it in g["items"] or []:
            rows += (f"<tr><td><span class='dot' style='background:{color[it['level']]}'></span></td>"
                     f"<td><b>{e(it['name'])}</b><br><small>{e(it['entity_id'])}</small></td>"
                     f"<td>{e(it['display'])}</td><td class='lv' style='color:{color[it['level']]}'>{LEVEL_LABEL[it['level']]}</td></tr>")
        if not g["items"]:
            rows += "<tr><td colspan=4><i>Aucune entité détectée</i></td></tr>"
        rows += "</table>"
    analysis = f"<h2>Analyse Jarvis</h2><p>{e(r['analysis'])}</p>" if r.get("analysis") else ""
    core_txt = f"OK · {e(str(core.get('version')))}" if core.get("healthy") else "INJOIGNABLE"
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Jarvis — Rapport de diagnostic</title>
<style>body{{font-family:system-ui,sans-serif;max-width:820px;margin:24px auto;padding:0 16px;color:#16202a}}
h1{{margin:0}} h2{{margin-top:28px;border-bottom:2px solid #00a7bd;padding-bottom:4px;color:#007a8c}}
.badge{{display:inline-block;padding:6px 14px;border-radius:20px;color:#fff;font-weight:700;background:{color[r['overall']]}}}
table{{width:100%;border-collapse:collapse}} td{{padding:8px 6px;border-bottom:1px solid #e3e8ec;vertical-align:top}}
small{{color:#6b7782}} .dot{{display:inline-block;width:12px;height:12px;border-radius:50%}} .lv{{font-weight:700;text-align:right}}
@media print{{body{{margin:0}}}}</style></head><body>
<h1>J.A.R.V.I.S — Rapport de diagnostic</h1><p>Généré le {e(r['generated'])}</p>
<p><span class="badge">{e(r['overall_label'])}</span></p>
<p>Home Assistant Core : <b>{core_txt}</b><br>Entités : {r['counts']['ok']} OK · {r['counts']['warn']} attention · {r['counts']['ko']} KO</p>
{rows}{analysis}</body></html>"""
