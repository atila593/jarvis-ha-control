"""Tests unitaires pour le client WebSocket Home Assistant.

Ces tests vérifient le bon fonctionnement du client WebSocket,
notamment la gestion des connexions, la reconnexion automatique,
et le traitement des événements.
"""

import asyncio
import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch, call

# Configuration pour les tests
os.environ["JARVIS_DEV"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "jarvis_ha_control", "app"))

import pytest

from autonomy.ha_websocket import (
    HAWebSocketClient,
    WebSocketConfig,
    init_websocket,
    get_websocket_client,
    close_websocket,
)


@pytest.fixture
def mock_websocket():
    """Fixtue pour mock le websocket."""
    mock = AsyncMock()
    mock.send = AsyncMock()
    mock.recv = AsyncMock()
    mock.close = AsyncMock()
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=None)
    return mock


@pytest.fixture
def config():
    """Configuration de test."""
    return WebSocketConfig(
        url="ws://test.local",
        token="test_token",
        event_types=["state_changed"],
        retry_base=1.0,
        retry_max=10.0,
        jitter_factor=0.1,
        ping_interval=30,
        connection_timeout=10
    )


class TestWebSocketConfig:
    """Tests pour la configuration WebSocket."""

    def test_default_config(self):
        """Test la configuration par défaut."""
        config = WebSocketConfig()
        assert config.url == "ws://supervisor/core/websocket"
        assert config.token == ""
        assert config.event_types == ["state_changed", "call_service"]
        assert config.retry_base == 1.0
        assert config.retry_max == 60.0
        assert config.jitter_factor == 0.1

    def test_custom_config(self):
        """Test une configuration personnalisée."""
        config = WebSocketConfig(
            url="ws://custom",
            token="custom_token",
            event_types=["test_event"],
            retry_base=2.0,
            retry_max=30.0
        )
        assert config.url == "ws://custom"
        assert config.token == "custom_token"
        assert config.event_types == ["test_event"]
        assert config.retry_base == 2.0
        assert config.retry_max == 30.0


class TestHAWebSocketClient:
    """Tests pour le client WebSocket."""

    @pytest.mark.asyncio
    async def test_connect_success(self, config, mock_websocket):
        """Test une connexion réussie."""
        on_connect = MagicMock()
        on_event = MagicMock()
        on_disconnect = MagicMock()
        
        client = HAWebSocketClient(
            config=config,
            on_connect=on_connect,
            on_event=on_event,
            on_disconnect=on_disconnect
        )
        
        with patch("websockets.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_websocket
            
            # Mock les réponses d'authentification
            mock_websocket.recv.side_effect = [
                json.dumps({"type": "auth_ok"}),
                asyncio.CancelledError()  # Arrêter la boucle de réception
            ]
            
            await client.connect()
            
            assert client.connected is True
            on_connect.assert_called_once()
            mock_connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_auth_failure(self, config, mock_websocket):
        """Test un échec d'authentification."""
        client = HAWebSocketClient(config=config)
        
        with patch("websockets.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_websocket
            
            # Mock une réponse d'authentification échouée
            mock_websocket.recv.side_effect = [
                json.dumps({"type": "auth_required", "message": "Invalid token"}),
            ]
            
            with pytest.raises(Exception, match="Authentification échouée"):
                await client.connect()
            
            assert client.connected is False

    @pytest.mark.asyncio
    async def test_connect_timeout(self, config):
        """Test un timeout de connexion."""
        client = HAWebSocketClient(config=config)
        
        with patch("websockets.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.side_effect = asyncio.TimeoutError()
            
            with pytest.raises(asyncio.TimeoutError):
                await client.connect()
            
            assert client.connected is False

    def test_retry_delay_calculation(self, config):
        """Test le calcul du délai de retry."""
        client = HAWebSocketClient(config=config)
        
        # Test avec attempt = 0
        delay = client._get_retry_delay(0)
        assert 0.9 <= delay <= 1.1  # base * 2^0 * jitter
        
        # Test avec attempt = 1
        delay = client._get_retry_delay(1)
        assert 1.8 <= delay <= 2.2  # base * 2^1 * jitter
        
        # Test avec attempt élevé (plafonné à retry_max)
        delay = client._get_retry_delay(10)
        assert delay <= config.retry_max * 1.1

    @pytest.mark.asyncio
    async def test_disconnect(self, config, mock_websocket):
        """Test la déconnexion."""
        client = HAWebSocketClient(config=config)
        client.websocket = mock_websocket
        client._connected = True
        
        await client.disconnect()
        
        assert client.connected is False
        assert client.websocket is None
        mock_websocket.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_subscribe_to_events(self, config, mock_websocket):
        """Test l'abonnement aux événements."""
        client = HAWebSocketClient(config=config)
        client.websocket = mock_websocket
        client._connected = True
        
        await client._subscribe_to_events()
        
        # Vérifier que subscribe_events a été envoyé pour chaque event_type
        assert mock_websocket.send.call_count == len(config.event_types)
        
        # Vérifier le contenu des messages
        calls = mock_websocket.send.call_args_list
        for i, event_type in enumerate(config.event_types):
            message = json.loads(calls[i][0][0])
            assert message["type"] == "subscribe_events"
            assert message["event_type"] == event_type

    def test_next_id(self, config):
        """Test la génération des IDs."""
        client = HAWebSocketClient(config=config)
        
        id1 = client._next_id()
        id2 = client._next_id()
        id3 = client._next_id()
        
        assert id1 == 1
        assert id2 == 2
        assert id3 == 3


class TestEventHandling:
    """Tests pour la gestion des événements."""

    @pytest.mark.asyncio
    async def test_handle_state_changed_event(self, config, mock_websocket):
        """Test le traitement d'un événement state_changed."""
        received_events = []
        
        def on_event(event):
            received_events.append(event)
        
        client = HAWebSocketClient(config=config, on_event=on_event)
        client.websocket = mock_websocket
        client._connected = True
        
        # Simuler la réception d'un événement
        event_message = {
            "type": "event",
            "event": {
                "event_type": "state_changed",
                "data": {
                    "entity_id": "light.living_room",
                    "old_state": {"state": "off"},
                    "new_state": {"state": "on"}
                }
            }
        }
        
        # Simuler la réception via le websocket
        mock_websocket.__aiter__.return_value = [json.dumps(event_message)]
        
        # Démarrer la boucle de réception
        receive_task = asyncio.create_task(client._receive_loop())
        
        # Attendre un peu pour que l'événement soit traité
        await asyncio.sleep(0.1)
        
        # Arrêter la tâche
        receive_task.cancel()
        
        # Vérifier que l'événement a été reçu
        assert len(received_events) == 1
        assert received_events[0]["event_type"] == "state_changed"
        assert received_events[0]["data"]["entity_id"] == "light.living_room"

    @pytest.mark.asyncio
    async def test_handle_call_service_event(self, config, mock_websocket):
        """Test le traitement d'un événement call_service."""
        received_events = []
        
        def on_event(event):
            received_events.append(event)
        
        client = HAWebSocketClient(
            config=WebSocketConfig(
                url="ws://test.local",
                token="test_token",
                event_types=["call_service"]
            ),
            on_event=on_event
        )
        client.websocket = mock_websocket
        client._connected = True
        
        # Simuler un événement call_service
        event_message = {
            "type": "event",
            "event": {
                "event_type": "call_service",
                "data": {
                    "domain": "light",
                    "service": "turn_on",
                    "entity_id": "light.living_room"
                }
            }
        }
        
        mock_websocket.__aiter__.return_value = [json.dumps(event_message)]
        
        receive_task = asyncio.create_task(client._receive_loop())
        await asyncio.sleep(0.1)
        receive_task.cancel()
        
        assert len(received_events) == 1
        assert received_events[0]["event_type"] == "call_service"


class TestGlobalFunctions:
    """Tests pour les fonctions globales."""

    @pytest.mark.asyncio
    async def test_init_websocket(self, mock_websocket):
        """Test l'initialisation du WebSocket global."""
        received_events = []
        
        def on_event(event):
            received_events.append(event)
        
        with patch("websockets.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_websocket
            mock_websocket.recv.side_effect = [
                json.dumps({"type": "auth_ok"}),
                asyncio.CancelledError()
            ]
            
            client = await init_websocket(on_event=on_event)
            
            assert client is not None
            assert client.connected is True
            
            # Vérifier que le client global est défini
            from autonomy.ha_websocket import _websocket_client
            assert _websocket_client is client

    @pytest.mark.asyncio
    async def test_get_websocket_client(self, mock_websocket):
        """Test la récupération du client WebSocket global."""
        with patch("websockets.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_websocket
            mock_websocket.recv.side_effect = [
                json.dumps({"type": "auth_ok"}),
                asyncio.CancelledError()
            ]
            
            await init_websocket(on_event=lambda e: None)
            
            client = await get_websocket_client()
            assert client is not None
            assert client.connected is True

    @pytest.mark.asyncio
    async def test_close_websocket(self, mock_websocket):
        """Test la fermeture du WebSocket global."""
        with patch("websockets.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_websocket
            mock_websocket.recv.side_effect = [
                json.dumps({"type": "auth_ok"}),
                asyncio.CancelledError()
            ]
            
            await init_websocket(on_event=lambda e: None)
            
            await close_websocket()
            
            from autonomy.ha_websocket import _websocket_client
            assert _websocket_client is None
            mock_websocket.close.assert_called_once()


class TestPingLoop:
    """Tests pour la boucle de ping."""

    @pytest.mark.asyncio
    async def test_ping_loop_sends_ping(self, config, mock_websocket):
        """Test que la boucle de ping envoie des pings."""
        client = HAWebSocketClient(config=config)
        client.websocket = mock_websocket
        client._connected = True
        client._last_ping = 0  # Forcer un ping immédiat
        
        # Démarrer la boucle de ping
        ping_task = asyncio.create_task(client._ping_loop())
        
        # Attendre un peu
        await asyncio.sleep(0.5)
        
        # Arrêter la tâche
        ping_task.cancel()
        
        # Vérifier qu'un ping a été envoyé
        assert mock_websocket.send.call_count >= 1
        
        # Vérifier le contenu du ping
        if mock_websocket.send.call_count > 0:
            message = json.loads(mock_websocket.send.call_args[0][0])
            assert message["type"] == "ping"


class TestReconnectLoop:
    """Tests pour la boucle de reconnexion."""

    @pytest.mark.asyncio
    async def test_reconnect_after_disconnect(self, config, mock_websocket):
        """Test la reconnexion après une déconnexion."""
        connect_count = 0
        
        async def mock_connect():
            nonlocal connect_count
            connect_count += 1
            if connect_count == 1:
                # Première connexion échoue
                raise Exception("Connection failed")
            else:
                # Deuxième connexion réussit
                return mock_websocket
        
        client = HAWebSocketClient(config=config)
        
        with patch.object(client, 'connect', side_effect=mock_connect):
            # Simuler une déconnexion
            await client._handle_disconnect(Exception("Test disconnect"))
            
            # Attendre la reconnexion
            await asyncio.sleep(2)  # Attendre le retry
            
            # Vérifier que la reconnexion a été tentée
            assert connect_count >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
