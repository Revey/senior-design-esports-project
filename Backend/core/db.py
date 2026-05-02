"""Postgres connection pool + cursor helpers for Campus Rankers Hub.

Phase 2 of postgres-migration-v2 — replaces the previous Mongo-flavored
core/db.py. The five public helpers (init_pool, close_pool, get_conn,
get_cursor, ping) are the locked contract that Phase 3 routers import.
See migrations/postgres-v2/phase-2-SPEC.md.

MODULE-LEVEL INVARIANT
    Importing this module is side-effect-free except for load_dotenv() and
    reading three env vars into module constants. No network calls, no pool
    init, no psycopg2 connection attempts. The pool is initialized at FastAPI
    startup via init_pool(); routers must NOT touch DB helpers at import time.

MULTI-STATEMENT TRANSACTION PATTERN (canonical for Phase 3 routers)
    For atomic multi-statement writes, use get_conn() and call conn.cursor()
    directly. NEVER call get_cursor() inside a get_conn() block — get_cursor()
    fetches a separate connection from the pool, breaking transaction
    atomicity and risking pool deadlock when MAX is small.

        with get_conn() as conn:
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("INSERT ... RETURNING id", (...))
                    new_id = cur.fetchone()["id"]
                    cur.execute("UPDATE ... WHERE id = %s", (...))
                conn.commit()
            except Exception:
                conn.rollback()
                raise
"""

import logging
import os
from contextlib import contextmanager
from typing import Optional

from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
DB_POOL_MIN = int(os.getenv("DB_POOL_MIN", "1"))
DB_POOL_MAX = int(os.getenv("DB_POOL_MAX", "10"))

_pool: Optional[pool.ThreadedConnectionPool] = None


def init_pool() -> None:
    """Initialize the threaded connection pool. Idempotent — calling twice
    after a successful first call is a no-op.

    Raises:
        RuntimeError: if DATABASE_URL is missing or pool sizing is invalid
            (DB_POOL_MIN < 1 or DB_POOL_MAX < DB_POOL_MIN).
    """
    global _pool
    if _pool is not None:
        return
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is required to initialize the Postgres connection pool. "
            "Set it via .env (host dev) or docker-compose.yml's environment block (in-docker)."
        )
    if DB_POOL_MIN < 1:
        raise RuntimeError(f"DB_POOL_MIN must be >= 1 (got {DB_POOL_MIN})")
    if DB_POOL_MAX < DB_POOL_MIN:
        raise RuntimeError(
            f"DB_POOL_MAX ({DB_POOL_MAX}) must be >= DB_POOL_MIN ({DB_POOL_MIN})"
        )
    _pool = pool.ThreadedConnectionPool(DB_POOL_MIN, DB_POOL_MAX, DATABASE_URL)
    logger.info(
        "Postgres connection pool initialized (min=%d, max=%d).",
        DB_POOL_MIN,
        DB_POOL_MAX,
    )


def close_pool() -> None:
    """Close all pooled connections. Idempotent. Called from FastAPI shutdown."""
    global _pool
    if _pool is None:
        return
    _pool.closeall()
    _pool = None
    logger.info("Postgres connection pool closed.")


@contextmanager
def get_conn():
    """Yield a raw psycopg2 connection from the pool.

    The caller manages the transaction explicitly — get_conn() does NOT
    auto-commit on successful exit. Writes that need to persist MUST call
    `conn.commit()` before the with-block ends. (Reads inside get_conn() are
    automatically rolled back at exit, which is harmless for pure reads but
    means uncommitted writes are silently discarded — the most common Phase 3
    foot-gun.)

    The caller is also responsible for closing any cursors it creates against
    the connection. The connection is ALWAYS returned to the pool in `finally`,
    with a rollback first if the body raised, so a poisoned-state connection
    never leaks back.

    DO NOT call get_cursor() while a get_conn() context is open — see the
    module docstring's "MULTI-STATEMENT TRANSACTION PATTERN" for the canonical
    idiom.
    """
    if _pool is None:
        raise RuntimeError(
            "Postgres pool not initialized — main.py must call init_pool() at startup."
        )
    conn = _pool.getconn()
    try:
        yield conn
    except Exception:
        # Roll back so the connection isn't returned to the pool in a bad
        # transaction state. Then let the exception propagate.
        try:
            conn.rollback()
        except Exception:
            logger.exception("rollback failed while handling earlier exception")
        raise
    finally:
        _pool.putconn(conn)


@contextmanager
def get_cursor(dict_rows: bool = True):
    """Yield a cursor; commit on success, rollback on exception.

    `dict_rows=True` (default) returns RealDictCursor rows (snake_case keys).
    `dict_rows=False` returns plain tuple rows (used by ping()).

    The cursor's connection is always rolled-back-then-returned-to-pool on
    exception so the pool never holds a poisoned connection.

    USE THIS FOR: single-statement reads, single-statement writes that fit one
    SQL statement. For atomic multi-statement work, use get_conn() instead.
    """
    if _pool is None:
        raise RuntimeError(
            "Postgres pool not initialized — main.py must call init_pool() at startup."
        )
    conn = _pool.getconn()
    cursor_factory = RealDictCursor if dict_rows else None
    cur = conn.cursor(cursor_factory=cursor_factory)
    try:
        yield cur
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            logger.exception("rollback failed while handling earlier exception")
        raise
    finally:
        # Cursor close should never raise in practice, but if it does, swallow
        # so the connection can still be returned to the pool. A leaked
        # connection is worse than a leaked cursor.
        try:
            cur.close()
        except Exception:
            logger.exception("cursor close failed; returning connection anyway")
        _pool.putconn(conn)


def ping() -> bool:
    """Cheap connectivity check used by /api/health. Returns False on any
    pool/network/SQL failure (does not raise). Uses `SELECT 1` with
    dict_rows=False; the result is discarded.
    """
    try:
        with get_cursor(dict_rows=False) as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return True
    except Exception as exc:
        logger.warning("Postgres ping failed: %s", exc)
        return False


# Note: `get_db()` is intentionally NOT exported. The legacy routers all do
# `from core.db import get_db` at module top — that import fails with
# `ImportError(name='core.db')` and message "cannot import name 'get_db' from
# 'core.db'". The Phase 2 _try_router() guard in main.py recognizes that
# specific signal as an Option-Z legacy-Mongo failure (alongside missing
# pymongo/bson/certifi modules) and skips registration. This is what makes
# all 7 routers — even those whose only Mongo dep is via get_db() — stay
# unregistered until Phase 3 ports them. See migrations/postgres-v2/phase-2-SPEC.md.
