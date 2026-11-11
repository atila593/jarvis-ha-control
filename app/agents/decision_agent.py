"""Agent Décision - Prise de décision autonome basée sur la confiance.

Cet agent est responsable de :
- Évaluer les propositions d'action
- Calculer les scores de confiance
- Prendre des décisions autonomes ou demander validation
- Gérer les règles de sécurité
- Intégration avec le système de confiance
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Awaitable

logger = logging.getLogger("DecisionAgent")


class DecisionType(Enum):
    """Types de décision."""
    AUTO_APPROVE = "auto_approve"  # Approbation automatique
    REQUEST_VALIDATION = "request_validation"  # Demande de validation
    REJECT = "reject"  # Rejet automatique
    NEED_MORE_INFO = "need_more_info"  # Besoin de plus d'informations


class RiskLevel(Enum):
    """Niveaux de risque."""
    LOW = "low"  # Faible risque (ex: allumer une lumière)
    MEDIUM = "medium"  # Risque moyen (ex: changer la température)
    HIGH = "high"  # Risque élevé (ex: ouvrir une porte)
    CRITICAL = "critical"  # Risque critique (ex: désactiver l'alarme)


# Actions interdites sans validation manuelle explicite
FORBIDDEN_ACTIONS = {
    "lock": ["unlock", "open"],
    "alarm_control_panel": ["alarm_disarm", "alarm_turn_off"],
    "cover": ["open", "close"] if "window" in "entity_id" else [],
    "switch": ["turn_on"] if "alarm" in "entity_id" else [],
}

# Domaines à risque élevé
HIGH_RISK_DOMAINS = {"lock", "alarm_control_panel", "cover", "door", "window"}

# Domaines à risque critique
CRITICAL_DOMAINS = {"lock", "alarm_control_panel"}


@dataclass
class Decision:
    """Représente une décision."""
    action: Dict[str, Any]
    decision_type: DecisionType
    confidence_score: float
    risk_level: RiskLevel
    reason: str
    proposed_by: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    validation_required: bool = True
    auto_approved: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit la décision en dictionnaire."""
        return {
            "action": self.action,
            "decision_type": self.decision_type.value,
            "confidence_score": self.confidence_score,
            "risk_level": self.risk_level.value,
            "reason": self.reason,
            "proposed_by": self.proposed_by,
            "timestamp": self.timestamp.isoformat(),
            "validation_required": self.validation_required,
            "auto_approved": self.auto_approved
        }


@dataclass
class DecisionContext:
    """Contexte pour la prise de décision."""
    current_state: Dict[str, Any]
    user_preferences: Dict[str, Any]
    system_status: Dict[str, Any]
    time_of_day: str
    presence: List[str]
    weather: Dict[str, Any]
    recent_actions: List[Dict[str, Any]]


class DecisionAgent:
    """Agent de décision pour Jarvis HA Control.
    
    Cet agent gère :
    - L'évaluation des propositions d'action
    - Le calcul des scores de confiance
    - La prise de décision autonome
    - La gestion des règles de sécurité
    """
    
    def __init__(
        self,
        confidence_scorer: Any,
        store: Any,
        ha_client: Any = None,
        auto_approve_threshold: float = 0.85,
        min_confidence: float = 0.5
    ):
        """
        Initialise l'agent de décision.
        
        Args:
            confidence_scorer: Instance de ConfidenceScorer
            store: Instance de Store pour la persistance
            ha_client: Client Home Assistant
            auto_approve_threshold: Seuil pour l'approbation automatique (0.0-1.0)
            min_confidence: Score minimum pour considérer une action (0.0-1.0)
        """
        self.confidence_scorer = confidence_scorer
        self.store = store
        self.ha_client = ha_client
        self.auto_approve_threshold = auto_approve_threshold
        self.min_confidence = min_confidence
        
        # Callbacks pour les décisions
        self._decision_handlers: Dict[DecisionType, List[Callable[[Decision], Awaitable[Any]]]] = {
            DecisionType.AUTO_APPROVE: [],
            DecisionType.REQUEST_VALIDATION: [],
            DecisionType.REJECT: [],
            DecisionType.NEED_MORE_INFO: []
        }
        
        logger.info("DecisionAgent initialisé")
    
    def register_handler(
        self,
        decision_type: DecisionType,
        handler: Callable[[Decision], Awaitable[Any]]
    ) -> None:
        """Enregistre un handler pour un type de décision."""
        self._decision_handlers[decision_type].append(handler)
        logger.debug(f"Handler enregistré pour {decision_type.value}")
    
    async def evaluate_proposal(
        self,
        action: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        user: Optional[str] = None
    ) -> Decision:
        """
        Évalue une proposition d'action.
        
        Args:
            action: Action proposée (domain, service, entity_id, etc.)
            context: Contexte actuel
            user: Utilisateur qui propose l'action
            
        Returns:
            Decision avec le type de décision et les détails
        """
        logger.info(f"Évaluation de la proposition: {action}")
        
        # Vérifier si l'action est interdite
        if self._is_forbidden_action(action):
            return Decision(
                action=action,
                decision_type=DecisionType.REJECT,
                confidence_score=0.0,
                risk_level=RiskLevel.CRITICAL,
                reason="Action interdite sans validation manuelle explicite",
                proposed_by=user or "system",
                validation_required=True,
                auto_approved=False
            )
        
        # Calculer le score de confiance
        context = context or {}
        confidence_score = await self._calculate_confidence(action, context, user)
        
        # Déterminer le niveau de risque
        risk_level = self._assess_risk(action)
        
        # Prendre une décision basée sur la confiance et le risque
        decision_type, reason = self._make_decision(confidence_score, risk_level, action)
        
        # Créer la décision
        decision = Decision(
            action=action,
            decision_type=decision_type,
            confidence_score=confidence_score,
            risk_level=risk_level,
            reason=reason,
            proposed_by=user or "system",
            validation_required=decision_type != DecisionType.AUTO_APPROVE,
            auto_approved=decision_type == DecisionType.AUTO_APPROVE
        )
        
        # Enregistrer la proposition dans le store
        self._log_proposal(action, decision, user)
        
        # Notifier les handlers
        await self._notify_handlers(decision)
        
        logger.info(f"Décision: {decision_type.value}, Confiance: {confidence_score:.2f}, Risque: {risk_level.value}")
        
        return decision
    
    def _is_forbidden_action(self, action: Dict[str, Any]) -> bool:
        """
        Vérifie si une action est interdite.
        
        Args:
            action: Action à vérifier
            
        Returns:
            True si l'action est interdite
        """
        domain = action.get("domain", "")
        service = action.get("service", "")
        entity_id = action.get("entity_id", "")
        
        # Vérifier les domaines critiques
        if domain in CRITICAL_DOMAINS:
            return True
        
        # Vérifier les actions spécifiques interdites
        if domain in FORBIDDEN_ACTIONS:
            if service in FORBIDDEN_ACTIONS[domain]:
                return True
        
        # Vérifier si l'entité contient des mots clés dangereux
        dangerous_keywords = ["alarm", "lock", "door", "window", "security"]
        if any(keyword in entity_id.lower() for keyword in dangerous_keywords):
            if service in ["turn_off", "unlock", "open", "disarm"]:
                return True
        
        return False
    
    async def _calculate_confidence(
        self,
        action: Dict[str, Any],
        context: Dict[str, Any],
        user: Optional[str]
    ) -> float:
        """
        Calcule le score de confiance pour une action.
        
        Args:
            action: Action proposée
            context: Contexte actuel
            user: Utilisateur
            
        Returns:
            Score de confiance (0.0-1.0)
        """
        try:
            score = await self.confidence_scorer.calculate(action, context)
            return score.total
        except Exception as e:
            logger.error(f"Erreur lors du calcul de la confiance: {e}")
            return 0.0
    
    def _assess_risk(self, action: Dict[str, Any]) -> RiskLevel:
        """
        Évalue le niveau de risque d'une action.
        
        Args:
            action: Action à évaluer
            
        Returns:
            Niveau de risque
        """
        domain = action.get("domain", "")
        service = action.get("service", "")
        entity_id = action.get("entity_id", "")
        
        # Risque critique
        if domain in CRITICAL_DOMAINS:
            return RiskLevel.CRITICAL
        
        # Risque élevé
        if domain in HIGH_RISK_DOMAINS:
            return RiskLevel.HIGH
        
        # Actions spécifiques à risque
        if service in ["turn_off", "unlock", "open", "disarm"]:
            return RiskLevel.HIGH
        
        # Actions à risque moyen
        if service in ["set_temperature", "set_position", "turn_on"]:
            return RiskLevel.MEDIUM
        
        # Actions à faible risque
        if service in ["turn_on", "turn_off"] and domain in ["light", "switch"]:
            return RiskLevel.LOW
        
        # Par défaut
        return RiskLevel.MEDIUM
    
    def _make_decision(
        self,
        confidence: float,
        risk_level: RiskLevel,
        action: Dict[str, Any]
    ) -> tuple:
        """
        Prend une décision basée sur la confiance et le risque.
        
        Args:
            confidence: Score de confiance
            risk_level: Niveau de risque
            action: Action proposée
            
        Returns:
            Tuple (DecisionType, raison)
        """
        # Si la confiance est trop faible
        if confidence < self.min_confidence:
            return DecisionType.REJECT, f"Confiance trop faible ({confidence:.2f} < {self.min_confidence})"
        
        # Si le risque est critique ou élevé, toujours demander validation
        if risk_level in [RiskLevel.CRITICAL, RiskLevel.HIGH]:
            return DecisionType.REQUEST_VALIDATION, f"Risque {risk_level.value} - validation requise"
        
        # Si la confiance est suffisante et le risque est faible
        if confidence >= self.auto_approve_threshold and risk_level == RiskLevel.LOW:
            return DecisionType.AUTO_APPROVE, f"Confiance élevée ({confidence:.2f} >= {self.auto_approve_threshold}) et risque faible"
        
        # Si la confiance est suffisante et le risque est moyen
        if confidence >= self.auto_approve_threshold + 0.1 and risk_level == RiskLevel.MEDIUM:
            return DecisionType.AUTO_APPROVE, f"Confiance très élevée ({confidence:.2f}) pour risque moyen"
        
        # Par défaut, demander validation
        return DecisionType.REQUEST_VALIDATION, f"Confiance {confidence:.2f} - validation recommandée"
    
    def _log_proposal(self, action: Dict[str, Any], decision: Decision, user: Optional[str]) -> None:
        """
        Enregistre une proposition dans le store.
        
        Args:
            action: Action proposée
            decision: Décision prise
            user: Utilisateur
        """
        try:
            # Enregistrer dans le journal
            self.store.log(
                severity="info" if decision.auto_approved else "warning",
                kind="proposal",
                message=f"Proposition: {action.get('service', 'unknown')} sur {action.get('entity_id', 'unknown')}",
                entity_id=action.get("entity_id")
            )
            
            # Enregistrer la proposition
            proposal_id = self.store.add_proposal(
                rule="autonomy",
                entity_id=action.get("entity_id", "unknown"),
                message=decision.reason,
                action=action,
                expect_state=None
            )
            
            # Mettre à jour le statut de la proposition
            if decision.auto_approved:
                self.store.set_proposal(proposal_id, "approved", decided_by=user or "auto")
            else:
                self.store.set_proposal(proposal_id, "pending", decided_by=None)
                
        except Exception as e:
            logger.error(f"Erreur lors de l'enregistrement de la proposition: {e}")
    
    async def _notify_handlers(self, decision: Decision) -> None:
        """
        Notifie les handlers enregistrés.
        
        Args:
            decision: Décision à notifier
        """
        handlers = self._decision_handlers.get(decision.decision_type, [])
        for handler in handlers:
            try:
                await handler(decision)
            except Exception as e:
                logger.error(f"Erreur dans le handler pour {decision.decision_type}: {e}")
    
    async def approve_proposal(self, proposal_id: int, user: str) -> Dict[str, Any]:
        """
        Approuve une proposition.
        
        Args:
            proposal_id: ID de la proposition
            user: Utilisateur qui approuve
            
        Returns:
            Résultat de l'approbation
        """
        try:
            proposal = self.store.get_proposal(proposal_id)
            if not proposal:
                return {"ok": False, "error": "Proposition non trouvée"}
            
            # Mettre à jour le statut
            self.store.set_proposal(proposal_id, "approved", decided_by=user)
            
            # Enregistrer dans le journal
            self.store.log(
                severity="info",
                kind="approval",
                message=f"Proposition {proposal_id} approuvée par {user}",
                entity_id=proposal.get("entity_id")
            )
            
            return {
                "ok": True,
                "status": "approved",
                "proposal_id": proposal_id,
                "action": proposal.get("action")
            }
        except Exception as e:
            logger.error(f"Erreur lors de l'approbation: {e}")
            return {"ok": False, "error": str(e)}
    
    async def reject_proposal(self, proposal_id: int, user: str, reason: str = "") -> Dict[str, Any]:
        """
        Rejette une proposition.
        
        Args:
            proposal_id: ID de la proposition
            user: Utilisateur qui rejette
            reason: Raison du rejet
            
        Returns:
            Résultat du rejet
        """
        try:
            proposal = self.store.get_proposal(proposal_id)
            if not proposal:
                return {"ok": False, "error": "Proposition non trouvée"}
            
            # Mettre à jour le statut
            self.store.set_proposal(proposal_id, "rejected", decided_by=user, result=reason)
            
            # Enregistrer dans le journal
            self.store.log(
                severity="info",
                kind="rejection",
                message=f"Proposition {proposal_id} rejetée par {user}: {reason}",
                entity_id=proposal.get("entity_id")
            )
            
            return {
                "ok": True,
                "status": "rejected",
                "proposal_id": proposal_id
            }
        except Exception as e:
            logger.error(f"Erreur lors du rejet: {e}")
            return {"ok": False, "error": str(e)}
    
    def get_pending_proposals(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Récupère les propositions en attente de validation.
        
        Args:
            limit: Nombre maximum de propositions
            
        Returns:
            Liste des propositions en attente
        """
        try:
            proposals = self.store.proposals(status="pending", limit=limit)
            return [
                {
                    "id": p["id"],
                    "message": p["message"],
                    "entity_id": p["entity_id"],
                    "action": p["action"],
                    "created": p["created"]
                }
                for p in proposals
            ]
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des propositions: {e}")
            return []
    
    def get_decision_stats(self) -> Dict[str, Any]:
        """
        Récupère les statistiques des décisions.
        
        Returns:
            Statistiques des décisions
        """
        try:
            # Récupérer les propositions récentes
            all_proposals = self.store.proposals(limit=100)
            
            stats = {
                "total": len(all_proposals),
                "approved": 0,
                "rejected": 0,
                "pending": 0,
                "expired": 0
            }
            
            for p in all_proposals:
                status = p.get("status", "unknown")
                if status in stats:
                    stats[status] += 1
            
            return stats
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des stats: {e}")
            return {"error": str(e)}
