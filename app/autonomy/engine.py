"""Moteur d'autonomie de Jarvis.

Politique :
  urgent    -> agit seul si la règle figure dans `auto_rules`, parle (même la nuit) et notifie
  important -> propose une action à valider (HUD) ; parle sauf la nuit ; notifie
  minor     -> note dans le journal (repris dans le rapport du matin)

Jamais d'action sans validation, sauf règle explicitement listée dans `auto_rules`.

NOUVEAU : Polling optimisé
- Polling adaptatif : intervalle dynamique basé sur l'activité
- Polling ciblé : uniquement les entités surveillées
- Traitement parallèle des règles
"""
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional, Set

from autonomy import rules
from autonomy.store import Store

logger = logging.getLogger("JarvisAutonomy")

URGENT_REPEAT_MIN = 10
URGENT_MAX_REMINDERS = 3

# NOUVEAU : Configuration du polling optimisé
MIN_POLLING_INTERVAL = 5  # Secondes (minimum pour éviter la surcharge)
MAX_POLLING_INTERVAL = 60  # Secondes (maximum)
DEFAULT_POLLING_INTERVAL = 30  # Secondes

# NOUVEAU : Seuil pour le polling adaptatif
ACTIVE_ALERTS_THRESHOLD = 1  # Si des alertes urgentes, polling rapide
PENDING_PROPOSALS_THRESHOLD = 1  # Si des propositions en attente, polling moyen


@dataclass
class Settings:
    enabled: bool = False
    interval: int = 30
    auto_rules: list = field(default_factory=list)
    approvers: list = field(default_factory=list)
    proposal_ttl_min: int = 120
    daily_report_time: str = ""
    adaptive_polling: bool = True
    targeted_polling: bool = True
    parallel_processing: bool = True


class AutonomyEngine:
    """Les dépendances (réseau, voix, notifications) sont injectées : le moteur se teste sans HA."""

    def __init__(self, store: Store, settings: Settings, params: rules.Params, *,
                 fetch_states, execute, speak, notify, report, local_now, handlers=None, vision=None,
                 fetch_targeted_states=None):
        self.store = store
        self.s = settings
        self.params = params
        self.fetch_states = fetch_states   # async () -> list[dict] (toutes les entités)
        self.fetch_targeted_states = fetch_targeted_states or fetch_states  # async (entities) -> list[dict]
        self.execute = execute             # async (domain, service, entity_id) -> str ("OK ..." si réussi)
        self.speak = speak                 # async (text) -> None
        self.notify = notify               # async (title, message) -> None
        self.report = report               # async () -> str  (texte parlé du diagnostic)
        self.local_now = local_now         # async () -> datetime (fuseau local)
        self.handlers = handlers or {}     # type d'action -> async (action: dict) -> str ("OK ..." si réussi)
        self.vision = vision               # Vision | None
        self.last_tick: str | None = None
        self.states_by_id: dict = {}
        self.active: dict = {
            k: {"severity": v["severity"], "first": v["first_seen"], "last": v["last_notified"], "n": v["notified_count"]}
            for k, v in store.active_load().items()
        }
        # NOUVEAU : Tracking pour le polling optimisé
        self._urgent_alerts_count: int = 0
        self._pending_proposals_count: int = 0
        self._last_activity_time: Optional[datetime] = None

    # ------------------------------------------------------------------ boucle
    async def run(self):
        await asyncio.sleep(10)
        while True:
            try:
                await self.tick()
            except Exception:
                logger.exception("Erreur dans la boucle d'autonomie")
            # NOUVEAU : Intervalle adaptatif
            interval = self._calculate_adaptive_interval()
            logger.debug("Prochain tick dans %s secondes (intervalle adaptatif)", interval)
            await asyncio.sleep(max(5, interval))  # Minimum 5 secondes pour éviter la surcharge

    async def tick(self):
        now = await self.local_now()
        
        # NOUVEAU : Polling ciblé si activé
        if self.s.targeted_polling and self._has_watched_entities():
            watched_entities = self._get_watched_entities()
            states = await self._fetch_targeted_states(watched_entities)
            logger.debug("Polling ciblé : %d entités surveillées", len(watched_entities))
        else:
            states = await self.fetch_states()
            logger.debug("Polling complet : toutes les entités")
        
        self.states_by_id = {s.get("entity_id"): s for s in states}
        
        # NOUVEAU : Traitement parallèle des règles si activé
        if self.s.parallel_processing:
            findings = await self._evaluate_rules_parallel(states, now)
        else:
            findings = rules.evaluate(states, now, self.params)
        
        await self._process(findings, now)
        
        # NOUVEAU: Mettre à jour les compteurs d'activité
        self._update_activity_counters()
        
        if self.vision:
            try:
                for f in await self.vision.poll(now):
                    await self._announce(f, now)
            except Exception:
                logger.exception("Erreur de la vision (les règles continuent)")
        self._expire(now)
        await self._daily_report(now)
        self.last_tick = now.isoformat(timespec="seconds")
        self._last_activity_time = now

    # ----------------------------------------- NOUVEAU : Polling Optimisé
    def _calculate_adaptive_interval(self) -> int:
        """Calcule l'intervalle de polling en fonction de l'activité."""
        if self._urgent_alerts_count > 0:
            return 5
        if self._pending_proposals_count > 0:
            return 10
        if self._last_activity_time:
            time_since_activity = (datetime.now(timezone.utc) - self._last_activity_time.replace(tzinfo=timezone.utc)).total_seconds()
            if time_since_activity < 30:
                return 15
        return self.s.interval

    def _has_watched_entities(self) -> bool:
        """Vérifie s'il y a des entités à surveiller."""
        return bool(self.params.watched or self.params.hidden)

    def _get_watched_entities(self) -> Set[str]:
        """Récupère la liste des entités à surveiller."""
        watched = set(self.params.watched or [])
        for key in self.active:
            entity_id = key.split(":", 1)[-1]
            watched.add(entity_id)
        return watched

    async def _fetch_targeted_states(self, entities: Set[str]) -> list:
        """Récupère uniquement les états des entités spécifiées."""
        if self.fetch_targeted_states != self.fetch_states:
            try:
                return await self.fetch_targeted_states(entities)
            except Exception as e:
                logger.warning("Polling ciblé échoué: %s", e)
        all_states = await self.fetch_states()
        return [s for s in all_states if s.get("entity_id") in entities]

    async def _evaluate_rules_parallel(self, states: list, now: datetime) -> list:
        """Évalue les règles en parallèle."""
        BATCH_SIZE = 10
        batches = [states[i:i + BATCH_SIZE] for i in range(0, len(states), BATCH_SIZE)]
        tasks = [self._evaluate_batch(batch, now, self.params) for batch in batches]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        findings = []
        for result in results:
            if isinstance(result, Exception):
                logger.warning("Erreur évaluation parallèle: %s", result)
            elif isinstance(result, list):
                findings.extend(result)
        return findings

    async def _evaluate_batch(self, states: list, now: datetime, params: rules.Params) -> list:
        """Évalue un batch d'états."""
        return rules.evaluate(states, now, params)

    def _update_activity_counters(self) -> None:
        """Met à jour les compteurs d'activité."""
        self._urgent_alerts_count = sum(
            1 for v in self.active.values() if v.get("severity") == "urgent"
        )
        self._pending_proposals_count = len(self.store.proposals("pending"))

    # ------------------------------------------------------------ traitement
    def is_quiet(self, now: datetime) -> bool:
        return rules.in_window(now.time(), self.params.quiet_start, self.params.quiet_end)

    async def _process(self, findings: list, now: datetime):
        stamp = now.astimezone(timezone.utc).isoformat(timespec="seconds")
        current = {f.key: f for f in findings}

        for key, f in current.items():
            known = self.active.get(key)
            if known is None:
                self.active[key] = {"severity": f.severity, "first": stamp, "last": stamp, "n": 1}
                self.store.active_save(key, f.severity, stamp, stamp, 1)
                await self._announce(f, now)
            elif f.severity == "urgent" and known["n"] <= URGENT_MAX_REMINDERS:
                last = datetime.fromisoformat(known["last"])
                if now.astimezone(timezone.utc) - last >= timedelta(minutes=URGENT_REPEAT_MIN):
                    known["n"] += 1
                    known["last"] = stamp
                    self.store.active_save(key, f.severity, known["first"], stamp, known["n"])
                    await self._say(f"Rappel. {f.message}", urgent=True, now=now)

        for key in [k for k in self.active if k not in current]:
            sev = self.active.pop(key)["severity"]
            self.store.active_delete(key)
            if sev in ("urgent", "important"):
                self.store.log("info", "resolu", f"Situation terminée : {key}", key.split(":", 1)[-1])

    async def _announce(self, f: rules.Finding, now: datetime):
        self.store.log(f.severity, f.rule, f.message, f.entity_id)

        if f.severity == "minor":
            return

        if f.severity == "urgent":
            text = f.message
            if f.action and f.rule in self.s.auto_rules:
                result = await self.execute(f.action["domain"], f.action["service"], f.action["entity_id"])
                self.store.log("auto", f.rule, f"Action automatique : {f.action['domain']}.{f.action['service']} "
                                               f"sur {f.entity_id} -> {result}", f.entity_id)
                text += " J'ai agi automatiquement." if result.startswith("OK") else " L'action automatique a échoué."
            await self._say(text, urgent=True, now=now)
            return

        # important
        text = f.message
        if f.action:
            if not self.store.pending_for(f.rule, f.entity_id):
                pid = self.store.add_proposal(f.rule, f.entity_id, f.message, f.action, f.expect_state)
                self.store.log("proposition", f.rule, f"Proposition #{pid} : {f.action['domain']}.{f.action['service']} "
                                                      f"sur {f.entity_id}", f.entity_id)
            text += " Je peux le faire : valide dans le HUD."
        await self._say(text, urgent=False, now=now)

    async def _say(self, text: str, *, urgent: bool, now: datetime):
        try:
            await self.notify("Jarvis" + (" — URGENT" if urgent else ""), text)
        except Exception:
            logger.exception("Notification impossible")
        if urgent or not self.is_quiet(now):
            try:
                await self.speak(text)
            except Exception:
                logger.exception("Synthèse vocale impossible")

    # ----------------------------------------------------------- propositions
    def authorised(self, user: str | None) -> bool:
        """Seuls les `approvers` peuvent valider. Liste vide = tout accès via le panneau Jarvis."""
        if not self.s.approvers:
            return True
        return bool(user) and user.strip().lower() in [a.strip().lower() for a in self.s.approvers]

    async def decide(self, pid: int, approve: bool, user: str | None) -> dict:
        if not self.authorised(user):
            return {"ok": False, "code": 403, "detail": "Seul un approbateur autorisé peut valider."}
        prop = self.store.get_proposal(pid)
        if not prop:
            return {"ok": False, "code": 404, "detail": "Proposition introuvable."}
        if prop["status"] != "pending":
            return {"ok": False, "code": 409, "detail": f"Proposition déjà traitée ({prop['status']})."}

        who = user or "inconnu"
        if not approve:
            self.store.set_proposal(pid, "rejected", decided_by=who)
            self.store.log("info", "refus", f"Proposition #{pid} refusée par {who}", prop["entity_id"])
            return {"ok": True, "status": "rejected"}

        # L'état attendu doit être encore vrai : sinon la situation a changé depuis la proposition.
        if prop["expect_state"]:
            try:
                current = {s["entity_id"]: s for s in await self.fetch_states()}.get(prop["entity_id"])
            except Exception as e:
                return {"ok": False, "code": 502, "detail": f"Lecture de l'état impossible : {e}"}
            if not current or str(current.get("state")) != prop["expect_state"]:
                self.store.set_proposal(pid, "obsolete", decided_by=who, result="situation changée")
                self.store.log("info", "obsolete", f"Proposition #{pid} obsolète (l'état a changé)", prop["entity_id"])
                return {"ok": True, "status": "obsolete"}

        a = prop["action"]
        kind = a.get("type", "service")
        if kind == "service":
            result = await self.execute(a["domain"], a["service"], a["entity_id"])
        elif kind in self.handlers:
            try:
                result = await self.handlers[kind](a)
            except Exception as e:
                logger.exception("Échec du gestionnaire %s", kind)
                result = f"ERREUR : {e}"
        else:
            result = f"ERREUR : type d'action inconnu ({kind})."
        status = "executed" if result.startswith("OK") else "failed"
        self.store.set_proposal(pid, status, decided_by=who, result=result)
        self.store.log("action" if status == "executed" else "erreur", prop["rule"],
                       f"Proposition #{pid} validée par {who} : {result}", prop["entity_id"])
        return {"ok": True, "status": status, "result": result}

    def _expire(self, now: datetime):
        cutoff = (now.astimezone(timezone.utc) - timedelta(minutes=self.s.proposal_ttl_min)).isoformat(timespec="seconds")
        n = self.store.expire_proposals(cutoff)
        if n:
            self.store.log("info", "expire", f"{n} proposition(s) expirée(s) sans réponse")

    # ------------------------------------------------------- rapport quotidien
    async def _daily_report(self, now: datetime):
        hhmm = (self.s.daily_report_time or "").strip()
        if not hhmm:
            return
        target = rules.parse_time(hhmm, None)
        if target is None:
            return
        today = now.date().isoformat()
        if self.store.meta_get("daily_report_date") == today or now.time() < target:
            return
        self.store.meta_set("daily_report_date", today)
        since = self.store.meta_get("daily_report_ts")
        recent = [j for j in self.store.journal(200, since=since) if j["severity"] in ("urgent", "important", "minor")]
        pending = len(self.store.proposals("pending"))
        try:
            text = await self.report()
        except Exception as e:
            logger.exception("Rapport quotidien impossible")
            text = f"Le diagnostic n'a pas pu être fait : {e}."
        extra = f" Depuis le dernier rapport : {len(recent)} événement(s) noté(s)"
        extra += f", {pending} proposition(s) en attente." if pending else "."
        self.store.meta_set("daily_report_ts", datetime.now(timezone.utc).isoformat(timespec="seconds"))
        self.store.log("info", "rapport", "Rapport quotidien lu")
        await self.speak("Bonjour Olivier. " + text + extra)

    # ----------------------------------------------------------------- statut
    def snapshot(self, now: datetime | None = None) -> dict:
        return {
            "enabled": self.s.enabled,
            "last_tick": self.last_tick,
            "interval": self.s.interval,
            "quiet": self.is_quiet(now) if now else None,
            "pending": len(self.store.proposals("pending")),
            "active": [{"key": k, "severity": v["severity"], "since": v["first"]} for k, v in self.active.items()],
            "auto_rules": self.s.auto_rules,
            "approvers": self.s.approvers,
        }
