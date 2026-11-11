"""
Batch processing module for efficient handling of multiple operations.
Provides batch processing, queue management, and bulk operations.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union

logger = logging.getLogger(__name__)

T = TypeVar("T")
R = TypeVar("R")


class BatchStatus(Enum):
    """Batch processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class BatchResult(Generic[R]):
    """Result of a batch operation."""
    status: BatchStatus
    results: List[R] = field(default_factory=list)
    errors: List[Exception] = field(default_factory=list)
    start_time: float = field(default_factory=asyncio.get_event_loop().time)
    end_time: float = 0.0
    
    @property
    def duration(self) -> float:
        """Calculate duration in seconds."""
        return self.end_time - self.start_time if self.end_time > 0 else 0.0
    
    @property
    def success_count(self) -> int:
        """Count successful results."""
        return len(self.results)
    
    @property
    def failure_count(self) -> int:
        """Count failed operations."""
        return len(self.errors)
    
    @property
    def is_successful(self) -> bool:
        """Check if batch was successful."""
        return self.status == BatchStatus.COMPLETED and self.failure_count == 0


@dataclass
class BatchItem(Generic[T]):
    """Item to be processed in a batch."""
    data: T
    priority: int = 0
    retry_count: int = 0
    max_retries: int = 3
    timeout: float = 30.0
    
    @property
    def should_retry(self) -> bool:
        """Check if item should be retried."""
        return self.retry_count < self.max_retries


class BatchProcessor(Generic[T, R]):
    """
    Batch processor for efficient processing of multiple items.
    
    Processes items in batches with configurable batch size,
    concurrency, and retry logic.
    """
    
    def __init__(
        self,
        processor: Callable[[T], R],
        batch_size: int = 10,
        max_concurrency: int = 5,
        timeout: float = 30.0,
        retry_delay: float = 1.0
    ):
        """
        Initialize batch processor.
        
        Args:
            processor: Function to process individual items
            batch_size: Number of items per batch
            max_concurrency: Maximum concurrent batches
            timeout: Timeout for each item in seconds
            retry_delay: Delay between retries in seconds
        """
        self._processor = processor
        self.batch_size = batch_size
        self.max_concurrency = max_concurrency
        self.timeout = timeout
        self.retry_delay = retry_delay
        
        self._queue: asyncio.Queue[BatchItem[T]] = asyncio.Queue()
        self._active_batches: Dict[str, asyncio.Task] = {}
        self._processing = False
        self._stats = {
            "total_processed": 0,
            "total_failed": 0,
            "total_retries": 0,
            "active_batches": 0
        }
        self._lock = asyncio.Lock()
    
    async def add_item(self, data: T, priority: int = 0) -> None:
        """
        Add an item to the processing queue.
        
        Args:
            data: Item data
            priority: Item priority (higher = more important)
        """
        item = BatchItem(data=data, priority=priority)
        await self._queue.put(item)
        
        if not self._processing:
            await self._start_processing()
    
    async def add_batch(self, items: List[T], priority: int = 0) -> None:
        """
        Add multiple items to the processing queue.
        
        Args:
            items: List of item data
            priority: Priority for all items
        """
        for item in items:
            await self.add_item(item, priority)
    
    async def _start_processing(self) -> None:
        """Start processing items from the queue."""
        self._processing = True
        
        while True:
            if self._queue.empty():
                self._processing = False
                break
            
            batch = []
            for _ in range(min(self.batch_size, self._queue.qsize())):
                if not self._queue.empty():
                    item = await self._queue.get()
                    batch.append(item)
            
            if batch:
                async with self._lock:
                    if len(self._active_batches) >= self.max_concurrency:
                        await asyncio.sleep(0.1)
                        continue
                
                task = asyncio.create_task(self._process_batch(batch))
                async with self._lock:
                    self._active_batches[task.get_name()] = task
    
    async def _process_batch(self, batch: List[BatchItem[T]]) -> BatchResult[R]:
        """
        Process a batch of items.
        
        Args:
            batch: List of items to process
            
        Returns:
            BatchResult with results and errors
        """
        result = BatchResult[R](status=BatchStatus.PROCESSING)
        
        async def process_item(item: BatchItem[T]) -> Optional[R]:
            """Process a single item with retry logic."""
            last_error = None
            
            for attempt in range(item.max_retries + 1):
                try:
                    async with asyncio.timeout(item.timeout):
                        return await self._processor(item.data)
                except asyncio.TimeoutError:
                    last_error = asyncio.TimeoutError(f"Timeout after {item.timeout}s")
                except Exception as e:
                    last_error = e
                
                if attempt < item.max_retries:
                    item.retry_count += 1
                    self._stats["total_retries"] += 1
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
            
            if last_error:
                result.errors.append(last_error)
                self._stats["total_failed"] += 1
            return None
        
        tasks = [process_item(item) for item in batch]
        
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for r in results:
                if isinstance(r, Exception):
                    result.errors.append(r)
                elif r is not None:
                    result.results.append(r)
            
            result.status = BatchStatus.COMPLETED
            self._stats["total_processed"] += len(batch)
            
        except Exception as e:
            result.status = BatchStatus.FAILED
            result.errors.append(e)
        finally:
            result.end_time = asyncio.get_event_loop().time()
            async with self._lock:
                del self._active_batches[asyncio.current_task().get_name()]
        
        return result
    
    async def process_all(self, items: List[T]) -> BatchResult[R]:
        """
        Process all items and wait for completion.
        
        Args:
            items: List of items to process
            
        Returns:
            Aggregate BatchResult
        """
        aggregate = BatchResult[R](status=BatchStatus.PENDING)
        
        for item in items:
            await self.add_item(item)
        
        while not self._queue.empty() or self._active_batches:
            await asyncio.sleep(0.1)
        
        aggregate.status = BatchStatus.COMPLETED
        aggregate.results = [r for batch in self._active_batches.values() 
                            for r in batch.result().results]
        aggregate.errors = [e for batch in self._active_batches.values() 
                           for e in batch.result().errors]
        aggregate.end_time = asyncio.get_event_loop().time()
        
        return aggregate
    
    async def wait_for_completion(self) -> None:
        """Wait for all pending items to be processed."""
        while not self._queue.empty() or self._active_batches:
            await asyncio.sleep(0.1)
    
    async def clear(self) -> None:
        """Clear the processing queue."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        
        for task in self._active_batches.values():
            task.cancel()
        
        self._active_batches.clear()
        self._processing = False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get processor statistics."""
        return self._stats.copy()


class ActionBatcher:
    """
    Specialized batch processor for Home Assistant actions.
    
    Groups actions by domain, entity, or service for efficient
    batch execution.
    """
    
    def __init__(
        self,
        batch_size: int = 5,
        max_concurrency: int = 3,
        timeout: float = 10.0
    ):
        """
        Initialize action batcher.
        
        Args:
            batch_size: Maximum actions per batch
            max_concurrency: Maximum concurrent batches
            timeout: Timeout per action in seconds
        """
        self.batch_size = batch_size
        self.max_concurrency = max_concurrency
        self.timeout = timeout
        
        self._queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        self._active_tasks: List[asyncio.Task] = []
        self._stats = {
            "total_actions": 0,
            "batches_processed": 0,
            "actions_per_second": 0.0
        }
        self._start_time = asyncio.get_event_loop().time()
    
    async def add_action(
        self,
        domain: str,
        service: str,
        entity_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        priority: int = 0
    ) -> None:
        """
        Add an action to the batch queue.
        
        Args:
            domain: Home Assistant domain (e.g., "light", "switch")
            service: Service to call (e.g., "turn_on", "turn_off")
            entity_id: Target entity ID
            data: Additional service data
            priority: Action priority
        """
        action = {
            "domain": domain,
            "service": service,
            "entity_id": entity_id,
            "data": data or {},
            "priority": priority,
            "timestamp": asyncio.get_event_loop().time()
        }
        await self._queue.put(action)
    
    async def process_batch(
        self,
        ha_client: Any
    ) -> BatchResult[Dict[str, Any]]:
        """
        Process a batch of actions.
        
        Args:
            ha_client: Home Assistant client for executing actions
            
        Returns:
            BatchResult with action results
        """
        result = BatchResult[Dict[str, Any]](status=BatchStatus.PROCESSING)
        batch = []
        
        for _ in range(min(self.batch_size, self._queue.qsize())):
            if not self._queue.empty():
                action = await self._queue.get()
                batch.append(action)
        
        if not batch:
            result.status = BatchStatus.COMPLETED
            return result
        
        async def execute_action(action: Dict[str, Any]) -> Dict[str, Any]:
            """Execute a single action."""
            try:
                service_data = action["data"].copy()
                if action["entity_id"]:
                    service_data["entity_id"] = action["entity_id"]
                
                method = getattr(ha_client, f"{action['domain']}_{action['service']}")
                async with asyncio.timeout(self.timeout):
                    response = await method(**service_data)
                    return {"action": action, "status": "success", "response": response}
            except Exception as e:
                return {"action": action, "status": "failed", "error": str(e)}
        
        tasks = [execute_action(action) for action in batch]
        
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for r in results:
                if isinstance(r, Exception):
                    result.errors.append(r)
                else:
                    result.results.append(r)
            
            result.status = BatchStatus.COMPLETED
            self._stats["total_actions"] += len(batch)
            self._stats["batches_processed"] += 1
            
        except Exception as e:
            result.status = BatchStatus.FAILED
            result.errors.append(e)
        finally:
            result.end_time = asyncio.get_event_loop().time()
        
        return result
    
    async def process_all(
        self,
        ha_client: Any
    ) -> BatchResult[Dict[str, Any]]:
        """
        Process all queued actions.
        
        Args:
            ha_client: Home Assistant client
            
        Returns:
            Aggregate result for all actions
        """
        aggregate = BatchResult[Dict[str, Any]](status=BatchStatus.PENDING)
        
        while not self._queue.empty() or self._active_tasks:
            batch_result = await self.process_batch(ha_client)
            aggregate.results.extend(batch_result.results)
            aggregate.errors.extend(batch_result.errors)
            
            if batch_result.status != BatchStatus.COMPLETED:
                aggregate.status = BatchStatus.FAILED
        
        aggregate.status = BatchStatus.COMPLETED
        aggregate.end_time = asyncio.get_event_loop().time()
        
        elapsed = aggregate.end_time - self._start_time
        if elapsed > 0:
            self._stats["actions_per_second"] = self._stats["total_actions"] / elapsed
        
        return aggregate
    
    async def clear(self) -> None:
        """Clear the action queue."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        
        for task in self._active_tasks:
            task.cancel()
        
        self._active_tasks.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get batcher statistics."""
        return self._stats.copy()
