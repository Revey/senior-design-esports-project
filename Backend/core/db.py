"""Shared PostgreSQL connection pool (psycopg2.ThreadedConnectionPool).

All database access across the backend goes through get_conn() / get_cursor().
The pool is lazy-initialized on first use and reads DATABASE_URL from the
environment. DigitalOcean Managed Postgres requires TLS; the connection
string should already include ?sslmode=require.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Iterator, Optional

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "")

_POOL: Optional[ThreadedConnectionPool] = None


def _pool() -> Optional[ThreadedConnectionPool]:
    global _POOL
    if not DATABASE_URL:
        return None
    if _POOL is None:
        minconn = int(os.getenv("DB_POOL_MIN", "1"))
        maxconn = int(os.getenv("DB_POOL_MAX", "10"))
        _POOL = ThreadedConnectionPool(minconn, maxconn, DATABASE_URL)
        logger.info("Initialized Postgres pool (min=%d max=%d)", minconn, maxconn)
    return _POOL


@contextmanager
def get_conn() -> Iterator[psycopg2.extensions.connection]:
    """Yield a pooled connection, returning it to the pool on exit."""
    pool = _pool()
    if pool is None:
        raise RuntimeError("DATABASE_URL not set")
    conn = pool.getconn()
    try:
        yield conn
    finally:
        pool.putconn(conn)


@contextmanager
def get_cursor(commit: bool = False, dict_rows: bool = True):
    """Yield a cursor from a pooled connection.

    On exit, commits when commit=True and no exception was raised; rolls
    back on any exception regardless.
    """
    with get_conn() as conn:
        cursor_factory = RealDictCursor if dict_rows else None
        cur = conn.cursor(cursor_factory=cursor_factory)
        try:
            yield cur
            if commit:
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()


def ping() -> bool:
    """Return True if a `SELECT 1` round-trip succeeds."""
    try:
        with get_cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return True
    except Exception as exc:
        logger.error("Postgres ping failed: %s", exc)
        return False


def close_pool() -> None:
    """Close all pooled connections. Primarily for tests / graceful shutdown."""
    global _POOL
    if _POOL is not None:
        _POOL.closeall()
        _POOL = None
