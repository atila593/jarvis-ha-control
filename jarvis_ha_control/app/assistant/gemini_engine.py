import asyncio
import logging

import httpx
import google.genai as genai
from google.genai import types

import config
from assistant.prompts import system_prompt
from tools import presence
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
    """Gemini injoignable ou quota épuisé. `retry_after` (s), `quota` et `detail` viennent de la réponse de Google si présents."""

    def __init__(self, message: str, retry_after: int | None = None, quota: str | None = None, detail: str = ""):
        super().__init__(message)
        self.retry_after, self.quota, self.detail = retry_after, quota, detail


def quota_info(exc) -> tuple[int | None, str | None, str]:
    """(secondes avant réessai, identifiant du quota dépassé, message de Google) tirés d'une erreur API."""
    # Essayer d'extraire les infos de quota depuis différentes sources
    retry, quota, detail = None, None, ""
    
    # Pour les erreurs Google GenAI / HTTP
    if hasattr(exc, 'response') and exc.response:
        # Erreur HTTP avec réponse
        resp = exc.response
        if hasattr(resp, 'json'):
            try:
                body = resp.json()
                err = body.get("error", body) if isinstance(body, dict) else body
                if isinstance(err, dict):
                    detail = str(err.get("message", ""))[:240]
                    # Extraire retry info
                    if "retryAfterSeconds" in err:
                        retry = int(err["retryAfterSeconds"])
                    # Extraire quota info
                    if "quotaId" in err:
                        quota = err["quotaId"]
            except Exception:
                pass
        detail = str(getattr(resp, 'text', ''))[:240]
    elif hasattr(exc, 'details'):
        # Ancien format (google-generativeai)
        body = exc.details
        err = (body.get("error", body) if isinstance(body, dict) else None) or {}
        detail = str(err.get("message", ""))[:240]
        for d in err.get("details") or []:
            kind = str(d.get("@type", ""))
            if kind.endswith("RetryInfo"):
                try:
                    retry = int(float(str(d.get("retryDelay", "")).rstrip("s")))
                except ValueError:
                    pass
            elif kind.endswith("QuotaFailure"):
                v = (d.get("violations") or [{}])[0]
                quota = v.get("quotaId") or v.get("quotaMetric")
    elif hasattr(exc, 'status_code'):
        detail = f"HTTP {exc.status_code}: {str(exc)}"
    else:
        detail = str(exc)[:240]
    
    return retry, quota, detail


class JarvisEngine:
    def __init__(self):
        self.client = genai.Client(api_key=config.GEMINI_API_KEY) if config.GEMINI_API_KEY else None
        # Clé dédiée à la vision (quota séparé) ; sinon on partage la clé principale.
        self.vision_client = genai.Client(api_key=config.VISION_API_KEY) if config.VISION_API_KEY else None

    async def _generate(self, model: str, contents, tools=None, system: str | None = None, client=None):
        return await (client or self.client).aio.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system or system_prompt(bool(tools)),
                tools=tools or None,
            ),
        )

    async def process_command(self, prompt: str, who: str | None = None, role: str = "admin",
                              toolbox=None, facts: list | None = None):
        """Retourne (texte, actions exécutées). `role` : admin / member / guest (guest = lecture seule)."""
        if not self.client:
            return "Clé API Gemini non configurée : renseigne gemini_api_key dans les options de l'add-on.", []

        context, known = await self._fetch_ha_states()
        tools, runner = [], None
        can_act = role in ("admin", "member")
        if can_act and config.ACTIONS_ENABLED and allowed_domains() and known:
            runner = ActionRunner(known)
            tools.append(runner.call_service)
        extra = toolbox.tools() if (toolbox and can_act) else []
        tools += extra
        engineer = any(t.__name__.startswith("propose_") for t in extra)
        memory = any(t.__name__ == "remember" for t in extra)
        system = system_prompt(bool(runner), engineer=engineer, memory=memory)

        mem = ""
        if facts:
            mem = "\n\n[Mémoire sur " + (who or "la personne") + "]\n" + "\n".join(f"- {f}" for f in facts)
        who_line = f"\n\n[Interlocuteur] {who} (rôle : {role})" if who else ""
        text = await self.ask(f"[Contexte domotique actuel]\n{context}{mem}{who_line}\n\n[Requête]\n{prompt}",
                              tools or None, system)
        return text, (runner.done if runner else [])

    async def describe_image(self, image: bytes, prompt: str) -> str:
        """Analyse d'une image de caméra (utilisée par la vision)."""
        client = self.vision_client or self.client
        if not client:
            raise GeminiUnavailable("clé API Gemini non configurée")
        part = types.Part.from_bytes(data=image, mime_type="image/jpeg")
        # Un seul essai par modèle : réessayer sur un 429 ne ferait qu'aggraver la saturation du quota.
        models = [config.VISION_MODEL] if config.VISION_MODEL else None
        return await self.ask([part, prompt], client=client, attempts=1, models=models)

    async def analyse(self, report_text: str) -> str:
        if not self.client:
            return "Analyse IA indisponible : clé API Gemini non configurée."
        return await self.ask(
            f"[Rapport de statut]\n{report_text}\n\n[Requête]\n"
            "Fais le diagnostic : résume l'état général en 4 phrases maximum, signale chaque anomalie "
            "et propose une action pour chacune. Une entité « Introuvable » signifie que son identifiant n'existe plus "
            "dans Home Assistant (à corriger ou retirer de la liste), pas qu'une intégration est cassée. Pas de markdown."
        )

    async def ask(self, contents, tools=None, system: str | None = None, client=None, attempts: int = ATTEMPTS,
                  models: list | None = None) -> str:
        if not models:
            models = [config.GEMINI_MODEL]
            if config.GEMINI_FALLBACK_MODEL and config.GEMINI_FALLBACK_MODEL != config.GEMINI_MODEL:
                models.append(config.GEMINI_FALLBACK_MODEL)

        last_error, retry_after, quota, detail = None, None, None, ""
        for model in models:
            for attempt in range(attempts):
                try:
                    response = await asyncio.wait_for(self._generate(model, contents, tools, system, client), timeout=TIMEOUT)
                    return (response.text or "").strip() or "Je n'ai pas de réponse."
                except asyncio.TimeoutError:
                    last_error = "délai dépassé"
                    logger.warning("%s: délai dépassé (essai %d)", model, attempt + 1)
                except Exception as e:
                    # Capture les erreurs API (GenAIError, HTTP errors, etc.)
                    if hasattr(e, 'status_code'):
                        # Erreurs HTTP standard
                        last_error = f"{e.status_code}"
                        retry_after, quota, detail = quota_info(e)
                        logger.warning("%s: %s (essai %d) quota=%s retry=%ss — %s", model, last_error, attempt + 1,
                                       quota, retry_after, detail)
                        if e.status_code not in RETRYABLE:
                            break  # erreur définitive pour ce modèle → modèle suivant
                    elif hasattr(e, 'code'):
                        # Erreurs GenAI
                        last_error = f"{e.code}"
                        retry_after, quota, detail = quota_info(e)
                        logger.warning("%s: %s (essai %d) quota=%s retry=%ss — %s", model, last_error, attempt + 1,
                                       quota, retry_after, detail)
                        if e.code not in RETRYABLE:
                            break  # erreur définitive pour ce modèle → modèle suivant
                    else:
                        last_error = str(e)
                        logger.warning("%s: %s (essai %d)", model, last_error, attempt + 1)
                        break  # erreur inattendue, passer au modèle suivant
                if attempt < attempts - 1:
                    await asyncio.sleep(1.5 * (attempt + 1))
        raise GeminiUnavailable(f"Gemini indisponible ({last_error}). Réessaie dans un instant.",
                                retry_after=retry_after, quota=quota, detail=detail)

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
        pres = presence.context_block(presence.zones(states))
        text = (head + "\n" + "\n".join(lines)
                + (("\n\n[Prévisions météo]\n" + forecast) if forecast else "")
                + (("\n\n" + pres) if pres else ""))
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
