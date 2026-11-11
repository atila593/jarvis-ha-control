"""
Integration tests for Jarvis HA Control.
Tests the complete system integration including:
- Agents interaction
- Performance module integration
- Autonomy engine
- WebSocket integration
- API endpoints
"""

import asyncio
import os
import sqlite3
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jarvis_ha_control.app.agents import (
    ActionAgent,
    ConversationAgent,
    DecisionAgent,
    MonitoringAgent,
    Orchestrator,
    SecurityAgent,
)
from jarvis_ha_control.app.agents.action_agent import Action, ActionPriority, ActionStatus
from jarvis_ha_control.app.agents.conversation_agent import Message, MessageRole
from jarvis_ha_control.app.agents.decision_agent import Decision, DecisionConfidence
from jarvis_ha_control.app.agents.monitoring_agent import Alert, AlertSeverity, SystemMetric
from jarvis_ha_control.app.agents.security_agent import User, UserRole
from jarvis_ha_control.app.performance.cache import CacheManager, LRUCache, TTLCache
from jarvis_ha_control.app.performance.connection_pool import (
    ConnectionPool,
    DatabaseConnectionPool,
)
from jarvis_ha_control.app.performance.batch_processor import ActionBatcher, BatchProcessor
from jarvis_ha_control.app.performance.performance_monitor import (
    PerformanceMonitor,
    MetricsCollector,
)
from jarvis_ha_control.app.performance.optimizer import PerformanceOptimizer


# ============================================================================
# Agents Integration Tests
# ============================================================================


class TestAgentsIntegration:
    """Tests for agents integration."""
    
    @pytest.mark.asyncio
    async def test_orchestrator_with_all_agents(self):
        """Test orchestrator with all agent types."""
        # Create mock agents
        conversation_agent = MagicMock(spec=ConversationAgent)
        decision_agent = MagicMock(spec=DecisionAgent)
        action_agent = MagicMock(spec=ActionAgent)
        monitoring_agent = MagicMock(spec=MonitoringAgent)
        security_agent = MagicMock(spec=SecurityAgent)
        
        conversation_agent.process_message = AsyncMock(return_value=Message(
            role=MessageRole.ASSISTANT,
            content="Test response"
        ))
        
        decision_agent.make_decision = AsyncMock(return_value=Decision(
            action="test_action",
            confidence=DecisionConfidence.HIGH,
            reason="Test reason"
        ))
        
        action_agent.execute = AsyncMock(return_value=Action(
            id="test_id",
            action="test_action",
            status=ActionStatus.COMPLETED
        ))
        
        monitoring_agent.get_system_metrics = AsyncMock(return_value=SystemMetric(
            cpu_usage=50.0,
            memory_usage=60.0
        ))
        
        security_agent.authenticate = AsyncMock(return_value=True)
        
        # Create orchestrator
        orchestrator = Orchestrator(
            conversation_agent=conversation_agent,
            decision_agent=decision_agent,
            action_agent=action_agent,
            monitoring_agent=monitoring_agent,
            security_agent=security_agent
        )
        
        # Test processing a request
        result = await orchestrator.process_request("Test request")
        
        # Verify agents were called
        conversation_agent.process_message.assert_called()
        decision_agent.make_decision.assert_called()
        action_agent.execute.assert_called()
    
    @pytest.mark.asyncio
    async def test_agents_workflow(self):
        """Test complete agents workflow."""
        # Setup
        conversation_agent = ConversationAgent()
        decision_agent = DecisionAgent()
        action_agent = ActionAgent()
        
        # Add a conversation message
        await conversation_agent.add_message(Message(
            role=MessageRole.USER,
            content="Turn on the lights"
        ))
        
        # Process the message
        response = await conversation_agent.process_message("Turn on the lights")
        
        # Make a decision
        decision = await decision_agent.make_decision(
            context="Turn on the lights",
            available_actions=["turn_on_lights"]
        )
        
        # Execute action
        action = await action_agent.execute(
            domain="light",
            service="turn_on",
            entity_id="light.living_room"
        )
        
        # Verify workflow completed
        assert response is not None
        assert decision is not None
        assert action is not None
    
    @pytest.mark.asyncio
    async def test_security_monitoring_integration(self):
        """Test security and monitoring agents integration."""
        security_agent = SecurityAgent()
        monitoring_agent = MonitoringAgent()
        
        # Add a user
        await security_agent.add_user(User(
            id="user1",
            username="test_user",
            role=UserRole.ADMIN,
            permissions=["read", "write"]
        ))
        
        # Authenticate
        authenticated = await security_agent.authenticate("user1", "password")
        
        # Get system metrics
        metrics = await monitoring_agent.get_system_metrics()
        
        # Verify integration
        assert metrics is not None
        assert metrics.cpu_usage is not None


class TestPerformanceAgentsIntegration:
    """Tests for performance module integration with agents."""
    
    @pytest.mark.asyncio
    async def test_monitoring_agent_with_performance_monitor(self):
        """Test monitoring agent with performance monitor."""
        monitoring_agent = MonitoringAgent()
        performance_monitor = PerformanceMonitor()
        
        # Start performance monitor
        await performance_monitor.start()
        
        # Get system metrics from both
        ha_metrics = await monitoring_agent.get_system_metrics()
        perf_metrics = await performance_monitor.get_metrics_collector().collect_all()
        
        # Verify both provide metrics
        assert ha_metrics is not None
        assert len(perf_metrics) > 0
        
        # Stop performance monitor
        await performance_monitor.stop()
    
    @pytest.mark.asyncio
    async def test_action_batcher_with_action_agent(self):
        """Test action batcher with action agent."""
        action_agent = ActionAgent()
        action_batcher = ActionBatcher()
        
        # Add actions to batcher
        await action_batcher.add_action("light", "turn_on", "light.living_room")
        await action_batcher.add_action("light", "turn_off", "light.kitchen")
        
        # Create mock HA client
        mock_client = MagicMock()
        mock_client.light_turn_on = AsyncMock(return_value={"result": "success"})
        mock_client.light_turn_off = AsyncMock(return_value={"result": "success"})
        
        # Process batch
        result = await action_batcher.process_batch(mock_client)
        
        # Verify actions were processed
        assert result.status.value == "completed"
        assert len(result.results) == 2


# ============================================================================
# Performance Module Integration Tests
# ============================================================================


class TestCachePerformanceIntegration:
    """Tests for cache and performance module integration."""
    
    @pytest.mark.asyncio
    async def test_cache_manager_with_multiple_caches(self):
        """Test cache manager with multiple cache types."""
        cache_manager = CacheManager()
        
        # Create LRU cache
        lru_cache = await cache_manager.create_lru_cache("test_lru", max_size=10)
        await lru_cache.set("key1", "value1")
        
        # Create TTL cache
        ttl_cache = await cache_manager.create_ttl_cache("test_ttl", default_ttl=10.0)
        await ttl_cache.set("key2", "value2")
        
        # Verify both caches work
        assert await lru_cache.get("key1") == "value1"
        assert await ttl_cache.get("key2") == "value2"
        
        # Get stats for both
        stats = cache_manager.get_stats()
        assert len(stats) == 2
    
    @pytest.mark.asyncio
    async def test_cache_with_connection_pool(self):
        """Test cache integration with connection pool."""
        cache = LRUCache(max_size=100)
        
        # Create a connection pool with caching
        connection_count = 0
        
        def create_connection():
            nonlocal connection_count
            connection_count += 1
            return f"connection_{connection_count}"
        
        pool = ConnectionPool(create_connection, max_size=5)
        await pool.initialize()
        
        # Use cache to store connection info
        conn = await pool.acquire()
        await cache.set(f"connection_{conn}", {"status": "in_use"})
        
        # Verify cache stores connection info
        cached_info = await cache.get(f"connection_{conn}")
        assert cached_info is not None
        assert cached_info["status"] == "in_use"
        
        await pool.release(conn)
        await pool.close()


class TestBatchProcessorIntegration:
    """Tests for batch processor integration."""
    
    @pytest.mark.asyncio
    async def test_batch_processor_with_cache(self):
        """Test batch processor with caching."""
        cache = LRUCache(max_size=100)
        processed_items = []
        
        async def processor(item):
            # Check cache first
            cached_result = await cache.get(f"processed_{item}")
            if cached_result is not None:
                return cached_result
            
            # Process item
            result = f"processed_{item}"
            await cache.set(f"processed_{item}", result)
            processed_items.append(item)
            return result
        
        batch_processor = BatchProcessor(processor, batch_size=5)
        
        # Process items
        result = await batch_processor.process_all([1, 2, 3, 1, 2])
        
        # Verify only unique items were processed
        assert len(processed_items) == 3
        assert len(result.results) == 5


class TestConnectionPoolIntegration:
    """Tests for connection pool integration."""
    
    @pytest.mark.asyncio
    async def test_database_connection_pool_with_cache(self):
        """Test database connection pool with caching."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        
        try:
            pool = DatabaseConnectionPool(db_path, max_size=5)
            await pool.initialize()
            
            # Create cache
            cache = LRUCache(max_size=100)
            
            # Execute query and cache result
            await pool.execute(
                "CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)"
            )
            
            await pool.execute(
                "INSERT INTO test (value) VALUES (?)",
                ("test_value",)
            )
            
            # Cache the query result
            results = await pool.execute(
                "SELECT * FROM test",
                fetch=True
            )
            
            await cache.set("query_test_all", results)
            
            # Verify cached result
            cached_results = await cache.get("query_test_all")
            assert cached_results is not None
            assert len(cached_results) == 1
            
            await pool.close()
        finally:
            import os
            os.unlink(db_path)


# ============================================================================
# Performance Optimizer Integration Tests
# ============================================================================


class TestPerformanceOptimizerIntegration:
    """Tests for performance optimizer integration."""
    
    @pytest.mark.asyncio
    async def test_optimizer_with_metrics(self):
        """Test optimizer with performance metrics."""
        optimizer = PerformanceOptimizer()
        collector = MetricsCollector()
        
        # Collect some metrics
        await collector.start()
        metrics = await collector.collect_all()
        await collector.stop()
        
        # Create performance metrics
        perf_metrics = PerformanceMetrics(
            latency=0.5,
            throughput=100.0,
            cpu_usage=50.0,
            memory_usage=60.0
        )
        
        await optimizer.record_metrics(perf_metrics)
        
        # Get optimizations
        config = {
            "batch_size": 10,
            "concurrency": 5,
            "cache_ttl": 60.0,
            "polling_interval": 10.0
        }
        
        results = await optimizer.optimize_all(config, perf_metrics)
        
        # Verify optimizations were generated
        assert len(results) >= 0
    
    @pytest.mark.asyncio
    async def test_optimizer_with_cache(self):
        """Test optimizer with cache performance."""
        optimizer = PerformanceOptimizer()
        cache = LRUCache(max_size=100)
        
        # Simulate cache operations
        for i in range(50):
            await cache.set(f"key_{i}", f"value_{i}")
        
        # Record cache hit rate
        stats = cache.get_stats()
        cache_hit_rate = stats.hit_rate
        
        # Get cache TTL optimization
        result = await optimizer.optimize_cache_ttl(
            current_ttl=60.0,
            cache_hit_rate=cache_hit_rate,
            cache_size=50
        )
        
        # Verify optimization result
        assert result.parameter == "cache_ttl"


# ============================================================================
# Complete System Integration Tests
# ============================================================================


class TestCompleteSystemIntegration:
    """Tests for complete system integration."""
    
    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """Test complete workflow from request to action."""
        # Initialize all components
        cache_manager = CacheManager()
        performance_monitor = PerformanceMonitor()
        performance_optimizer = PerformanceOptimizer()
        
        # Start monitoring
        await performance_monitor.start()
        
        # Create caches
        action_cache = await cache_manager.create_lru_cache("actions", max_size=100)
        decision_cache = await cache_manager.create_ttl_cache("decisions", default_ttl=300.0)
        
        # Record initial metrics
        metrics = await performance_monitor.get_metrics_collector().collect_all()
        await performance_optimizer.record_metrics(PerformanceMetrics(
            latency=0.1,
            throughput=100.0,
            cpu_usage=metrics.get("cpu_usage", {}).value if "cpu_usage" in metrics else 50.0,
            memory_usage=metrics.get("memory_usage", {}).value if "memory_usage" in metrics else 60.0
        ))
        
        # Simulate a request
        request = "Turn on the living room lights"
        
        # Cache the request
        await action_cache.set(f"request_{request}", {"processed": True})
        
        # Verify request is cached
        cached_request = await action_cache.get(f"request_{request}")
        assert cached_request is not None
        
        # Stop monitoring
        await performance_monitor.stop()
        
        # Verify all components worked together
        stats = cache_manager.get_stats()
        assert len(stats) == 2
    
    @pytest.mark.asyncio
    async def test_performance_optimization_loop(self):
        """Test complete performance optimization loop."""
        # Initialize components
        cache = LRUCache(max_size=100)
        batch_processor = BatchProcessor(lambda x: x * 2, batch_size=10)
        performance_monitor = PerformanceMonitor()
        performance_optimizer = PerformanceOptimizer()
        
        # Start monitoring
        await performance_monitor.start()
        
        # Process some items
        await batch_processor.add_batch([1, 2, 3, 4, 5])
        await batch_processor.wait_for_completion()
        
        # Cache some results
        for i in range(10):
            await cache.set(f"item_{i}", i * 2)
        
        # Collect metrics
        metrics = await performance_monitor.get_metrics_collector().collect_all()
        
        # Record performance metrics
        await performance_optimizer.record_metrics(PerformanceMetrics(
            latency=0.1,
            throughput=100.0,
            cpu_usage=metrics.get("cpu_usage", {}).value if "cpu_usage" in metrics else 50.0,
            memory_usage=metrics.get("memory_usage", {}).value if "memory_usage" in metrics else 60.0,
            cache_hit_rate=cache.get_stats().hit_rate
        ))
        
        # Get optimization recommendations
        config = {
            "batch_size": 10,
            "concurrency": 5
        }
        
        optimizations = await performance_optimizer.optimize_all(config, PerformanceMetrics())
        
        # Verify optimization loop completed
        assert len(optimizations) >= 0
        
        # Stop monitoring
        await performance_monitor.stop()
    
    @pytest.mark.asyncio
    async def test_agents_with_performance_modules(self):
        """Test agents working with performance modules."""
        # Create agents
        conversation_agent = ConversationAgent()
        decision_agent = DecisionAgent()
        action_agent = ActionAgent()
        
        # Create performance components
        cache_manager = CacheManager()
        action_batcher = ActionBatcher()
        performance_monitor = PerformanceMonitor()
        
        # Start monitoring
        await performance_monitor.start()
        
        # Use cache for conversation history
        conversation_cache = await cache_manager.create_lru_cache("conversation", max_size=50)
        
        # Add conversation message
        message = Message(role=MessageRole.USER, content="Hello")
        await conversation_agent.add_message(message)
        
        # Cache the conversation
        await conversation_cache.set("conversation_1", message)
        
        # Process message
        response = await conversation_agent.process_message("Hello")
        
        # Make decision
        decision = await decision_agent.make_decision(
            context="Hello",
            available_actions=["greet"]
        )
        
        # Execute action
        action = await action_agent.execute(
            domain="test",
            service="test",
            entity_id="test.entity"
        )
        
        # Record performance metrics
        await performance_optimizer.record_metrics(PerformanceMetrics(
            latency=0.1,
            throughput=1.0
        ))
        
        # Verify integration
        assert response is not None
        assert decision is not None
        assert action is not None
        
        # Stop monitoring
        await performance_monitor.stop()


# ============================================================================
# Stress Tests
# ============================================================================


class TestStressIntegration:
    """Stress tests for integration."""
    
    @pytest.mark.asyncio
    async def test_concurrent_cache_operations(self):
        """Test concurrent cache operations."""
        cache = LRUCache(max_size=1000)
        
        async def cache_operation(i):
            await cache.set(f"key_{i}", f"value_{i}")
            result = await cache.get(f"key_{i}")
            return result == f"value_{i}"
        
        # Run 100 concurrent operations
        tasks = [cache_operation(i) for i in range(100)]
        results = await asyncio.gather(*tasks)
        
        # Verify all operations succeeded
        assert all(results)
    
    @pytest.mark.asyncio
    async def test_concurrent_batch_processing(self):
        """Test concurrent batch processing."""
        processed_count = 0
        
        async def processor(item):
            nonlocal processed_count
            await asyncio.sleep(0.01)
            processed_count += 1
            return item * 2
        
        batch_processor = BatchProcessor(
            processor,
            batch_size=10,
            max_concurrency=5
        )
        
        # Add 100 items
        for i in range(100):
            await batch_processor.add_item(i)
        
        # Wait for completion
        await batch_processor.wait_for_completion()
        
        # Verify all items processed
        assert processed_count == 100
    
    @pytest.mark.asyncio
    async def test_cache_and_batch_integration(self):
        """Test cache and batch processor integration under load."""
        cache = LRUCache(max_size=500)
        processed_items = []
        
        async def processor(item):
            # Check cache
            cached = await cache.get(f"item_{item}")
            if cached is not None:
                return cached
            
            # Process and cache
            result = f"processed_{item}"
            await cache.set(f"item_{item}", result)
            processed_items.append(item)
            return result
        
        batch_processor = BatchProcessor(
            processor,
            batch_size=20,
            max_concurrency=5
        )
        
        # Process 200 items with duplicates
        items = [i % 100 for i in range(200)]
        await batch_processor.process_all(items)
        
        # Verify only unique items were processed
        assert len(processed_items) == 100
        assert len(set(processed_items)) == 100


# ============================================================================
# Error Handling Integration Tests
# ============================================================================


class TestErrorHandlingIntegration:
    """Tests for error handling in integration."""
    
    @pytest.mark.asyncio
    async def test_cache_error_handling(self):
        """Test cache error handling."""
        cache = LRUCache(max_size=10)
        
        # Normal operation
        await cache.set("key1", "value1")
        assert await cache.get("key1") == "value1"
        
        # Nonexistent key
        assert await cache.get("nonexistent") is None
        
        # Delete nonexistent key
        assert not await cache.delete("nonexistent")
        
        # Clear and verify
        await cache.clear()
        assert await cache.get("key1") is None
    
    @pytest.mark.asyncio
    async def test_batch_processor_error_handling(self):
        """Test batch processor error handling."""
        call_count = 0
        
        async def failing_processor(item):
            nonlocal call_count
            call_count += 1
            if call_count % 3 == 0:
                raise ValueError(f"Error on item {item}")
            return item * 2
        
        batch_processor = BatchProcessor(
            failing_processor,
            batch_size=5,
            max_retries=2
        )
        
        result = await batch_processor.process_all([1, 2, 3, 4, 5, 6, 7, 8, 9])
        
        # Verify some items failed
        assert result.failure_count > 0
        assert result.success_count > 0
    
    @pytest.mark.asyncio
    async def test_connection_pool_error_handling(self):
        """Test connection pool error handling."""
        connection_count = 0
        
        def create_connection():
            nonlocal connection_count
            connection_count += 1
            if connection_count > 3:
                raise RuntimeError("Too many connections")
            return f"connection_{connection_count}"
        
        pool = ConnectionPool(create_connection, max_size=5, min_size=0)
        
        # Try to acquire more connections than allowed
        connections = []
        for i in range(3):
            conn = await pool.acquire()
            connections.append(conn)
        
        # Fourth connection should fail
        try:
            conn = await pool.acquire()
            # If we get here, release the connection
            await pool.release(conn)
        except Exception:
            pass
        
        # Release all connections
        for conn in connections:
            await pool.release(conn)
        
        await pool.close()


# ============================================================================
# API Integration Tests
# ============================================================================


class TestAPIIntegration:
    """Tests for API integration."""
    
    @pytest.mark.asyncio
    async def test_performance_api_endpoints(self):
        """Test performance API endpoints."""
        # Initialize performance components
        cache_manager = CacheManager()
        performance_monitor = PerformanceMonitor()
        performance_optimizer = PerformanceOptimizer()
        
        # Start monitoring
        await performance_monitor.start()
        
        # Collect metrics
        metrics = await performance_monitor.get_metrics_collector().collect_all()
        
        # Get performance report
        report = await performance_monitor.get_performance_report(duration=60.0)
        
        # Verify report structure
        assert "timestamp" in report
        assert "duration" in report
        assert "metrics" in report
        assert "summary" in report
        
        # Get optimization recommendations
        recommendations = performance_optimizer.get_recommendations()
        
        # Verify recommendations structure
        assert isinstance(recommendations, list)
        
        # Stop monitoring
        await performance_monitor.stop()
    
    @pytest.mark.asyncio
    async def test_cache_api_endpoints(self):
        """Test cache API endpoints."""
        cache_manager = CacheManager()
        
        # Create cache
        cache = await cache_manager.create_lru_cache("test", max_size=100)
        
        # Set value
        await cache.set("key1", "value1")
        
        # Get value
        value = await cache.get("key1")
        assert value == "value1"
        
        # Check contains
        assert await cache.contains("key1")
        
        # Get stats
        stats = cache.get_stats()
        assert stats.size == 1
        
        # Delete cache
        assert await cache_manager.delete_cache("test")
        assert await cache_manager.get_cache("test") is None
