#!/usr/bin/env python3
"""
Database Connection Pool Manager

Provides thread-safe connection pooling for PostgreSQL and MySQL.
Uses psycopg2.pool for PostgreSQL and SQLAlchemy for MySQL.
"""

import os
import logging
import threading
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Pool configuration from environment
POOL_MIN_CONN = int(os.getenv('DB_POOL_MIN', 2))
POOL_MAX_CONN = int(os.getenv('DB_POOL_MAX', 10))

# Global pool instance
_pool = None
_pool_lock = threading.Lock()


def _get_db_type():
    """Get database type from environment"""
    return os.getenv('DB_TYPE', 'postgresql')


def _create_postgresql_pool():
    """Create PostgreSQL connection pool using psycopg2"""
    from psycopg2 import pool
    from config.database import get_db_config

    db_config = get_db_config('postgresql')
    return pool.ThreadedConnectionPool(
        minconn=POOL_MIN_CONN,
        maxconn=POOL_MAX_CONN,
        **db_config
    )


def _create_mysql_pool():
    """Create MySQL connection pool using SQLAlchemy"""
    from sqlalchemy import create_engine
    from sqlalchemy.pool import QueuePool
    from config.database import get_connection_string

    connection_string = get_connection_string('mysql')
    return create_engine(
        connection_string,
        poolclass=QueuePool,
        pool_size=POOL_MIN_CONN,
        max_overflow=POOL_MAX_CONN - POOL_MIN_CONN,
        pool_pre_ping=True,  # Verify connections before use
        pool_recycle=3600,   # Recycle connections after 1 hour
    )


def init_pool():
    """
    Initialize the database connection pool.
    Call this once at application startup.
    """
    global _pool

    with _pool_lock:
        if _pool is not None:
            logger.warning("Pool already initialized")
            return

        db_type = _get_db_type()
        try:
            if db_type == 'postgresql':
                _pool = _create_postgresql_pool()
                logger.info(f"PostgreSQL pool initialized (min={POOL_MIN_CONN}, max={POOL_MAX_CONN})")
            elif db_type == 'mysql':
                _pool = _create_mysql_pool()
                logger.info(f"MySQL pool initialized (size={POOL_MIN_CONN}, overflow={POOL_MAX_CONN - POOL_MIN_CONN})")
            else:
                raise ValueError(f"Unsupported DB_TYPE: {db_type}")
        except Exception as e:
            logger.error(f"Failed to initialize connection pool: {e}")
            raise


def close_pool():
    """
    Close the connection pool and release all connections.
    Call this at application shutdown.
    """
    global _pool

    with _pool_lock:
        if _pool is None:
            return

        db_type = _get_db_type()
        try:
            if db_type == 'postgresql':
                _pool.closeall()
            elif db_type == 'mysql':
                _pool.dispose()
            logger.info("Connection pool closed")
        except Exception as e:
            logger.error(f"Error closing pool: {e}")
        finally:
            _pool = None


class PooledConnection:
    """
    Wrapper for pooled connections that returns to pool on close().

    This allows existing code using conn.close() to work with pooling.
    """

    def __init__(self, conn, pool, db_type):
        self._conn = conn
        self._pool = pool
        self._db_type = db_type
        self._closed = False

    def close(self):
        """Return connection to pool instead of closing"""
        if self._closed or self._conn is None:
            return

        try:
            if self._db_type == 'postgresql':
                # Rollback any uncommitted transaction before returning to pool
                try:
                    self._conn.rollback()
                except Exception:
                    pass
                self._pool.putconn(self._conn)
            elif self._db_type == 'mysql':
                self._conn.close()  # SQLAlchemy returns to pool on close
            self._closed = True
        except Exception as e:
            logger.error(f"Error returning connection to pool: {e}")

    def cursor(self, *args, **kwargs):
        """Pass through to underlying connection"""
        return self._conn.cursor(*args, **kwargs)

    def commit(self):
        """Pass through to underlying connection"""
        return self._conn.commit()

    def rollback(self):
        """Pass through to underlying connection"""
        return self._conn.rollback()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def __getattr__(self, name):
        """Pass through any other attributes to underlying connection"""
        return getattr(self._conn, name)


def get_connection():
    """
    Get a connection from the pool.

    Returns:
        PooledConnection wrapper or None if pool not initialized

    Usage:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT ...")
            conn.commit()
        finally:
            conn.close()  # Returns to pool, doesn't actually close
    """
    global _pool

    if _pool is None:
        # Lazy initialization if not done at startup
        try:
            init_pool()
        except Exception as e:
            logger.error(f"Failed to lazy-init pool: {e}")
            return None

    db_type = _get_db_type()
    try:
        if db_type == 'postgresql':
            conn = _pool.getconn()
            return PooledConnection(conn, _pool, db_type)
        elif db_type == 'mysql':
            conn = _pool.connect()
            return PooledConnection(conn, _pool, db_type)
    except Exception as e:
        logger.error(f"Failed to get connection from pool: {e}")
        return None


def return_connection(conn):
    """
    Return a connection to the pool.

    Args:
        conn: The connection to return (PooledConnection wrapper or raw connection)
    """
    global _pool

    if conn is None or _pool is None:
        return

    # Handle PooledConnection wrapper - just call close() which returns to pool
    if isinstance(conn, PooledConnection):
        conn.close()
        return

    db_type = _get_db_type()
    try:
        if db_type == 'postgresql':
            _pool.putconn(conn)
        elif db_type == 'mysql':
            conn.close()  # SQLAlchemy returns to pool on close
    except Exception as e:
        logger.error(f"Failed to return connection to pool: {e}")


@contextmanager
def get_db_connection():
    """
    Context manager for database connections.

    Usage:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ...")

    Automatically returns connection to pool when done.
    """
    conn = get_connection()
    try:
        yield conn
    finally:
        return_connection(conn)


def get_pool_status():
    """
    Get current pool status for monitoring.

    Returns:
        dict with pool statistics
    """
    global _pool

    if _pool is None:
        return {'status': 'not_initialized'}

    db_type = _get_db_type()

    if db_type == 'postgresql':
        # psycopg2 pool doesn't expose detailed stats easily
        return {
            'status': 'active',
            'type': 'postgresql',
            'min_connections': POOL_MIN_CONN,
            'max_connections': POOL_MAX_CONN,
        }
    elif db_type == 'mysql':
        pool_obj = _pool.pool
        return {
            'status': 'active',
            'type': 'mysql',
            'pool_size': pool_obj.size(),
            'checked_in': pool_obj.checkedin(),
            'checked_out': pool_obj.checkedout(),
            'overflow': pool_obj.overflow(),
        }

    return {'status': 'unknown'}
