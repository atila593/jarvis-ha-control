"""Tests unitaires pour le polling optimisé.

Ces tests vérifient le bon fonctionnement du polling adaptatif,
du polling ciblé et du traitement parallèle des règles.
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

os.environ["JARVIS_DEV"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "jarvis_ha_control", "app"))

import pytest

from autonomy.engine import AutonomyEngine, Settings
from autonomy import rules
from autonomy.store import Store


@pytest.fixture
def mock_store():
    """Fixtue pour un store mock."""
    store = MagicMock(spec=Store)
    store.active_load.return_value = {}
    store.proposals.return_value = []
    return store


@pytest.fixture
def mock_params():
    """Fixtue pour les paramètres de règles."""
    return rules.Params(
        quiet_start=rules.time(23, 0),
        quiet_end=rules.time(7, 0),
        watched=["sensor.temperature", "binary_sensor.door"],
        hidden=["sensor.hidden"],
        enabled=[]
    )


@pytest.fixture
def mock_settings():
    """Fixtue pour les paramètres du moteur."""
    return Settings(
        enabled=True,
        interval=30,
        auto_rules=[],
        approvers=[],
        proposal_ttl_min=120,
        daily_report_time="",
        adaptive_polling=True,
        targeted_polling=True,
        parallel_processing=True
    )


class TestAdaptivePolling:
    """Tests pour le polling adaptatif."""

    @pytest.mark.asyncio
    async def test_adaptive_interval_urgent_alerts(self, mock_store, mock_params, mock_settings):
        """Test : intervalle réduit si alertes urgentes."""
        engine = AutonomyEngine(
            store=mock_store,
            settings=mock_settings,
            params=mock_params,
            fetch_states=AsyncMock(return_value=[]),
            execute=AsyncMock(),
            speak=AsyncMock(),
            notify=AsyncMock(),
            report=AsyncMock(),
            local_now=AsyncMock(return_value=datetime.now(timezone.utc))
        )
        
        # Simuler des alertes urgentes
        engine.active = {
            "safety_sensor:binary_sensor.smoke": {"severity": "urgent", "first": "2026-01-01T00:00:00Z", "last": "2026-01-01T00:00:00Z", "n": 1}
        }
        engine._update_activity_counters()
        
        interval = engine._calculate_adaptive_interval()
        assert interval == 5, f"Expected 5s, got {interval}s"

    @pytest.mark.asyncio
    async def test_adaptive_interval_pending_proposals(self, mock_store, mock_params, mock_settings):
        """Test : intervalle moyen si propositions en attente."""
        engine = AutonomyEngine(
            store=mock_store,
            settings=mock_settings,
            params=mock_params,
            fetch_states=AsyncMock(return_value=[]),
            execute=AsyncMock(),
            speak=AsyncMock(),
            notify=AsyncMock(),
            report=AsyncMock(),
            local_now=AsyncMock(return_value=datetime.now(timezone.utc))
        )
        
        # Simuler des propositions en attente
        mock_store.proposals.return_value = [{"id": 1, "status": "pending"}]
        engine._update_activity_counters()
        
        interval = engine._calculate_adaptive_interval()
        assert interval == 10, f"Expected 10s, got {interval}s"

    @pytest.mark.asyncio
    async def test_adaptive_interval_recent_activity(self, mock_store, mock_params, mock_settings):
        """Test : intervalle moyen si activité récente."""
        engine = AutonomyEngine(
            store=mock_store,
            settings=mock_settings,
            params=mock_params,
            fetch_states=AsyncMock(return_value=[]),
            execute=AsyncMock(),
            speak=AsyncMock(),
            notify=AsyncMock(),
            report=AsyncMock(),
            local_now=AsyncMock(return_value=datetime.now(timezone.utc))
        )
        
        # Simuler une activité récente
        engine._last_activity_time = datetime.now(timezone.utc)
        engine._update_activity_counters()
        
        interval = engine._calculate_adaptive_interval()
        assert interval == 15, f"Expected 15s, got {interval}s"

    @pytest.mark.asyncio
    async def test_adaptive_interval_default(self, mock_store, mock_params, mock_settings):
        """Test : intervalle par défaut si aucune activité."""
        engine = AutonomyEngine(
            store=mock_store,
            settings=mock_settings,
            params=mock_params,
            fetch_states=AsyncMock(return_value=[]),
            execute=AsyncMock(),
            speak=AsyncMock(),
            notify=AsyncMock(),
            report=AsyncMock(),
            local_now=AsyncMock(return_value=datetime.now(timezone.utc))
        )
        
        # Aucun activité
        engine._update_activity_counters()
        
        interval = engine._calculate_adaptive_interval()
        assert interval == 30, f"Expected 30s (default), got {interval}s"


class TestTargetedPolling:
    """Tests pour le polling ciblé."""

    @pytest.mark.asyncio
    async def test_has_watched_entities(self, mock_store, mock_params, mock_settings):
        """Test : détection des entités à surveiller."""
        engine = AutonomyEngine(
            store=mock_store,
            settings=mock_settings,
            params=mock_params,
            fetch_states=AsyncMock(return_value=[]),
            execute=AsyncMock(),
            speak=AsyncMock(),
            notify=AsyncMock(),
            report=AsyncMock(),
            local_now=AsyncMock(return_value=datetime.now(timezone.utc))
        )
        
        assert engine._has_watched_entities() is True

    @pytest.mark.asyncio
    async def test_get_watched_entities(self, mock_store, mock_params, mock_settings):
        """Test : récupération des entités à surveiller."""
        engine = AutonomyEngine(
            store=mock_store,
            settings=mock_settings,
            params=mock_params,
            fetch_states=AsyncMock(return_value=[]),
            execute=AsyncMock(),
            speak=AsyncMock(),
            notify=AsyncMock(),
            report=AsyncMock(),
            local_now=AsyncMock(return_value=datetime.now(timezone.utc))
        )
        
        entities = engine._get_watched_entities()
        assert "sensor.temperature" in entities
        assert "binary_sensor.door" in entities

    @pytest.mark.asyncio
    async def test_fetch_targeted_states(self, mock_store, mock_params, mock_settings):
        """Test : récupération ciblée des états."""
        all_states = [
            {"entity_id": "sensor.temperature", "state": "22"},
            {"entity_id": "binary_sensor.door", "state": "on"},
            {"entity_id": "light.living_room", "state": "off"}
        ]
        
        engine = AutonomyEngine(
            store=mock_store,
            settings=mock_settings,
            params=mock_params,
            fetch_states=AsyncMock(return_value=all_states),
            execute=AsyncMock(),
            speak=AsyncMock(),
            notify=AsyncMock(),
            report=AsyncMock(),
            local_now=AsyncMock(return_value=datetime.now(timezone.utc))
        )
        
        entities = {"sensor.temperature", "binary_sensor.door"}
        targeted_states = await engine._fetch_targeted_states(entities)
        
        assert len(targeted_states) == 2
        entity_ids = {s["entity_id"] for s in targeted_states}
        assert entity_ids == entities


class TestParallelProcessing:
    """Tests pour le traitement parallèle des règles."""

    @pytest.mark.asyncio
    async def test_evaluate_rules_parallel(self, mock_store, mock_params, mock_settings):
        """Test : évaluation parallèle des règles."""
        states = [
            {"entity_id": f"sensor.temp_{i}", "state": str(20 + i), "attributes": {},"last_changed": datetime.now(timezone.utc).isoformat()}
            for i in range(20)
        ]
        
        engine = AutonomyEngine(
            store=mock_store,
            settings=mock_settings,
            params=mock_params,
            fetch_states=AsyncMock(return_value=states),
            execute=AsyncMock(),
            speak=AsyncMock(),
            notify=AsyncMock(),
            report=AsyncMock(),
            local_now=AsyncMock(return_value=datetime.now(timezone.utc))
        )
        
        now = datetime.now(timezone.utc)
        findings = await engine._evaluate_rules_parallel(states, now)
        
        # Doit retourner une liste (même vide)
        assert isinstance(findings, list)

    @pytest.mark.asyncio
    async def test_evaluate_batch(self, mock_store, mock_params, mock_settings):
        """Test : évaluation d'un batch d'états."""
        states = [
            {"entity_id": "sensor.temperature", "state": "22", "attributes": {},"last_changed": datetime.now(timezone.utc).isoformat()}
        ]
        
        engine = AutonomyEngine(
            store=mock_store,
            settings=mock_settings,
            params=mock_params,
            fetch_states=AsyncMock(return_value=states),
            execute=AsyncMock(),
            speak=AsyncMock(),
            notify=AsyncMock(),
            report=AsyncMock(),
            local_now=AsyncMock(return_value=datetime.now(timezone.utc))
        )
        
        now = datetime.now(timezone.utc)
        findings = await engine._evaluate_batch(states, now, mock_params)
        
        assert isinstance(findings, list)


class TestActivityCounters:
    """Tests pour les compteurs d'activité."""

    @pytest.mark.asyncio
    async def test_update_activity_counters(self, mock_store, mock_params, mock_settings):
        """Test : mise à jour des compteurs d'activité."""
        engine = AutonomyEngine(
            store=mock_store,
            settings=mock_settings,
            params=mock_params,
            fetch_states=AsyncMock(return_value=[]),
            execute=AsyncMock(),
            speak=AsyncMock(),
            notify=AsyncMock(),
            report=AsyncMock(),
            local_now=AsyncMock(return_value=datetime.now(timezone.utc))
        )
        
        # Simuler des alertes actives
        engine.active = {
            "safety_sensor:binary_sensor.smoke": {"severity": "urgent", "first": "2026-01-01T00:00:00Z", "last": "2026-01-01T00:00:00Z", "n": 1},
            "garage_open:cover.garage": {"severity": "important", "first": "2026-01-01T00:00:00Z", "last": "2026-01-01T00:00:00Z", "n": 1}
        }
        
        # Simuler des propositions en attente
        mock_store.proposals.return_value = [
            {"id": 1, "status": "pending"},
            {"id": 2, "status": "pending"}
        ]
        
        engine._update_activity_counters()
        
        assert engine._urgent_alerts_count == 1
        assert engine._pending_proposals_count == 2


class TestIntegration:
    """Tests d'intégration du polling optimisé."""

    @pytest.mark.asyncio
    async def test_tick_with_parallel_processing(self, mock_store, mock_params, mock_settings):
        """Test : tick avec traitement parallèle activé."""
        states = [
            {"entity_id": "sensor.temperature", "state": "22", "attributes": {},"last_changed": datetime.now(timezone.utc).isoformat()}
        ]
        
        engine = AutonomyEngine(
            store=mock_store,
            settings=Settings(
                enabled=True,
                interval=30,
                auto_rules=[],
                approvers=[],
                proposal_ttl_min=120,
                daily_report_time="",
                adaptive_polling=True,
                targeted_polling=False,  # Désactivé pour ce test
                parallel_processing=True
            ),
            params=mock_params,
            fetch_states=AsyncMock(return_value=states),
            execute=AsyncMock(),
            speak=AsyncMock(),
            notify=AsyncMock(),
            report=AsyncMock(),
            local_now=AsyncMock(return_value=datetime.now(timezone.utc))
        )
        
        # Ne doit pas lever d'exception
        await engine.tick()

    @pytest.mark.asyncio
    async def test_tick_with_targeted_polling(self, mock_store, mock_params, mock_settings):
        """Test : tick avec polling ciblé activé."""
        states = [
            {"entity_id": "sensor.temperature", "state": "22", "attributes": {},"last_changed": datetime.now(timezone.utc).isoformat()}
        ]
        
        engine = AutonomyEngine(
            store=mock_store,
            settings=Settings(
                enabled=True,
                interval=30,
                auto_rules=[],
                approvers=[],
                proposal_ttl_min=120,
                daily_report_time="",
                adaptive_polling=False,  # Désactivé pour ce test
                targeted_polling=True,
                parallel_processing=False
            ),
            params=mock_params,
            fetch_states=AsyncMock(return_value=states),
            execute=AsyncMock(),
            speak=AsyncMock(),
            notify=AsyncMock(),
            report=AsyncMock(),
            local_now=AsyncMock(return_value=datetime.now(timezone.utc))
        )
        
        # Ne doit pas lever d'exception
        await engine.tick()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
