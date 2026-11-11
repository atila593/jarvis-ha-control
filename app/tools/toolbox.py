"""Outils mis à disposition de Gemini pour UNE requête, selon le rôle de la personne qui parle."""
import logging
from datetime import datetime, timezone

from autonomy.access import SECRET_RE

logger = logging.getLogger("JarvisToolbox")


class Toolbox:
    def __init__(self, engineer, store, who: str | None, role: str, *, engineer_on: bool, memory_on: bool, stale_days: int = 7):
        self.engineer, self.store, self.who, self.role = engineer, store, who, role
        self.engineer_on, self.memory_on, self.stale_days = engineer_on, memory_on, stale_days

    def tools(self) -> list:
        out = []
        if self.engineer_on and self.role == "admin" and self.engineer:
            out += [self.propose_automation, self.propose_script, self.propose_remove_entity, self.list_stale_entities]
        if self.memory_on and self.who and self.role in ("admin", "member"):
            out.append(self.remember)
        return out

    @staticmethod
    def _reply(r: dict) -> str:
        if r.get("ok"):
            return (f"Proposition n°{r['id']} créée : {r['summary']}. Elle n'est PAS appliquée : "
                    "Olivier doit la valider (panneau Jarvis, ou à la voix avec son code).")
        return f"REFUSÉ : {r['error']}"

    async def propose_automation(self, operation: str, config_json: str = "", reason: str = "", object_id: str = "") -> str:
        """Propose de créer, modifier ou supprimer une automatisation Home Assistant. N'applique RIEN : crée une proposition à valider.

        Args:
            operation: 'create', 'update' ou 'delete'.
            config_json: configuration complète en JSON au format Home Assistant récent (alias, description, triggers, conditions, actions). Pour 'delete', laisser vide.
            reason: pourquoi (une phrase).
            object_id: identifiant de l'automatisation à modifier/supprimer ; vide pour 'create'.
        """
        return self._reply(await self.engineer.propose_change("automation", operation, config_json, object_id, reason))

    async def propose_script(self, operation: str, config_json: str = "", reason: str = "", object_id: str = "") -> str:
        """Comme propose_automation, mais pour un script (config avec alias et sequence). N'applique RIEN.

        Args:
            operation: 'create', 'update' ou 'delete'.
            config_json: configuration JSON du script (alias, sequence).
            reason: pourquoi (une phrase).
            object_id: identifiant du script à modifier/supprimer ; vide pour 'create'.
        """
        return self._reply(await self.engineer.propose_change("script", operation, config_json, object_id, reason))

    async def propose_remove_entity(self, entity_id: str, reason: str = "") -> str:
        """Propose de retirer une entité fantôme (indisponible, utilisée nulle part). Irréversible, donc soumis à validation.

        Args:
            entity_id: identifiant exact de l'entité.
            reason: pourquoi (une phrase).
        """
        return self._reply(await self.engineer.propose_remove_entity(entity_id, reason))

    async def list_stale_entities(self) -> str:
        """Liste les entités fantômes candidates au nettoyage (restaurées ou indisponibles depuis longtemps)."""
        items = await self.engineer.stale_entities(self.stale_days, datetime.now(timezone.utc))
        if not items:
            return "Aucune entité fantôme."
        return f"{len(items)} candidates, par ancienneté : " + "; ".join(f"{i['entity_id']} ({i['days']} j)" for i in items[:15])

    async def remember(self, fact: str) -> str:
        """Retient un fait utile sur la personne qui parle (préférence, habitude). Jamais de secret, de mot de passe ni de code.

        Args:
            fact: le fait, en une phrase courte.
        """
        fact = (fact or "").strip()
        if not fact or len(fact) > 200:
            return "REFUSÉ : fait vide ou trop long."
        if SECRET_RE.search(fact):
            return "REFUSÉ : je ne retiens jamais de mot de passe, code ou donnée bancaire."
        self.store.add_fact(self.who, fact)
        return "Retenu."
