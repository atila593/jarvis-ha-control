"""
Connection pooling module for database and HTTP connections.
Provides efficient connection management and reuse.
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional, TypeVar, Union

import aiohttp

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class ConnectionPoolStats:
    """Connection pool statistics."""
    total_connections: int = 0
    available_connections: int = 0
    in_use_connections: int = 0
    max_connections: int = 0
    wait_time_total: float = 0.0
    wait_time_count: int = 0
    
    @property
    def avg_wait_time(self) -> float:
        """Calculate average wait time."""
        return self.wait_time_total / self.wait_time_count if self.wait_time_count > 0 else 0.0
    
    @property
    def utilization_rate(self) -> float:
        """Calculate connection utilization rate."""
        return self.in_use_connections / self.max_connections if self.max_connections > 0 else 0.0


class ConnectionPool(Generic[T]):
    """
    Generic connection pool.
    
    Manages a pool of reusable connections with configurable size limits.
    """
    
    def __init__(
        self,
        create_connection: Callable[[], T],
        max_size: int = 10,
        min_size: int = 2,
        max_wait_time: float = 30.0,
        validation_interval: float = 60.0
    ):
        """
        Initialize connection pool.
        
        Args:
            create_connection: Function to create a new connection
            max_size: Maximum number of connections in pool
            min_size: Minimum number of connections to maintain
            max_wait_time: Maximum time to wait for a connection
            validation_interval: Interval for connection validation
        """
        self._create_connection = create_connection
        self.max_size = max_size
        self.min_size = min_size
        self.max_wait_time = max_wait_time
        self.validation_interval = validation_interval
        
        self._pool: List[T] = []
        self._in_use: Dict[T, float] = {}
        self._stats = ConnectionPoolStats(max_connections=max_size)
        self._lock = asyncio.Lock()
        self._condition = asyncio.Condition(self._lock)
        self._validation_task: Optional[asyncio.Task] = None
        self._closed = False
    
    async def initialize(self) -> None:
        """Initialize pool with minimum connections."""
        async with self._lock:
            for _ in range(self.min_size):
                try:
                    conn = self._create_connection()
                    self._pool.append(conn)
                    self._stats.total_connections += 1
                    self._stats.available_connections += 1
                except Exception as e:
                    logger.error(f"Failed to create connection: {e}")
                    break
    
    async def acquire(self) -> T:
        """
        Acquire a connection from the pool.
        
        Returns:
            Connection from pool
            
        Raises:
            asyncio.TimeoutError: If wait time exceeds max_wait_time
        """
        if self._closed:
            raise RuntimeError("Connection pool is closed")
        
        start_time = asyncio.get_event_loop().time()
        
        async with self._condition:
            while True:
                if self._pool:
                    conn = self._pool.pop()
                    self._in_use[conn] = start_time
                    self._stats.in_use_connections += 1
                    self._stats.available_connections -= 1
                    return conn
                
                if len(self._in_use) >= self.max_size:
                    elapsed = asyncio.get_event_loop().time() - start_time
                    if elapsed >= self.max_wait_time:
                        raise asyncio.TimeoutError(
                            f"Timeout waiting for connection after {elapsed:.2f}s"
                        )
                    await self._condition.wait()
                else:
                    try:
                        conn = self._create_connection()
                        self._in_use[conn] = start_time
                        self._stats.total_connections += 1
                        self._stats.in_use_connections += 1
                        return conn
                    except Exception as e:
                        logger.error(f"Failed to create connection: {e}")
                        elapsed = asyncio.get_event_loop().time() - start_time
                        if elapsed >= self.max_wait_time:
                            raise asyncio.TimeoutError(
                                f"Timeout waiting for connection after {elapsed:.2f}s"
                            )
                        await self._condition.wait()
    
    async def release(self, connection: T) -> None:
        """
        Release a connection back to the pool.
        
        Args:
            connection: Connection to release
        """
        if self._closed:
            try:
                self._close_connection(connection)
            except Exception as e:
                logger.error(f"Failed to close connection: {e}")
            return
        
        async with self._lock:
            if connection not in self._in_use:
                logger.warning(f"Connection not in use: {connection}")
                return
            
            del self._in_use[connection]
            self._stats.in_use_connections -= 1
            
            if len(self._pool) < self.max_size:
                self._pool.append(connection)
                self._stats.available_connections += 1
            else:
                try:
                    self._close_connection(connection)
                    self._stats.total_connections -= 1
                except Exception as e:
                    logger.error(f"Failed to close connection: {e}")
            
            self._condition.notify()
    
    async def invalidate(self, connection: T) -> None:
        """
        Invalidate a connection.
        
        Args:
            connection: Connection to invalidate
        """
        async with self._lock:
            if connection in self._in_use:
                del self._in_use[connection]
                self._stats.in_use_connections -= 1
            elif connection in self._pool:
                self._pool.remove(connection)
                self._stats.available_connections -= 1
                self._stats.total_connections -= 1
            
            try:
                self._close_connection(connection)
            except Exception as e:
                logger.error(f"Failed to close connection: {e}")
    
    def _close_connection(self, connection: T) -> None:
        """Close a connection."""
        if hasattr(connection, "close"):
            connection.close()
        elif hasattr(connection, "__aexit__"):
            import asyncio
            asyncio.run(connection.__aexit__(None, None, None))
    
    async def clear(self) -> None:
        """Clear all connections from pool."""
        async with self._lock:
            for conn in self._pool + list(self._in_use.keys()):
                try:
                    self._close_connection(conn)
                except Exception as e:
                    logger.error(f"Failed to close connection: {e}")
            
            self._pool.clear()
            self._in_use.clear()
            self._stats = ConnectionPoolStats(max_connections=self.max_size)
    
    async def close(self) -> None:
        """Close the connection pool."""
        self._closed = True
        
        if self._validation_task:
            self._validation_task.cancel()
            try:
                await self._validation_task
            except asyncio.CancelledError:
                pass
        
        await self.clear()
    
    def get_stats(self) -> ConnectionPoolStats:
        """Get pool statistics."""
        return self._stats
    
    async def __aenter__(self) -> "ConnectionPool[T]":
        """Async context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()


class DatabaseConnectionPool(ConnectionPool[sqlite3.Connection]):
    """
    Connection pool for SQLite database connections.
    """
    
    def __init__(
        self,
        database_path: str,
        max_size: int = 10,
        min_size: int = 2,
        max_wait_time: float = 30.0,
        check_same_thread: bool = False
    ):
        """
        Initialize database connection pool.
        
        Args:
            database_path: Path to SQLite database
            max_size: Maximum number of connections
            min_size: Minimum number of connections
            max_wait_time: Maximum wait time for connection
            check_same_thread: SQLite check_same_thread parameter
        """
        self.database_path = database_path
        self.check_same_thread = check_same_thread
        
        super().__init__(
            create_connection=lambda: sqlite3.connect(
                database_path,
                check_same_thread=check_same_thread
            ),
            max_size=max_size,
            min_size=min_size,
            max_wait_time=max_wait_time
        )
    
    async def execute(
        self,
        query: str,
        params: tuple = (),
        fetch: bool = False
    ) -> Optional[List[sqlite3.Row]]:
        """
        Execute a query using a connection from the pool.
        
        Args:
            query: SQL query
            params: Query parameters
            fetch: Whether to fetch results
            
        Returns:
            Query results if fetch=True, None otherwise
        """
        conn = await self.acquire()
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            
            if fetch:
                return cursor.fetchall()
            
            conn.commit()
            return None
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            await self.release(conn)


class HTTPConnectionPool:
    """
    Connection pool for HTTP connections using aiohttp.
    
    Manages a pool of aiohttp ClientSession instances for efficient
    HTTP request handling.
    """
    
    def __init__(
        self,
        max_connections: int = 100,
        connector_limit: int = 10,
        timeout: float = 30.0,
        headers: Optional[Dict[str, str]] = None
    ):
        """
        Initialize HTTP connection pool.
        
        Args:
            max_connections: Maximum total connections
            connector_limit: Maximum connections per host
            timeout: Request timeout in seconds
            headers: Default headers for requests
        """
        self.max_connections = max_connections
        self.connector_limit = connector_limit
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.headers = headers or {}
        
        self._sessions: List[aiohttp.ClientSession] = []
        self._in_use: List[aiohttp.ClientSession] = []
        self._stats = ConnectionPoolStats(max_connections=max_connections)
        self._lock = asyncio.Lock()
        self._closed = False
    
    async def _create_session(self) -> aiohttp.ClientSession:
        """Create a new aiohttp session."""
        connector = aiohttp.TCPConnector(limit=self.connector_limit)
        return aiohttp.ClientSession(
            timeout=self.timeout,
            headers=self.headers,
            connector=connector
        )
    
    async def acquire(self) -> aiohttp.ClientSession:
        """
        Acquire an HTTP session from the pool.
        
        Returns:
            aiohttp ClientSession
        """
        if self._closed:
            raise RuntimeError("HTTP connection pool is closed")
        
        async with self._lock:
            if self._sessions:
                session = self._sessions.pop()
                self._in_use.append(session)
                self._stats.in_use_connections += 1
                self._stats.available_connections -= 1
                return session
            
            if len(self._in_use) >= self.max_connections:
                raise RuntimeError("Maximum connections reached")
            
            session = await self._create_session()
            self._in_use.append(session)
            self._stats.total_connections += 1
            self._stats.in_use_connections += 1
            return session
    
    async def release(self, session: aiohttp.ClientSession) -> None:
        """
        Release an HTTP session back to the pool.
        
        Args:
            session: Session to release
        """
        if self._closed:
            await session.close()
            return
        
        async with self._lock:
            if session in self._in_use:
                self._in_use.remove(session)
                self._stats.in_use_connections -= 1
                
                if len(self._sessions) < self.max_connections:
                    self._sessions.append(session)
                    self._stats.available_connections += 1
                else:
                    await session.close()
                    self._stats.total_connections -= 1
    
    async def request(
        self,
        method: str,
        url: str,
        **kwargs: Any
    ) -> aiohttp.ClientResponse:
        """
        Make an HTTP request using a connection from the pool.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            **kwargs: Additional arguments for session.request()
            
        Returns:
            aiohttp ClientResponse
        """
        session = await self.acquire()
        try:
            response = await session.request(method, url, **kwargs)
            return response
        except Exception as e:
            logger.error(f"HTTP request failed: {e}")
            raise
        finally:
            await self.release(session)
    
    async def get(
        self,
        url: str,
        **kwargs: Any
    ) -> aiohttp.ClientResponse:
        """HTTP GET request."""
        return await self.request("GET", url, **kwargs)
    
    async def post(
        self,
        url: str,
        **kwargs: Any
    ) -> aiohttp.ClientResponse:
        """HTTP POST request."""
        return await self.request("POST", url, **kwargs)
    
    async def put(
        self,
        url: str,
        **kwargs: Any
    ) -> aiohttp.ClientResponse:
        """HTTP PUT request."""
        return await self.request("PUT", url, **kwargs)
    
    async def delete(
        self,
        url: str,
        **kwargs: Any
    ) -> aiohttp.ClientResponse:
        """HTTP DELETE request."""
        return await self.request("DELETE", url, **kwargs)
    
    async def clear(self) -> None:
        """Clear all sessions from pool."""
        async with self._lock:
            for session in self._sessions + self._in_use:
                try:
                    await session.close()
                except Exception as e:
                    logger.error(f"Failed to close session: {e}")
            
            self._sessions.clear()
            self._in_use.clear()
            self._stats = ConnectionPoolStats(max_connections=self.max_connections)
    
    async def close(self) -> None:
        """Close the HTTP connection pool."""
        self._closed = True
        await self.clear()
    
    def get_stats(self) -> ConnectionPoolStats:
        """Get pool statistics."""
        return self._stats
    
    async def __aenter__(self) -> "HTTPConnectionPool":
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()
