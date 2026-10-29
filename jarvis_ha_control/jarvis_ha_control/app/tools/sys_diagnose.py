import logging

import httpx

import config

logger = logging.getLogger("SysDiagnose")


class SystemDiagnose:
    async def check_system_health(self) -> dict:
        headers = {"Authorization": f"Bearer {config.SUPERVISOR_TOKEN}"}
        try:
            async with httpx.AsyncClient(timeout=4) as http:
                res = await http.get(f"{config.SUPERVISOR_URL}/core/info", headers=headers)
            if res.status_code == 200:
                data = res.json().get("data", {})
                return {"version": data.get("version"), "healthy": True}
            logger.error("Superviseur: HTTP %s", res.status_code)
        except Exception as e:
            logger.error("Erreur de diagnostic Superviseur: %s", e)
        return {"healthy": False, "error": "Impossible de joindre le superviseur HA."}
