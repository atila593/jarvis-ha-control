"""Tests unitaires pour le système de confiance (confidence.py).

Ce module teste :
- ConfidenceScorer : Calcul des scores de confiance
- ActionMemory : Mémoire des actions passées
"""

import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime, timedelta, timezone
from jarvis_ha_control.app.autonomy.confidence import (
    ConfidenceScore,
    ConfidenceScorer,
    ActionMemory,
)


# =============================================================================
# Tests pour ConfidenceScore
# =============================================================================

class TestConfidenceScore:
    """Tests pour la classe ConfidenceScore."""

    def test_confidence_score_creation(self):
        """Test la création d'un score de confiance."""
        score = ConfidenceScore(
            total=0.85,
            historical=0.8,
            contextual=0.9,
            safety=0.9,
            risk=0.1,
            reason="Score élevé basé sur l'historique"
        )
        assert score.total == 0.85
        assert score.historical == 0.8
        assert score.contextual == 0.9
        assert score.safety == 0.9
        assert score.risk == 0.1
        assert score.reason == "Score élevé basé sur l'historique"

    def test_confidence_score_bool_true(self):
        """Test qu'un score suffisant retourne True."""
        score = ConfidenceScore(total=0.8, historical=0.8, contextual=0.8, safety=0.8, risk=0.2, reason="")
        assert bool(score) is True
        assert score.can_auto_approve() is True

    def test_confidence_score_bool_false(self):
        """Test qu'un score insuffisant retourne False."""
        score = ConfidenceScore(total=0.5, historical=0.5, contextual=0.5, safety=0.5, risk=0.5, reason="")
        assert bool(score) is False
        assert score.can_auto_approve() is False

    def test_confidence_score_custom_threshold(self):
        """Test avec un seuil personnalisé."""
        score = ConfidenceScore(total=0.6, historical=0.6, contextual=0.6, safety=0.6, risk=0.4, reason="")
        assert score.can_auto_approve(threshold=0.5) is True
        assert score.can_auto_approve(threshold=0.7) is False


# =============================================================================
# Tests pour ConfidenceScorer
# =============================================================================

class TestConfidenceScorer:
    """Tests pour la classe ConfidenceScorer."""

    @pytest.fixture
    def mock_store(self):
        """Crée un mock pour le store."""
        store = Mock()
        store.journal = Mock(return_value=[])
        store.proposals = Mock(return_value=[])
        store.facts = Mock(return_value=[])
        return store

    @pytest.fixture
    def mock_ha_client(self):
        """Crée un mock pour le client HA."""
        ha_client = AsyncMock()
        ha_client.get_states = AsyncMock(return_value={})
        ha_client.get_entity_state = AsyncMock(return_value=None)
        return ha_client

    @pytest.fixture
    def scorer(self, mock_store, mock_ha_client):
        """Crée un instance de ConfidenceScorer."""
        return ConfidenceScorer(store=mock_store, ha_client=mock_ha_client)

    def test_scorer_initialization(self, scorer, mock_store, mock_ha_client):
        """Test l'initialisation du scorer."""
        assert scorer.store == mock_store
        assert scorer.ha_client == mock_ha_client
        assert scorer.HISTORICAL_WEIGHT == 0.4
        assert scorer.CONTEXTUAL_WEIGHT == 0.3
        assert scorer.SAFETY_WEIGHT == 0.3
        assert scorer.AUTO_APPROVE_THRESHOLD == 0.7

    @pytest.mark.asyncio
    async def test_calculate_basic_action(self, scorer):
        """Test le calcul de confiance pour une action basique."""
        action = {"domain": "light", "service": "turn_on", "entity_id": "light.living_room"}
        context = {"time": "18:00", "presence": True, "weather": "clear"}
        
        score = await scorer.calculate(action, context)
        
        assert isinstance(score, ConfidenceScore)
        assert 0.0 <= score.total <= 1.0
        assert 0.0 <= score.historical <= 1.0
        assert 0.0 <= score.contextual <= 1.0
        assert 0.0 <= score.safety <= 1.0

    @pytest.mark.asyncio
    async def test_calculate_high_risk_action(self, scorer):
        """Test le calcul pour une action à haut risque."""
        action = {"domain": "lock", "service": "unlock", "entity_id": "lock.front_door"}
        context = {}
        
        score = await scorer.calculate(action, context)
        
        # Une action sur un lock devrait avoir un risque élevé
        assert score.risk > 0.5


# =============================================================================
# Tests pour ActionMemory
# =============================================================================

class TestActionMemory:
    """Tests pour la classe ActionMemory."""

    @pytest.fixture
    def mock_store(self):
        """Crée un mock pour le store."""
        store = AsyncMock()
        store.log_action = AsyncMock(return_value=None)
        store.get_similar_actions = AsyncMock(return_value=[])
        return store

    @pytest.fixture
    def memory(self, mock_store):
        """Crée une instance de ActionMemory."""
        return ActionMemory(store=mock_store)

    def test_memory_initialization(self, memory, mock_store):
        """Test l'initialisation de la mémoire."""
        assert memory.store == mock_store

    @pytest.mark.asyncio
    async def test_log_action(self, memory):
        """Test l'enregistrement d'une action."""
        rule = "test_rule"
        entity_id = "light.living_room"
        action = {"domain": "light", "service": "turn_on"}
        result = "success"
        user = "alice"
        context = {"time": "18:00"}
        
        await memory.log_action(rule, entity_id, action, result, user, context)
        
        # Vérifier que log_action a été appelé sur le store
        assert memory.store.log_action.called

    @pytest.mark.asyncio
    async def test_get_similar_actions(self, memory):
        """Test la récupération d'actions similaires."""
        memory.store.get_similar_actions = AsyncMock(return_value=[
            {"id": 1, "domain": "light", "service": "turn_on"}
        ])
        
        actions = await memory.get_similar_actions("light", "turn_on", "light.living_room")
        
        assert len(actions) == 1
        assert memory.store.get_similar_actions.called

    @pytest.mark.asyncio
    async def test_get_action_stats(self, memory):
        """Test la récupération des statistiques d'une action."""
        memory.store.get_similar_actions = AsyncMock(return_value=[
            {"result": "OK: success"},
            {"result": "OK: success"},
            {"result": "ERROR: failed"},
        ])
        
        stats = await memory.get_action_stats("light", "turn_on")
        
        assert stats["count"] == 3
        assert "success_rate" in stats


# =============================================================================
# Tests de performance
# =============================================================================

class TestPerformance:
    """Tests de performance pour le système de confiance."""

    @pytest.mark.asyncio
    async def test_scorer_performance(self):
        """Test la performance du scorer."""
        import time
        
        mock_store = Mock()
        mock_store.journal = Mock(return_value=[])
        
        mock_ha_client = AsyncMock()
        mock_ha_client.get_states = AsyncMock(return_value={})
        
        scorer = ConfidenceScorer(store=mock_store, ha_client=mock_ha_client)
        
        action = {"domain": "light", "service": "turn_on", "entity_id": "light.test"}
        context = {}
        
        # Mesurer le temps pour 100 calculs
        start = time.time()
        for _ in range(100):
            await scorer.calculate(action, context)
        elapsed = time.time() - start
        
        # Devrait être rapide (< 1 seconde pour 100 calculs)
        assert elapsed < 1.0, f"Trop lent : {elapsed}s pour 100 calculs"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
