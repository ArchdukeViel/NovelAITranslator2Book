"""Connection pooling for improved resource management."""

from __future__ import annotations

import asyncio
import inspect
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Generic, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class PoolConfig:
    """Configuration for connection pool."""

    min_size: int = 5  # Minimum pool size
    max_size: int = 20  # Maximum pool size
    timeout: float = 30.0  # Connection timeout
    idle_timeout: float = 300.0  # Close idle connections after this
    max_overflow: int = 10  # Allow this many overflow connections
    acquire_timeout: float = 10.0  # Timeout to get connection from pool


@dataclass
class PoolStats:
    """Statistics for connection pool."""

    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    overflow_connections: int = 0
    total_acquired: int = 0
    total_released: int = 0
    total_created: int = 0
    average_wait_time: float = 0.0


class PooledConnection(Generic[T]):
    """Wrapper for pooled connections."""

    def __init__(
        self,
        connection_id: str,
        connection: T,
        pool: ConnectionPool[T],
    ) -> None:
        self.connection_id = connection_id
        self.connection = connection
        self.pool = pool
        self.last_used: float = 0.0
        self.created_at: float = 0.0

    async def close(self) -> None:
        """Close the connection."""
        close_method = getattr(self.connection, "close", None)
        if not callable(close_method):
            return

        result = close_method()
        if inspect.isawaitable(result):
            await result


class ConnectionPool(Generic[T]):
    """Generic async connection pool."""

    def __init__(
        self,
        factory_func: Callable[[], Awaitable[T]],
        config: Optional[PoolConfig] = None,
    ) -> None:
        """Initialize connection pool.
        
        Args:
            factory_func: Async function to create new connections
            config: Pool configuration
        """
        self.factory_func = factory_func
        self.config = config or PoolConfig()
        
        # Connection queues
        self._available: asyncio.Queue[PooledConnection[T]] = asyncio.Queue()
        self._all_connections: dict[str, PooledConnection[T]] = {}
        self._overflow_connections: list[str] = []
        
        # Initialization
        self._initialized = False
        self._lock = asyncio.Lock()
        
        # Statistics
        self.stats = PoolStats()
        
        # Connection ID counter
        self._connection_counter = 0

    async def initialize(self) -> None:
        """Initialize the pool with minimum connections."""
        async with self._lock:
            if self._initialized:
                return
            
            logger.info(f"Initializing connection pool (min_size: {self.config.min_size})")
            
            for _ in range(self.config.min_size):
                await self._create_connection()
            
            self._initialized = True
            logger.info(f"Pool initialized with {self.config.min_size} connections")

    async def acquire(self) -> T:
        """Acquire a connection from the pool.
        
        Returns:
            Connection object
            
        Raises:
            TimeoutError if cannot acquire within timeout
        """
        if not self._initialized:
            await self.initialize()
        
        wait_start = asyncio.get_event_loop().time()
        
        try:
            # Try to get available connection
            pooled_conn = await asyncio.wait_for(
                self._available.get(),
                timeout=self.config.acquire_timeout,
            )
            
        except asyncio.TimeoutError:
            # No connections available, try to create overflow
            if len(self._overflow_connections) < self.config.max_overflow:
                logger.debug("Creating overflow connection")
                pooled_conn = await self._create_connection(overflow=True)
            else:
                logger.error("Connection pool exhausted")
                raise TimeoutError(
                    f"Cannot acquire connection within {self.config.acquire_timeout}s"
                )
        
        wait_time = asyncio.get_event_loop().time() - wait_start
        
        # Update statistics
        self.stats.total_acquired += 1
        self.stats.active_connections += 1
        self.stats.idle_connections = max(0, self.stats.idle_connections - 1)
        
        # Update average wait time
        prev_avg = self.stats.average_wait_time
        self.stats.average_wait_time = (
            (prev_avg * (self.stats.total_acquired - 1) + wait_time)
            / self.stats.total_acquired
        )
        
        logger.debug(
            f"Acquired connection {pooled_conn.connection_id} "
            f"(active: {self.stats.active_connections})"
        )
        
        # Mark as used
        pooled_conn.last_used = asyncio.get_event_loop().time()
        
        return pooled_conn.connection

    async def release(self, connection: T) -> None:
        """Release a connection back to the pool.
        
        Args:
            connection: Connection to release
        """
        # Find the pooled connection
        pooled_conn = None
        for conn in self._all_connections.values():
            if conn.connection == connection:
                pooled_conn = conn
                break
        
        if pooled_conn is None:
            logger.warning("Attempted to release unknown connection")
            return
        
        # Return to pool or close if overflow
        if pooled_conn.connection_id in self._overflow_connections:
            await pooled_conn.close()
            del self._all_connections[pooled_conn.connection_id]
            self._overflow_connections.remove(pooled_conn.connection_id)
            logger.debug(f"Closed overflow connection {pooled_conn.connection_id}")
        else:
            try:
                await asyncio.wait_for(
                    self._available.put(pooled_conn),
                    timeout=1.0,
                )
            except asyncio.TimeoutError:
                logger.warning("Queue full, closing connection")
                await pooled_conn.close()
                del self._all_connections[pooled_conn.connection_id]
        
        # Update statistics
        self.stats.total_released += 1
        self.stats.active_connections = max(0, self.stats.active_connections - 1)
        self.stats.idle_connections = self._available.qsize()
        
        logger.debug(
            f"Released connection {pooled_conn.connection_id} "
            f"(active: {self.stats.active_connections})"
        )

    async def close(self) -> None:
        """Close all connections in the pool."""
        logger.info("Closing connection pool")
        
        # Close all connections
        for pooled_conn in self._all_connections.values():
            try:
                await pooled_conn.close()
            except Exception as e:
                logger.error(f"Error closing connection: {e}")
        
        self._all_connections.clear()
        self._overflow_connections.clear()
        self._initialized = False
        
        logger.info("Connection pool closed")

    async def _create_connection(self, overflow: bool = False) -> PooledConnection[T]:
        """Create a new connection.
        
        Args:
            overflow: Whether this is an overflow connection
            
        Returns:
            PooledConnection wrapper
        """
        try:
            logger.debug("Creating new connection")
            connection = await self.factory_func()
            
            # Create wrapper
            self._connection_counter += 1
            conn_id = f"conn-{self._connection_counter}"
            pooled_conn = PooledConnection(conn_id, connection, self)
            pooled_conn.created_at = asyncio.get_event_loop().time()
            
            self._all_connections[conn_id] = pooled_conn
            
            if overflow:
                self._overflow_connections.append(conn_id)
            else:
                # Add to available queue
                await self._available.put(pooled_conn)
            
            self.stats.total_created += 1
            self.stats.total_connections = len(self._all_connections)
            
            logger.debug(f"Created connection {conn_id}")
            
            return pooled_conn
            
        except Exception as e:
            logger.error(f"Failed to create connection: {e}")
            raise

    def get_stats(self) -> PoolStats:
        """Get pool statistics.
        
        Returns:
            PoolStats
        """
        self.stats.total_connections = len(self._all_connections)
        self.stats.idle_connections = self._available.qsize()
        self.stats.active_connections = (
            self.stats.total_connections - self.stats.idle_connections
        )
        self.stats.overflow_connections = len(self._overflow_connections)
        
        return self.stats


class ContextManagedPool(Generic[T]):
    """Async context manager wrapper for connection pool."""

    def __init__(self, pool: ConnectionPool[T]):
        self.pool = pool
        self._connection: Optional[T] = None

    async def __aenter__(self) -> T:
        """Acquire connection on context enter."""
        self._connection = await self.pool.acquire()
        return self._connection

    async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Release connection on context exit."""
        if self._connection:
            await self.pool.release(self._connection)


def create_connection_pool(
    factory_func: Callable[[], Awaitable[T]],
    min_size: int = 5,
    max_size: int = 20,
) -> ConnectionPool[T]:
    """Create a connection pool.
    
    Args:
        factory_func: Async function to create connections
        min_size: Minimum pool size
        max_size: Maximum pool size
        
    Returns:
        ConnectionPool
    """
    config = PoolConfig(min_size=min_size, max_size=max_size)
    return ConnectionPool(factory_func, config)


async def with_pooled_connection(
    pool: ConnectionPool[T],
    func: Callable[[T], Awaitable[Any]],
) -> Any:
    """Execute function with pooled connection.
    
    Args:
        pool: Connection pool
        func: Async function that takes connection
        
    Returns:
        Function result
    """
    async with ContextManagedPool(pool) as conn:
        return await func(conn)
