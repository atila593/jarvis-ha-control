import logging

import httpx

import config

logger = logging.getLogger("JarvisSpeak")


async def speak(text: str) -> dict:
    """Appelle le service HA configuré (ex. notify.alexa_media, notify.jarvis)."""
    service = config.SPEAK_SERVICE
    if not service or "." not in service:
        return {"spoken": False, "reason": "speak_service non configuré"}

    domain, name = service.split(".", 1)
    payload = {"message": text}
    if domain == "chime_tts":
        # Appel direct à Chime TTS : on envoie tout explicitement (plateforme, langue, voix) pour ne dépendre
        # d'aucun profil `notify.*` ni d'aucune valeur par défaut de l'intégration.
        payload["tts_platform"] = config.SPEAK_TTS_PLATFORM
        payload["language"] = config.SPEAK_LANGUAGE
        if config.SPEAK_VOICE:
            payload["options"] = {"voice": config.SPEAK_VOICE}
        if config.SPEAK_TARGETS:
            payload["entity_id"] = config.SPEAK_TARGETS
    elif config.SPEAK_TARGETS:
        payload["target"] = config.SPEAK_TARGETS
    if domain == "notify" and name.startswith("alexa_media"):
        payload["data"] = {"type": "announce"}

    headers = {"Authorization": f"Bearer {config.SUPERVISOR_TOKEN}"}
    try:
        async with httpx.AsyncClient(timeout=10) as http:
            res = await http.post(f"{config.HA_API_URL}/services/{domain}/{name}", headers=headers, json=payload)
        res.raise_for_status()
        return {"spoken": True}
    except Exception as e:
        logger.error("Échec speak via %s: %s", service, e)
        return {"spoken": False, "reason": str(e)}
