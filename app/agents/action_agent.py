"""Agent Action - Exécution des actions validées.

Cet agent est responsable de :
- Exécuter les actions approuvées
- Vérifier les préconditions
- Gérer les erreurs et les rollbacks
- Enregistrer les résultats
- Intégration avec Home Assistant
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Awaitable

logger = logging.getLogger("ActionAgent")


class ActionStatus(Enum):
    """Statuts des actions."""
    PENDING = "pending"  # En attente d'exécution
    RUNNING = "running"  # En cours d'exécution
    COMPLETED = "completed"  # Terminée avec succès
    FAILED = "failed"  # Échec
    CANCELLED = "cancelled"  # Annulée
    ROLLED_BACK = "rolled_back"  # Rollback effectué


@dataclass
class ActionResult:
    """Résultat d'une action."""
    action_id: str
    status: ActionStatus
    success: bool
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit le résultat en dictionnaire."""
        return {
            "action_id": self.action_id,
            "status": self.status.value,
            "success": self.success,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
            "duration_ms": self.duration_ms
        }


@dataclass
class ActionQueueItem:
    """Élément de la file d'attente des actions."""
    action: Dict[str, Any]
    action_id: str
    priority: int
    proposed_by: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    retries: int = 0
    max_retries: int = 3
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit l'élément en dictionnaire."""
        return {
            "action": self.action,
            "action_id": self.action_id,
            "priority": self.priority,
            "proposed_by": self.proposed_by,
            "timestamp": self.timestamp.isoformat(),
            "retries": self.retries,
            "max_retries": self.max_retries
        }


class ActionAgent:
    """Agent d'action pour Jarvis HA Control.
    
    Cet agent gère :
    - L'exécution des actions validées
    - La file d'attente des actions
    - Les préconditions et postconditions
    - Les rollbacks en cas d'échec
    - L'enregistrement des résultats
    """
    
    def __init__(
        self,
        ha_client: Any,
        store: Any,
        max_concurrent_actions: int = 5,
        default_timeout: float = 30.0
    ):
        """
        Initialise l'agent d'action.
        
        Args:
            ha_client: Client Home Assistant
            store: Instance de Store pour la persistance
            max_concurrent_actions: Nombre maximum d'actions simultanées
            default_timeout: Timeout par défaut pour les actions (secondes)
        """
        self.ha_client = ha_client
        self.store = store
        self.max_concurrent_actions = max_concurrent_actions
        self.default_timeout = default_timeout
        
        # File d'attente des actions
        self._queue: List[ActionQueueItem] = []
        
        # Actions en cours
        self._running_actions: Dict[str, ActionQueueItem] = {}
        
        # Callbacks pour les événements d'action
        self._action_handlers: Dict[ActionStatus, List[Callable[[ActionResult], Awaitable[Any]]]] = {
            ActionStatus.PENDING: [],
            ActionStatus.RUNNING: [],
            ActionStatus.COMPLETED: [],
            ActionStatus.FAILED: [],
            ActionStatus.CANCELLED: [],
            ActionStatus.ROLLED_BACK: []
        }
        
        # Verrou pour la file d'attente
        self._queue_lock = asyncio.Lock()
        
        # Compteur d'ID d'action
        self._action_counter = 0
        
        logger.info("ActionAgent initialisé")
    
    def register_handler(
        self,
        status: ActionStatus,
        handler: Callable[[ActionResult], Awaitable[Any]]
    ) -> None:
        """Enregistre un handler pour un statut d'action."""
        self._action_handlers[status].append(handler)
        logger.debug(f"Handler enregistré pour {status.value}")
    
    async def enqueue_action(
        self,
        action: Dict[str, Any],
        proposed_by: str,
        priority: int = 0
    ) -> str:
        """
        Ajoute une action à la file d'attente.
        
        Args:
            action: Action à exécuter
            proposed_by: Utilisateur qui propose l'action
            priority: Priorité (0 = normale, >0 = haute, <0 = basse)
            
        Returns:
            ID de l'action
        """
        async with self._queue_lock:
            self._action_counter += 1
            action_id = f"action_{self._action_counter}"
            
            item = ActionQueueItem(
                action=action,
                action_id=action_id,
                priority=priority,
                proposed_by=proposed_by
            )
            
            # Insérer dans la file en fonction de la priorité
            self._queue.append(item)
            self._queue.sort(key=lambda x: -x.priority)  # Priorité la plus élevée en premier
            
            logger.info(f"Action ajoutée à la file: {action_id}, Priorité: {priority}")
            
            # Notifier les handlers
            await self._notify_handlers(ActionResult(
                action_id=action_id,
                status=ActionStatus.PENDING,
                success=False,
                message="Action en attente d'exécution"
            ))
            
            # Démarrer le traitement si possible
            await self._process_queue()
            
            return action_id
    
    async def _process_queue(self) -> None:
        """
        Traite la file d'attente des actions.
        """
        async with self._queue_lock:
            # Vérifier le nombre d'actions en cours
            while len(self._running_actions) < self.max_concurrent_actions and self._queue:
                # Prendre la prochaine action
                item = self._queue.pop(0)
                self._running_actions[item.action_id] = item
                
                # Exécuter l'action en arrière-plan
                asyncio.create_task(self._execute_action(item))
    
    async def _execute_action(self, item: ActionQueueItem) -> None:
        """
        Exécute une action.
        
        Args:
            item: Élément de la file à exécuter
        """
        action_id = item.action_id
        action = item.action
        
        logger.info(f"Exécution de l'action: {action_id}")
        
        # Notifier que l'action a commencé
        await self._notify_handlers(ActionResult(
            action_id=action_id,
            status=ActionStatus.RUNNING,
            success=False,
            message="Action en cours d'exécution"
        ))
        
        start_time = datetime.now(timezone.utc)
        result = None
        
        try:
            # Vérifier les préconditions
            if not await self._check_preconditions(action):
                result = ActionResult(
                    action_id=action_id,
                    status=ActionStatus.FAILED,
                    success=False,
                    message="Préconditions non remplies"
                )
            else:
                # Exécuter l'action
                result = await self._execute_ha_action(action)
                
                # Vérifier les postconditions
                if result.success:
                    if not await self._check_postconditions(action):
                        # Rollback si les postconditions ne sont pas remplies
                        logger.warning(f"Postconditions non remplies pour {action_id}, rollback...")
                        rollback_result = await self._rollback_action(action)
                        if rollback_result.success:
                            result = ActionResult(
                                action_id=action_id,
                                status=ActionStatus.ROLLED_BACK,
                                success=False,
                                message="Action annulée (postconditions non remplies)"
                            )
                        else:
                            result = ActionResult(
                                action_id=action_id,
                                status=ActionStatus.FAILED,
                                success=False,
                                message="Action échouée et rollback échoué"
                            )
                
                # Calculer la durée
                end_time = datetime.now(timezone.utc)
                result.duration_ms = (end_time - start_time).total_seconds() * 1000
                
        except Exception as e:
            logger.error(f"Erreur lors de l'exécution de {action_id}: {e}")
            result = ActionResult(
                action_id=action_id,
                status=ActionStatus.FAILED,
                success=False,
                message=f"Erreur: {str(e)}"
            )
        
        # Nettoyer
        async with self._queue_lock:
            self._running_actions.pop(action_id, None)
        
        # Enregistrer le résultat
        self._log_action_result(item, result)
        
        # Notifier les handlers
        await self._notify_handlers(result)
        
        # Traiter la file suivante
        await self._process_queue()
    
    async def _check_preconditions(self, action: Dict[str, Any]) -> bool:
        """
        Vérifie les préconditions d'une action.
        
        Args:
            action: Action à vérifier
            
        Returns:
            True si les préconditions sont remplies
        """
        try:
            domain = action.get("domain")
            entity_id = action.get("entity_id")
            
            # Vérifier que l'entité existe
            if self.ha_client:
                state = await self.ha_client.get_entity_state(entity_id)
                if state is None:
                    logger.warning(f"Entité non trouvée: {entity_id}")
                    return False
            
            # Vérifier les préconditions spécifiques au domaine
            if domain == "light" and action.get("service") == "turn_off":
                # Ne pas éteindre si déjà éteint
                if self.ha_client:
                    state = await self.ha_client.get_entity_state(entity_id)
                    if state and state.get("state") == "off":
                        logger.info(f"Lumière déjà éteinte: {entity_id}")
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification des préconditions: {e}")
            return False
    
    async def _execute_ha_action(self, action: Dict[str, Any]) -> ActionResult:
        """
        Exécute une action Home Assistant.
        
        Args:
            action: Action à exécuter
            
        Returns:
            Résultat de l'exécution
        """
        try:
            if not self.ha_client:
                return ActionResult(
                    action_id=action.get("action_id", "unknown"),
                    status=ActionStatus.FAILED,
                    success=False,
                    message="Client Home Assistant non disponible"
                )
            
            domain = action.get("domain")
            service = action.get("service")
            entity_id = action.get("entity_id")
            data = action.get("data", {})
            
            logger.debug(f"Exécution HA: {domain}.{service} sur {entity_id} avec {data}")
            
            # Exécuter l'action via le client HA
            result = await self.ha_client.call_service(
                domain=domain,
                service=service,
                entity_id=entity_id,
                data=data
            )
            
            if result:
                return ActionResult(
                    action_id=action.get("action_id", "unknown"),
                    status=ActionStatus.COMPLETED,
                    success=True,
                    message="Action exécutée avec succès",
                    details={"result": result}
                )
            else:
                return ActionResult(
                    action_id=action.get("action_id", "unknown"),
                    status=ActionStatus.FAILED,
                    success=False,
                    message="Action exécutée mais aucun résultat retourné"
                )
                
        except Exception as e:
            logger.error(f"Erreur lors de l'exécution HA: {e}")
            return ActionResult(
                action_id=action.get("action_id", "unknown"),
                status=ActionStatus.FAILED,
                success=False,
                message=f"Erreur HA: {str(e)}"
            )
    
    async def _check_postconditions(self, action: Dict[str, Any]) -> bool:
        """
        Vérifie les postconditions d'une action.
        
        Args:
            action: Action à vérifier
            
        Returns:
            True si les postconditions sont remplies
        """
        try:
            domain = action.get("domain")
            service = action.get("service")
            entity_id = action.get("entity_id")
            
            if not self.ha_client:
                return True  # On ne peut pas vérifier sans client
            
            # Vérifier que l'état a changé comme prévu
            if domain == "light" and service == "turn_on":
                state = await self.ha_client.get_entity_state(entity_id)
                if state and state.get("state") != "on":
                    logger.warning(f"Lumière non allumée: {entity_id}")
                    return False
            
            if domain == "light" and service == "turn_off":
                state = await self.ha_client.get_entity_state(entity_id)
                if state and state.get("state") != "off":
                    logger.warning(f"Lumière non éteinte: {entity_id}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification des postconditions: {e}")
            return False
    
    async def _rollback_action(self, action: Dict[str, Any]) -> ActionResult:
        """
        Effectue un rollback d'une action.
        
        Args:
            action: Action à annuler
            
        Returns:
            Résultat du rollback
        """
        try:
            domain = action.get("domain")
            service = action.get("service")
            entity_id = action.get("entity_id")
            
            # Déterminer l'action inverse
            rollback_action = self._get_rollback_action(action)
            
            if rollback_action:
                logger.info(f"Rollback: {rollback_action}")
                result = await self._execute_ha_action(rollback_action)
                return result
            else:
                return ActionResult(
                    action_id=action.get("action_id", "unknown"),
                    status=ActionStatus.COMPLETED,
                    success=True,
                    message="Pas de rollback nécessaire ou possible"
                )
                
        except Exception as e:
            logger.error(f"Erreur lors du rollback: {e}")
            return ActionResult(
                action_id=action.get("action_id", "unknown"),
                status=ActionStatus.FAILED,
                success=False,
                message=f"Erreur de rollback: {str(e)}"
            )
    
    def _get_rollback_action(self, action: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Détermine l'action inverse pour un rollback.
        
        Args:
            action: Action originale
            
        Returns:
            Action inverse ou None
        """
        domain = action.get("domain")
        service = action.get("service")
        entity_id = action.get("entity_id")
        data = action.get("data", {})
        
        # Mapping des services inverses
        rollback_map = {
            "turn_on": "turn_off",
            "turn_off": "turn_on",
            "open": "close",
            "close": "open",
            "lock": "unlock",
            "unlock": "lock",
            "set_temperature": "set_temperature",  # Revenir à la température précédente
            "set_position": "set_position",  # Revenir à la position précédente
        }
        
        if service in rollback_map:
            return {
                "domain": domain,
                "service": rollback_map[service],
                "entity_id": entity_id,
                "data": data,
                "action_id": f"rollback_{action.get('action_id', 'unknown')}"
            }
        
        return None
    
    def _log_action_result(self, item: ActionQueueItem, result: ActionResult) -> None:
        """
        Enregistre le résultat d'une action.
        
        Args:
            item: Élément de la file
            result: Résultat de l'action
        """
        try:
            # Enregistrer dans le journal
            severity = "info" if result.success else "error"
            self.store.log(
                severity=severity,
                kind="action",
                message=f"Action {result.status.value}: {item.action.get('service', 'unknown')} sur {item.action.get('entity_id', 'unknown')}",
                entity_id=item.action.get("entity_id")
            )
            
            # Enregistrer dans l'historique des actions
            # (À implémenter selon le schéma de la base)
            
        except Exception as e:
            logger.error(f"Erreur lors de l'enregistrement du résultat: {e}")
    
    async def _notify_handlers(self, result: ActionResult) -> None:
        """
        Notifie les handlers enregistrés.
        
        Args:
            result: Résultat à notifier
        """
        handlers = self._action_handlers.get(result.status, [])
        for handler in handlers:
            try:
                await handler(result)
            except Exception as e:
                logger.error(f"Erreur dans le handler pour {result.status}: {e}")
    
    async def cancel_action(self, action_id: str) -> Dict[str, Any]:
        """
        Annule une action.
        
        Args:
            action_id: ID de l'action à annuler
            
        Returns:
            Résultat de l'annulation
        """
        async with self._queue_lock:
            # Vérifier si l'action est en cours
            if action_id in self._running_actions:
                item = self._running_actions[action_id]
                
                # Créer un résultat d'annulation
                result = ActionResult(
                    action_id=action_id,
                    status=ActionStatus.CANCELLED,
                    success=False,
                    message="Action annulée par l'utilisateur"
                )
                
                # Retirer de la liste des actions en cours
                del self._running_actions[action_id]
                
                # Notifier les handlers
                await self._notify_handlers(result)
                
                return {"ok": True, "status": "cancelled", "action_id": action_id}
            
            # Vérifier si l'action est dans la file
            for i, item in enumerate(self._queue):
                if item.action_id == action_id:
                    del self._queue[i]
                    
                    result = ActionResult(
                        action_id=action_id,
                        status=ActionStatus.CANCELLED,
                        success=False,
                        message="Action annulée avant exécution"
                    )
                    
                    await self._notify_handlers(result)
                    
                    return {"ok": True, "status": "cancelled", "action_id": action_id}
            
            return {"ok": False, "error": "Action non trouvée", "action_id": action_id}
    
    async def get_queue_status(self) -> Dict[str, Any]:
        """
        Récupère l'état de la file d'attente.
        
        Returns:
            État de la file
        """
        async with self._queue_lock:
            return {
                "queue_length": len(self._queue),
                "running_count": len(self._running_actions),
                "max_concurrent": self.max_concurrent_actions,
                "queue": [item.to_dict() for item in self._queue],
                "running": {aid: item.to_dict() for aid, item in self._running_actions.items()}
            }
    
    def get_action_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Récupère l'historique des actions.
        
        Args:
            limit: Nombre maximum d'actions
            
        Returns:
            Historique des actions
        """
        try:
            # Récupérer depuis le journal
            logs = self.store.journal(limit=limit, since=None)
            actions = [
                {
                    "timestamp": log["ts"],
                    "severity": log["severity"],
                    "kind": log["kind"],
                    "message": log["message"],
                    "entity_id": log.get("entity_id")
                }
                for log in logs
                if log.get("kind") == "action"
            ]
            return actions
        except Exception as e:
            logger.error(f"Erreur lors de la récupération de l'historique: {e}")
            return []
