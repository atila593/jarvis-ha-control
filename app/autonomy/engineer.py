"""Ingénieur HA : Jarvis propose, Olivier valide, Jarvis applique, vérifie, et sait revenir en arrière.

Garde-fous :
  - tout passe par une proposition validée par un approbateur (jamais d'écriture directe) ;
  - validation stricte (taille, services interdits, entités inexistantes) à la proposition ET à l'application ;
  - par défaut Jarvis ne modifie / supprime que ce qu'il a créé (option engineer_edit_existing) ;
  - après écriture, vérification que HA a bien chargé l'objet ; sinon retour arrière automatique ;
  - chaque modification est journalisée avec son état « avant » : annulation possible (« annule ça »).
"""
import asyncio
import json
import logging
import re
import secrets
import unicodedata

from autonomy.store import Store

logger = logging.getLogger("JarvisEngineer")

KINDS = ("automation", "script")
OPS = ("create", "update", "delete")
MAX_CONFIG_BYTES = 20_000
MAX_PENDING = 10
SIGNATURE = "Créée par Jarvis"

# Domaines/services jamais autorisés dans une configuration générée par Jarvis.
BLOCKED_DOMAINS = {"lock", "alarm_control_panel", "shell_command", "python_script", "hassio", "rest_command", "cloud"}
BLOCKED_SERVICES = {"homeassistant.restart", "homeassistant.stop", "homeassistant.reload_all",
                    "homeassistant.reload_config_entry", "homeassistant.update_entity"}
ENTITY_RE = re.compile(r"^[a-z_]+\.[a-z0-9_]+$")
SERVICE_KEYS = ("action", "service")


class EngineerError(Exception):
    pass


def slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:40] or "sans_nom"


def _walk(node, services: set, entities: set):
    """Parcourt une config HA et collecte services appelés et entity_id littéraux (hors templates)."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k in SERVICE_KEYS and isinstance(v, str) and "." in v and "{{" not in v:
                services.add(v.strip())
            elif k == "entity_id":
                vals = v if isinstance(v, list) else [v]
                for e in vals:
                    if isinstance(e, str) and "{{" not in e and e.lower() != "all":
                        entities.add(e.strip())
            _walk(v, services, entities)
    elif isinstance(node, list):
        for x in node:
            _walk(x, services, entities)


def validate(kind: str, config: dict, known_entities: set) -> list[str]:
    """Renvoie la liste des problèmes (vide = valide)."""
    problems = []
    if not isinstance(config, dict):
        return ["La configuration doit être un objet JSON."]
    if len(json.dumps(config)) > MAX_CONFIG_BYTES:
        problems.append("Configuration trop volumineuse.")
    if not str(config.get("alias") or "").strip():
        problems.append("Il manque un 'alias' (nom lisible).")
    if kind == "automation":
        if not (config.get("triggers") or config.get("trigger")):
            problems.append("Il manque au moins un déclencheur ('triggers').")
        if not (config.get("actions") or config.get("action")):
            problems.append("Il manque au moins une action ('actions').")
    elif kind == "script":
        if not config.get("sequence"):
            problems.append("Il manque la séquence ('sequence').")
    services, entities = set(), set()
    _walk(config, services, entities)
    for s in services:
        if s in BLOCKED_SERVICES or s.split(".")[0] in BLOCKED_DOMAINS:
            problems.append(f"Service interdit pour Jarvis : {s}.")
    unknown = sorted(e for e in entities if ENTITY_RE.match(e) and e not in known_entities)
    bad = sorted(e for e in entities if not ENTITY_RE.match(e))
    if unknown:
        problems.append("Entités inexistantes : " + ", ".join(unknown[:8]))
    if bad:
        problems.append("Identifiants d'entité invalides : " + ", ".join(bad[:8]))
    return problems


class Engineer:
    def __init__(self, store: Store, ha, *, edit_existing: bool = False, sleep=asyncio.sleep, load_retries: int = 5):
        self.store = store
        self.ha = ha
        self.edit_existing = edit_existing
        self.sleep = sleep
        self.load_retries = load_retries

    # ------------------------------------------------------------------ outils
    async def _known(self) -> tuple[set, list]:
        states = await self.ha.get("states") or []
        return {s["entity_id"] for s in states}, states

    @staticmethod
    def _path(kind: str, object_id: str) -> str:
        return f"config/{kind}/config/{object_id}"

    # ------------------------------------------------------------- propositions
    async def propose_change(self, kind: str, op: str, config_json: str = "", object_id: str = "",
                             reason: str = "") -> dict:
        kind, op, object_id = (kind or "").strip(), (op or "").strip(), (object_id or "").strip()
        if kind not in KINDS or op not in OPS:
            return {"ok": False, "error": f"kind doit être {KINDS}, operation {OPS}."}
        if len(self.store.proposals("pending")) >= MAX_PENDING:
            return {"ok": False, "error": "Trop de propositions en attente : Olivier doit d'abord en traiter."}

        known, _ = await self._known()
        config = None
        if op in ("create", "update"):
            try:
                config = json.loads(config_json)
            except Exception as e:
                return {"ok": False, "error": f"config_json invalide : {e}"}
            problems = validate(kind, config, known)
            if problems:
                return {"ok": False, "error": " ".join(problems)}

        existing = None
        if op == "create":
            object_id = f"jarvis_{slug(config['alias'])}_{secrets.token_hex(2)}"
            alias = config["alias"].strip()
            config["alias"] = alias if alias.startswith("[Jarvis]") else f"[Jarvis] {alias}"
            config["description"] = (str(config.get("description") or "").strip() + f" {SIGNATURE}.").strip()
        else:
            if not object_id:
                return {"ok": False, "error": "object_id requis pour modifier ou supprimer."}
            existing = await self.ha.get(self._path(kind, object_id))
            if existing is None:
                return {"ok": False, "error": f"{kind} '{object_id}' introuvable (ou définie en YAML)."}
            if not self.edit_existing and SIGNATURE not in str(existing.get("description") or ""):
                return {"ok": False, "error": "Jarvis ne peut modifier ou supprimer que ce qu'il a créé "
                                              "(option engineer_edit_existing)."}
            if op == "update":
                config["description"] = str(config.get("description") or existing.get("description") or "")

        name = (config or existing or {}).get("alias", object_id)
        verb = {"create": "Créer", "update": "Modifier", "delete": "Supprimer"}[op]
        summary = f"{verb} {kind} « {name} »" + (f" — {reason.strip()}" if reason.strip() else "")
        action = {"type": "config_change", "kind": kind, "op": op, "object_id": object_id, "config": config,
                  "summary": summary}
        pid = self.store.add_proposal("engineer", f"{kind}.{object_id}", summary, action, None)
        self.store.log("proposition", "engineer", f"Proposition #{pid} : {summary}", f"{kind}.{object_id}")
        return {"ok": True, "id": pid, "summary": summary}

    # -------------------------------------------------------------- application
    async def apply_change(self, action: dict) -> str:
        kind, op, oid, config = action["kind"], action["op"], action["object_id"], action.get("config")
        known, _ = await self._known()
        if op in ("create", "update"):
            problems = validate(kind, config, known)
            if problems:
                return "ERREUR : validation à l'application : " + " ".join(problems)
        path = self._path(kind, oid)
        before = await self.ha.get(path)
        if op == "create" and before is not None:
            return f"ERREUR : {kind} '{oid}' existe déjà."
        if op in ("update", "delete") and before is None:
            return f"ERREUR : {kind} '{oid}' introuvable."

        cid = self.store.add_change(kind, oid, op, before, config)
        try:
            if op == "delete":
                await self.ha.delete(path)
            else:
                await self.ha.post(path, config)
        except Exception as e:
            await self._restore(kind, oid, before)
            self.store.set_change(cid, "failed", f"écriture refusée : {e}")
            return f"ERREUR : écriture refusée par HA ({e}). État précédent conservé."

        ok, why = await self._verify(kind, oid, op)
        if not ok:
            await self._restore(kind, oid, before)
            self.store.set_change(cid, "rolled_back", why)
            return f"ERREUR : {why} Retour arrière automatique effectué."
        self.store.set_change(cid, "applied")
        return f"OK : {op} {kind} {oid} appliqué (modification #{cid}, annulable)."

    async def _verify(self, kind: str, oid: str, op: str) -> tuple[bool, str]:
        stored = await self.ha.get(self._path(kind, oid))
        if op == "delete":
            return (stored is None, "la suppression n'a pas été prise en compte.")
        if stored is None:
            return False, "HA n'a pas enregistré la configuration."
        for _ in range(self.load_retries):                   # HA recharge puis crée l'entité : on attend
            states = await self.ha.get("states") or []
            for s in states:
                eid = s.get("entity_id", "")
                if kind == "automation" and eid.startswith("automation.") and (s.get("attributes") or {}).get("id") == oid:
                    return (s.get("state") != "unavailable", "l'automation est chargée mais indisponible (config invalide).")
                if kind == "script" and eid == f"script.{oid}":
                    return (s.get("state") != "unavailable", "le script est chargé mais indisponible (config invalide).")
            await self.sleep(1)
        return False, "HA n'a pas chargé l'objet (config invalide ?)."

    async def _restore(self, kind: str, oid: str, before):
        try:
            if before is None:
                await self.ha.delete(self._path(kind, oid))
            else:
                await self.ha.post(self._path(kind, oid), before)
        except Exception:
            logger.exception("Restauration impossible pour %s %s", kind, oid)

    # ---------------------------------------------------------------- annulation
    async def undo(self, change_id: int) -> str:
        ch = self.store.get_change(change_id)
        if not ch:
            return "ERREUR : modification introuvable."
        if ch["status"] != "applied":
            return f"ERREUR : modification #{change_id} non annulable (statut {ch['status']})."
        kind, oid = ch["kind"], ch["object_id"]
        try:
            if ch["before"] is None:
                await self.ha.delete(self._path(kind, oid))
            else:
                await self.ha.post(self._path(kind, oid), ch["before"])
        except Exception as e:
            return f"ERREUR : annulation refusée par HA ({e})."
        self.store.set_change(change_id, "undone")
        self.store.log("action", "engineer", f"Modification #{change_id} annulée ({kind} {oid})", f"{kind}.{oid}")
        return f"OK : modification #{change_id} annulée ({kind} {oid})."

    async def undo_last(self) -> str:
        ch = self.store.last_applied_change()
        return await self.undo(ch["id"]) if ch else "ERREUR : aucune modification à annuler."

    # ------------------------------------------------------- nettoyage d'entités
    async def references(self, entity_id: str) -> dict:
        """Où l'entité est utilisée (automations/scripts UI et dashboards). `unscanned` = définitions non lisibles (YAML)."""
        refs, unscanned = [], 0
        _, states = await self._known()
        for s in states:
            eid = s.get("entity_id", "")
            if eid.startswith("automation."):
                oid = (s.get("attributes") or {}).get("id")
                cfg = await self.ha.get(self._path("automation", oid)) if oid else None
                kind = "automation"
            elif eid.startswith("script."):
                oid = eid.split(".", 1)[1]
                cfg = await self.ha.get(self._path("script", oid))
                kind = "script"
            else:
                continue
            if cfg is None:
                unscanned += 1
            elif entity_id in json.dumps(cfg):
                refs.append(f"{kind} {cfg.get('alias', eid)}")
        try:
            boards = [None] + [d.get("url_path") for d in (await self.ha.ws("lovelace/dashboards/list") or [])]
            for url in boards:
                cfg = await self.ha.ws("lovelace/config", url_path=url) if url else await self.ha.ws("lovelace/config")
                if entity_id in json.dumps(cfg):
                    refs.append(f"dashboard {url or 'par défaut'}")
        except Exception as e:
            logger.warning("Lecture des dashboards impossible: %s", e)
            unscanned += 1
        return {"refs": refs, "unscanned": unscanned}

    async def propose_remove_entity(self, entity_id: str, reason: str = "") -> dict:
        _, states = await self._known()
        st = next((s for s in states if s.get("entity_id") == entity_id), None)
        if st is None:
            return {"ok": False, "error": f"Entité {entity_id} introuvable."}
        attrs = st.get("attributes") or {}
        if st.get("state") not in ("unavailable", "unknown") and not attrs.get("restored"):
            return {"ok": False, "error": f"{entity_id} fonctionne (état {st.get('state')}) : je ne propose pas de la retirer."}
        info = await self.references(entity_id)
        if info["refs"]:
            return {"ok": False, "error": f"{entity_id} est utilisée par : {', '.join(info['refs'][:5])}."}
        warn = f" (attention : {info['unscanned']} définition(s) non lisibles, YAML ?)" if info["unscanned"] else ""
        summary = f"Retirer l'entité {entity_id} (irréversible){warn}" + (f" — {reason.strip()}" if reason.strip() else "")
        action = {"type": "entity_remove", "entity_id": entity_id, "summary": summary}
        pid = self.store.add_proposal("engineer", entity_id, summary, action, None)
        self.store.log("proposition", "engineer", f"Proposition #{pid} : {summary}", entity_id)
        return {"ok": True, "id": pid, "summary": summary}

    async def remove_entity(self, action: dict) -> str:
        eid = action["entity_id"]
        _, states = await self._known()
        st = next((s for s in states if s.get("entity_id") == eid), None)
        if st and st.get("state") not in ("unavailable", "unknown") and not (st.get("attributes") or {}).get("restored"):
            return f"ERREUR : {eid} fonctionne maintenant, retrait annulé."
        info = await self.references(eid)
        if info["refs"]:
            return f"ERREUR : {eid} est maintenant utilisée par {', '.join(info['refs'][:3])}."
        try:
            before = await self.ha.ws("config/entity_registry/get", entity_id=eid)
        except Exception:
            before = None
        try:
            await self.ha.ws("config/entity_registry/remove", entity_id=eid)
        except Exception as e:
            return f"ERREUR : retrait refusé par HA ({e})."
        cid = self.store.add_change("entity", eid, "remove", before, None)
        self.store.set_change(cid, "irreversible", "entrée de registre supprimée")
        return f"OK : entité {eid} retirée (irréversible)."

    async def stale_entities(self, min_days: int, now_utc) -> list[dict]:
        """Candidats au nettoyage : état restauré (jamais revenue depuis le démarrage) ou indisponible depuis N jours."""
        from datetime import datetime, timezone
        _, states = await self._known()
        out = []
        for s in states:
            attrs = s.get("attributes") or {}
            if s.get("state") not in ("unavailable", "unknown"):
                continue
            try:
                since = datetime.fromisoformat(s["last_changed"].replace("Z", "+00:00"))
                days = (now_utc - since.astimezone(timezone.utc)).total_seconds() / 86400
            except Exception:
                days = 0
            if attrs.get("restored") or days >= min_days:
                out.append({"entity_id": s["entity_id"], "days": round(days, 1), "restored": bool(attrs.get("restored"))})
        return sorted(out, key=lambda x: -x["days"])
