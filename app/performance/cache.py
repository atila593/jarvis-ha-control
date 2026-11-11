"""
Caching module for performance optimization.
Implements LRU cache, TTL cache, and cache management.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Generic, Optional, TypeVar, Union

T = TypeVar("T")


class CacheEvictionPolicy(Enum):
    """Cache eviction policies."""
    LRU = "lru"
    LFU = "lfu"
    FIFO = "fifo"
    TTL = "ttl"


@dataclass
class CacheStats:
    """Cache statistics."""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    size: int = 0
    max_size: int = 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    @property
    def miss_rate(self) -> float:
        """Calculate miss rate."""
        total = self.hits + self.misses
        return self.misses / total if total > 0 else 0.0


@dataclass
class CacheItem(Generic[T]):
    """Cache item with value and metadata."""
    value: T
    timestamp: float = field(default_factory=time.time)
    ttl: Optional[float] = None
    access_count: int = 0
    
    def is_expired(self) -> bool:
        """Check if item is expired."""
        if self.ttl is None:
            return False
        return time.time() > self.timestamp + self.ttl


class LRUCache(Generic[T]):
    """
    Thread-safe LRU (Least Recently Used) cache.
    
    Attributes:
        max_size: Maximum number of items in cache
        cache: Dictionary storing cache items
        order: OrderedDict to track access order
        stats: Cache statistics
        lock: Async lock for thread safety
    """
    
    def __init__(self, max_size: int = 100):
        """
        Initialize LRU cache.
        
        Args:
            max_size: Maximum number of items in cache
        """
        self.max_size = max_size
        self.cache: Dict[str, CacheItem[T]] = {}
        self.order: OrderedDict[str, None] = OrderedDict()
        self.stats = CacheStats(max_size=max_size)
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[T]:
        """
        Get item from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found or expired
        """
        async with self._lock:
            if key not in self.cache:
                self.stats.misses += 1
                return None
            
            item = self.cache[key]
            
            if item.is_expired():
                del self.cache[key]
                del self.order[key]
                self.stats.misses += 1
                self.stats.evictions += 1
                return None
            
            self.order.move_to_end(key)
            item.access_count += 1
            self.stats.hits += 1
            return item.value
    
    async def set(self, key: str, value: T, ttl: Optional[float] = None) -> None:
        """
        Set item in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (optional)
        """
        async with self._lock:
            if key in self.cache:
                del self.order[key]
                self.stats.evictions += 1
            
            self.cache[key] = CacheItem(value=value, ttl=ttl)
            self.order[key] = None
            self.stats.size = len(self.cache)
            
            if len(self.cache) > self.max_size:
                await self._evict()
    
    async def _evict(self) -> None:
        """Evict least recently used items."""
        while len(self.cache) > self.max_size:
            oldest_key = next(iter(self.order))
            del self.cache[oldest_key]
            del self.order[oldest_key]
            self.stats.evictions += 1
            self.stats.size = len(self.cache)
    
    async def delete(self, key: str) -> bool:
        """
        Delete item from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if item was deleted, False otherwise
        """
        async with self._lock:
            if key in self.cache:
                del self.cache[key]
                del self.order[key]
                self.stats.size = len(self.cache)
                return True
            return False
    
    async def clear(self) -> None:
        """Clear all items from cache."""
        async with self._lock:
            self.cache.clear()
            self.order.clear()
            self.stats.size = 0
    
    async def contains(self, key: str) -> bool:
        """
        Check if key exists in cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if key exists and is not expired
        """
        async with self._lock:
            if key not in self.cache:
                return False
            return not self.cache[key].is_expired()
    
    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        return self.stats


class TTLCache(Generic[T]):
    """
    Time-based cache with automatic expiration.
    
    Attributes:
        default_ttl: Default time to live for items
        cache: Dictionary storing cache items
        stats: Cache statistics
        cleanup_interval: Interval for cleanup task
        cleanup_task: Background cleanup task
    """
    
    def __init__(self, default_ttl: float = 300.0, cleanup_interval: float = 60.0):
        """
        Initialize TTL cache.
        
        Args:
            default_ttl: Default TTL in seconds
            cleanup_interval: Cleanup interval in seconds
        """
        self.default_ttl = default_ttl
        self.cache: Dict[str, CacheItem[T]] = {}
        self.stats = CacheStats()
        self.cleanup_interval = cleanup_interval
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
    
    async def start_cleanup(self) -> None:
        """Start background cleanup task."""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def stop_cleanup(self) -> None:
        """Stop background cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
    
    async def _cleanup_loop(self) -> None:
        """Background cleanup loop."""
        while True:
            await asyncio.sleep(self.cleanup_interval)
            await self._cleanup_expired()
    
    async def _cleanup_expired(self) -> None:
        """Remove expired items from cache."""
        async with self._lock:
            expired_keys = [
                key for key, item in self.cache.items() 
                if item.is_expired()
            ]
            for key in expired_keys:
                del self.cache[key]
                self.stats.evictions += 1
            self.stats.size = len(self.cache)
    
    async def get(self, key: str) -> Optional[T]:
        """
        Get item from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found or expired
        """
        async with self._lock:
            if key not in self.cache:
                self.stats.misses += 1
                return None
            
            item = self.cache[key]
            
            if item.is_expired():
                del self.cache[key]
                self.stats.misses += 1
                self.stats.evictions += 1
                return None
            
            item.access_count += 1
            self.stats.hits += 1
            return item.value
    
    async def set(self, key: str, value: T, ttl: Optional[float] = None) -> None:
        """
        Set item in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (uses default_ttl if not specified)
        """
        async with self._lock:
            self.cache[key] = CacheItem(value=value, ttl=ttl or self.default_ttl)
            self.stats.size = len(self.cache)
    
    async def delete(self, key: str) -> bool:
        """
        Delete item from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if item was deleted, False otherwise
        """
        async with self._lock:
            if key in self.cache:
                del self.cache[key]
                self.stats.size = len(self.cache)
                return True
            return False
    
    async def clear(self) -> None:
        """Clear all items from cache."""
        async with self._lock:
            self.cache.clear()
            self.stats.size = 0


class CacheManager:
    """
    Centralized cache manager for multiple cache instances.
    
    Provides a unified interface for managing different types of caches
    with different configurations.
    """
    
    def __init__(self):
        """Initialize cache manager."""
        self.caches: Dict[str, Union[LRUCache, TTLCache]] = {}
        self._lock = asyncio.Lock()
    
    async def create_lru_cache(
        self, 
        name: str, 
        max_size: int = 100
    ) -> LRUCache:
        """
        Create or get an LRU cache.
        
        Args:
            name: Cache name
            max_size: Maximum size of cache
            
        Returns:
            LRUCache instance
        """
        async with self._lock:
            if name not in self.caches:
                self.caches[name] = LRUCache(max_size=max_size)
            return self.caches[name]
    
    async def create_ttl_cache(
        self,
        name: str,
        default_ttl: float = 300.0,
        cleanup_interval: float = 60.0
    ) -> TTLCache:
        """
        Create or get a TTL cache.
        
        Args:
            name: Cache name
            default_ttl: Default TTL in seconds
            cleanup_interval: Cleanup interval in seconds
            
        Returns:
            TTLCache instance
        """
        async with self._lock:
            if name not in self.caches:
                cache = TTLCache(default_ttl=default_ttl, cleanup_interval=cleanup_interval)
                await cache.start_cleanup()
                self.caches[name] = cache
            return self.caches[name]
    
    async def get_cache(self, name: str) -> Optional[Union[LRUCache, TTLCache]]:
        """
        Get a cache by name.
        
        Args:
            name: Cache name
            
        Returns:
            Cache instance or None if not found
        """
        async with self._lock:
            return self.caches.get(name)
    
    async def delete_cache(self, name: str) -> bool:
        """
        Delete a cache.
        
        Args:
            name: Cache name
            
        Returns:
            True if cache was deleted, False otherwise
        """
        async with self._lock:
            if name in self.caches:
                cache = self.caches[name]
                if isinstance(cache, TTLCache):
                    await cache.stop_cleanup()
                await cache.clear()
                del self.caches[name]
                return True
            return False
    
    async def clear_all(self) -> None:
        """Clear all caches."""
        async with self._lock:
            for name, cache in self.caches.items():
                if isinstance(cache, TTLCache):
                    await cache.stop_cleanup()
                await cache.clear()
            self.caches.clear()
    
    def get_stats(self) -> Dict[str, CacheStats]:
        """Get statistics for all caches."""
        return {name: cache.get_stats() for name, cache in self.caches.items()}


def generate_cache_key(prefix: str, *args: Any, **kwargs: Any) -> str:
    """
    Generate a cache key from arguments.
    
    Args:
        prefix: Key prefix
        *args: Positional arguments
        **kwargs: Keyword arguments
        
    Returns:
        Generated cache key
    """
    key_data = {"prefix": prefix, "args": args, "kwargs": kwargs}
    key_str = json.dumps(key_data, sort_keys=True, default=str)
    return hashlib.md5(key_str.encode()).hexdigest()


async def cached(
    cache: Union[LRUCache, TTLCache],
    key: str,
    ttl: Optional[float] = None
):
    """
    Decorator for caching async function results.
    
    Args:
        cache: Cache instance
        key: Cache key or function to generate key
        ttl: Time to live in seconds
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            actual_key = key if callable(key) else key
            if callable(actual_key):
                actual_key = actual_key(*args, **kwargs)
            
            cached_value = await cache.get(actual_key)
            if cached_value is not None:
                return cached_value
            
            result = await func(*args, **kwargs)
            await cache.set(actual_key, result, ttl)
            return result
        
        return wrapper
    return decorator
