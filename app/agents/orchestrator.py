"""Orchestrateur - Coordination des agents IA.

Cet agent est responsable de :
- Coordonner les agents Conversation, Décision et Action
- Gérer le workflow complet : conversation → décision → action
- Maintenir l'état global du système
- Gérer les priorités et les conflits
- Optimiser les performances
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Awaitable

logger = logging.getLogger("Orchestrator")


class SystemState(Enum):
    """États du système."""
    IDLE = "idle"  # Inactif
    PROCESSING = "processing"  # Traitement en cours
    BUSY = "busy"  # Occupé (plusieurs actions)
    OVERLOADED = "overloaded"  # Surchargé
    ERROR = "error"  # Erreur


@dataclass
class WorkflowResult:
    """Résultat d'un workflow."""
    workflow_id: str
    success: bool
    message: str
    steps: List[Dict[str, Any]] = field(default_factory=list)
    duration_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit le résultat en dictionnaire."""
        return {
            "workflow_id": self.workflow_id,
            "success": self.success,
            "message": self.message,
            "steps": self.steps,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp.isoformat()
        }


class Orchestrator:
    """Orchestrateur des agents IA pour Jarvis HA Control.
    
    Cet agent coordonne :
    - ConversationAgent : Gestion des conversations
    - DecisionAgent : Prise de décision
    - ActionAgent : Exécution des actions
    
    Il gère :
    - Le workflow complet
    - Les priorités
    - Les conflits
    - L'état global
    """
    
    def __init__(
        self,
        conversation_agent: Any,
        decision_agent: Any,
        action_agent: Any,
        store: Any,
        ha_client: Any = None,
        max_concurrent_workflows: int = 3
    ):
        """
        Initialise l'orchestrateur.
        
        Args:
            conversation_agent: Instance de ConversationAgent
            decision_agent: Instance de DecisionAgent
            action_agent: Instance de ActionAgent
            store: Instance de Store
            ha_client: Client Home Assistant
            max_concurrent_workflows: Nombre maximum de workflows simultanés
        """
        self.conversation_agent = conversation_agent
        self.decision_agent = decision_agent
        self.action_agent = action_agent
        self.store = store
        self.ha_client = ha_client
        self.max_concurrent_workflows = max_concurrent_workflows
        
        # État du système
        self._state = SystemState.IDLE
        
        # Workflows en cours
        self._workflows: Dict[str, Dict[str, Any]] = {}
        
        # Compteur d'ID de workflow
        self._workflow_counter = 0
        
        # Verrou pour les workflows
        self._workflow_lock = asyncio.Lock()
        
        # Callbacks pour les événements
        self._event_handlers: Dict[str, List[Callable[[Dict[str, Any]], Awaitable[Any]]]] = {}
        
        logger.info("Orchestrator initialisé")
    
    def register_event_handler(
        self,
        event_type: str,
        handler: Callable[[Dict[str, Any]], Awaitable[Any]]
    ) -> None:
        """Enregistre un handler pour un type d'événement."""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)
        logger.debug(f"Handler enregistré pour {event_type}")
    
    async def _emit_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Émet un événement aux handlers enregistrés."""
        handlers = self._event_handlers.get(event_type, [])
        for handler in handlers:
            try:
                await handler(data)
            except Exception as e:
                logger.error(f"Erreur dans le handler pour {event_type}: {e}")
    
    async def process_request(
        self,
        user_id: str,
        message: str,
        session_id: Optional[str] = None,
        priority: int = 0
    ) -> WorkflowResult:
        """
        Traite une requête utilisateur complète.
        
        Workflow :
        1. Conversation → Comprendre l'intention
        2. Décision → Évaluer et décider
        3. Action → Exécuter si approuvé
        
        Args:
            user_id: ID de l'utilisateur
            message: Message de l'utilisateur
            session_id: ID de la session (optionnel)
            priority: Priorité de la requête
            
        Returns:
            Résultat du workflow
        """
        import time
        
        start_time = time.time()
        
        async with self._workflow_lock:
            self._workflow_counter += 1
            workflow_id = f"workflow_{self._workflow_counter}"
            
            # Créer le contexte du workflow
            workflow = {
                "id": workflow_id,
                "user_id": user_id,
                "session_id": session_id or f"session_{workflow_id}",
                "priority": priority,
                "status": "starting",
                "steps": []
            }
            self._workflows[workflow_id] = workflow
            
            # Mettre à jour l'état du système
            self._update_system_state()
        
        steps = []
        
        try:
            # Étape 1: Conversation
            logger.info(f"[Workflow {workflow_id}] Étape 1: Conversation")
            conversation_result = await self._run_conversation(
                session_id or f"session_{workflow_id}",
                message,
                user_id
            )
            steps.append({
                "step": "conversation",
                "intent": conversation_result.get("intent"),
                "entities": conversation_result.get("entities"),
                "response": conversation_result.get("response"),
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            workflow["steps"] = steps
            
            # Si l'intention est une validation vocale, passer directement à l'action
            if conversation_result.get("intent") == "validate_action":
                # Extraire l'action depuis le contexte
                action = self._extract_action_from_conversation(conversation_result)
                if action:
                    # Étape 2: Décision (pour validation vocale, on suppose déjà approuvé)
                    logger.info(f"[Workflow {workflow_id}] Étape 2: Décision (validation vocale)")
                    decision = await self.decision_agent.evaluate_proposal(
                        action,
                        {"user": user_id, "source": "voice"},
                        user_id
                    )
                    steps.append({
                        "step": "decision",
                        "decision_type": decision.decision_type.value,
                        "confidence": decision.confidence_score,
                        "risk_level": decision.risk_level.value,
                        "reason": decision.reason,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                    
                    # Si approuvé automatiquement ou validé
                    if decision.auto_approved or decision.decision_type == "auto_approve":
                        # Étape 3: Action
                        logger.info(f"[Workflow {workflow_id}] Étape 3: Action")
                        action_id = await self.action_agent.enqueue_action(
                            action,
                            user_id,
                            priority
                        )
                        steps.append({
                            "step": "action",
                            "action_id": action_id,
                            "status": "queued",
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })
                        
                        return WorkflowResult(
                            workflow_id=workflow_id,
                            success=True,
                            message="Action validée et mise en file d'attente",
                            steps=steps,
                            duration_ms=(time.time() - start_time) * 1000
                        )
            
            # Étape 2: Décision
            logger.info(f"[Workflow {workflow_id}] Étape 2: Décision")
            action = self._extract_action_from_conversation(conversation_result)
            
            if action:
                decision = await self.decision_agent.evaluate_proposal(
                    action,
                    {"user": user_id, "session_id": workflow["session_id"]},
                    user_id
                )
                steps.append({
                    "step": "decision",
                    "decision_type": decision.decision_type.value,
                    "confidence": decision.confidence_score,
                    "risk_level": decision.risk_level.value,
                    "reason": decision.reason,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
                workflow["steps"] = steps
                
                # Si approbation automatique
                if decision.auto_approved:
                    # Étape 3: Action
                    logger.info(f"[Workflow {workflow_id}] Étape 3: Action (auto-apprové)")
                    action_id = await self.action_agent.enqueue_action(
                        action,
                        user_id,
                        priority
                    )
                    steps.append({
                        "step": "action",
                        "action_id": action_id,
                        "status": "queued",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                    
                    return WorkflowResult(
                        workflow_id=workflow_id,
                        success=True,
                        message="Action approuvée automatiquement et mise en file",
                        steps=steps,
                        duration_ms=(time.time() - start_time) * 1000
                    )
                
                # Si validation requise
                if decision.decision_type == "request_validation":
                    # Créer une proposition dans le store
                    proposal_id = self.store.add_proposal(
                        rule="autonomy",
                        entity_id=action.get("entity_id", "unknown"),
                        message=decision.reason,
                        action=action,
                        expect_state=None
                    )
                    
                    return WorkflowResult(
                        workflow_id=workflow_id,
                        success=True,
                        message=f"Validation requise pour cette action (ID: {proposal_id})",
                        steps=steps,
                        duration_ms=(time.time() - start_time) * 1000
                    )
                
                # Si rejet
                if decision.decision_type == "reject":
                    return WorkflowResult(
                        workflow_id=workflow_id,
                        success=False,
                        message=f"Action rejetée: {decision.reason}",
                        steps=steps,
                        duration_ms=(time.time() - start_time) * 1000
                    )
            
            # Si pas d'action détectée, juste une conversation
            return WorkflowResult(
                workflow_id=workflow_id,
                success=True,
                message=conversation_result.get("response", "OK"),
                steps=steps,
                duration_ms=(time.time() - start_time) * 1000
            )
            
        except Exception as e:
            logger.error(f"[Workflow {workflow_id}] Erreur: {e}")
            return WorkflowResult(
                workflow_id=workflow_id,
                success=False,
                message=f"Erreur: {str(e)}",
                steps=steps,
                duration_ms=(time.time() - start_time) * 1000
            )
        
        finally:
            async with self._workflow_lock:
                workflow["status"] = "completed"
                self._update_system_state()
    
    async def _run_conversation(
        self,
        session_id: str,
        message: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Exécute l'étape de conversation.
        
        Args:
            session_id: ID de la session
            message: Message de l'utilisateur
            user_id: ID de l'utilisateur
            
        Returns:
            Résultat de la conversation
        """
        try:
            result = await self.conversation_agent.process_message(
                session_id,
                message,
                {"user_id": user_id}
            )
            return result
        except Exception as e:
            logger.error(f"Erreur dans la conversation: {e}")
            return {
                "response": "Désolé, j'ai eu un problème pour comprendre ta demande.",
                "intent": None,
                "entities": {},
                "error": str(e)
            }
    
    def _extract_action_from_conversation(self, conversation_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extrait une action depuis le résultat de la conversation.
        
        Args:
            conversation_result: Résultat de la conversation
            
        Returns:
            Action ou None
        """
        intent = conversation_result.get("intent")
        entities = conversation_result.get("entities", {})
        
        # Si pas d'intention, pas d'action
        if not intent:
            return None
        
        # Extraire l'entité
        entity_id = entities.get("entities", [None])[0]
        if not entity_id:
            return None
        
        # Mapping des intentions aux actions
        intent_to_action = {
            "control_device": self._create_control_action,
            "query_state": None,  # Pas d'action, juste une requête
            "remember_preference": self._create_remember_action,
            "validate_action": self._create_validate_action,
            "undo_action": self._create_undo_action,
        }
        
        action_creator = intent_to_action.get(intent)
        if action_creator:
            return action_creator(entity_id, entities, conversation_result)
        
        return None
    
    def _create_control_action(
        self,
        entity_id: str,
        entities: Dict[str, Any],
        conversation_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Crée une action de contrôle."""
        message = conversation_result.get("response", "").lower()
        
        # Déterminer le service en fonction du message
        if any(word in message for word in ["allume", "allumer", "active"]):
            return {
                "domain": entity_id.split(".")[0],
                "service": "turn_on",
                "entity_id": entity_id,
                "data": {}
            }
        elif any(word in message for word in ["éteins", "éteindre", "désactive"]):
            return {
                "domain": entity_id.split(".")[0],
                "service": "turn_off",
                "entity_id": entity_id,
                "data": {}
            }
        
        return None
    
    def _create_remember_action(
        self,
        entity_id: str,
        entities: Dict[str, Any],
        conversation_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Crée une action de mémorisation."""
        # Pas d'action HA, mais enregistrement dans la mémoire
        return {
            "domain": "jarvis",
            "service": "remember",
            "entity_id": entity_id,
            "data": {
                "preference": conversation_result.get("response"),
                "user": conversation_result.get("metadata", {}).get("user_id")
            }
        }
    
    def _create_validate_action(
        self,
        entity_id: str,
        entities: Dict[str, Any],
        conversation_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Crée une action de validation."""
        # Extraire l'action depuis le contexte de la conversation
        # (À implémenter selon le contexte)
        return {
            "domain": entity_id.split(".")[0],
            "service": "validate",
            "entity_id": entity_id,
            "data": {"validation": True}
        }
    
    def _create_undo_action(
        self,
        entity_id: str,
        entities: Dict[str, Any],
        conversation_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Crée une action d'annulation."""
        return {
            "domain": "jarvis",
            "service": "undo",
            "entity_id": entity_id,
            "data": {}
        }
    
    def _update_system_state(self) -> None:
        """Met à jour l'état du système."""
        workflow_count = len(self._workflows)
        running_count = len([w for w in self._workflows.values() if w.get("status") == "running"])
        
        if running_count >= self.max_concurrent_workflows:
            self._state = SystemState.OVERLOADED
        elif running_count > 0:
            self._state = SystemState.BUSY
        elif workflow_count > 0:
            self._state = SystemState.PROCESSING
        else:
            self._state = SystemState.IDLE
        
        logger.debug(f"État du système: {self._state.value}")
    
    def get_system_state(self) -> Dict[str, Any]:
        """
        Récupère l'état du système.
        
        Returns:
            État du système
        """
        return {
            "state": self._state.value,
            "workflow_count": len(self._workflows),
            "max_concurrent_workflows": self.max_concurrent_workflows,
            "workflows": [
                {
                    "id": wf["id"],
                    "user_id": wf["user_id"],
                    "status": wf["status"],
                    "priority": wf["priority"],
                    "step_count": len(wf.get("steps", []))
                }
                for wf in self._workflows.values()
            ]
        }
    
    def get_workflow(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """
        Récupère un workflow.
        
        Args:
            workflow_id: ID du workflow
            
        Returns:
            Workflow ou None
        """
        return self._workflows.get(workflow_id)
    
    async def cancel_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """
        Annule un workflow.
        
        Args:
            workflow_id: ID du workflow
            
        Returns:
            Résultat de l'annulation
        """
        async with self._workflow_lock:
            workflow = self._workflows.get(workflow_id)
            if not workflow:
                return {"ok": False, "error": "Workflow non trouvé"}
            
            # Annuler toutes les actions associées
            for step in workflow.get("steps", []):
                if step.get("step") == "action":
                    await self.action_agent.cancel_action(step.get("action_id"))
            
            # Mettre à jour le statut
            workflow["status"] = "cancelled"
            self._update_system_state()
            
            return {"ok": True, "status": "cancelled", "workflow_id": workflow_id}
    
    def cleanup_completed_workflows(self, max_age_seconds: int = 3600) -> int:
        """
        Nettoie les workflows terminés.
        
        Args:
            max_age_seconds: Âge maximum des workflows à conserver
            
        Returns:
            Nombre de workflows supprimés
        """
        import time
        
        current_time = time.time()
        removed = 0
        
        for workflow_id, workflow in list(self._workflows.items()):
            # Vérifier si le workflow est terminé
            if workflow.get("status") in ["completed", "cancelled"]:
                # Vérifier l'âge
                created_time = workflow.get("created_at")
                if created_time:
                    try:
                        created_timestamp = datetime.fromisoformat(created_time).timestamp()
                        if current_time - created_timestamp > max_age_seconds:
                            del self._workflows[workflow_id]
                            removed += 1
                    except:
                        pass
        
        if removed > 0:
            logger.info(f"Nettoyage: {removed} workflows supprimés")
        
        return removed
