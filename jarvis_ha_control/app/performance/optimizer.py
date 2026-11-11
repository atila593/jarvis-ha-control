"""
Performance optimizer module for automatic optimization of system parameters.
Uses machine learning and heuristics to optimize performance.
"""

from __future__ import annotations

import asyncio
import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class OptimizationStrategy(Enum):
    """Optimization strategies."""
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"


class OptimizationTarget(Enum):
    """Optimization targets."""
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    RESOURCE_USAGE = "resource_usage"
    BALANCED = "balanced"


@dataclass
class OptimizationConfig:
    """Configuration for performance optimization."""
    strategy: OptimizationStrategy = OptimizationStrategy.BALANCED
    target: OptimizationTarget = OptimizationTarget.BALANCED
    min_batch_size: int = 1
    max_batch_size: int = 50
    min_concurrency: int = 1
    max_concurrency: int = 20
    cache_ttl_min: float = 1.0
    cache_ttl_max: float = 3600.0
    polling_interval_min: float = 1.0
    polling_interval_max: float = 60.0


@dataclass
class OptimizationResult:
    """Result of an optimization operation."""
    parameter: str
    old_value: Any
    new_value: Any
    improvement_score: float
    confidence: float
    reason: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "parameter": self.parameter,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "improvement_score": self.improvement_score,
            "confidence": self.confidence,
            "reason": self.reason
        }


@dataclass
class PerformanceMetrics:
    """Performance metrics for optimization decisions."""
    latency: float = 0.0
    throughput: float = 0.0
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    error_rate: float = 0.0
    cache_hit_rate: float = 0.0
    queue_length: int = 0
    active_connections: int = 0
    
    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            "latency": self.latency,
            "throughput": self.throughput,
            "cpu_usage": self.cpu_usage,
            "memory_usage": self.memory_usage,
            "error_rate": self.error_rate,
            "cache_hit_rate": self.cache_hit_rate,
            "queue_length": self.queue_length,
            "active_connections": self.active_connections
        }


class PerformanceOptimizer:
    """
    Automatic performance optimizer.
    
    Uses heuristics and adaptive algorithms to optimize system performance
    based on current workload and resource usage.
    """
    
    def __init__(self, config: Optional[OptimizationConfig] = None):
        """
        Initialize performance optimizer.
        
        Args:
            config: Optimization configuration
        """
        self.config = config or OptimizationConfig()
        self._metrics_history: List[Tuple[float, PerformanceMetrics]] = []
        self._optimization_history: List[OptimizationResult] = []
        self._max_history = 100
        self._lock = asyncio.Lock()
    
    async def record_metrics(self, metrics: PerformanceMetrics) -> None:
        """
        Record performance metrics for analysis.
        
        Args:
            metrics: Current performance metrics
        """
        async with self._lock:
            timestamp = asyncio.get_event_loop().time()
            self._metrics_history.append((timestamp, metrics))
            
            if len(self._metrics_history) > self._max_history:
                self._metrics_history = self._metrics_history[-self._max_history:]
    
    async def optimize_batch_size(
        self,
        current_batch_size: int,
        current_latency: float,
        current_throughput: float
    ) -> OptimizationResult:
        """
        Optimize batch size based on current performance.
        
        Args:
            current_batch_size: Current batch size
            current_latency: Current average latency
            current_throughput: Current throughput
            
        Returns:
            Optimization result
        """
        target_latency = 0.1
        
        if current_latency > target_latency * 2:
            new_size = max(self.config.min_batch_size, current_batch_size - 5)
            improvement = (current_latency - target_latency) / current_latency
            return OptimizationResult(
                parameter="batch_size",
                old_value=current_batch_size,
                new_value=new_size,
                improvement_score=improvement,
                confidence=0.8,
                reason=f"High latency ({current_latency:.3f}s), reducing batch size"
            )
        elif current_latency < target_latency and current_batch_size < self.config.max_batch_size:
            new_size = min(self.config.max_batch_size, current_batch_size + 5)
            improvement = 0.1
            return OptimizationResult(
                parameter="batch_size",
                old_value=current_batch_size,
                new_value=new_size,
                improvement_score=improvement,
                confidence=0.7,
                reason=f"Low latency ({current_latency:.3f}s), increasing batch size"
            )
        
        return OptimizationResult(
            parameter="batch_size",
            old_value=current_batch_size,
            new_value=current_batch_size,
            improvement_score=0.0,
            confidence=1.0,
            reason="Batch size is optimal"
        )
    
    async def optimize_concurrency(
        self,
        current_concurrency: int,
        cpu_usage: float,
        memory_usage: float,
        queue_length: int
    ) -> OptimizationResult:
        """
        Optimize concurrency level based on resource usage.
        
        Args:
            current_concurrency: Current concurrency level
            cpu_usage: Current CPU usage percentage
            memory_usage: Current memory usage percentage
            queue_length: Current queue length
            
        Returns:
            Optimization result
        """
        target_cpu = 70.0
        target_memory = 70.0
        
        if cpu_usage > target_cpu or memory_usage > target_memory:
            new_concurrency = max(self.config.min_concurrency, current_concurrency - 1)
            improvement = min(cpu_usage / 100, memory_usage / 100)
            return OptimizationResult(
                parameter="concurrency",
                old_value=current_concurrency,
                new_value=new_concurrency,
                improvement_score=improvement,
                confidence=0.9,
                reason=f"High resource usage (CPU: {cpu_usage:.1f}%, Memory: {memory_usage:.1f}%)"
            )
        elif queue_length > current_concurrency * 2 and current_concurrency < self.config.max_concurrency:
            new_concurrency = min(self.config.max_concurrency, current_concurrency + 1)
            return OptimizationResult(
                parameter="concurrency",
                old_value=current_concurrency,
                new_value=new_concurrency,
                improvement_score=0.2,
                confidence=0.8,
                reason=f"Queue growing ({queue_length} items), increasing concurrency"
            )
        
        return OptimizationResult(
            parameter="concurrency",
            old_value=current_concurrency,
            new_value=current_concurrency,
            improvement_score=0.0,
            confidence=1.0,
            reason="Concurrency is optimal"
        )
    
    async def optimize_cache_ttl(
        self,
        current_ttl: float,
        cache_hit_rate: float,
        cache_size: int
    ) -> OptimizationResult:
        """
        Optimize cache TTL based on hit rate and size.
        
        Args:
            current_ttl: Current TTL in seconds
            cache_hit_rate: Current cache hit rate
            cache_size: Current cache size
            
        Returns:
            Optimization result
        """
        target_hit_rate = 0.8
        
        if cache_hit_rate < target_hit_rate and current_ttl < self.config.cache_ttl_max:
            new_ttl = min(self.config.cache_ttl_max, current_ttl * 1.5)
            improvement = (target_hit_rate - cache_hit_rate) / target_hit_rate
            return OptimizationResult(
                parameter="cache_ttl",
                old_value=current_ttl,
                new_value=new_ttl,
                improvement_score=improvement,
                confidence=0.7,
                reason=f"Low hit rate ({cache_hit_rate:.2%}), increasing TTL"
            )
        elif cache_hit_rate > target_hit_rate * 1.2 and current_ttl > self.config.cache_ttl_min:
            new_ttl = max(self.config.cache_ttl_min, current_ttl * 0.75)
            return OptimizationResult(
                parameter="cache_ttl",
                old_value=current_ttl,
                new_value=new_ttl,
                improvement_score=0.1,
                confidence=0.6,
                reason=f"High hit rate ({cache_hit_rate:.2%}), reducing TTL to save memory"
            )
        
        return OptimizationResult(
            parameter="cache_ttl",
            old_value=current_ttl,
            new_value=current_ttl,
            improvement_score=0.0,
            confidence=1.0,
            reason="Cache TTL is optimal"
        )
    
    async def optimize_polling_interval(
        self,
        current_interval: float,
        change_rate: float,
        error_rate: float
    ) -> OptimizationResult:
        """
        Optimize polling interval based on change rate and error rate.
        
        Args:
            current_interval: Current polling interval in seconds
            change_rate: Rate of state changes per second
            error_rate: Current error rate
            
        Returns:
            Optimization result
        """
        target_latency = 0.1
        
        if change_rate > 10 and current_interval > self.config.polling_interval_min:
            new_interval = max(self.config.polling_interval_min, current_interval * 0.8)
            return OptimizationResult(
                parameter="polling_interval",
                old_value=current_interval,
                new_value=new_interval,
                improvement_score=0.3,
                confidence=0.8,
                reason=f"High change rate ({change_rate:.1f}/s), decreasing polling interval"
            )
        elif change_rate < 1 and current_interval < self.config.polling_interval_max:
            new_interval = min(self.config.polling_interval_max, current_interval * 1.2)
            return OptimizationResult(
                parameter="polling_interval",
                old_value=current_interval,
                new_value=new_interval,
                improvement_score=0.1,
                confidence=0.7,
                reason=f"Low change rate ({change_rate:.1f}/s), increasing polling interval"
            )
        elif error_rate > 0.1 and current_interval < self.config.polling_interval_max:
            new_interval = min(self.config.polling_interval_max, current_interval * 1.5)
            return OptimizationResult(
                parameter="polling_interval",
                old_value=current_interval,
                new_value=new_interval,
                improvement_score=0.2,
                confidence=0.9,
                reason=f"High error rate ({error_rate:.2%}), increasing polling interval"
            )
        
        return OptimizationResult(
            parameter="polling_interval",
            old_value=current_interval,
            new_value=current_interval,
            improvement_score=0.0,
            confidence=1.0,
            reason="Polling interval is optimal"
        )
    
    async def optimize_all(
        self,
        current_config: Dict[str, Any],
        metrics: PerformanceMetrics
    ) -> List[OptimizationResult]:
        """
        Optimize all parameters based on current metrics.
        
        Args:
            current_config: Current configuration
            metrics: Current performance metrics
            
        Returns:
            List of optimization results
        """
        results = []
        
        if "batch_size" in current_config:
            result = await self.optimize_batch_size(
                current_config["batch_size"],
                metrics.latency,
                metrics.throughput
            )
            if result.improvement_score > 0:
                results.append(result)
        
        if "concurrency" in current_config:
            result = await self.optimize_concurrency(
                current_config["concurrency"],
                metrics.cpu_usage,
                metrics.memory_usage,
                metrics.queue_length
            )
            if result.improvement_score > 0:
                results.append(result)
        
        if "cache_ttl" in current_config:
            result = await self.optimize_cache_ttl(
                current_config["cache_ttl"],
                metrics.cache_hit_rate,
                0
            )
            if result.improvement_score > 0:
                results.append(result)
        
        if "polling_interval" in current_config:
            result = await self.optimize_polling_interval(
                current_config["polling_interval"],
                metrics.throughput,
                metrics.error_rate
            )
            if result.improvement_score > 0:
                results.append(result)
        
        async with self._lock:
            self._optimization_history.extend(results)
            if len(self._optimization_history) > self._max_history:
                self._optimization_history = self._optimization_history[-self._max_history:]
        
        return results
    
    def get_optimization_history(self, count: int = 100) -> List[OptimizationResult]:
        """
        Get optimization history.
        
        Args:
            count: Number of recent optimizations to return
            
        Returns:
            List of optimization results
        """
        return self._optimization_history[-count:]
    
    def get_recommendations(self) -> List[Dict[str, Any]]:
        """
        Get optimization recommendations based on history.
        
        Returns:
            List of recommendations
        """
        recommendations = []
        
        if not self._optimization_history:
            return recommendations
        
        recent = self._optimization_history[-10:]
        
        batch_sizes = [r.new_value for r in recent if r.parameter == "batch_size"]
        if batch_sizes:
            avg_batch_size = sum(batch_sizes) / len(batch_sizes)
            recommendations.append({
                "parameter": "batch_size",
                "recommended_value": int(avg_batch_size),
                "reason": "Based on recent optimizations"
            })
        
        concurrencies = [r.new_value for r in recent if r.parameter == "concurrency"]
        if concurrencies:
            avg_concurrency = sum(concurrencies) / len(concurrencies)
            recommendations.append({
                "parameter": "concurrency",
                "recommended_value": int(avg_concurrency),
                "reason": "Based on recent optimizations"
            })
        
        return recommendations
    
    async def get_performance_score(self) -> float:
        """
        Calculate overall performance score (0-100).
        
        Returns:
            Performance score
        """
        if not self._metrics_history:
            return 50.0
        
        latest_metrics = self._metrics_history[-1][1]
        
        score = 100.0
        
        if latest_metrics.latency > 1.0:
            score -= min(50, latest_metrics.latency * 20)
        
        if latest_metrics.cpu_usage > 80:
            score -= (latest_metrics.cpu_usage - 80) * 0.5
        
        if latest_metrics.memory_usage > 80:
            score -= (latest_metrics.memory_usage - 80) * 0.5
        
        if latest_metrics.error_rate > 0.01:
            score -= latest_metrics.error_rate * 100
        
        if latest_metrics.cache_hit_rate < 0.5:
            score -= (0.5 - latest_metrics.cache_hit_rate) * 20
        
        return max(0, min(100, score))
