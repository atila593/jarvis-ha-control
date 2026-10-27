import asyncio
import logging

import httpx
from google import genai
from google.genai import errors, types

import config
from assistant.prompts import system_prompt
from tools.actions import ActionRunner, allowed_domains

logger = logging.getLogger("JarvisEngine")

# Domaines pilotables en premier, puis le reste (les capteurs en dernier)
OTHER_DOMAINS = ["camera", "media_player", "climate", "binary_sensor", "sensor"]
MAX_ENTITIES = 150

RETRYABLE = {429, 500, 502, 503, 504}
ATTEMPTS = 3
TIMEOUT = 40


class GeminiUnavailable(Exception):
    pass


class JarvisEngine:
    def __init__(self):
        self.client = genai.Client(api_key=config.GEMINI_API_KEY) if config.GEMINI_API_KEY else None

    async def _generate(self, model: str, contents: str, tools=None):
        return await self.client.aio.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt(bool(tools)),
                tools=tools or None,
            ),
        )

    async def process_command(self, prompt: str):
        """Retourne (texte, actions exécutées)."""
        if not self.client:
            return "Clé API Gemini non configurée : renseigne gemini_api_key dans les options de l'add-on.", []

        context, known = await self._fetch_ha_states()
        tools, runner = None, None
        if config.ACTIONS_ENABLED and allowed_domains() and known:
            runner = ActionRunner(known)
            tools = [runner.call_service]
        text = await self.ask(f"[Contexte domotique actuel]\n{context}\n\n[Requête]\n{prompt}", tools)
        return text, (runner.done if runner else [])

    async def analyse(self, report_text: str) -> str:
        if not self.client:
            return "Analyse IA indisponible : clé API Gemini non configurée."
        return await self.ask(
            f"[Rapport de statut]\n{report_text}\n\n[Requête]\n"
            "Fais le diagnostic : résume l'état général en 4 phrases maximum, signale chaque anomalie "
            "et propose une action pour chacune. Pas de markdown."
        )

    async def ask(self, contents: str, tools=None) -> str:
        models = [config.GEMINI_MODEL]
        if config.GEMINI_FALLBACK_MODEL and config.GEMINI_FALLBACK_MODEL != config.GEMINI_MODEL:
            models.append(config.GEMINI_FALLBACK_MODEL)

        last_error = None
        for model in models:
            for attempt in range(ATTEMPTS):
                try:
                    response = await asyncio.wait_for(self._generate(model, contents, tools), timeout=TIMEOUT)
                    return (response.text or "").strip() or "Je n'ai pas de réponse."
                except asyncio.TimeoutError:
                    last_error = "délai dépassé"
                    logger.warning("%s: délai dépassé (essai %d)", model, attempt + 1)
                except errors.APIError as e:
                    last_error = f"{e.code} {e.status}"
                    logger.warning("%s: %s (essai %d)", model, last_error, attempt + 1)
                    if e.code not in RETRYABLE:
                        break  # erreur définitive pour ce modèle → modèle suivant
                if attempt < ATTEMPTS - 1:
                    await asyncio.sleep(1.5 * (attempt + 1))
        raise GeminiUnavailable(f"Gemini indisponible ({last_error}). Réessaie dans un instant.")

    async def _fetch_ha_states(self):
        headers = {"Authorization": f"Bearer {config.SUPERVISOR_TOKEN}"}
        try:
            async with httpx.AsyncClient(timeout=5) as http:
                res = await http.get(f"{config.HA_API_URL}/states", headers=headers)
            res.raise_for_status()
        except Exception as e:
            logger.warning("Lecture des états HA impossible: %s", e)
            return "Impossible de récupérer l'état des entités en temps réel.", set()

        domains = allowed_domains() + [d for d in OTHER_DOMAINS if d not in allowed_domains()]
        by_domain = {d: [] for d in domains}
        known = set()
        for s in res.json():
            entity_id = s.get("entity_id", "")
            domain = entity_id.split(".")[0]
            if domain in by_domain:
                known.add(entity_id)
                name = s.get("attributes", {}).get("friendly_name", entity_id)
                by_domain[domain].append(f"- {name} ({entity_id}): {s.get('state')}")

        lines = [line for d in domains for line in by_domain[d]]
        return "\n".join(lines[:MAX_ENTITIES]), known
