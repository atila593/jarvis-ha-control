"""Agent Monitoring - Surveillance du système et des performances.

Cet agent est responsable de :
- Surveiller l'état du système (CPU, mémoire, disque)
- Surveiller les performances des agents
- Détecter les anomalies et les problèmes
- Générer des alertes et des rapports
- Optimiser les ressources
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Awaitable

logger = logging.getLogger("MonitoringAgent")


class MonitorStatus(Enum):
    """Statuts du monitoring."""
    NORMAL = "normal"  # Tout va bien
    WARNING = "warning"  # Avertissement
    CRITICAL = "critical"  # Critique
    UNKNOWN = "unknown"  # Inconnu


class MetricType(Enum):
    """Types de métriques."""
    CPU = "cpu"  # Utilisation CPU
    MEMORY = "memory"  # Utilisation mémoire
    DISK = "disk"  # Utilisation disque
    NETWORK = "network"  # Trafic réseau
    TEMPERATURE = "temperature"  # Température
    RESPONSE_TIME = "response_time"  # Temps de réponse
    QUEUE_LENGTH = "queue_length"  # Longueur de la file
    ERROR_RATE = "error_rate"  # Taux d'erreurs
    UPTIME = "uptime"  # Temps de fonctionnement


@dataclass
class Metric:
    """Représente une métrique."""
    name: str
    type: MetricType
    value: float
    unit: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    threshold_warning: Optional[float] = None
    threshold_critical: Optional[float] = None
    
    def get_status(self) -> MonitorStatus:
        """Détermine le statut basé sur les seuils."""
        if self.threshold_critical is not None and self.value >= self.threshold_critical:
            return MonitorStatus.CRITICAL
        if self.threshold_warning is not None and self.value >= self.threshold_warning:
            return MonitorStatus.WARNING
        return MonitorStatus.NORMAL
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit la métrique en dictionnaire."""
        return {
            "name": self.name,
            "type": self.type.value,
            "value": self.value,
            "unit": self.unit,
            "timestamp": self.timestamp.isoformat(),
            "status": self.get_status().value,
            "threshold_warning": self.threshold_warning,
            "threshold_critical": self.threshold_critical
        }


@dataclass
class Alert:
    """Représente une alerte."""
    alert_id: str
    metric_name: str
    metric_type: MetricType
    current_value: float
    threshold: float
    status: MonitorStatus
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged: bool = False
    resolved: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit l'alerte en dictionnaire."""
        return {
            "alert_id": self.alert_id,
            "metric_name": self.metric_name,
            "metric_type": self.metric_type.value,
            "current_value": self.current_value,
            "threshold": self.threshold,
            "status": self.status.value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "acknowledged": self.acknowledged,
            "resolved": self.resolved
        }


@dataclass
class SystemReport:
    """Rapport du système."""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: MonitorStatus = MonitorStatus.NORMAL
    metrics: List[Metric] = field(default_factory=list)
    alerts: List[Alert] = field(default_factory=list)
    uptime: float = 0.0
    recommendations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit le rapport en dictionnaire."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "status": self.status.value,
            "metrics": [m.to_dict() for m in self.metrics],
            "alerts": [a.to_dict() for a in self.alerts],
            "uptime": self.uptime,
            "recommendations": self.recommendations
        }


class MonitoringAgent:
    """Agent de monitoring pour Jarvis HA Control.
    
    Cet agent surveille :
    - L'état du système (CPU, mémoire, disque)
    - Les performances des agents
    - Les métriques Home Assistant
    - Les anomalies et problèmes
    """
    
    # Seuils par défaut
    DEFAULT_THRESHOLDS = {
        MetricType.CPU: {"warning": 70.0, "critical": 90.0},
        MetricType.MEMORY: {"warning": 75.0, "critical": 90.0},
        MetricType.DISK: {"warning": 80.0, "critical": 95.0},
        MetricType.RESPONSE_TIME: {"warning": 1.0, "critical": 5.0},
        MetricType.QUEUE_LENGTH: {"warning": 10, "critical": 20},
        MetricType.ERROR_RATE: {"warning": 0.05, "critical": 0.1},
    }
    
    # Intervalle de monitoring (secondes)
    DEFAULT_INTERVAL = 60
    
    def __init__(
        self,
        ha_client: Any,
        store: Any,
        orchestrator: Any = None,
        interval: int = DEFAULT_INTERVAL,
        thresholds: Optional[Dict[MetricType, Dict[str, float]]] = None
    ):
        """
        Initialise l'agent de monitoring.
        
        Args:
            ha_client: Client Home Assistant
            store: Instance de Store pour la persistance
            orchestrator: Instance de Orchestrator pour surveiller les agents
            interval: Intervalle de monitoring (secondes)
            thresholds: Seuils personnalisés
        """
        self.ha_client = ha_client
        self.store = store
        self.orchestrator = orchestrator
        self.interval = interval
        self.thresholds = thresholds or self.DEFAULT_THRESHOLDS
        
        # Historique des métriques
        self._metrics_history: Dict[str, List[Metric]] = {}
        
        # Alertes actives
        self._active_alerts: Dict[str, Alert] = {}
        
        # Temps de démarrage
        self._start_time = datetime.now(timezone.utc)
        
        # État du monitoring
        self._running = False
        self._monitoring_task: Optional[asyncio.Task] = None
        
        # Callbacks pour les alertes
        self._alert_handlers: List[Callable[[Alert], Awaitable[Any]]] = []
        
        logger.info("MonitoringAgent initialisé")
    
    def register_alert_handler(self, handler: Callable[[Alert], Awaitable[Any]]) -> None:
        """Enregistre un handler pour les alertes."""
        self._alert_handlers.append(handler)
        logger.debug("Handler d'alerte enregistré")
    
    async def start(self) -> None:
        """Démarre le monitoring."""
        if self._running:
            logger.warning("Monitoring déjà en cours")
            return
        
        self._running = True
        self._monitoring_task = asyncio.create_task(self._monitor_loop())
        logger.info("Monitoring démarré")
    
    async def stop(self) -> None:
        """Arrête le monitoring."""
        if not self._running:
            logger.warning("Monitoring non démarré")
            return
        
        self._running = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("Monitoring arrêté")
    
    async def _monitor_loop(self) -> None:
        """Boucle de monitoring."""
        while self._running:
            try:
                await self._collect_metrics()
                await self._check_alerts()
                await self._generate_report()
            except Exception as e:
                logger.error(f"Erreur dans la boucle de monitoring: {e}")
            
            await asyncio.sleep(self.interval)
    
    async def _collect_metrics(self) -> None:
        """Collecte les métriques."""
        logger.debug("Collecte des métriques...")
        
        # Collecter les métriques système
        system_metrics = await self._collect_system_metrics()
        
        # Collecter les métriques Home Assistant
        ha_metrics = await self._collect_ha_metrics()
        
        # Collecter les métriques des agents
        agent_metrics = await self._collect_agent_metrics()
        
        # Stocker les métriques
        all_metrics = system_metrics + ha_metrics + agent_metrics
        for metric in all_metrics:
            self._store_metric(metric)
    
    async def _collect_system_metrics(self) -> List[Metric]:
        """Collecte les métriques système."""
        metrics = []
        
        try:
            # Utilisation CPU (simulée ou réelle)
            cpu_usage = await self._get_cpu_usage()
            if cpu_usage is not None:
                metrics.append(Metric(
                    name="system.cpu.usage",
                    type=MetricType.CPU,
                    value=cpu_usage,
                    unit="%",
                    threshold_warning=self.thresholds[MetricType.CPU]["warning"],
                    threshold_critical=self.thresholds[MetricType.CPU]["critical"]
                ))
            
            # Utilisation mémoire (simulée ou réelle)
            memory_usage = await self._get_memory_usage()
            if memory_usage is not None:
                metrics.append(Metric(
                    name="system.memory.usage",
                    type=MetricType.MEMORY,
                    value=memory_usage,
                    unit="%",
                    threshold_warning=self.thresholds[MetricType.MEMORY]["warning"],
                    threshold_critical=self.thresholds[MetricType.MEMORY]["critical"]
                ))
            
            # Utilisation disque (simulée ou réelle)
            disk_usage = await self._get_disk_usage()
            if disk_usage is not None:
                metrics.append(Metric(
                    name="system.disk.usage",
                    type=MetricType.DISK,
                    value=disk_usage,
                    unit="%",
                    threshold_warning=self.thresholds[MetricType.DISK]["warning"],
                    threshold_critical=self.thresholds[MetricType.DISK]["critical"]
                ))
            
            # Uptime
            uptime = (datetime.now(timezone.utc) - self._start_time).total_seconds()
            metrics.append(Metric(
                name="system.uptime",
                type=MetricType.UPTIME,
                value=uptime,
                unit="s"
            ))
            
        except Exception as e:
            logger.error(f"Erreur lors de la collecte des métriques système: {e}")
        
        return metrics
    
    async def _collect_ha_metrics(self) -> List[Metric]:
        """Collecte les métriques Home Assistant."""
        metrics = []
        
        try:
            if not self.ha_client:
                return metrics
            
            # Récupérer les états des entités système
            states = await self.ha_client.get_states()
            
            for state in states:
                entity_id = state.get("entity_id", "")
                domain = entity_id.split(".")[0] if "." in entity_id else ""
                
                # Métriques CPU
                if domain == "sensor" and "cpu" in entity_id.lower():
                    try:
                        value = float(state.get("state", 0))
                        metrics.append(Metric(
                            name=f"ha.{entity_id}",
                            type=MetricType.CPU,
                            value=value,
                            unit="%",
                            threshold_warning=self.thresholds[MetricType.CPU]["warning"],
                            threshold_critical=self.thresholds[MetricType.CPU]["critical"]
                        ))
                    except (ValueError, TypeError):
                        pass
                
                # Métriques mémoire
                if domain == "sensor" and "memory" in entity_id.lower():
                    try:
                        value = float(state.get("state", 0))
                        metrics.append(Metric(
                            name=f"ha.{entity_id}",
                            type=MetricType.MEMORY,
                            value=value,
                            unit="%",
                            threshold_warning=self.thresholds[MetricType.MEMORY]["warning"],
                            threshold_critical=self.thresholds[MetricType.MEMORY]["critical"]
                        ))
                    except (ValueError, TypeError):
                        pass
                
                # Métriques disque
                if domain == "sensor" and "disk" in entity_id.lower():
                    try:
                        value = float(state.get("state", 0))
                        metrics.append(Metric(
                            name=f"ha.{entity_id}",
                            type=MetricType.DISK,
                            value=value,
                            unit="%",
                            threshold_warning=self.thresholds[MetricType.DISK]["warning"],
                            threshold_critical=self.thresholds[MetricType.DISK]["critical"]
                        ))
                    except (ValueError, TypeError):
                        pass
                
                # Métriques température
                if domain == "sensor" and "temperature" in entity_id.lower():
                    try:
                        value = float(state.get("state", 0))
                        metrics.append(Metric(
                            name=f"ha.{entity_id}",
                            type=MetricType.TEMPERATURE,
                            value=value,
                            unit="°C"
                        ))
                    except (ValueError, TypeError):
                        pass
            
        except Exception as e:
            logger.error(f"Erreur lors de la collecte des métriques HA: {e}")
        
        return metrics
    
    async def _collect_agent_metrics(self) -> List[Metric]:
        """Collecte les métriques des agents."""
        metrics = []
        
        try:
            if self.orchestrator:
                # Récupérer l'état du système
                system_state = self.orchestrator.get_system_state()
                
                # Métrique : nombre de workflows
                workflow_count = system_state.get("workflow_count", 0)
                metrics.append(Metric(
                    name="agents.workflow_count",
                    type=MetricType.QUEUE_LENGTH,
                    value=float(workflow_count),
                    unit="workflows",
                    threshold_warning=self.thresholds[MetricType.QUEUE_LENGTH]["warning"],
                    threshold_critical=self.thresholds[MetricType.QUEUE_LENGTH]["critical"]
                ))
                
                # Métrique : état du système
                state_value = 0
                if system_state.get("state") == "busy":
                    state_value = 50
                elif system_state.get("state") == "overloaded":
                    state_value = 100
                metrics.append(Metric(
                    name="agents.system_load",
                    type=MetricType.CPU,
                    value=float(state_value),
                    unit="%",
                    threshold_warning=70.0,
                    threshold_critical=90.0
                ))
            
        except Exception as e:
            logger.error(f"Erreur lors de la collecte des métriques agents: {e}")
        
        return metrics
    
    async def _get_cpu_usage(self) -> Optional[float]:
        """Récupère l'utilisation CPU."""
        # Implémentation par défaut (à personnaliser selon le système)
        try:
            # Essayer de récupérer depuis le système
            import psutil
            return psutil.cpu_percent(interval=1)
        except ImportError:
            # Retourner une valeur par défaut
            return None
        except Exception:
            return None
    
    async def _get_memory_usage(self) -> Optional[float]:
        """Récupère l'utilisation mémoire."""
        try:
            import psutil
            return psutil.virtual_memory().percent
        except ImportError:
            return None
        except Exception:
            return None
    
    async def _get_disk_usage(self) -> Optional[float]:
        """Récupère l'utilisation disque."""
        try:
            import psutil
            return psutil.disk_usage('/').percent
        except ImportError:
            return None
        except Exception:
            return None
    
    def _store_metric(self, metric: Metric) -> None:
        """Stocke une métrique."""
        try:
            # Stocker dans l'historique
            if metric.name not in self._metrics_history:
                self._metrics_history[metric.name] = []
            
            self._metrics_history[metric.name].append(metric)
            
            # Limiter l'historique
            if len(self._metrics_history[metric.name]) > 100:
                self._metrics_history[metric.name] = self._metrics_history[metric.name][-100:]
            
            # Stocker dans le journal
            self.store.log(
                severity="info",
                kind="metric",
                message=f"{metric.name}: {metric.value}{metric.unit}",
                entity_id=metric.name
            )
            
        except Exception as e:
            logger.error(f"Erreur lors du stockage de la métrique: {e}")
    
    async def _check_alerts(self) -> None:
        """Vérifie les alertes."""
        logger.debug("Vérification des alertes...")
        
        try:
            # Récupérer toutes les métriques
            all_metrics = []
            for metrics in self._metrics_history.values():
                if metrics:
                    all_metrics.append(metrics[-1])  # Prendre la dernière
            
            # Vérifier chaque métrique
            for metric in all_metrics:
                status = metric.get_status()
                
                if status == MonitorStatus.CRITICAL:
                    await self._create_alert(metric, status)
                elif status == MonitorStatus.WARNING:
                    # Vérifier si une alerte critique existe déjà
                    if not any(
                        a.metric_name == metric.name and a.status == MonitorStatus.CRITICAL
                        for a in self._active_alerts.values()
                    ):
                        await self._create_alert(metric, status)
                else:
                    # Résoudre les alertes si la métrique est revenue à la normale
                    await self._resolve_alert(metric)
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification des alertes: {e}")
    
    async def _create_alert(self, metric: Metric, status: MonitorStatus) -> None:
        """Crée une alerte."""
        alert_id = f"alert_{metric.name}_{int(time.time())}"
        
        threshold = metric.threshold_warning if status == MonitorStatus.WARNING else metric.threshold_critical
        
        alert = Alert(
            alert_id=alert_id,
            metric_name=metric.name,
            metric_type=metric.type,
            current_value=metric.value,
            threshold=threshold or 0,
            status=status,
            message=f"{metric.name} a atteint {metric.value}{metric.unit} (seuil: {threshold}{metric.unit})"
        )
        
        self._active_alerts[alert_id] = alert
        
        # Enregistrer dans le store
        self.store.log(
            severity="warning" if status == MonitorStatus.WARNING else "error",
            kind="alert",
            message=alert.message,
            entity_id=metric.name
        )
        
        # Notifier les handlers
        for handler in self._alert_handlers:
            try:
                await handler(alert)
            except Exception as e:
                logger.error(f"Erreur dans le handler d'alerte: {e}")
        
        logger.warning(f"Alerte créée: {alert.message}")
    
    async def _resolve_alert(self, metric: Metric) -> None:
        """Résout une alerte."""
        for alert_id, alert in list(self._active_alerts.items()):
            if alert.metric_name == metric.name:
                alert.resolved = True
                alert.acknowledged = True
                
                # Enregistrer dans le store
                self.store.log(
                    severity="info",
                    kind="alert_resolved",
                    message=f"Alerte résolue: {alert.message}",
                    entity_id=metric.name
                )
                
                logger.info(f"Alerte résolue: {alert.message}")
    
    async def _generate_report(self) -> None:
        """Génère un rapport du système."""
        try:
            # Récupérer toutes les métriques
            all_metrics = []
            for metrics in self._metrics_history.values():
                if metrics:
                    all_metrics.append(metrics[-1])
            
            # Récupérer les alertes actives
            active_alerts = list(self._active_alerts.values())
            
            # Déterminer le statut global
            status = MonitorStatus.NORMAL
            if any(a.status == MonitorStatus.CRITICAL for a in active_alerts):
                status = MonitorStatus.CRITICAL
            elif any(a.status == MonitorStatus.WARNING for a in active_alerts):
                status = MonitorStatus.WARNING
            
            # Calculer l'uptime
            uptime = (datetime.now(timezone.utc) - self._start_time).total_seconds()
            
            # Générer des recommandations
            recommendations = self._generate_recommendations(all_metrics, active_alerts)
            
            # Créer le rapport
            report = SystemReport(
                status=status,
                metrics=all_metrics,
                alerts=active_alerts,
                uptime=uptime,
                recommendations=recommendations
            )
            
            # Stocker le rapport
            self._store_report(report)
            
            logger.debug(f"Rapport généré: {status.value}")
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération du rapport: {e}")
    
    def _generate_recommendations(self, metrics: List[Metric], alerts: List[Alert]) -> List[str]:
        """Génère des recommandations."""
        recommendations = []
        
        # Recommandations basées sur les alertes
        for alert in alerts:
            if alert.status == MonitorStatus.CRITICAL:
                recommendations.append(f"⚠️ URGENT: {alert.message}. Action requise immédiatement!")
            elif alert.status == MonitorStatus.WARNING:
                recommendations.append(f"⚠️ Avertissement: {alert.message}. Surveillance recommandée.")
        
        # Recommandations basées sur les métriques
        for metric in metrics:
            if metric.type == MetricType.CPU and metric.value > 80:
                recommendations.append("💡 Considérer l'ajout de ressources CPU ou l'optimisation des processus.")
            if metric.type == MetricType.MEMORY and metric.value > 85:
                recommendations.append("💡 Considérer l'ajout de mémoire ou l'optimisation de l'utilisation mémoire.")
            if metric.type == MetricType.DISK and metric.value > 90:
                recommendations.append("💡 Espace disque insuffisant. Nettoyer les fichiers inutiles ou ajouter de l'espace.")
        
        return recommendations
    
    def _store_report(self, report: SystemReport) -> None:
        """Stocke un rapport."""
        try:
            # Stocker dans le journal
            self.store.log(
                severity=report.status.value,
                kind="system_report",
                message=f"Rapport système: {report.status.value}",
                entity_id="system"
            )
            
            # Stocker les métriques du rapport
            for metric in report.metrics:
                self._store_metric(metric)
            
        except Exception as e:
            logger.error(f"Erreur lors du stockage du rapport: {e}")
    
    def get_metrics(self, metric_type: Optional[MetricType] = None) -> List[Metric]:
        """
        Récupère les métriques.
        
        Args:
            metric_type: Type de métrique (optionnel)
            
        Returns:
            Liste des métriques
        """
        metrics = []
        for m_list in self._metrics_history.values():
            if m_list:
                latest = m_list[-1]
                if metric_type is None or latest.type == metric_type:
                    metrics.append(latest)
        return metrics
    
    def get_alerts(self, status: Optional[MonitorStatus] = None) -> List[Alert]:
        """
        Récupère les alertes.
        
        Args:
            status: Statut de l'alerte (optionnel)
            
        Returns:
            Liste des alertes
        """
        if status is None:
            return list(self._active_alerts.values())
        return [a for a in self._active_alerts.values() if a.status == status]
    
    def get_active_alerts(self) -> List[Alert]:
        """Récupère les alertes actives."""
        return [a for a in self._active_alerts.values() if not a.resolved]
    
    async def acknowledge_alert(self, alert_id: str) -> Dict[str, Any]:
        """
        Acquitte une alerte.
        
        Args:
            alert_id: ID de l'alerte
            
        Returns:
            Résultat de l'acquittement
        """
        alert = self._active_alerts.get(alert_id)
        if not alert:
            return {"ok": False, "error": "Alerte non trouvée"}
        
        alert.acknowledged = True
        
        # Enregistrer dans le store
        self.store.log(
            severity="info",
            kind="alert_acknowledged",
            message=f"Alerte acquittée: {alert.message}",
            entity_id=alert.metric_name
        )
        
        return {"ok": True, "alert_id": alert_id, "acknowledged": True}
    
    async def get_system_report(self) -> SystemReport:
        """
        Génère et retourne un rapport du système.
        
        Returns:
            Rapport du système
        """
        # Récupérer toutes les métriques
        all_metrics = self.get_metrics()
        
        # Récupérer les alertes actives
        active_alerts = self.get_active_alerts()
        
        # Déterminer le statut global
        status = MonitorStatus.NORMAL
        if any(a.status == MonitorStatus.CRITICAL for a in active_alerts):
            status = MonitorStatus.CRITICAL
        elif any(a.status == MonitorStatus.WARNING for a in active_alerts):
            status = MonitorStatus.WARNING
        
        # Calculer l'uptime
        uptime = (datetime.now(timezone.utc) - self._start_time).total_seconds()
        
        # Générer des recommandations
        recommendations = self._generate_recommendations(all_metrics, active_alerts)
        
        return SystemReport(
            status=status,
            metrics=all_metrics,
            alerts=active_alerts,
            uptime=uptime,
            recommendations=recommendations
        )
    
    def get_health_status(self) -> Dict[str, Any]:
        """
        Récupère l'état de santé du système.
        
        Returns:
            État de santé
        """
        report = asyncio.run(self.get_system_report())
        
        return {
            "status": report.status.value,
            "uptime": report.uptime,
            "metrics_count": len(report.metrics),
            "alerts_count": len(report.alerts),
            "critical_alerts": len([a for a in report.alerts if a.status == MonitorStatus.CRITICAL]),
            "warning_alerts": len([a for a in report.alerts if a.status == MonitorStatus.WARNING]),
            "recommendations": report.recommendations
        }
