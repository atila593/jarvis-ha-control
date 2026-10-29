import asyncio
import logging

import httpx
from google import genai
from google.genai import errors, types

import config
from assistant.prompts import system_prompt
from tools.actions import ActionRunner, allowed_domains
from tools.status import WEATHER_FR, now_str

logger = logging.getLogger("JarvisEngine")

# Domaines pilotables en premier, puis le reste (les capteurs en dernier)
OTHER_DOMAINS = ["camera", "media_player", "climate", "binary_sensor", "sensor"]
MAX_ENTITIES = 220

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
            "et propose une action pour chacune. Une entité « Introuvable » signifie que son identifiant n'existe plus "
            "dans Home Assistant (à corriger ou retirer de la liste), pas qu'une intégration est cassée. Pas de markdown."
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
        """Contexte envoyé à Gemini : (texte, ensemble des entités pilotables connues)."""
        headers = {"Authorization": f"Bearer {config.SUPERVISOR_TOKEN}"}
        try:
            async with httpx.AsyncClient(timeout=6) as http:
                res = await http.get(f"{config.HA_API_URL}/states", headers=headers)
                res.raise_for_status()
                states = res.json()
                forecast = ""
                for eid in config.EXTRA_ENTITIES:
                    if eid.startswith("weather."):
                        forecast = await self._forecast(http, headers, eid)
                        break
        except Exception as e:
            logger.warning("Lecture des états HA impossible: %s", e)
            return "Impossible de récupérer l'état des entités en temps réel.", set()

        by_id = {s.get("entity_id"): s for s in states}
        domains = allowed_domains() + [d for d in OTHER_DOMAINS if d not in allowed_domains()]
        listed = ("script", "automation")

        def line(s):
            eid = s["entity_id"]
            a = s.get("attributes", {}) or {}
            unit = a.get("unit_of_measurement")
            val = f"{s.get('state')} {unit}" if unit else s.get("state")
            extra = f", {a['temperature']} °C" if eid.startswith("weather.") and "temperature" in a else ""
            return f"- {a.get('friendly_name', eid)} ({eid}): {val}{extra}"

        ordered, seen, known = [], set(), set()
        # 1. tout ce que l'utilisateur surveille ou autorise explicitement
        for eid in list(config.EXTRA_ENTITIES) + list(config.ACTION_ENTITIES):
            if eid in by_id and eid not in seen and eid not in config.HIDDEN_ENTITIES:
                seen.add(eid)
                ordered.append(by_id[eid])
        # 2. le reste des domaines utiles
        by_domain = {d: [] for d in domains}
        for s in states:
            eid = s.get("entity_id", "")
            d = eid.split(".")[0]
            if eid in seen or eid in config.HIDDEN_ENTITIES or d not in by_domain:
                continue
            if d in listed and eid not in config.ACTION_ENTITIES:
                continue
            by_domain[d].append(s)
        for d in domains:
            ordered += by_domain[d]

        lines = []
        for s in ordered[:MAX_ENTITIES]:
            lines.append(line(s))
            d = s["entity_id"].split(".")[0]
            if d in allowed_domains() and (d not in listed or s["entity_id"] in config.ACTION_ENTITIES):
                known.add(s["entity_id"])
        head = f"Date et heure actuelles : {await now_str()}"
        text = head + "\n" + "\n".join(lines) + (("\n\n[Prévisions météo]\n" + forecast) if forecast else "")
        return text, known

    async def _forecast(self, http, headers, entity_id: str) -> str:
        try:
            res = await http.post(f"{config.HA_API_URL}/services/weather/get_forecasts?return_response",
                                  headers=headers, json={"entity_id": entity_id, "type": "daily"})
            res.raise_for_status()
            items = res.json().get("service_response", {}).get(entity_id, {}).get("forecast", [])[:5]
            out = []
            for f in items:
                cond = WEATHER_FR.get(f.get("condition"), f.get("condition", "?"))
                low, high, rain = f.get("templow"), f.get("temperature"), f.get("precipitation_probability")
                out.append(f"- {str(f.get('datetime', ''))[:10]} : {cond}, {low}/{high} °C"
                           + (f", pluie {rain} %" if rain is not None else ""))
            return "\n".join(out)
        except Exception as e:
            logger.info("Prévisions indisponibles: %s", e)
            return ""
