"""Client minimal pour l'API Home Assistant (REST + une commande WebSocket à la fois)."""
import json

import httpx


class HaError(Exception):
    pass


class HaClient:
    def __init__(self, api_url: str, ws_url: str, token: str, timeout: float = 10):
        self.api_url = api_url.rstrip("/")
        self.ws_url = ws_url
        self.token = token
        self.timeout = timeout

    @property
    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    async def get(self, path: str):
        """GET JSON ; None si 404 (l'objet n'existe pas)."""
        async with httpx.AsyncClient(timeout=self.timeout) as http:
            res = await http.get(f"{self.api_url}/{path.lstrip('/')}", headers=self._headers)
        if res.status_code == 404:
            return None
        res.raise_for_status()
        return res.json()

    async def post(self, path: str, payload: dict):
        async with httpx.AsyncClient(timeout=self.timeout) as http:
            res = await http.post(f"{self.api_url}/{path.lstrip('/')}", headers=self._headers, json=payload)
        res.raise_for_status()
        return res.json() if res.content else None

    async def delete(self, path: str):
        async with httpx.AsyncClient(timeout=self.timeout) as http:
            res = await http.delete(f"{self.api_url}/{path.lstrip('/')}", headers=self._headers)
        if res.status_code == 404:
            return None
        res.raise_for_status()
        return res.json() if res.content else None

    async def ws(self, msg_type: str, **payload):
        """Ouvre une session WebSocket, s'authentifie, envoie UNE commande et renvoie son résultat."""
        import websockets

        async with websockets.connect(self.ws_url, open_timeout=self.timeout, close_timeout=2) as sock:
            await sock.recv()  # auth_required
            await sock.send(json.dumps({"type": "auth", "access_token": self.token}))
            reply = json.loads(await sock.recv())
            if reply.get("type") != "auth_ok":
                raise HaError("Authentification WebSocket refusée")
            await sock.send(json.dumps({"id": 1, "type": msg_type, **payload}))
            while True:
                msg = json.loads(await sock.recv())
                if msg.get("id") == 1 and msg.get("type") == "result":
                    if msg.get("success"):
                        return msg.get("result")
                    raise HaError(str((msg.get("error") or {}).get("message", "erreur inconnue")))
