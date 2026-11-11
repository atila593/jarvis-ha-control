"""
Performance monitoring module for tracking system and application metrics.
Provides real-time monitoring, alerting, and performance analysis.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

import psutil

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of performance metrics."""
    CPU_USAGE = "cpu_usage"
    MEMORY_USAGE = "memory_usage"
    DISK_USAGE = "disk_usage"
    NETWORK_IO = "network_io"
    RESPONSE_TIME = "response_time"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"
    QUEUE_LENGTH = "queue_length"
    ACTIVE_CONNECTIONS = "active_connections"
    CACHE_HIT_RATE = "cache_hit_rate"


class AlertLevel(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class Metric:
    """Performance metric data point."""
    name: str
    value: float
    unit: str
    timestamp: float = field(default_factory=time.time)
    tags: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metric to dictionary."""
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "timestamp": self.timestamp,
            "tags": self.tags
        }


@dataclass
class Alert:
    """Performance alert."""
    name: str
    level: AlertLevel
    message: str
    timestamp: float = field(default_factory=time.time)
    metric_name: Optional[str] = None
    metric_value: Optional[float] = None
    threshold: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary."""
        return {
            "name": self.name,
            "level": self.level.value,
            "message": self.message,
            "timestamp": self.timestamp,
            "metric_name": self.metric_name,
            "metric_value": self.metric_value,
            "threshold": self.threshold
        }


@dataclass
class PerformanceSnapshot:
    """Snapshot of performance metrics at a point in time."""
    timestamp: float = field(default_factory=time.time)
    metrics: Dict[str, Metric] = field(default_factory=dict)
    alerts: List[Alert] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert snapshot to dictionary."""
        return {
            "timestamp": self.timestamp,
            "metrics": {name: metric.to_dict() for name, metric in self.metrics.items()},
            "alerts": [alert.to_dict() for alert in self.alerts]
        }


class MetricsCollector:
    """
    Collects system and application metrics.
    """
    
    def __init__(self, collection_interval: float = 1.0):
        """
        Initialize metrics collector.
        
        Args:
            collection_interval: Interval between metric collections in seconds
        """
        self.collection_interval = collection_interval
        self._metrics: Dict[str, List[Metric]] = {}
        self._callbacks: List[Callable[[Metric], None]] = []
        self._collection_task: Optional[asyncio.Task] = None
        self._running = False
    
    async def start(self) -> None:
        """Start metric collection."""
        if self._running:
            return
        
        self._running = True
        self._collection_task = asyncio.create_task(self._collect_loop())
    
    async def stop(self) -> None:
        """Stop metric collection."""
        if not self._running:
            return
        
        self._running = False
        if self._collection_task:
            self._collection_task.cancel()
            try:
                await self._collection_task
            except asyncio.CancelledError:
                pass
    
    async def _collect_loop(self) -> None:
        """Background collection loop."""
        while self._running:
            await self.collect_all()
            await asyncio.sleep(self.collection_interval)
    
    async def collect_all(self) -> Dict[str, Metric]:
        """
        Collect all available metrics.
        
        Returns:
            Dictionary of collected metrics
        """
        metrics = {}
        
        try:
            metrics["cpu_usage"] = await self.collect_cpu_usage()
            metrics["memory_usage"] = await self.collect_memory_usage()
            metrics["disk_usage"] = await self.collect_disk_usage()
            metrics["network_io"] = await self.collect_network_io()
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
        
        for name, metric in metrics.items():
            if name not in self._metrics:
                self._metrics[name] = []
            self._metrics[name].append(metric)
            
            for callback in self._callbacks:
                callback(metric)
        
        return metrics
    
    async def collect_cpu_usage(self) -> Metric:
        """Collect CPU usage metric."""
        cpu_percent = psutil.cpu_percent(interval=0.1)
        return Metric(
            name="cpu_usage",
            value=cpu_percent,
            unit="%",
            tags={"type": "system"}
        )
    
    async def collect_memory_usage(self) -> Metric:
        """Collect memory usage metric."""
        memory = psutil.virtual_memory()
        return Metric(
            name="memory_usage",
            value=memory.percent,
            unit="%",
            tags={"type": "system", "total": str(memory.total), "available": str(memory.available)}
        )
    
    async def collect_disk_usage(self) -> Metric:
        """Collect disk usage metric."""
        disk = psutil.disk_usage("/")
        return Metric(
            name="disk_usage",
            value=disk.percent,
            unit="%",
            tags={"type": "system", "path": "/", "total": str(disk.total), "free": str(disk.free)}
        )
    
    async def collect_network_io(self) -> Metric:
        """Collect network I/O metric."""
        net_io = psutil.net_io_counters()
        total_bytes = net_io.bytes_sent + net_io.bytes_recv
        return Metric(
            name="network_io",
            value=total_bytes,
            unit="bytes",
            tags={"type": "system", "sent": str(net_io.bytes_sent), "recv": str(net_io.bytes_recv)}
        )
    
    def record_custom_metric(
        self,
        name: str,
        value: float,
        unit: str = "",
        tags: Optional[Dict[str, str]] = None
    ) -> Metric:
        """
        Record a custom metric.
        
        Args:
            name: Metric name
            value: Metric value
            unit: Metric unit
            tags: Optional tags
            
        Returns:
            Created metric
        """
        metric = Metric(name=name, value=value, unit=unit, tags=tags or {})
        
        if name not in self._metrics:
            self._metrics[name] = []
        self._metrics[name].append(metric)
        
        for callback in self._callbacks:
            callback(metric)
        
        return metric
    
    def get_metrics(self, name: str, count: int = 100) -> List[Metric]:
        """
        Get historical metrics for a specific metric name.
        
        Args:
            name: Metric name
            count: Number of recent metrics to return
            
        Returns:
            List of metrics
        """
        if name not in self._metrics:
            return []
        
        return self._metrics[name][-count:]
    
    def get_all_metrics(self) -> Dict[str, List[Metric]]:
        """Get all collected metrics."""
        return self._metrics.copy()
    
    def add_callback(self, callback: Callable[[Metric], None]) -> None:
        """
        Add a callback for new metrics.
        
        Args:
            callback: Function to call with new metrics
        """
        self._callbacks.append(callback)
    
    def remove_callback(self, callback: Callable[[Metric], None]) -> None:
        """
        Remove a callback.
        
        Args:
            callback: Callback to remove
        """
        if callback in self._callbacks:
            self._callbacks.remove(callback)


class PerformanceMonitor:
    """
    Monitors performance metrics and generates alerts.
    """
    
    def __init__(self):
        """Initialize performance monitor."""
        self._collector = MetricsCollector()
        self._alert_rules: Dict[str, Dict[str, Any]] = {}
        self._alerts: List[Alert] = []
        self._alert_callbacks: List[Callable[[Alert], None]] = []
        self._snapshots: List[PerformanceSnapshot] = []
        self._max_snapshots = 1000
    
    async def start(self) -> None:
        """Start monitoring."""
        await self._collector.start()
    
    async def stop(self) -> None:
        """Stop monitoring."""
        await self._collector.stop()
    
    def add_alert_rule(
        self,
        name: str,
        metric_name: str,
        threshold: float,
        level: AlertLevel = AlertLevel.WARNING,
        comparison: str = ">",
        duration: float = 0.0
    ) -> None:
        """
        Add an alert rule.
        
        Args:
            name: Rule name
            metric_name: Metric to monitor
            threshold: Threshold value
            level: Alert level
            comparison: Comparison operator (>, <, >=, <=, ==)
            duration: Duration threshold must be exceeded (in seconds)
        """
        self._alert_rules[name] = {
            "metric_name": metric_name,
            "threshold": threshold,
            "level": level,
            "comparison": comparison,
            "duration": duration,
            "triggered_at": None,
            "triggered_value": None
        }
    
    def remove_alert_rule(self, name: str) -> None:
        """Remove an alert rule."""
        if name in self._alert_rules:
            del self._alert_rules[name]
    
    async def check_alerts(self) -> List[Alert]:
        """
        Check all alert rules against current metrics.
        
        Returns:
            List of triggered alerts
        """
        alerts = []
        current_time = time.time()
        
        metrics = await self._collector.collect_all()
        
        for rule_name, rule in self._alert_rules.items():
            metric_name = rule["metric_name"]
            
            if metric_name not in metrics:
                continue
            
            metric = metrics[metric_name]
            threshold = rule["threshold"]
            comparison = rule["comparison"]
            
            triggered = False
            
            if comparison == ">" and metric.value > threshold:
                triggered = True
            elif comparison == "<" and metric.value < threshold:
                triggered = True
            elif comparison == ">=" and metric.value >= threshold:
                triggered = True
            elif comparison == "<=" and metric.value <= threshold:
                triggered = True
            elif comparison == "==" and metric.value == threshold:
                triggered = True
            
            if triggered:
                if rule["duration"] > 0:
                    if rule["triggered_at"] is None:
                        rule["triggered_at"] = current_time
                        rule["triggered_value"] = metric.value
                    elif current_time - rule["triggered_at"] >= rule["duration"]:
                        alert = Alert(
                            name=rule_name,
                            level=rule["level"],
                            message=f"{metric_name} {comparison} {threshold} for {rule['duration']}s",
                            metric_name=metric_name,
                            metric_value=metric.value,
                            threshold=threshold
                        )
                        alerts.append(alert)
                        self._alerts.append(alert)
                        rule["triggered_at"] = None
                        rule["triggered_value"] = None
                else:
                    alert = Alert(
                        name=rule_name,
                        level=rule["level"],
                        message=f"{metric_name} {comparison} {threshold}",
                        metric_name=metric_name,
                        metric_value=metric.value,
                        threshold=threshold
                    )
                    alerts.append(alert)
                    self._alerts.append(alert)
            else:
                rule["triggered_at"] = None
                rule["triggered_value"] = None
        
        for callback in self._alert_callbacks:
            for alert in alerts:
                callback(alert)
        
        return alerts
    
    async def take_snapshot(self) -> PerformanceSnapshot:
        """
        Take a performance snapshot.
        
        Returns:
            Performance snapshot
        """
        metrics = await self._collector.collect_all()
        alerts = await self.check_alerts()
        
        snapshot = PerformanceSnapshot(
            timestamp=time.time(),
            metrics=metrics,
            alerts=alerts
        )
        
        self._snapshots.append(snapshot)
        
        if len(self._snapshots) > self._max_snapshots:
            self._snapshots = self._snapshots[-self._max_snapshots:]
        
        return snapshot
    
    def get_snapshots(self, count: int = 100) -> List[PerformanceSnapshot]:
        """
        Get recent snapshots.
        
        Args:
            count: Number of recent snapshots to return
            
        Returns:
            List of snapshots
        """
        return self._snapshots[-count:]
    
    def get_alerts(self, count: int = 100) -> List[Alert]:
        """
        Get recent alerts.
        
        Args:
            count: Number of recent alerts to return
            
        Returns:
            List of alerts
        """
        return self._alerts[-count:]
    
    def get_metrics_collector(self) -> MetricsCollector:
        """Get the metrics collector."""
        return self._collector
    
    def add_alert_callback(self, callback: Callable[[Alert], None]) -> None:
        """
        Add a callback for alerts.
        
        Args:
            callback: Function to call with new alerts
        """
        self._alert_callbacks.append(callback)
    
    def remove_alert_callback(self, callback: Callable[[Alert], None]) -> None:
        """
        Remove an alert callback.
        
        Args:
            callback: Callback to remove
        """
        if callback in self._alert_callbacks:
            self._alert_callbacks.remove(callback)
    
    async def get_performance_report(
        self,
        duration: float = 3600.0
    ) -> Dict[str, Any]:
        """
        Generate a performance report for the specified duration.
        
        Args:
            duration: Time period in seconds
            
        Returns:
            Performance report dictionary
        """
        current_time = time.time()
        start_time = current_time - duration
        
        report: Dict[str, Any] = {
            "timestamp": current_time,
            "duration": duration,
            "metrics": {},
            "alerts": [],
            "summary": {}
        }
        
        for metric_name, metrics in self._collector.get_all_metrics().items():
            recent_metrics = [m for m in metrics if m.timestamp >= start_time]
            
            if recent_metrics:
                values = [m.value for m in recent_metrics]
                report["metrics"][metric_name] = {
                    "count": len(recent_metrics),
                    "min": min(values),
                    "max": max(values),
                    "avg": sum(values) / len(values),
                    "latest": recent_metrics[-1].value,
                    "unit": recent_metrics[-1].unit
                }
        
        recent_alerts = [a for a in self._alerts if a.timestamp >= start_time]
        report["alerts"] = [a.to_dict() for a in recent_alerts]
        report["summary"]["alert_count"] = len(recent_alerts)
        report["summary"]["metric_count"] = len(report["metrics"])
        
        return report
