"""Système de confiance pour les décisions autonomes.

Ce module calcule un score de confiance (0.0-1.0) pour chaque action proposée,
permettant à Jarvis de prendre des décisions autonomes de manière intelligente et sécurisée.

Fonctionnalités :
- Calcul de confiance basé sur l'historique des actions
- Évaluation du contexte actuel
- Vérification des règles de sécurité
- Apprentissage continu des préférences utilisateur

Score de confiance :
- 0.0-0.3 : Faible confiance -> Validation manuelle requise
- 0.3-0.7 : Confiance moyenne -> Validation recommandée
- 0.7-0.9 : Bonne confiance -> Validation automatique possible
- 0.9-1.0 : Excellente confiance -> Action automatique
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set, Any

logger = logging.getLogger("JarvisConfidence")


@dataclass
class ConfidenceScore:
    """Score de confiance pour une action."""
    total: float  # Score total (0.0-1.0)
    historical: float  # Confiance basée sur l'historique (0.0-1.0)
    contextual: float  # Confiance basée sur le contexte (0.0-1.0)
    safety: float  # Confiance basée sur la sécurité (0.0-1.0)
    risk: float  # Niveau de risque (0.0-1.0, 0=pas de risque)
    reason: str  # Explication du score
    
    def __bool__(self) -> bool:
        """Retourne True si la confiance est suffisante pour une action automatique."""
        return self.total >= 0.7  # Seuil par défaut
    
    def can_auto_approve(self, threshold: float = 0.7) -> bool:
        """Vérifie si l'action peut être approuvée automatiquement."""
        return self.total >= threshold


class ConfidenceScorer:
    """Calculateur de confiance pour les actions autonomes."""
    
    # Poids pour chaque composante du score
    HISTORICAL_WEIGHT = 0.4  # 40% basé sur l'historique
    CONTEXTUAL_WEIGHT = 0.3  # 30% basé sur le contexte
    SAFETY_WEIGHT = 0.3      # 30% basé sur la sécurité
    
    # Seuil pour l'approbation automatique
    AUTO_APPROVE_THRESHOLD = 0.7
    
    def __init__(self, store: Any, ha_client: Any = None):
        """
        Initialise le calculateur de confiance.
        
        Args:
            store: Instance de Store pour accéder à l'historique
            ha_client: Client Home Assistant pour le contexte
        """
        self.store = store
        self.ha_client = ha_client
        
    async def calculate(self, action: Dict[str, Any], context: Dict[str, Any]) -> ConfidenceScore:
        """
        Calcule le score de confiance pour une action.
        
        Args:
            action: Dictionnaire décrivant l'action (domain, service, entity_id, etc.)
            context: Contexte actuel (heure, présence, météo, etc.)
            
        Returns:
            ConfidenceScore avec le score total et les détails
        """
        # 1. Confiance basée sur l'historique
        historical_score = await self._calculate_historical_confidence(action)
        
        # 2. Confiance basée sur le contexte
        contextual_score = self._calculate_contextual_confidence(action, context)
        
        # 3. Confiance basée sur la sécurité
        safety_score, risk = self._calculate_safety_confidence(action)
        
        # Calcul du score total (moyenne pondérée)
        total_score = (
            historical_score * self.HISTORICAL_WEIGHT +
            contextual_score * self.CONTEXTUAL_WEIGHT +
            safety_score * self.SAFETY_WEIGHT
        )
        
        # Générer une explication
        reason = self._generate_reason(historical_score, contextual_score, safety_score, risk)
        
        return ConfidenceScore(
            total=total_score,
            historical=historical_score,
            contextual=contextual_score,
            safety=safety_score,
            risk=risk,
            reason=reason
        )
    
    async def _calculate_historical_confidence(self, action: Dict[str, Any]) -> float:
        """
        Calcule la confiance basée sur l'historique des actions similaires.
        
        Plus une action a été exécutée avec succès dans le passé, plus la confiance est élevée.
        """
        try:
            # Récupérer les actions similaires depuis le store
            similar_actions = await self.store.get_similar_actions(
                action.get("domain", ""),
                action.get("service", ""),
                action.get("entity_id", "")
            )
            
            if not similar_actions:
                # Aucune action similaire -> confiance neutre
                return 0.5
            
            # Calculer le taux de succès
            success_count = sum(1 for a in similar_actions if a.get("result", "").startswith("OK"))
            total_count = len(similar_actions)
            success_rate = success_count / total_count
            
            # Confiance = taux de succès (0.0-1.0)
            # Mais on ne descend pas en dessous de 0.2 pour éviter de bloquer complètement
            return max(0.2, success_rate)
            
        except Exception as e:
            logger.warning("Erreur lors du calcul de la confiance historique: %s", e)
            return 0.5  # Confiance neutre en cas d'erreur
    
    def _calculate_contextual_confidence(self, action: Dict[str, Any], context: Dict[str, Any]) -> float:
        """
        Calcule la confiance basée sur le contexte actuel.
        
        Le contexte peut inclure :
        - Heure de la journée (nuit/jour)
        - Présence des utilisateurs
        - Météo
        - État du système
        """
        confidence = 0.5  # Confiance de base
        
        try:
            # 1. Heure de la journée
            now = datetime.now(timezone.utc)
            hour = now.hour
            
            # Si c'est la nuit (22h-6h) et que l'action est bruyante, réduire la confiance
            if 22 <= hour or hour < 6:
                if action.get("domain") in ["media_player", "tts"]:
                    confidence -= 0.2  # Moins de confiance pour les actions bruyantes la nuit
            
            # 2. Présence des utilisateurs
            presence = context.get("presence", {})
            if presence.get("home", False):
                # Si quelqu'un est à la maison, plus de confiance pour les actions locales
                confidence += 0.1
            else:
                # Si personne n'est à la maison, moins de confiance pour les actions qui nécessitent une présence
                if action.get("domain") in ["light", "cover", "vacuum"]:
                    confidence -= 0.1
            
            # 3. Météo (si disponible)
            weather = context.get("weather", {})
            weather_state = weather.get("state", "").lower()
            if "rain" in weather_state or "storm" in weather_state:
                # Si il pleut, plus de confiance pour fermer les fenêtres
                if action.get("domain") == "cover" and action.get("service") == "close_cover":
                    confidence += 0.2
            
            # 4. Système (si disponible)
            system = context.get("system", {})
            if system.get("load_avg", 0) > 2.0:
                # Si le système est chargé, moins de confiance pour les actions non critiques
                confidence -= 0.1
            
            # Limiter la confiance entre 0.0 et 1.0
            return max(0.0, min(1.0, confidence))
            
        except Exception as e:
            logger.warning("Erreur lors du calcul de la confiance contextuelle: %s", e)
            return 0.5
    
    def _calculate_safety_confidence(self, action: Dict[str, Any]) -> tuple:
        """
        Calcule la confiance basée sur la sécurité.
        
        Returns:
            tuple: (safety_score, risk_level)
        """
        safety_score = 0.5
        risk_level = 0.5
        
        try:
            domain = action.get("domain", "")
            service = action.get("service", "")
            
            # Domaines dangereux (jamais autorisés)
            DANGEROUS_DOMAINS = {
                "lock", "alarm_control_panel", "shell_command", 
                "python_script", "hassio", "rest_command"
            }
            
            # Services dangereux
            DANGEROUS_SERVICES = {
                "turn_on": ["alarm"],
                "unlock": ["lock"],
                "open": ["lock", "alarm"],
            }
            
            # Vérifier les domaines dangereux
            if domain in DANGEROUS_DOMAINS:
                safety_score = 0.0
                risk_level = 1.0
                return safety_score, risk_level
            
            # Vérifier les services dangereux
            if domain in DANGEROUS_SERVICES and service in DANGEROUS_SERVICES[domain]:
                safety_score = 0.0
                risk_level = 1.0
                return safety_score, risk_level
            
            # Domaines sûrs
            SAFE_DOMAINS = {"light", "cover", "vacuum", "scene", "switch", "fan", "climate"}
            if domain in SAFE_DOMAINS:
                safety_score += 0.3
                risk_level -= 0.3
            
            # Services sûrs
            SAFE_SERVICES = {"turn_on", "turn_off", "open_cover", "close_cover", "set_position"}
            if service in SAFE_SERVICES:
                safety_score += 0.2
                risk_level -= 0.2
            
            # Limiter les scores entre 0.0 et 1.0
            safety_score = max(0.0, min(1.0, safety_score))
            risk_level = max(0.0, min(1.0, risk_level))
            
            return safety_score, risk_level
            
        except Exception as e:
            logger.warning("Erreur lors du calcul de la confiance de sécurité: %s", e)
            return 0.5, 0.5
    
    def _generate_reason(self, historical: float, contextual: float, safety: float, risk: float) -> str:
        """Génère une explication du score de confiance."""
        reasons = []
        
        # Confiance historique
        if historical > 0.8:
            reasons.append("historique très positif")
        elif historical < 0.3:
            reasons.append("historique peu fiable")
        
        # Confiance contextuelle
        if contextual > 0.8:
            reasons.append("contexte favorable")
        elif contextual < 0.3:
            reasons.append("contexte défavorable")
        
        # Sécurité
        if safety > 0.8:
            reasons.append("action sûre")
        elif safety < 0.3:
            reasons.append("⚠️ action à risque")
        
        # Risque
        if risk > 0.7:
            reasons.append("⚠️ risque élevé")
        elif risk < 0.3:
            reasons.append("risque faible")
        
        # Combiner les raisons
        if reasons:
            return ", ".join(reasons)
        else:
            return "score de confiance moyen"


class ActionMemory:
    """Mémoire des actions pour l'apprentissage continu."""
    
    def __init__(self, store: Any):
        """
        Initialise la mémoire des actions.
        
        Args:
            store: Instance de Store pour la persistance
        """
        self.store = store
        
    async def log_action(self, rule: str, entity_id: str, action: Dict[str, Any], 
                       result: str, user: Optional[str] = None, context: Optional[Dict] = None) -> None:
        """
        Enregistre une action et son résultat dans la mémoire.
        
        Args:
            rule: Règle qui a déclenché l'action
            entity_id: Entité concernée
            action: Action exécutée
            result: Résultat de l'action
            user: Utilisateur qui a validé (optionnel)
            context: Contexte au moment de l'action (optionnel)
        """
        try:
            await self.store.log_action(rule, entity_id, action, result, user, context)
            logger.debug("Action enregistrée dans la mémoire: %s sur %s -> %s", 
                        action.get("service"), entity_id, result)
        except Exception as e:
            logger.error("Erreur lors de l'enregistrement de l'action: %s", e)
    
    async def get_similar_actions(self, domain: str, service: str, entity_id: str, 
                                  limit: int = 10) -> List[Dict[str, Any]]:
        """
        Récupère les actions similaires depuis la mémoire.
        
        Args:
            domain: Domaine de l'action
            service: Service de l'action
            entity_id: Entité concernée
            limit: Nombre maximum de résultats
            
        Returns:
            Liste des actions similaires
        """
        try:
            return await self.store.get_similar_actions(domain, service, entity_id, limit)
        except Exception as e:
            logger.error("Erreur lors de la récupération des actions similaires: %s", e)
            return []
    
    async def get_action_stats(self, domain: str, service: str) -> Dict[str, Any]:
        """
        Récupère les statistiques pour un type d'action.
        
        Args:
            domain: Domaine de l'action
            service: Service de l'action
            
        Returns:
            Dictionnaire avec les statistiques (count, success_rate, etc.)
        """
        try:
            actions = await self.get_similar_actions(domain, service, "", limit=100)
            if not actions:
                return {"count": 0, "success_rate": 0.5, "last_result": None}
            
            success_count = sum(1 for a in actions if a.get("result", "").startswith("OK"))
            return {
                "count": len(actions),
                "success_rate": success_count / len(actions),
                "last_result": actions[0].get("result") if actions else None
            }
        except Exception as e:
            logger.error("Erreur lors de la récupération des stats: %s", e)
            return {"count": 0, "success_rate": 0.5, "last_result": None}


class DynamicRuleEngine:
    """Moteur de règles dynamiques basé sur le contexte."""
    
    def __init__(self, store: Any, ha_client: Any = None):
        """
        Initialise le moteur de règles dynamiques.
        
        Args:
            store: Instance de Store
            ha_client: Client Home Assistant
        """
        self.store = store
        self.ha_client = ha_client
        self._rules_cache: Dict[str, Any] = {}
        
    async def evaluate_dynamic_rules(self, states: List[Dict[str, Any]], 
                                     now: datetime, params: Any) -> List[Any]:
        """
        Évalue les règles dynamiques en plus des règles statiques.
        
        Args:
            states: Liste des états des entités
            now: Date/heure actuelle
            params: Paramètres des règles
            
        Returns:
            Liste des findings (découvertes)
        """
        findings = []
        
        # 1. Règles basées sur la présence
        findings.extend(await self._evaluate_presence_rules(states, now, params))
        
        # 2. Règles basées sur l'heure
        findings.extend(await self._evaluate_time_rules(states, now, params))
        
        # 3. Règles basées sur la météo
        findings.extend(await self._evaluate_weather_rules(states, now, params))
        
        # 4. Règles basées sur le système
        findings.extend(await self._evaluate_system_rules(states, now, params))
        
        return findings
    
    async def _evaluate_presence_rules(self, states: List[Dict[str, Any]], 
                                       now: datetime, params: Any) -> List[Any]:
        """Évalue les règles basées sur la présence."""
        findings = []
        
        try:
            # Vérifier si quelqu'un est à la maison
            presence_entity = self._find_entity(states, "group.all_people", "person")
            if presence_entity:
                is_home = presence_entity.get("state") == "home"
                
                # Si personne n'est à la maison
                if not is_home:
                    # Vérifier les lumières allumées
                    for state in states:
                        if state.get("domain") == "light" and state.get("state") == "on":
                            findings.append({
                                "rule": "smart_light_off",
                                "entity_id": state.get("entity_id"),
                                "severity": "important",
                                "message": f"Lumière {state.get('entity_id')} allumée alors que personne n'est à la maison",
                                "action": {
                                    "domain": "light",
                                    "service": "turn_off",
                                    "entity_id": state.get("entity_id")
                                },
                                "expect_state": "on",
                                "confidence": 0.8
                            })
                    
                    # Vérifier les fenêtres ouvertes
                    for state in states:
                        if state.get("domain") == "cover" and state.get("state") == "open":
                            # Vérifier si c'est une fenêtre (et non un volet)
                            device_class = state.get("attributes", {}).get("device_class")
                            if device_class in ["window", "door"]:
                                findings.append({
                                    "rule": "smart_cover_close",
                                    "entity_id": state.get("entity_id"),
                                    "severity": "important",
                                    "message": f"Fenêtre {state.get('entity_id')} ouverte alors que personne n'est à la maison",
                                    "action": {
                                        "domain": "cover",
                                        "service": "close_cover",
                                        "entity_id": state.get("entity_id")
                                    },
                                    "expect_state": "open",
                                    "confidence": 0.9
                                })
        
        except Exception as e:
            logger.warning("Erreur lors de l'évaluation des règles de présence: %s", e)
        
        return findings
    
    async def _evaluate_time_rules(self, states: List[Dict[str, Any]], 
                                    now: datetime, params: Any) -> List[Any]:
        """Évalue les règles basées sur l'heure."""
        findings = []
        
        try:
            hour = now.hour
            minute = now.minute
            
            # Si c'est le soir (18h-22h) et qu'il fait nuit
            if 18 <= hour < 22:
                # Allumer les lumières extérieures
                for state in states:
                    if state.get("domain") == "light" and "exterieur" in state.get("entity_id", ""):
                        if state.get("state") == "off":
                            findings.append({
                                "rule": "smart_light_on_evening",
                                "entity_id": state.get("entity_id"),
                                "severity": "minor",
                                "message": f"Allumer {state.get('entity_id')} pour le soir",
                                "action": {
                                    "domain": "light",
                                    "service": "turn_on",
                                    "entity_id": state.get("entity_id")
                                },
                                "expect_state": "off",
                                "confidence": 0.7
                            })
            
            # Si c'est la nuit (22h-6h)
            if 22 <= hour or hour < 6:
                # Éteindre les lumières intérieures
                for state in states:
                    if state.get("domain") == "light" and "exterieur" not in state.get("entity_id", ""):
                        if state.get("state") == "on":
                            findings.append({
                                "rule": "smart_light_off_night",
                                "entity_id": state.get("entity_id"),
                                "severity": "minor",
                                "message": f"Éteindre {state.get('entity_id')} pour la nuit",
                                "action": {
                                    "domain": "light",
                                    "service": "turn_off",
                                    "entity_id": state.get("entity_id")
                                },
                                "expect_state": "on",
                                "confidence": 0.6
                            })
        
        except Exception as e:
            logger.warning("Erreur lors de l'évaluation des règles temporelles: %s", e)
        
        return findings
    
    async def _evaluate_weather_rules(self, states: List[Dict[str, Any]], 
                                      now: datetime, params: Any) -> List[Any]:
        """Évalue les règles basées sur la météo."""
        findings = []
        
        try:
            # Trouver l'entité météo
            weather_entity = self._find_entity(states, "weather.", "sensor")
            if not weather_entity:
                return findings
            
            weather_state = weather_entity.get("state", "").lower()
            
            # Si il pleut ou il y a une tempête
            if "rain" in weather_state or "storm" in weather_state:
                # Fermer les fenêtres
                for state in states:
                    if state.get("domain") == "cover" and state.get("state") == "open":
                        device_class = state.get("attributes", {}).get("device_class")
                        if device_class in ["window", None]:  # None = classe non définie
                            findings.append({
                                "rule": "weather_cover_close",
                                "entity_id": state.get("entity_id"),
                                "severity": "important",
                                "message": f"Fermer {state.get('entity_id')} à cause de la pluie",
                                "action": {
                                    "domain": "cover",
                                    "service": "close_cover",
                                    "entity_id": state.get("entity_id")
                                },
                                "expect_state": "open",
                                "confidence": 0.9
                            })
            
            # Si il fait très chaud (> 25°C)
            temp_entity = self._find_entity(states, "sensor.temperature", "sensor")
            if temp_entity:
                try:
                    temp = float(temp_entity.get("state", 0))
                    if temp > 25:
                        # Allumer la climatisation si disponible
                        for state in states:
                            if state.get("domain") == "climate" and state.get("state") == "off":
                                findings.append({
                                    "rule": "weather_climate_on",
                                    "entity_id": state.get("entity_id"),
                                    "severity": "minor",
                                    "message": f"Allumer {state.get('entity_id')} à cause de la chaleur ({temp}°C)",
                                    "action": {
                                        "domain": "climate",
                                        "service": "turn_on",
                                        "entity_id": state.get("entity_id")
                                    },
                                    "expect_state": "off",
                                    "confidence": 0.7
                                })
                except (ValueError, TypeError):
                    pass
        
        except Exception as e:
            logger.warning("Erreur lors de l'évaluation des règles météo: %s", e)
        
        return findings
    
    async def _evaluate_system_rules(self, states: List[Dict[str, Any]], 
                                     now: datetime, params: Any) -> List[Any]:
        """Évalue les règles basées sur l'état du système."""
        findings = []
        
        try:
            # Vérifier l'utilisation du CPU
            cpu_entity = self._find_entity(states, "sensor.cpu", "sensor")
            if cpu_entity:
                try:
                    cpu_usage = float(cpu_entity.get("state", 0))
                    if cpu_usage > 80:
                        findings.append({
                            "rule": "system_high_cpu",
                            "entity_id": cpu_entity.get("entity_id"),
                            "severity": "important",
                            "message": f"Utilisation CPU élevée: {cpu_usage}%",
                            "action": None,  # Pas d'action automatique, juste une alerte
                            "expect_state": None,
                            "confidence": 0.8
                        })
                except (ValueError, TypeError):
                    pass
            
            # Vérifier l'utilisation de la mémoire
            mem_entity = self._find_entity(states, "sensor.memory", "sensor")
            if mem_entity:
                try:
                    mem_usage = float(mem_entity.get("state", 0))
                    if mem_usage > 90:
                        findings.append({
                            "rule": "system_high_memory",
                            "entity_id": mem_entity.get("entity_id"),
                            "severity": "important",
                            "message": f"Utilisation mémoire élevée: {mem_usage}%",
                            "action": None,
                            "expect_state": None,
                            "confidence": 0.8
                        })
                except (ValueError, TypeError):
                    pass
        
        except Exception as e:
            logger.warning("Erreur lors de l'évaluation des règles système: %s", e)
        
        return findings
    
    def _find_entity(self, states: List[Dict[str, Any]], pattern: str, domain: str = None) -> Optional[Dict[str, Any]]:
        """Trouve une entité correspondant à un pattern."""
        for state in states:
            entity_id = state.get("entity_id", "")
            if pattern in entity_id:
                if domain is None or state.get("domain") == domain:
                    return state
        return None
