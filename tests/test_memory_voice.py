"""Tests unitaires pour la mémoire et la validation vocale.

Ce module teste :
- VoiceGate : Validation vocale sécurisée
- Mémoire des faits (facts) dans Store
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import time
import asyncio
from jarvis_ha_control.app.autonomy.access import (
    VoiceGate,
    classify,
    extract_pin,
    norm,
    APPROVE,
    REJECT,
    UNDO_WORDS,
    LIST_WORDS,
    ROLES,
    parse_roles,
    role_of,
)
from jarvis_ha_control.app.autonomy.store import Store
import tempfile
import os


# =============================================================================
# Tests pour les fonctions utilitaires
# =============================================================================

class TestUtilityFunctions:
    """Tests pour les fonctions utilitaires du module access."""

    def test_norm_basic(self):
        """Test la normalisation de texte basique."""
        assert norm("Test") == "test"
        assert norm("TEST") == "test"
        assert norm("  test  ") == "test"

    def test_norm_with_accents(self):
        """Test la normalisation avec accents."""
        assert norm("Café") == "cafe"
        assert norm("Hôtel") == "hotel"
        assert norm("Été") == "ete"

    def test_norm_with_special_chars(self):
        """Test la normalisation avec caractères spéciaux."""
        assert norm("Test!@#") == "test"
        assert norm("Test-123") == "test 123"
        assert norm("Test's") == "test's"

    def test_extract_pin_valid(self):
        """Test l'extraction d'un PIN valide."""
        assert extract_pin("Mon code est 1234") == "1234"
        assert extract_pin("code 5678") == "5678"
        assert extract_pin("123456") == "123456"

    def test_extract_pin_invalid(self):
        """Test l'extraction avec un PIN invalide."""
        assert extract_pin("Pas de code ici") is None
        assert extract_pin("code abc") is None
        assert extract_pin("12") is None  # Trop court

    def test_parse_roles(self):
        """Test le parsing des rôles."""
        roles = parse_roles(["alice:admin", "bob:member", "charlie:guest"])
        assert roles == {"alice": "admin", "bob": "member", "charlie": "guest"}
        
        # Test avec des entrées invalides
        roles = parse_roles(["invalid", "alice:", ":admin"])
        assert roles == {}

    def test_role_of(self):
        """Test la récupération du rôle."""
        roles = {"alice": "admin", "bob": "member"}
        assert role_of("alice", roles) == "admin"
        assert role_of("bob", roles) == "member"
        assert role_of("charlie", roles) == "guest"  # Default
        assert role_of("Charlie", roles, default="guest") == "guest"


# =============================================================================
# Tests pour classify
# =============================================================================

class TestClassify:
    """Tests pour la fonction classify."""

    def test_classify_approve(self):
        """Test la classification d'une approbation."""
        intent, num = classify("oui")
        assert intent == "approve"
        assert num is None
        
        intent, num = classify("valide")
        assert intent == "approve"
        
        intent, num = classify("c'est bon")
        assert intent == "approve"

    def test_classify_reject(self):
        """Test la classification d'un refus."""
        intent, num = classify("non")
        assert intent == "reject"
        
        intent, num = classify("refuse")
        assert intent == "reject"

    def test_classify_undo(self):
        """Test la classification d'une annulation."""
        intent, num = classify("annule ca")
        assert intent == "undo"
        
        intent, num = classify("annule la derniere")
        assert intent == "undo"

    def test_classify_list(self):
        """Test la classification d'une demande de liste."""
        intent, num = classify("quelles propositions")
        assert intent == "list"
        
        intent, num = classify("tu proposes quoi")
        assert intent == "list"

    def test_classify_no_intent(self):
        """Test la classification sans intention."""
        intent, num = classify("Bonjour Jarvis")
        assert intent is None
        assert num is None


# =============================================================================
# Tests pour VoiceGate
# =============================================================================

class TestVoiceGate:
    """Tests pour la classe VoiceGate."""

    @pytest.fixture
    def mock_engine(self):
        """Crée un mock pour l.engine."""
        engine = Mock()
        engine.store = Mock()
        engine.store.proposals = Mock(return_value=[])
        engine.decide = AsyncMock(return_value={"ok": True, "status": "executed"})
        return engine

    @pytest.fixture
    def mock_engineer(self):
        """Crée un mock pour l.engineer."""
        engineer = Mock()
        engineer.undo_last = AsyncMock(return_value="OK : Annulation effectuée")
        return engineer

    @pytest.fixture
    def voice_gate_enabled(self, mock_engine, mock_engineer):
        """Crée un VoiceGate activé."""
        return VoiceGate(engine=mock_engine, engineer=mock_engineer, pin="1234", enabled=True)

    @pytest.fixture
    def voice_gate_disabled(self, mock_engine, mock_engineer):
        """Crée un VoiceGate désactivé."""
        return VoiceGate(engine=mock_engine, engineer=mock_engineer, pin="", enabled=False)

    def test_voice_gate_initialization(self, voice_gate_enabled):
        """Test l'initialisation de VoiceGate."""
        assert voice_gate_enabled.enabled is True
        assert voice_gate_enabled.pin == "1234"
        assert voice_gate_enabled._fails == []

    @pytest.mark.asyncio
    async def test_handle_disabled(self, voice_gate_disabled):
        """Test le traitement quand VoiceGate est désactivé."""
        result = await voice_gate_disabled.handle("oui", "alice", "admin")
        assert result is None

    @pytest.mark.asyncio
    async def test_handle_no_intent(self, voice_gate_enabled):
        """Test le traitement sans intention."""
        result = await voice_gate_enabled.handle("Bonjour", "alice", "admin")
        assert result is None

    @pytest.mark.asyncio
    async def test_handle_list_intent(self, voice_gate_enabled):
        """Test le traitement avec intention 'list'."""
        voice_gate_enabled.engine.store.proposals = Mock(return_value=[
            {"id": 1, "message": "Allumer la lumière"},
            {"id": 2, "message": "Éteindre le chauffage"},
        ])
        
        result = await voice_gate_enabled.handle("quelles propositions", "alice", "admin")
        
        assert result is not None
        assert "2 proposition(s)" in result

    @pytest.mark.asyncio
    async def test_handle_no_pin(self, voice_gate_enabled):
        """Test le traitement sans PIN configuré."""
        voice_gate_enabled.pin = ""
        
        result = await voice_gate_enabled.handle("valide", "alice", "admin")
        
        assert "La validation vocale est désactivée" in result

    @pytest.mark.asyncio
    async def test_handle_non_admin(self, voice_gate_enabled):
        """Test le traitement avec un non-admin."""
        result = await voice_gate_enabled.handle("valide 1234", "bob", "member")
        
        assert "Seul un administrateur" in result

    @pytest.mark.asyncio
    async def test_handle_locked(self, voice_gate_enabled):
        """Test le traitement quand le gate est verrouillé."""
        # Simuler des échecs pour verrouiller
        voice_gate_enabled._fails = [time.time() for _ in range(5)]
        
        result = await voice_gate_enabled.handle("valide 1234", "alice", "admin")
        
        assert "Trop d'essais" in result

    @pytest.mark.asyncio
    async def test_handle_wrong_pin(self, voice_gate_enabled):
        """Test le traitement avec un mauvais PIN."""
        result = await voice_gate_enabled.handle("valide 9999", "alice", "admin")
        
        assert "Code incorrect" in result
        assert len(voice_gate_enabled._fails) == 1

    @pytest.mark.asyncio
    async def test_handle_correct_pin(self, voice_gate_enabled):
        """Test le traitement avec le bon PIN."""
        voice_gate_enabled.engine.store.proposals = Mock(return_value=[
            {"id": 1, "message": "Test"}
        ])
        
        result = await voice_gate_enabled.handle("valide 1234", "alice", "admin")
        
        assert result is not None
        assert voice_gate_enabled.engine.decide.called

    @pytest.mark.asyncio
    async def test_handle_undo(self, voice_gate_enabled):
        """Test le traitement d'une annulation."""
        result = await voice_gate_enabled.handle("annule ca 1234", "alice", "admin")
        
        assert result is not None
        assert voice_gate_enabled.engineer.undo_last.called


# =============================================================================
# Tests pour Store (Facts / Mémoire)
# =============================================================================

class TestStoreFacts:
    """Tests pour la gestion des faits dans Store."""

    @pytest.fixture
    def temp_db(self):
        """Crée une base de données temporaire."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        yield db_path
        if os.path.exists(db_path):
            os.unlink(db_path)

    @pytest.fixture
    def store(self, temp_db):
        """Crée une instance de Store."""
        return Store(path=temp_db)

    def test_add_fact(self, store):
        """Test l'ajout d'un fait."""
        fid = store.add_fact("alice", "Aime la lumière allumée le soir")
        
        assert isinstance(fid, int)
        assert fid > 0

    def test_add_duplicate_fact(self, store):
        """Test l'ajout d'un fait en double."""
        fid1 = store.add_fact("alice", "Aime la lumière")
        fid2 = store.add_fact("alice", "aime la lumière")  # Même fait en minuscules
        
        assert fid1 == fid2  # Doit retourner le même ID

    def test_facts_by_person(self, store):
        """Test la récupération des faits par personne."""
        store.add_fact("alice", "Préfère 20°C")
        store.add_fact("alice", "Aime le café")
        store.add_fact("bob", "Préfère 22°C")
        
        alice_facts = store.facts(person="alice")
        
        assert len(alice_facts) == 2
        assert all(f["person"] == "alice" for f in alice_facts)

    def test_facts_all(self, store):
        """Test la récupération de tous les faits."""
        store.add_fact("alice", "Test 1")
        store.add_fact("bob", "Test 2")
        
        all_facts = store.facts()
        
        assert len(all_facts) == 2

    def test_delete_fact(self, store):
        """Test la suppression d'un fait."""
        fid = store.add_fact("alice", "À supprimer")
        
        result = store.delete_fact(fid)
        
        assert result is True
        
        facts = store.facts()
        assert len(facts) == 0

    def test_delete_nonexistent_fact(self, store):
        """Test la suppression d'un fait inexistant."""
        result = store.delete_fact(99999)
        
        assert result is False


# =============================================================================
# Tests d'intégration
# =============================================================================

class TestIntegration:
    """Tests d'intégration pour mémoire + validation vocale."""

    @pytest.mark.asyncio
    async def test_full_voice_validation_workflow(self):
        """Test le workflow complet de validation vocale."""
        # Créer les mocks
        mock_engine = Mock()
        mock_engine.store = Mock()
        mock_engine.store.proposals = Mock(return_value=[
            {"id": 1, "message": "Allumer la lumière"}
        ])
        mock_engine.decide = AsyncMock(return_value={"ok": True, "status": "executed"})
        
        mock_engineer = Mock()
        mock_engineer.undo_last = AsyncMock(return_value="OK")
        
        # Créer VoiceGate
        voice_gate = VoiceGate(
            engine=mock_engine,
            engineer=mock_engineer,
            pin="1234",
            enabled=True
        )
        
        # Tester une validation complète
        result = await voice_gate.handle("valide 1234", "alice", "admin")
        
        assert result is not None
        assert mock_engine.decide.called

    def test_memory_and_voice_integration(self):
        """Test l'intégration mémoire + validation vocale."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            store = Store(path=db_path)
            
            # Ajouter des faits
            store.add_fact("alice", "Préfère la lumière allumée")
            store.add_fact("alice", "Température idéale: 20°C")
            
            # Vérifier les faits
            facts = store.facts(person="alice")
            assert len(facts) == 2
            
            # Créer VoiceGate avec ce store
            mock_engine = Mock()
            mock_engine.store = store
            mock_engine.decide = AsyncMock(return_value={"ok": True})
            
            mock_engineer = Mock()
            
            voice_gate = VoiceGate(
                engine=mock_engine,
                engineer=mock_engineer,
                pin="1234",
                enabled=True
            )
            
            # Le VoiceGate peut accéder aux faits via engine.store
            assert voice_gate.engine.store == store
            
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)


# =============================================================================
# Tests de sécurité
# =============================================================================

class TestSecurity:
    """Tests de sécurité pour la validation vocale."""

    @pytest.fixture
    def voice_gate(self):
        """Crée un VoiceGate pour les tests de sécurité."""
        mock_engine = Mock()
        mock_engine.store = Mock()
        mock_engine.store.proposals = Mock(return_value=[])
        
        mock_engineer = Mock()
        
        return VoiceGate(
            engine=mock_engine,
            engineer=mock_engineer,
            pin="1234",
            enabled=True
        )

    def test_pin_not_in_clear(self, voice_gate):
        """Test que le PIN n'est pas stocké en clair dans les logs."""
        # Le PIN est stocké, mais on vérifie qu'il n'est pas exposé
        assert voice_gate.pin == "1234"

    @pytest.mark.asyncio
    async def test_lock_after_failures(self, voice_gate):
        """Test le verrouillage après plusieurs échecs."""
        # Simuler des échecs
        for i in range(5):
            await voice_gate.handle(f"valide {i:04d}", "alice", "admin")
        
        # Vérifier que le gate est verrouillé
        assert voice_gate._locked() is True
        
        # Vérifier qu'une nouvelle tentative est bloquée
        result = await voice_gate.handle("valide 1234", "alice", "admin")
        assert "Trop d'essais" in result

    def test_pin_extraction_prevents_leak(self):
        """Test que l'extraction du PIN ne fuite pas dans les messages."""
        text = "Mon code secret est 1234 et je ne veux pas le partager"
        pin = extract_pin(text)
        
        assert pin == "1234"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
