"""Agent Conversation - Gestion des conversations et du contexte.

Cet agent est responsable de :
- Maintenir le contexte de la conversation
- Comprendre les intentions de l'utilisateur
- Générer des réponses naturelles
- Gérer l'historique des conversations
- Intégration avec Gemini pour le traitement du langage naturel
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Callable, Awaitable

logger = logging.getLogger("ConversationAgent")


@dataclass
class Message:
    """Représente un message dans la conversation."""
    role: str  # "user" ou "assistant"
    content: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit le message en dictionnaire."""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """Crée un Message à partir d'un dictionnaire."""
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            metadata=data.get("metadata", {})
        )


@dataclass
class ConversationContext:
    """Contexte de la conversation."""
    user_id: str
    session_id: str
    messages: List[Message] = field(default_factory=list)
    current_intent: Optional[str] = None
    entities: Dict[str, Any] = field(default_factory=dict)
    last_action: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def add_message(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Ajoute un message à la conversation."""
        message = Message(role=role, content=content, metadata=metadata or {})
        self.messages.append(message)
        self.updated_at = datetime.now(timezone.utc)
    
    def get_history(self, limit: int = 10) -> List[Message]:
        """Récupère l'historique des messages."""
        return self.messages[-limit:]
    
    def clear(self) -> None:
        """Efface l'historique de la conversation."""
        self.messages = []
        self.current_intent = None
        self.entities = {}
        self.last_action = None


class ConversationAgent:
    """Agent de conversation pour Jarvis HA Control.
    
    Cet agent gère :
    - Le contexte des conversations
    - L'historique des messages
    - L'intégration avec le moteur de langage (Gemini)
    - La compréhension des intentions
    """
    
    def __init__(
        self,
        gemini_client: Any,
        store: Any,
        user_id: str = "default",
        max_history: int = 20,
        timeout: float = 30.0
    ):
        """
        Initialise l'agent de conversation.
        
        Args:
            gemini_client: Client pour l'API Gemini
            store: Instance de Store pour la persistance
            user_id: ID de l'utilisateur
            max_history: Nombre maximum de messages à conserver
            timeout: Timeout pour les requêtes (secondes)
        """
        self.gemini_client = gemini_client
        self.store = store
        self.user_id = user_id
        self.max_history = max_history
        self.timeout = timeout
        
        # Conversations actives
        self._conversations: Dict[str, ConversationContext] = {}
        
        # Callbacks pour les intentions
        self._intent_handlers: Dict[str, Callable[[ConversationContext, str], Awaitable[Any]]] = {}
        
        logger.info(f"ConversationAgent initialisé pour user: {user_id}")
    
    def register_intent_handler(
        self, 
        intent: str, 
        handler: Callable[[ConversationContext, str], Awaitable[Any]]
    ) -> None:
        """Enregistre un handler pour une intention spécifique."""
        self._intent_handlers[intent] = handler
        logger.debug(f"Handler enregistré pour l'intention: {intent}")
    
    def get_conversation(self, session_id: str) -> ConversationContext:
        """Récupère ou crée une conversation."""
        if session_id not in self._conversations:
            self._conversations[session_id] = ConversationContext(
                user_id=self.user_id,
                session_id=session_id
            )
            logger.debug(f"Nouvelle conversation créée: {session_id}")
        return self._conversations[session_id]
    
    def end_conversation(self, session_id: str) -> None:
        """Termine une conversation."""
        if session_id in self._conversations:
            # Sauvegarder l'historique avant de supprimer
            context = self._conversations.pop(session_id)
            self._save_conversation(context)
            logger.debug(f"Conversation terminée: {session_id}")
    
    def _save_conversation(self, context: ConversationContext) -> None:
        """Sauvegarde une conversation dans le store."""
        try:
            # Sauvegarder dans le store (à implémenter)
            pass
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde de la conversation: {e}")
    
    async def process_message(
        self,
        session_id: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Traite un message utilisateur.
        
        Args:
            session_id: ID de la session de conversation
            message: Message de l'utilisateur
            metadata: Métadonnées supplémentaires
            
        Returns:
            Dictionnaire avec la réponse et les informations de traitement
        """
        context = self.get_conversation(session_id)
        
        # Ajouter le message utilisateur
        context.add_message("user", message, metadata)
        
        # Analyser l'intention
        intent, entities = self._analyze_intent(message, context)
        context.current_intent = intent
        context.entities = entities
        
        # Générer une réponse
        response = await self._generate_response(context, message, intent, entities)
        
        # Ajouter la réponse de l'assistant
        context.add_message("assistant", response["text"])
        
        # Appliquer les handlers d'intention si disponible
        if intent and intent in self._intent_handlers:
            try:
                await self._intent_handlers[intent](context, message)
            except Exception as e:
                logger.error(f"Erreur dans le handler pour {intent}: {e}")
        
        # Limiter l'historique
        if len(context.messages) > self.max_history:
            context.messages = context.messages[-self.max_history:]
        
        return {
            "response": response["text"],
            "intent": intent,
            "entities": entities,
            "confidence": response.get("confidence", 0.0),
            "session_id": session_id,
            "history_length": len(context.messages)
        }
    
    def _analyze_intent(self, message: str, context: ConversationContext) -> tuple:
        """
        Analyse l'intention d'un message.
        
        Args:
            message: Message à analyser
            context: Contexte de la conversation
            
        Returns:
            Tuple (intention, entités)
        """
        # Implémentation basique - à améliorer avec un modèle de langage
        message_lower = message.lower()
        
        # Détection des intentions courantes
        if any(word in message_lower for word in ["allume", "allumer", "éteins", "éteindre", "active", "désactive"]):
            return "control_device", self._extract_entities(message)
        elif any(word in message_lower for word in ["quelle", "qu'est", "qu'est-ce", "?", "température", "état"]):
            return "query_state", self._extract_entities(message)
        elif any(word in message_lower for word in ["rappelle", "mémoire", "préfère", "aime"]):
            return "remember_preference", self._extract_entities(message)
        elif any(word in message_lower for word in ["valide", "approuve", "oui", "non", "refuse"]):
            return "validate_action", self._extract_entities(message)
        elif any(word in message_lower for word in ["annule", "retour", "undo"]):
            return "undo_action", self._extract_entities(message)
        elif any(word in message_lower for word in ["aide", "help", "comment", "que faire"]):
            return "request_help", {}
        else:
            return "general_conversation", {}
    
    def _extract_entities(self, message: str) -> Dict[str, Any]:
        """
        Extrait les entités d'un message.
        
        Args:
            message: Message à analyser
            
        Returns:
            Dictionnaire des entités détectées
        """
        # Implémentation basique
        entities = {}
        
        # Détecter les entités Home Assistant (ex: light.living_room, sensor.temperature)
        import re
        entity_pattern = r'\b([a-z_]+\.[a-z_0-9]+)\b'
        matches = re.findall(entity_pattern, message)
        if matches:
            entities["entities"] = matches
        
        # Détecter les valeurs numériques
        number_pattern = r'\b(\d+\.?\d*)\b'
        numbers = re.findall(number_pattern, message)
        if numbers:
            entities["numbers"] = [float(n) for n in numbers]
        
        # Détecter les noms de personnes
        if "je" in message.lower() or "moi" in message.lower():
            entities["person"] = self.user_id
        
        return entities
    
    async def _generate_response(
        self,
        context: ConversationContext,
        message: str,
        intent: Optional[str],
        entities: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Génère une réponse à un message.
        
        Args:
            context: Contexte de la conversation
            message: Message de l'utilisateur
            intent: Intention détectée
            entities: Entités extraites
            
        Returns:
            Dictionnaire avec la réponse générée
        """
        # Si on a un client Gemini, utiliser l'IA
        if self.gemini_client:
            try:
                response = await asyncio.wait_for(
                    self._generate_with_gemini(context, message, intent, entities),
                    timeout=self.timeout
                )
                return response
            except asyncio.TimeoutError:
                logger.warning("Timeout lors de la génération avec Gemini")
            except Exception as e:
                logger.error(f"Erreur avec Gemini: {e}")
        
        # Réponse par défaut
        return await self._generate_default_response(intent, entities)
    
    async def _generate_with_gemini(
        self,
        context: ConversationContext,
        message: str,
        intent: Optional[str],
        entities: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Génère une réponse en utilisant l'API Gemini.
        
        Args:
            context: Contexte de la conversation
            message: Message de l'utilisateur
            intent: Intention détectée
            entities: Entités extraites
            
        Returns:
            Dictionnaire avec la réponse générée
        """
        # Construire le prompt avec l'historique
        history = context.get_history(limit=10)
        messages = [{"role": msg.role, "content": msg.content} for msg in history]
        messages.append({"role": "user", "content": message})
        
        # Ajouter le contexte système
        system_prompt = self._build_system_prompt(context, intent, entities)
        
        try:
            response = await self.gemini_client.generate_content(
                messages=messages,
                system_prompt=system_prompt,
                temperature=0.7,
                max_tokens=1000
            )
            
            return {
                "text": response.text,
                "confidence": 0.9,
                "source": "gemini"
            }
        except Exception as e:
            logger.error(f"Erreur lors de l'appel à Gemini: {e}")
            return await self._generate_default_response(intent, entities)
    
    def _build_system_prompt(
        self,
        context: ConversationContext,
        intent: Optional[str],
        entities: Dict[str, Any]
    ) -> str:
        """
        Construit le prompt système pour Gemini.
        
        Args:
            context: Contexte de la conversation
            intent: Intention détectée
            entities: Entités extraites
            
        Returns:
            Prompt système
        """
        prompt_parts = [
            "Tu es Jarvis, l'assistant IA pour Home Assistant.",
            "Tu es intelligent, serviable et tu parles français.",
            "Tu as accès aux informations de la maison et tu peux contrôler les appareils.",
            "",
            "Règles :",
            "- Sois concis et direct",
            "- Si tu ne comprends pas, demande des clarifications",
            "- Ne fais jamais d'actions dangereuses (verrouiller/déverrouiller, alarmes, etc.) sans validation explicite",
            "- Utilise les informations du contexte pour personnaliser tes réponses",
            "",
            f"Utilisateur actuel : {context.user_id}",
            f"Intention détectée : {intent or 'inconnu'}",
            f"Entités : {json.dumps(entities, ensure_ascii=False)}",
        ]
        
        return "\n".join(prompt_parts)
    
    async def _generate_default_response(
        self,
        intent: Optional[str],
        entities: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Génère une réponse par défaut (sans IA).
        
        Args:
            intent: Intention détectée
            entities: Entités extraites
            
        Returns:
            Dictionnaire avec la réponse par défaut
        """
        responses = {
            "control_device": "Je vais contrôler cet appareil pour toi.",
            "query_state": "Je vérifie l'état pour toi.",
            "remember_preference": "Je retiens cette préférence.",
            "validate_action": "Validation enregistrée.",
            "undo_action": "Annulation en cours.",
            "request_help": "Comment puis-je t'aider ? Tu peux me demander de contrôler des appareils, de vérifier des états, ou de te donner des informations.",
            "general_conversation": "Je comprends. Comment puis-je t'aider ?"
        }
        
        return {
            "text": responses.get(intent, "Je comprends. Comment puis-je t'aider ?"),
            "confidence": 0.5,
            "source": "default"
        }
    
    def get_conversation_summary(self, session_id: str) -> Dict[str, Any]:
        """
        Récupère un résumé de la conversation.
        
        Args:
            session_id: ID de la session
            
        Returns:
            Résumé de la conversation
        """
        context = self._conversations.get(session_id)
        if not context:
            return {"error": "Conversation non trouvée"}
        
        return {
            "session_id": session_id,
            "user_id": context.user_id,
            "message_count": len(context.messages),
            "current_intent": context.current_intent,
            "entities": context.entities,
            "created_at": context.created_at.isoformat(),
            "updated_at": context.updated_at.isoformat()
        }
    
    def list_conversations(self) -> List[Dict[str, Any]]:
        """Liste toutes les conversations actives."""
        return [
            {
                "session_id": session_id,
                "user_id": context.user_id,
                "message_count": len(context.messages),
                "updated_at": context.updated_at.isoformat()
            }
            for session_id, context in self._conversations.items()
        ]
