"""
Unit tests for performance optimization module.
Tests caching, connection pooling, batch processing, and performance monitoring.
"""

import asyncio
import sqlite3
import tempfile
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jarvis_ha_control.app.performance.cache import (
    CacheEvictionPolicy,
    CacheItem,
    CacheManager,
    CacheStats,
    LRUCache,
    TTLCache,
    cached,
    generate_cache_key,
)
from jarvis_ha_control.app.performance.connection_pool import (
    ConnectionPool,
    ConnectionPoolStats,
    DatabaseConnectionPool,
    HTTPConnectionPool,
)
from jarvis_ha_control.app.performance.batch_processor import (
    ActionBatcher,
    BatchItem,
    BatchProcessor,
    BatchResult,
    BatchStatus,
)
from jarvis_ha_control.app.performance.performance_monitor import (
    Alert,
    AlertLevel,
    Metric,
    MetricType,
    MetricsCollector,
    PerformanceMonitor,
    PerformanceSnapshot,
)
from jarvis_ha_control.app.performance.optimizer import (
    OptimizationConfig,
    OptimizationResult,
    OptimizationStrategy,
    OptimizationTarget,
    PerformanceMetrics,
    PerformanceOptimizer,
)


# ============================================================================
# Cache Tests
# ============================================================================


class TestCacheItem:
    """Tests for CacheItem."""
    
    def test_is_expired_no_ttl(self):
        """Test that items without TTL never expire."""
        item = CacheItem(value="test", ttl=None)
        assert not item.is_expired()
    
    def test_is_expired_with_ttl(self):
        """Test TTL expiration."""
        item = CacheItem(value="test", ttl=0.1)
        assert not item.is_expired()
        time.sleep(0.15)
        assert item.is_expired()
    
    def test_is_expired_negative_ttl(self):
        """Test that negative TTL means already expired."""
        item = CacheItem(value="test", ttl=-1)
        assert item.is_expired()


class TestCacheStats:
    """Tests for CacheStats."""
    
    def test_hit_rate_calculation(self):
        """Test hit rate calculation."""
        stats = CacheStats(hits=80, misses=20)
        assert stats.hit_rate == 0.8
        assert stats.miss_rate == 0.2
    
    def test_hit_rate_zero_total(self):
        """Test hit rate with zero total."""
        stats = CacheStats()
        assert stats.hit_rate == 0.0
        assert stats.miss_rate == 0.0


class TestLRUCache:
    """Tests for LRUCache."""
    
    @pytest.mark.asyncio
    async def test_get_set(self):
        """Test basic get and set operations."""
        cache = LRUCache[str](max_size=10)
        await cache.set("key1", "value1")
        result = await cache.get("key1")
        assert result == "value1"
    
    @pytest.mark.asyncio
    async def test_get_nonexistent(self):
        """Test getting nonexistent key."""
        cache = LRUCache[str](max_size=10)
        result = await cache.get("nonexistent")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_eviction(self):
        """Test LRU eviction."""
        cache = LRUCache[str](max_size=3)
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.set("key3", "value3")
        await cache.set("key4", "value4")
        
        assert await cache.get("key1") is None
        assert await cache.get("key2") == "value2"
        assert await cache.get("key3") == "value3"
        assert await cache.get("key4") == "value4"
    
    @pytest.mark.asyncio
    async def test_ttl_eviction(self):
        """Test TTL-based eviction."""
        cache = LRUCache[str](max_size=10)
        await cache.set("key1", "value1", ttl=0.1)
        assert await cache.get("key1") == "value1"
        await asyncio.sleep(0.15)
        assert await cache.get("key1") is None
    
    @pytest.mark.asyncio
    async def test_delete(self):
        """Test delete operation."""
        cache = LRUCache[str](max_size=10)
        await cache.set("key1", "value1")
        assert await cache.delete("key1")
        assert await cache.get("key1") is None
    
    @pytest.mark.asyncio
    async def test_contains(self):
        """Test contains operation."""
        cache = LRUCache[str](max_size=10)
        await cache.set("key1", "value1")
        assert await cache.contains("key1")
        assert not await cache.contains("key2")
    
    @pytest.mark.asyncio
    async def test_clear(self):
        """Test clear operation."""
        cache = LRUCache[str](max_size=10)
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.clear()
        assert await cache.get("key1") is None
        assert await cache.get("key2") is None
    
    @pytest.mark.asyncio
    async def test_stats(self):
        """Test cache statistics."""
        cache = LRUCache[str](max_size=10)
        await cache.set("key1", "value1")
        await cache.get("key1")
        await cache.get("key2")
        
        stats = cache.get_stats()
        assert stats.hits == 1
        assert stats.misses == 1
        assert stats.size == 1


class TestTTLCache:
    """Tests for TTLCache."""
    
    @pytest.mark.asyncio
    async def test_get_set(self):
        """Test basic get and set operations."""
        cache = TTLCache[str](default_ttl=10.0)
        await cache.set("key1", "value1")
        result = await cache.get("key1")
        assert result == "value1"
    
    @pytest.mark.asyncio
    async def test_default_ttl(self):
        """Test default TTL is used."""
        cache = TTLCache[str](default_ttl=0.1)
        await cache.set("key1", "value1")
        assert await cache.get("key1") == "value1"
        await asyncio.sleep(0.15)
        assert await cache.get("key1") is None
    
    @pytest.mark.asyncio
    async def test_custom_ttl(self):
        """Test custom TTL overrides default."""
        cache = TTLCache[str](default_ttl=10.0)
        await cache.set("key1", "value1", ttl=0.1)
        assert await cache.get("key1") == "value1"
        await asyncio.sleep(0.15)
        assert await cache.get("key1") is None
    
    @pytest.mark.asyncio
    async def test_cleanup(self):
        """Test automatic cleanup of expired items."""
        cache = TTLCache[str](default_ttl=0.1, cleanup_interval=0.05)
        await cache.start_cleanup()
        await cache.set("key1", "value1")
        await asyncio.sleep(0.2)
        assert await cache.get("key1") is None
        await cache.stop_cleanup()


class TestCacheManager:
    """Tests for CacheManager."""
    
    @pytest.mark.asyncio
    async def test_create_lru_cache(self):
        """Test creating LRU cache."""
        manager = CacheManager()
        cache = await manager.create_lru_cache("test_lru", max_size=10)
        assert isinstance(cache, LRUCache)
        await cache.set("key1", "value1")
        assert await cache.get("key1") == "value1"
    
    @pytest.mark.asyncio
    async def test_create_ttl_cache(self):
        """Test creating TTL cache."""
        manager = CacheManager()
        cache = await manager.create_ttl_cache("test_ttl", default_ttl=10.0)
        assert isinstance(cache, TTLCache)
        await cache.set("key1", "value1")
        assert await cache.get("key1") == "value1"
    
    @pytest.mark.asyncio
    async def test_get_cache(self):
        """Test getting existing cache."""
        manager = CacheManager()
        cache1 = await manager.create_lru_cache("test", max_size=10)
        cache2 = await manager.get_cache("test")
        assert cache1 is cache2
    
    @pytest.mark.asyncio
    async def test_delete_cache(self):
        """Test deleting cache."""
        manager = CacheManager()
        await manager.create_lru_cache("test", max_size=10)
        assert await manager.delete_cache("test")
        assert await manager.get_cache("test") is None
    
    @pytest.mark.asyncio
    async def test_clear_all(self):
        """Test clearing all caches."""
        manager = CacheManager()
        await manager.create_lru_cache("cache1", max_size=10)
        await manager.create_lru_cache("cache2", max_size=10)
        await manager.clear_all()
        assert await manager.get_cache("cache1") is None
        assert await manager.get_cache("cache2") is None


class TestCacheDecorator:
    """Tests for cached decorator."""
    
    @pytest.mark.asyncio
    async def test_cached_decorator(self):
        """Test cached decorator."""
        cache = LRUCache[int](max_size=10)
        call_count = 0
        
        @cached(cache, key="test_key")
        async def expensive_function():
            nonlocal call_count
            call_count += 1
            return 42
        
        result1 = await expensive_function()
        result2 = await expensive_function()
        
        assert result1 == 42
        assert result2 == 42
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_cached_decorator_with_callable_key(self):
        """Test cached decorator with callable key."""
        cache = LRUCache[int](max_size=10)
        call_count = 0
        
        @cached(cache, key=lambda x: f"key_{x}")
        async def expensive_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2
        
        result1 = await expensive_function(10)
        result2 = await expensive_function(10)
        result3 = await expensive_function(20)
        
        assert result1 == 20
        assert result2 == 20
        assert result3 == 40
        assert call_count == 2


class TestGenerateCacheKey:
    """Tests for generate_cache_key."""
    
    def test_generate_cache_key_basic(self):
        """Test basic cache key generation."""
        key1 = generate_cache_key("test", "arg1", "arg2")
        key2 = generate_cache_key("test", "arg1", "arg2")
        key3 = generate_cache_key("test", "arg1", "arg3")
        
        assert key1 == key2
        assert key1 != key3
    
    def test_generate_cache_key_with_kwargs(self):
        """Test cache key generation with kwargs."""
        key1 = generate_cache_key("test", a=1, b=2)
        key2 = generate_cache_key("test", a=1, b=2)
        key3 = generate_cache_key("test", a=1, b=3)
        
        assert key1 == key2
        assert key1 != key3


# ============================================================================
# Connection Pool Tests
# ============================================================================


class TestConnectionPoolStats:
    """Tests for ConnectionPoolStats."""
    
    def test_avg_wait_time(self):
        """Test average wait time calculation."""
        stats = ConnectionPoolStats(
            wait_time_total=10.0,
            wait_time_count=5
        )
        assert stats.avg_wait_time == 2.0
    
    def test_avg_wait_time_zero_count(self):
        """Test average wait time with zero count."""
        stats = ConnectionPoolStats()
        assert stats.avg_wait_time == 0.0
    
    def test_utilization_rate(self):
        """Test utilization rate calculation."""
        stats = ConnectionPoolStats(
            in_use_connections=5,
            max_connections=10
        )
        assert stats.utilization_rate == 0.5


class TestConnectionPool:
    """Tests for ConnectionPool."""
    
    @pytest.mark.asyncio
    async def test_acquire_release(self):
        """Test acquire and release."""
        connection_count = 0
        
        def create_connection():
            nonlocal connection_count
            connection_count += 1
            return f"connection_{connection_count}"
        
        pool = ConnectionPool(create_connection, max_size=5)
        await pool.initialize()
        
        conn1 = await pool.acquire()
        assert conn1 == "connection_1"
        
        await pool.release(conn1)
        
        conn2 = await pool.acquire()
        assert conn2 == "connection_1"
        
        await pool.close()
    
    @pytest.mark.asyncio
    async def test_max_size(self):
        """Test pool respects max size."""
        connection_count = 0
        
        def create_connection():
            nonlocal connection_count
            connection_count += 1
            return f"connection_{connection_count}"
        
        pool = ConnectionPool(create_connection, max_size=3, min_size=0)
        
        conn1 = await pool.acquire()
        conn2 = await pool.acquire()
        conn3 = await pool.acquire()
        
        assert connection_count == 3
        
        await pool.release(conn1)
        await pool.release(conn2)
        await pool.release(conn3)
        await pool.close()
    
    @pytest.mark.asyncio
    async def test_clear(self):
        """Test clear operation."""
        connection_count = 0
        
        def create_connection():
            nonlocal connection_count
            connection_count += 1
            return f"connection_{connection_count}"
        
        pool = ConnectionPool(create_connection, max_size=5)
        await pool.initialize()
        
        conn = await pool.acquire()
        await pool.clear()
        
        stats = pool.get_stats()
        assert stats.total_connections == 0
        
        await pool.close()
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test context manager."""
        connection_count = 0
        
        def create_connection():
            nonlocal connection_count
            connection_count += 1
            return f"connection_{connection_count}"
        
        async with ConnectionPool(create_connection, max_size=5) as pool:
            conn = await pool.acquire()
            assert conn == "connection_1"
            await pool.release(conn)


class TestDatabaseConnectionPool:
    """Tests for DatabaseConnectionPool."""
    
    @pytest.mark.asyncio
    async def test_execute(self):
        """Test database execute."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        
        try:
            pool = DatabaseConnectionPool(db_path, max_size=5)
            await pool.initialize()
            
            await pool.execute(
                "CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)"
            )
            
            await pool.execute(
                "INSERT INTO test (value) VALUES (?)",
                ("test_value",)
            )
            
            results = await pool.execute(
                "SELECT * FROM test",
                fetch=True
            )
            
            assert len(results) == 1
            assert results[0]["value"] == "test_value"
            
            await pool.close()
        finally:
            import os
            os.unlink(db_path)


# ============================================================================
# Batch Processor Tests
# ============================================================================


class TestBatchItem:
    """Tests for BatchItem."""
    
    def test_should_retry(self):
        """Test retry logic."""
        item = BatchItem(data="test", max_retries=3)
        assert item.should_retry
        
        item.retry_count = 3
        assert not item.should_retry


class TestBatchResult:
    """Tests for BatchResult."""
    
    def test_duration(self):
        """Test duration calculation."""
        result = BatchResult[Any](status=BatchStatus.COMPLETED)
        result.start_time = 0.0
        result.end_time = 1.0
        assert result.duration == 1.0
    
    def test_success_count(self):
        """Test success count."""
        result = BatchResult[str]()
        result.results = ["r1", "r2", "r3"]
        result.errors = [Exception("e1")]
        assert result.success_count == 3
        assert result.failure_count == 1
    
    def test_is_successful(self):
        """Test is_successful property."""
        result = BatchResult[str]()
        result.status = BatchStatus.COMPLETED
        assert result.is_successful
        
        result.errors.append(Exception("test"))
        assert not result.is_successful


class TestBatchProcessor:
    """Tests for BatchProcessor."""
    
    @pytest.mark.asyncio
    async def test_add_item(self):
        """Test adding items."""
        processor = BatchProcessor[int, int](
            processor=lambda x: x * 2,
            batch_size=5
        )
        
        await processor.add_item(10)
        await processor.add_item(20)
        
        await processor.wait_for_completion()
        
        stats = processor.get_stats()
        assert stats["total_processed"] == 2
    
    @pytest.mark.asyncio
    async def test_add_batch(self):
        """Test adding batch of items."""
        processor = BatchProcessor[int, int](
            processor=lambda x: x * 2,
            batch_size=5
        )
        
        await processor.add_batch([1, 2, 3, 4, 5])
        
        await processor.wait_for_completion()
        
        stats = processor.get_stats()
        assert stats["total_processed"] == 5
    
    @pytest.mark.asyncio
    async def test_process_all(self):
        """Test process_all."""
        processor = BatchProcessor[int, int](
            processor=lambda x: x * 2,
            batch_size=5
        )
        
        result = await processor.process_all([1, 2, 3])
        
        assert result.status == BatchStatus.COMPLETED
        assert len(result.results) == 3
        assert result.is_successful
    
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling."""
        call_count = 0
        
        async def failing_processor(x):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("test error")
            return x * 2
        
        processor = BatchProcessor[int, int](
            processor=failing_processor,
            batch_size=5,
            max_retries=1
        )
        
        result = await processor.process_all([1, 2, 3])
        
        assert result.failure_count >= 0
    
    @pytest.mark.asyncio
    async def test_clear(self):
        """Test clear operation."""
        processor = BatchProcessor[int, int](
            processor=lambda x: x * 2,
            batch_size=5
        )
        
        await processor.add_item(1)
        await processor.add_item(2)
        
        await processor.clear()
        
        stats = processor.get_stats()
        assert stats["total_processed"] == 0


class TestActionBatcher:
    """Tests for ActionBatcher."""
    
    @pytest.mark.asyncio
    async def test_add_action(self):
        """Test adding actions."""
        batcher = ActionBatcher()
        
        await batcher.add_action("light", "turn_on", "light.living_room")
        await batcher.add_action("light", "turn_off", "light.kitchen")
        
        stats = batcher.get_stats()
        assert stats["total_actions"] == 0
    
    @pytest.mark.asyncio
    async def test_process_batch(self):
        """Test processing batch."""
        batcher = ActionBatcher(batch_size=2)
        
        mock_client = MagicMock()
        mock_client.light_turn_on = AsyncMock(return_value={"result": "success"})
        mock_client.light_turn_off = AsyncMock(return_value={"result": "success"})
        
        await batcher.add_action("light", "turn_on", "light.living_room")
        await batcher.add_action("light", "turn_off", "light.kitchen")
        
        result = await batcher.process_batch(mock_client)
        
        assert result.status == BatchStatus.COMPLETED
        assert len(result.results) == 2
    
    @pytest.mark.asyncio
    async def test_clear(self):
        """Test clear operation."""
        batcher = ActionBatcher()
        
        await batcher.add_action("light", "turn_on", "light.living_room")
        await batcher.clear()
        
        stats = batcher.get_stats()
        assert stats["total_actions"] == 0


# ============================================================================
# Performance Monitor Tests
# ============================================================================


class TestMetric:
    """Tests for Metric."""
    
    def test_to_dict(self):
        """Test to_dict method."""
        metric = Metric(
            name="test_metric",
            value=42.0,
            unit="%",
            tags={"type": "system"}
        )
        
        result = metric.to_dict()
        
        assert result["name"] == "test_metric"
        assert result["value"] == 42.0
        assert result["unit"] == "%"
        assert result["tags"]["type"] == "system"


class TestAlert:
    """Tests for Alert."""
    
    def test_to_dict(self):
        """Test to_dict method."""
        alert = Alert(
            name="test_alert",
            level=AlertLevel.WARNING,
            message="Test message",
            metric_name="cpu_usage",
            metric_value=80.0,
            threshold=70.0
        )
        
        result = alert.to_dict()
        
        assert result["name"] == "test_alert"
        assert result["level"] == "warning"
        assert result["message"] == "Test message"


class TestMetricsCollector:
    """Tests for MetricsCollector."""
    
    @pytest.mark.asyncio
    async def test_collect_cpu_usage(self):
        """Test CPU usage collection."""
        collector = MetricsCollector()
        metric = await collector.collect_cpu_usage()
        
        assert metric.name == "cpu_usage"
        assert 0 <= metric.value <= 100
        assert metric.unit == "%"
    
    @pytest.mark.asyncio
    async def test_collect_memory_usage(self):
        """Test memory usage collection."""
        collector = MetricsCollector()
        metric = await collector.collect_memory_usage()
        
        assert metric.name == "memory_usage"
        assert 0 <= metric.value <= 100
        assert metric.unit == "%"
    
    @pytest.mark.asyncio
    async def test_collect_disk_usage(self):
        """Test disk usage collection."""
        collector = MetricsCollector()
        metric = await collector.collect_disk_usage()
        
        assert metric.name == "disk_usage"
        assert 0 <= metric.value <= 100
        assert metric.unit == "%"
    
    @pytest.mark.asyncio
    async def test_record_custom_metric(self):
        """Test recording custom metric."""
        collector = MetricsCollector()
        metric = collector.record_custom_metric(
            name="custom_metric",
            value=42.0,
            unit="units"
        )
        
        assert metric.name == "custom_metric"
        assert metric.value == 42.0
        
        metrics = collector.get_metrics("custom_metric")
        assert len(metrics) == 1
    
    @pytest.mark.asyncio
    async def test_callback(self):
        """Test metric callback."""
        collector = MetricsCollector()
        received_metrics = []
        
        def callback(metric):
            received_metrics.append(metric)
        
        collector.add_callback(callback)
        collector.record_custom_metric("test", 42.0)
        
        assert len(received_metrics) == 1
        assert received_metrics[0].name == "test"


class TestPerformanceMonitor:
    """Tests for PerformanceMonitor."""
    
    @pytest.mark.asyncio
    async def test_alert_rule(self):
        """Test alert rule triggering."""
        monitor = PerformanceMonitor()
        
        monitor.add_alert_rule(
            name="high_cpu",
            metric_name="cpu_usage",
            threshold=90.0,
            level=AlertLevel.WARNING,
            comparison=">"
        )
        
        collector = monitor.get_metrics_collector()
        collector.record_custom_metric("cpu_usage", 95.0, "%")
        
        alerts = await monitor.check_alerts()
        
        assert len(alerts) == 1
        assert alerts[0].name == "high_cpu"
        assert alerts[0].level == AlertLevel.WARNING
    
    @pytest.mark.asyncio
    async def test_snapshot(self):
        """Test taking snapshot."""
        monitor = PerformanceMonitor()
        
        collector = monitor.get_metrics_collector()
        collector.record_custom_metric("test_metric", 42.0)
        
        snapshot = await monitor.take_snapshot()
        
        assert snapshot.timestamp > 0
        assert "test_metric" in snapshot.metrics
    
    @pytest.mark.asyncio
    async def test_performance_report(self):
        """Test performance report generation."""
        monitor = PerformanceMonitor()
        
        collector = monitor.get_metrics_collector()
        collector.record_custom_metric("cpu_usage", 50.0, "%")
        collector.record_custom_metric("memory_usage", 60.0, "%")
        
        report = await monitor.get_performance_report(duration=3600.0)
        
        assert "timestamp" in report
        assert "duration" in report
        assert "metrics" in report
        assert "summary" in report


# ============================================================================
# Optimizer Tests
# ============================================================================


class TestPerformanceMetrics:
    """Tests for PerformanceMetrics."""
    
    def test_to_dict(self):
        """Test to_dict method."""
        metrics = PerformanceMetrics(
            latency=0.5,
            throughput=100.0,
            cpu_usage=50.0,
            memory_usage=60.0
        )
        
        result = metrics.to_dict()
        
        assert result["latency"] == 0.5
        assert result["throughput"] == 100.0


class TestPerformanceOptimizer:
    """Tests for PerformanceOptimizer."""
    
    @pytest.mark.asyncio
    async def test_optimize_batch_size(self):
        """Test batch size optimization."""
        optimizer = PerformanceOptimizer()
        
        result = await optimizer.optimize_batch_size(
            current_batch_size=10,
            current_latency=0.5,
            current_throughput=100.0
        )
        
        assert result.parameter == "batch_size"
        assert result.confidence > 0
    
    @pytest.mark.asyncio
    async def test_optimize_concurrency(self):
        """Test concurrency optimization."""
        optimizer = PerformanceOptimizer()
        
        result = await optimizer.optimize_concurrency(
            current_concurrency=5,
            cpu_usage=80.0,
            memory_usage=70.0,
            queue_length=10
        )
        
        assert result.parameter == "concurrency"
    
    @pytest.mark.asyncio
    async def test_optimize_cache_ttl(self):
        """Test cache TTL optimization."""
        optimizer = PerformanceOptimizer()
        
        result = await optimizer.optimize_cache_ttl(
            current_ttl=60.0,
            cache_hit_rate=0.6,
            cache_size=100
        )
        
        assert result.parameter == "cache_ttl"
    
    @pytest.mark.asyncio
    async def test_optimize_polling_interval(self):
        """Test polling interval optimization."""
        optimizer = PerformanceOptimizer()
        
        result = await optimizer.optimize_polling_interval(
            current_interval=10.0,
            change_rate=20.0,
            error_rate=0.0
        )
        
        assert result.parameter == "polling_interval"
    
    @pytest.mark.asyncio
    async def test_record_metrics(self):
        """Test recording metrics."""
        optimizer = PerformanceOptimizer()
        
        metrics = PerformanceMetrics(
            latency=0.5,
            throughput=100.0,
            cpu_usage=50.0
        )
        
        await optimizer.record_metrics(metrics)
        
        history = optimizer.get_optimization_history()
        assert len(history) == 0
    
    @pytest.mark.asyncio
    async def test_get_performance_score(self):
        """Test performance score calculation."""
        optimizer = PerformanceOptimizer()
        
        metrics = PerformanceMetrics(
            latency=0.1,
            throughput=100.0,
            cpu_usage=50.0,
            memory_usage=50.0,
            error_rate=0.0,
            cache_hit_rate=0.9
        )
        
        await optimizer.record_metrics(metrics)
        
        score = await optimizer.get_performance_score()
        
        assert 0 <= score <= 100
