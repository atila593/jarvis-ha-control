"""Tests unitaires pour les agents IA (J5).

Ce module teste :
- ConversationAgent : Gestion des conversations
- DecisionAgent : Prise de décision
- ActionAgent : Exécution des actions
- Orchestrator : Coordination
"""

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
from datetime import datetime, timezone
from jarvis_ha_control.app.agents.conversation_agent import (
    ConversationAgent,
    Message,
    ConversationContext,
)
from jarvis_ha_control.app.agents.decision_agent import (
    DecisionAgent,
    Decision,
    DecisionType,
    RiskLevel,
)
from jarvis_ha_control.app.agents.action_agent import (
    ActionAgent,
    ActionResult,
    ActionStatus,
    ActionQueueItem,
)
from jarvis_ha_control.app.agents.orchestrator import (
    Orchestrator,
    WorkflowResult,
    SystemState,
)


# =============================================================================
# Tests pour Message
# =============================================================================

class TestMessage:
    """Tests pour la classe Message."""

    def test_message_creation(self):
        """Test la création d'un message."""
        msg = Message(role="user", content="Test message")
        assert msg.role == "user"
        assert msg.content == "Test message"
        assert msg.timestamp is not None
        assert msg.metadata == {}

    def test_message_to_dict(self):
        """Test la conversion en dictionnaire."""
        msg = Message(role="assistant", content="Response", metadata={"key": "value"})
        d = msg.to_dict()
        assert d["role"] == "assistant"
        assert d["content"] == "Response"
        assert d["metadata"] == {"key": "value"}

    def test_message_from_dict(self):
        """Test la création depuis un dictionnaire."""
        data = {
            "role": "user",
            "content": "Test",
            "timestamp": "2024-01-01T00:00:00",
            "metadata": {}
        }
        msg = Message.from_dict(data)
        assert msg.role == "user"
        assert msg.content == "Test"


# =============================================================================
# Tests pour ConversationContext
# =============================================================================

class TestConversationContext:
    """Tests pour la classe ConversationContext."""

    def test_context_creation(self):
        """Test la création d'un contexte."""
        ctx = ConversationContext(user_id="alice", session_id="session1")
        assert ctx.user_id == "alice"
        assert ctx.session_id == "session1"
        assert ctx.messages == []
        assert ctx.current_intent is None

    def test_add_message(self):
        """Test l'ajout d'un message."""
        ctx = ConversationContext(user_id="alice", session_id="session1")
        ctx.add_message("user", "Test message")
        assert len(ctx.messages) == 1
        assert ctx.messages[0].role == "user"
        assert ctx.messages[0].content == "Test message"

    def test_get_history(self):
        """Test la récupération de l'historique."""
        ctx = ConversationContext(user_id="alice", session_id="session1")
        for i in range(10):
            ctx.add_message("user", f"Message {i}")
        
        history = ctx.get_history(limit=5)
        assert len(history) == 5

    def test_clear(self):
        """Test l'effacement du contexte."""
        ctx = ConversationContext(user_id="alice", session_id="session1")
        ctx.add_message("user", "Test")
        ctx.current_intent = "test_intent"
        ctx.entities = {"test": "value"}
        
        ctx.clear()
        
        assert len(ctx.messages) == 0
        assert ctx.current_intent is None
        assert ctx.entities == {}


# =============================================================================
# Tests pour ConversationAgent
# =============================================================================

class TestConversationAgent:
    """Tests pour la classe ConversationAgent."""

    @pytest.fixture
    def mock_gemini(self):
        """Crée un mock pour le client Gemini."""
        gemini = AsyncMock()
        gemini.generate_content = AsyncMock(return_value=Mock(text="Réponse test"))
        return gemini

    @pytest.fixture
    def mock_store(self):
        """Crée un mock pour le store."""
        return Mock()

    @pytest.fixture
    def agent(self, mock_gemini, mock_store):
        """Crée un agent de conversation."""
        return ConversationAgent(
            gemini_client=mock_gemini,
            store=mock_store,
            user_id="alice"
        )

    def test_agent_initialization(self, agent, mock_gemini, mock_store):
        """Test l'initialisation de l'agent."""
        assert agent.gemini_client == mock_gemini
        assert agent.store == mock_store
        assert agent.user_id == "alice"

    def test_get_conversation(self, agent):
        """Test la récupération d'une conversation."""
        ctx = agent.get_conversation("session1")
        assert ctx.user_id == "alice"
        assert ctx.session_id == "session1"

    def test_get_conversation_creates_new(self, agent):
        """Test la création d'une nouvelle conversation."""
        ctx1 = agent.get_conversation("session1")
        ctx2 = agent.get_conversation("session2")
        assert ctx1 is not ctx2

    def test_end_conversation(self, agent):
        """Test la fin d'une conversation."""
        agent.get_conversation("session1")
        agent.end_conversation("session1")
        
        # La conversation devrait être supprimée
        ctx = agent.get_conversation("session1")
        assert ctx != agent._conversations.get("session1")

    @pytest.mark.asyncio
    async def test_process_message(self, agent):
        """Test le traitement d'un message."""
        result = await agent.process_message("session1", "Allume la lumière")
        
        assert "response" in result
        assert "intent" in result
        assert result["session_id"] == "session1"

    def test_analyze_intent(self, agent):
        """Test l'analyse d'intention."""
        intent, entities = agent._analyze_intent("Allume la lumière", Mock())
        assert intent == "control_device"

    def test_extract_entities(self, agent):
        """Test l'extraction des entités."""
        entities = agent._extract_entities("Allume light.living_room à 18h")
        assert "entities" in entities
        assert "light.living_room" in entities["entities"]


# =============================================================================
# Tests pour Decision
# =============================================================================

class TestDecision:
    """Tests pour la classe Decision."""

    def test_decision_creation(self):
        """Test la création d'une décision."""
        decision = Decision(
            action={"domain": "light", "service": "turn_on"},
            decision_type=DecisionType.AUTO_APPROVE,
            confidence_score=0.9,
            risk_level=RiskLevel.LOW,
            reason="Confiance élevée",
            proposed_by="alice"
        )
        
        assert decision.action["domain"] == "light"
        assert decision.decision_type == DecisionType.AUTO_APPROVE
        assert decision.confidence_score == 0.9
        assert decision.risk_level == RiskLevel.LOW

    def test_decision_to_dict(self):
        """Test la conversion en dictionnaire."""
        decision = Decision(
            action={"test": "value"},
            decision_type=DecisionType.REJECT,
            confidence_score=0.5,
            risk_level=RiskLevel.HIGH,
            reason="Risque élevé",
            proposed_by="system"
        )
        
        d = decision.to_dict()
        assert d["decision_type"] == "reject"
        assert d["risk_level"] == "high"


# =============================================================================
# Tests pour DecisionAgent
# =============================================================================

class TestDecisionAgent:
    """Tests pour la classe DecisionAgent."""

    @pytest.fixture
    def mock_scorer(self):
        """Crée un mock pour le ConfidenceScorer."""
        scorer = Mock()
        scorer.calculate = AsyncMock(return_value=Mock(total=0.85))
        return scorer

    @pytest.fixture
    def mock_store(self):
        """Crée un mock pour le store."""
        store = Mock()
        store.log = Mock()
        store.add_proposal = Mock(return_value=1)
        store.set_proposal = Mock()
        store.proposals = Mock(return_value=[])
        return store

    @pytest.fixture
    def agent(self, mock_scorer, mock_store):
        """Crée un agent de décision."""
        return DecisionAgent(
            confidence_scorer=mock_scorer,
            store=mock_store,
            auto_approve_threshold=0.8
        )

    def test_agent_initialization(self, agent, mock_scorer, mock_store):
        """Test l'initialisation de l'agent."""
        assert agent.confidence_scorer == mock_scorer
        assert agent.store == mock_store

    @pytest.mark.asyncio
    async def test_evaluate_proposal_auto_approve(self, agent):
        """Test l'évaluation avec approbation automatique."""
        action = {"domain": "light", "service": "turn_on", "entity_id": "light.living_room"}
        
        decision = await agent.evaluate_proposal(action, {}, "alice")
        
        assert decision.decision_type == DecisionType.AUTO_APPROVE
        assert decision.auto_approved is True

    @pytest.mark.asyncio
    async def test_evaluate_proposal_reject(self, agent):
        """Test l'évaluation avec rejet."""
        # Action interdite
        action = {"domain": "lock", "service": "unlock", "entity_id": "lock.front_door"}
        
        decision = await agent.evaluate_proposal(action, {}, "alice")
        
        assert decision.decision_type == DecisionType.REJECT
        assert decision.auto_approved is False

    def test_is_forbidden_action(self, agent):
        """Test la détection des actions interdites."""
        assert agent._is_forbidden_action({"domain": "lock", "service": "unlock"}) is True
        assert agent._is_forbidden_action({"domain": "light", "service": "turn_on"}) is False

    def test_assess_risk(self, agent):
        """Test l'évaluation du risque."""
        assert agent._assess_risk({"domain": "lock", "service": "unlock"}) == RiskLevel.CRITICAL
        assert agent._assess_risk({"domain": "light", "service": "turn_on"}) == RiskLevel.LOW


# =============================================================================
# Tests pour ActionResult
# =============================================================================

class TestActionResult:
    """Tests pour la classe ActionResult."""

    def test_result_creation(self):
        """Test la création d'un résultat."""
        result = ActionResult(
            action_id="action1",
            status=ActionStatus.COMPLETED,
            success=True,
            message="Success"
        )
        
        assert result.action_id == "action1"
        assert result.status == ActionStatus.COMPLETED
        assert result.success is True

    def test_result_to_dict(self):
        """Test la conversion en dictionnaire."""
        result = ActionResult(
            action_id="action1",
            status=ActionStatus.FAILED,
            success=False,
            message="Error"
        )
        
        d = result.to_dict()
        assert d["status"] == "failed"
        assert d["success"] is False


# =============================================================================
# Tests pour ActionQueueItem
# =============================================================================

class TestActionQueueItem:
    """Tests pour la classe ActionQueueItem."""

    def test_item_creation(self):
        """Test la création d'un élément de file."""
        item = ActionQueueItem(
            action={"domain": "light", "service": "turn_on"},
            action_id="action1",
            priority=1,
            proposed_by="alice"
        )
        
        assert item.action["domain"] == "light"
        assert item.action_id == "action1"
        assert item.priority == 1


# =============================================================================
# Tests pour ActionAgent
# =============================================================================

class TestActionAgent:
    """Tests pour la classe ActionAgent."""

    @pytest.fixture
    def mock_ha_client(self):
        """Crée un mock pour le client HA."""
        ha_client = AsyncMock()
        ha_client.get_entity_state = AsyncMock(return_value={"state": "off"})
        ha_client.call_service = AsyncMock(return_value={"success": True})
        return ha_client

    @pytest.fixture
    def mock_store(self):
        """Crée un mock pour le store."""
        store = Mock()
        store.log = Mock()
        store.journal = Mock(return_value=[])
        return store

    @pytest.fixture
    def agent(self, mock_ha_client, mock_store):
        """Crée un agent d'action."""
        return ActionAgent(
            ha_client=mock_ha_client,
            store=mock_store,
            max_concurrent_actions=5
        )

    def test_agent_initialization(self, agent, mock_ha_client, mock_store):
        """Test l'initialisation de l'agent."""
        assert agent.ha_client == mock_ha_client
        assert agent.store == mock_store

    @pytest.mark.asyncio
    async def test_enqueue_action(self, agent):
        """Test l'ajout d'une action à la file."""
        action_id = await agent.enqueue_action(
            {"domain": "light", "service": "turn_on", "entity_id": "light.living_room"},
            "alice",
            priority=1
        )
        
        assert action_id.startswith("action_")

    def test_get_queue_status(self, agent):
        """Test la récupération de l'état de la file."""
        status = agent.get_queue_status()
        assert "queue_length" in status
        assert "running_count" in status
        assert "max_concurrent" in status


# =============================================================================
# Tests pour WorkflowResult
# =============================================================================

class TestWorkflowResult:
    """Tests pour la classe WorkflowResult."""

    def test_result_creation(self):
        """Test la création d'un résultat de workflow."""
        result = WorkflowResult(
            workflow_id="workflow1",
            success=True,
            message="Completed"
        )
        
        assert result.workflow_id == "workflow1"
        assert result.success is True

    def test_result_to_dict(self):
        """Test la conversion en dictionnaire."""
        result = WorkflowResult(
            workflow_id="workflow1",
            success=False,
            message="Error"
        )
        
        d = result.to_dict()
        assert d["workflow_id"] == "workflow1"
        assert d["success"] is False


# =============================================================================
# Tests pour Orchestrator
# =============================================================================

class TestOrchestrator:
    """Tests pour la classe Orchestrator."""

    @pytest.fixture
    def mock_conversation(self):
        """Crée un mock pour ConversationAgent."""
        conversation = AsyncMock()
        conversation.process_message = AsyncMock(return_value={
            "response": "Réponse test",
            "intent": "control_device",
            "entities": {}
        })
        return conversation

    @pytest.fixture
    def mock_decision(self):
        """Crée un mock pour DecisionAgent."""
        decision = AsyncMock()
        decision.evaluate_proposal = AsyncMock(return_value=Mock(
            decision_type=DecisionType.AUTO_APPROVE,
            auto_approved=True,
            confidence_score=0.9,
            risk_level=RiskLevel.LOW,
            reason="Test"
        ))
        return decision

    @pytest.fixture
    def mock_action(self):
        """Crée un mock pour ActionAgent."""
        action = AsyncMock()
        action.enqueue_action = AsyncMock(return_value="action1")
        action.get_queue_status = Mock(return_value={"queue_length": 0})
        return action

    @pytest.fixture
    def mock_store(self):
        """Crée un mock pour le store."""
        return Mock()

    @pytest.fixture
    def orchestrator(self, mock_conversation, mock_decision, mock_action, mock_store):
        """Crée un orchestrateur."""
        return Orchestrator(
            conversation_agent=mock_conversation,
            decision_agent=mock_decision,
            action_agent=mock_action,
            store=mock_store
        )

    def test_orchestrator_initialization(self, orchestrator, mock_conversation, mock_decision, mock_action):
        """Test l'initialisation de l'orchestrateur."""
        assert orchestrator.conversation_agent == mock_conversation
        assert orchestrator.decision_agent == mock_decision
        assert orchestrator.action_agent == mock_action

    @pytest.mark.asyncio
    async def test_process_request(self, orchestrator):
        """Test le traitement d'une requête."""
        result = await orchestrator.process_request(
            user_id="alice",
            message="Allume la lumière",
            priority=1
        )
        
        assert result.success is True
        assert result.workflow_id.startswith("workflow_")
        assert len(result.steps) > 0

    def test_get_system_state(self, orchestrator):
        """Test la récupération de l'état du système."""
        state = orchestrator.get_system_state()
        assert "state" in state
        assert "workflow_count" in state


# =============================================================================
# Tests d'intégration
# =============================================================================

class TestIntegration:
    """Tests d'intégration pour les agents."""

    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """Test un workflow complet."""
        # Créer les mocks
        mock_gemini = AsyncMock()
        mock_gemini.generate_content = AsyncMock(return_value=Mock(text="OK"))
        
        mock_store = Mock()
        mock_store.log = Mock()
        mock_store.add_proposal = Mock(return_value=1)
        mock_store.set_proposal = Mock()
        mock_store.journal = Mock(return_value=[])
        
        mock_ha_client = AsyncMock()
        mock_ha_client.get_entity_state = AsyncMock(return_value={"state": "off"})
        mock_ha_client.call_service = AsyncMock(return_value={"success": True})
        
        # Créer les agents
        conversation = ConversationAgent(mock_gemini, mock_store)
        
        from jarvis_ha_control.app.autonomy.confidence import ConfidenceScorer
        scorer = ConfidenceScorer(store=mock_store, ha_client=mock_ha_client)
        decision = DecisionAgent(scorer, mock_store, mock_ha_client)
        action = ActionAgent(mock_ha_client, mock_store)
        
        # Créer l'orchestrateur
        orchestrator = Orchestrator(conversation, decision, action, mock_store, mock_ha_client)
        
        # Exécuter un workflow
        result = await orchestrator.process_request(
            user_id="alice",
            message="Allume la lumière",
            priority=1
        )
        
        assert result.success is True
        assert len(result.steps) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
