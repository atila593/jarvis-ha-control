import logging

import httpx

import config

logger = logging.getLogger("JarvisActions")

# Liste blanche : seuls ces services peuvent être appelés (jamais lock, alarme, etc.).
# Pas de "toggle" : une relance après erreur réseau ne doit jamais inverser l'état.
SERVICES = {
    "light": {"turn_on", "turn_off"},
    "cover": {"open_cover", "close_cover", "stop_cover", "set_cover_position"},
    "vacuum": {"start", "pause", "stop", "return_to_base", "locate"},
    "scene": {"turn_on"},
    "switch": {"turn_on", "turn_off"},
    "fan": {"turn_on", "turn_off"},
}


def allowed_domains() -> list:
    return [d for d in config.ALLOWED_DOMAINS if d in SERVICES]


class ActionRunner:
    """Exécute les actions demandées par Gemini, sous contrôle strict."""

    def __init__(self, known_entities: set):
        self.known = known_entities
        self.done = []      # actions réellement exécutées (pour l'affichage)
        self._seen = set()  # évite de rejouer deux fois la même action

    async def call_service(self, domain: str, service: str, entity_id: str,
                           brightness_pct: int = 0, position: int = -1) -> str:
        """Exécute une action sur un appareil de la maison.

        Args:
            domain: domaine de l'appareil (light, cover, vacuum, scene, switch, fan).
            service: action (light: turn_on/turn_off ; cover: open_cover/close_cover/stop_cover/set_cover_position ;
                vacuum: start/pause/stop/return_to_base/locate ; scene: turn_on).
            entity_id: identifiant exact de l'entité, pris dans le contexte fourni (ex. light.salon).
            brightness_pct: luminosité 1-100 pour light.turn_on, 0 si non précisée.
            position: position 0-100 pour cover.set_cover_position, -1 si non précisée.
        """
        if domain not in allowed_domains():
            return f"REFUSÉ : le domaine '{domain}' n'est pas autorisé."
        if service not in SERVICES[domain]:
            return f"REFUSÉ : l'action '{service}' n'est pas autorisée pour {domain}."
        if not entity_id.startswith(domain + ".") or entity_id not in self.known:
            return f"ERREUR : entité '{entity_id}' introuvable. Utilise un identifiant du contexte."
        if entity_id in config.HIDDEN_ENTITIES:
            return f"REFUSÉ : l'entité '{entity_id}' est masquée."

        payload = {"entity_id": entity_id}
        if domain == "light" and service == "turn_on" and 1 <= brightness_pct <= 100:
            payload["brightness_pct"] = brightness_pct
        if service == "set_cover_position":
            if not 0 <= position <= 100:
                return "ERREUR : position (0-100) requise."
            payload["position"] = position

        key = (domain, service, entity_id, tuple(sorted(payload.items())))
        if key in self._seen:
            return "Déjà exécuté pour cette demande."

        headers = {"Authorization": f"Bearer {config.SUPERVISOR_TOKEN}"}
        try:
            async with httpx.AsyncClient(timeout=10) as http:
                res = await http.post(f"{config.HA_API_URL}/services/{domain}/{service}", headers=headers, json=payload)
            res.raise_for_status()
        except Exception as e:
            logger.error("Échec %s.%s sur %s: %s", domain, service, entity_id, e)
            return f"ERREUR : Home Assistant a refusé l'action ({e})."

        self._seen.add(key)
        self.done.append({"domain": domain, "service": service, "entity_id": entity_id})
        logger.info("ACTION %s.%s -> %s %s", domain, service, entity_id, payload)
        return f"OK : {domain}.{service} exécuté sur {entity_id}."
