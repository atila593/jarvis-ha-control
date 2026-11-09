"""Client WebSocket pour écouter les événements Home Assistant en temps réel.

Ce module remplace le polling par une connexion WebSocket persistante,
permettant une réactivité immédiate aux changements d'état.

Fonctionnalités :
- Connexion WebSocket avec authentification
- Réabonnements automatiques en cas de déconnexion
- Filtrage des événements pertinents
- Gestion des erreurs avec retry exponentiel + jitter
"""

import asyncio
import json
import logging
import random
import time
from dataclasses import dataclass, field
from typing import Callable, Optional, Any, Dict, List

import websockets

import config

logger = logging.getLogger("JarvisWebSocket")


@dataclass
class WebSocketConfig:
    """Configuration du client WebSocket"""
    url: str = config.HA_WS_URL
    token: str = config.SUPERVISOR_TOKEN
    event_types: List[str] = field(default_factory=lambda: ["state_changed", "call_service"])
    retry_base: float = 1.0  # Secondes de base pour le retry
    retry_max: float = 60.0  # Maximum de secondes entre les retries
    jitter_factor: float = 0.1  # ±10% de jitter
    ping_interval: int = 30  # Secondes entre les pings
    connection_timeout: int = 10  # Timeout de connexion


class HAWebSocketClient:
    """Client WebSocket pour Home Assistant avec reconnexion automatique."""

    def __init__(self, config: Optional[WebSocketConfig] = None,
                 on_event: Optional[Callable[[Dict[str, Any]], None]] = None,
                 on_connect: Optional[Callable[[], None]] = None,
                 on_disconnect: Optional[Callable[[Exception], None]] = None):
        """
        Initialise le client WebSocket.
        
        Args:
            config: Configuration du WebSocket (optionnel)
            on_event: Callback appelé lorsqu'un événement est reçu
            on_connect: Callback appelé après une connexion réussie
            on_disconnect: Callback appelé après une déconnexion
        """
        self.config = config or WebSocketConfig()
        self.on_event = on_event
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect
        
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self._connected = False
        self._reconnect_task: Optional[asyncio.Task] = None
        self._connection_attempt = 0
        self._last_ping = time.time()
        self._message_id = 1

    @property
    def connected(self) -> bool:
        """Indique si le client est connecté."""
        return self._connected

    def _get_retry_delay(self, attempt: int) -> float:
        """Calcule le délai de retry avec backoff exponentiel et jitter.
        
        Formule: min(retry_max, retry_base * 2^attempt) * (1 ± jitter_factor)
        """
        base_delay = min(self.config.retry_max, self.config.retry_base * (2 ** attempt))
        jitter = 1 + random.uniform(-self.config.jitter_factor, self.config.jitter_factor)
        return base_delay * jitter

    async def connect(self) -> None:
        """Établit une connexion WebSocket avec Home Assistant."""
        if self._connected:
            logger.debug("Déjà connecté, ignore la demande de connexion")
            return

        try:
            logger.info("Connexion WebSocket à %s...", self.config.url)
            
            # Connexion avec timeout
            self.websocket = await asyncio.wait_for(
                websockets.connect(
                    self.config.url,
                    extra_headers={"Authorization": f"Bearer {self.config.token}"}
                ),
                timeout=self.config.connection_timeout
            )
            
            self._connected = True
            self._connection_attempt = 0
            self._last_ping = time.time()
            
            logger.info("✅ Connexion WebSocket établie")
            
            # Authentification (nécessaire pour HA)
            await self._authenticate()
            
            # S'abonner aux événements
            await self._subscribe_to_events()
            
            # Démarrer la tâche de ping
            asyncio.create_task(self._ping_loop())
            
            # Démarrer la boucle de réception
            asyncio.create_task(self._receive_loop())
            
            if self.on_connect:
                self.on_connect()

        except asyncio.TimeoutError:
            logger.error("⏱️ Timeout de connexion WebSocket")
            await self._handle_disconnect(asyncio.TimeoutError("Connection timeout"))
        except websockets.exceptions.ConnectionClosed:
            logger.error("🔌 Connexion WebSocket fermée par le serveur")
            await self._handle_disconnect(websockets.exceptions.ConnectionClosed(1000, "Normal closure"))
        except Exception as e:
            logger.error("❌ Erreur de connexion WebSocket: %s", e)
            await self._handle_disconnect(e)

    async def _authenticate(self) -> None:
        """Authentifie auprès de Home Assistant via WebSocket."""
        auth_message = {
            "type": "auth",
            "access_token": self.config.token
        }
        
        try:
            await self.websocket.send(json.dumps(auth_message))
            response = await asyncio.wait_for(self.websocket.recv(), timeout=10)
            auth_response = json.loads(response)
            
            if auth_response.get("type") != "auth_ok":
                raise Exception(f"Authentification échouée: {auth_response}")
            
            logger.info("🔐 Authentification WebSocket réussie")
            
        except Exception as e:
            logger.error("❌ Erreur d'authentification: %s", e)
            raise

    async def _subscribe_to_events(self) -> None:
        """S'abonne aux types d'événements configurés."""
        for event_type in self.config.event_types:
            subscribe_message = {
                "id": self._next_id(),
                "type": "subscribe_events",
                "event_type": event_type
            }
            try:
                await self.websocket.send(json.dumps(subscribe_message))
                logger.debug("Abonnement à %s", event_type)
            except Exception as e:
                logger.error("Erreur d'abonnement à %s: %s", event_type, e)

    def _next_id(self) -> int:
        """Génère un ID unique pour les messages."""
        self._message_id += 1
        return self._message_id

    async def _receive_loop(self) -> None:
        """Boucle de réception des messages WebSocket."""
        try:
            async for message in self.websocket:
                self._last_ping = time.time()
                
                try:
                    event = json.loads(message)
                    
                    # Ignorer les réponses aux abonnements
                    if event.get("type") in ("auth_ok", "auth_required", "event"):
                        # C'est un événement valide
                        if event.get("type") == "event":
                            event_data = event.get("event", {})
                            event_type = event_data.get("event_type")
                            
                            # Filtrer les événements selon la configuration
                            if event_type in self.config.event_types:
                                if self.on_event:
                                    self.on_event(event_data)
                        elif self.on_event and event.get("type") in self.config.event_types:
                            # Certains événements n'ont pas le wrapper "event"
                            self.on_event(event)
                            
                except json.JSONDecodeError:
                    logger.debug("Message non-JSON reçu: %s", message[:100])
                except Exception as e:
                    logger.error("Erreur de traitement du message: %s", e)

        except websockets.exceptions.ConnectionClosed:
            logger.info("Connexion WebSocket fermée dans la boucle de réception")
            await self._handle_disconnect(websockets.exceptions.ConnectionClosed(1000, "Normal"))
        except Exception as e:
            logger.error("Erreur dans la boucle de réception: %s", e)
            await self._handle_disconnect(e)

    async def _ping_loop(self) -> None:
        """Envoie des pings périodiques pour maintenir la connexion."""
        while self._connected:
            try:
                await asyncio.sleep(self.config.ping_interval)
                if self._connected and self.websocket:
                    if time.time() - self._last_ping > self.config.ping_interval * 2:
                        # Pas de message reçu depuis 2 intervalles, envoyer un ping
                        try:
                            ping_id = self._next_id()
                            ping_message = {
                                "id": ping_id,
                                "type": "ping"
                            }
                            await self.websocket.send(json.dumps(ping_message))
                            logger.debug("Ping envoyé")
                        except Exception as e:
                            logger.error("Erreur lors de l'envoi du ping: %s", e)
                            break
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Erreur dans la boucle de ping: %s", e)
                break

    async def _handle_disconnect(self, error: Exception) -> None:
        """Gère la déconnexion et déclenche une reconnexion."""
        self._connected = False
        self.websocket = None
        
        if self.on_disconnect:
            self.on_disconnect(error)
        
        logger.warning("⚠️ Déconnecté: %s. Tentative de reconnexion...", error)
        
        # Annuler la tâche de reconnexion précédente si elle existe
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
        
        # Démarrer une nouvelle tâche de reconnexion
        self._reconnect_task = asyncio.create_task(self._reconnect_loop())

    async def _reconnect_loop(self) -> None:
        """Boucle de reconnexion avec backoff exponentiel."""
        while not self._connected:
            self._connection_attempt += 1
            delay = self._get_retry_delay(self._connection_attempt)
            
            logger.info("🔄 Tentative de reconnexion #%d dans %.1fs...", 
                       self._connection_attempt, delay)
            
            try:
                await asyncio.sleep(delay)
                await self.connect()
                if self._connected:
                    break
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Erreur de reconnexion: %s", e)

    async def disconnect(self) -> None:
        """Fermer la connexion WebSocket."""
        if not self._connected:
            return

        logger.info("Fermeture de la connexion WebSocket...")
        
        # Annuler la tâche de reconnexion
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
        
        # Fermer la connexion
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception as e:
                logger.error("Erreur lors de la fermeture: %s", e)
        
        self._connected = False
        self.websocket = None
        logger.info("✅ Connexion WebSocket fermée")

    async def send_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Envoyer une commande via WebSocket et attendre la réponse.
        
        Args:
            command: Commande à envoyer (ex: {"type": "call_service", ...})
            
        Returns:
            Réponse du serveur
        """
        if not self._connected or not self.websocket:
            raise ConnectionError("Non connecté au WebSocket")

        command_id = self._next_id()
        command["id"] = command_id
        
        try:
            await self.websocket.send(json.dumps(command))
            
            # Attendre la réponse (avec timeout)
            response = await asyncio.wait_for(self.websocket.recv(), timeout=30)
            return json.loads(response)
            
        except asyncio.TimeoutError:
            raise TimeoutError("Timeout en attendant la réponse")
        except Exception as e:
            raise Exception(f"Erreur lors de l'envoi de la commande: {e}")


# Instance globale pour le client WebSocket
_websocket_client: Optional[HAWebSocketClient] = None


async def init_websocket(
    on_event: Callable[[Dict[str, Any]], None],
    event_types: Optional[List[str]] = None
) -> HAWebSocketClient:
    """Initialise le client WebSocket global.
    
    Args:
        on_event: Callback pour les événements
        event_types: Types d'événements à écouter (défaut: state_changed, call_service)
        
    Returns:
        Instance du client WebSocket
    """
    global _websocket_client
    
    config = WebSocketConfig(
        event_types=event_types or ["state_changed", "call_service"]
    )
    
    _websocket_client = HAWebSocketClient(
        config=config,
        on_event=on_event,
        on_connect=lambda: logger.info("WebSocket connecté - écoute des événements HA"),
        on_disconnect=lambda e: logger.warning(f"WebSocket déconnecté: {e}")
    )
    
    await _websocket_client.connect()
    return _websocket_client


async def get_websocket_client() -> Optional[HAWebSocketClient]:
    """Récupère l'instance globale du client WebSocket."""
    global _websocket_client
    return _websocket_client


async def close_websocket() -> None:
    """Fermer la connexion WebSocket globale."""
    global _websocket_client
    if _websocket_client:
        await _websocket_client.disconnect()
        _websocket_client = None
