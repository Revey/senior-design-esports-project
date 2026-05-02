"""
Entry point for the Campus Rankers Hub backend server.

Run with:
    uvicorn main:app --reload --host 0.0.0.0 --port 8000

Phase 2 of postgres-migration-v2 — see migrations/postgres-v2/phase-2-SPEC.md.

Status: data layer is now Postgres (psycopg2 ThreadedConnectionPool via
core/db.py). The 6 remaining business routers (teams, players, matches,
tournaments, admin, valorant) are intentionally NOT registered yet — they
still import pymongo or use the removed core.db.get_db helper, so the
_try_router() guard below skips them via Option Z. The leagues router
was DELETED in Phase 3a (the leagues collection has no Postgres
equivalent — replaced by the org/conference hierarchy).
Any other ImportError fails the app boot — that's a real bug, not Option Z.
Phase 3 ports each router and the corresponding _try_router() line is
removed at that time.

Public endpoints alive: /, /health, /api/health.
"""

import importlib
import logging
import os
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

try:
    from slowapi import Limiter
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware
    from slowapi.util import get_remote_address
    from starlette.responses import JSONResponse
    _HAS_SLOWAPI = True
except ImportError:
    _HAS_SLOWAPI = False

from core.db import close_pool, init_pool, ping as db_ping

# --------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


# --------------------------------------------------------------------
# Environment
# --------------------------------------------------------------------
load_dotenv()

try:
    from valorant.config import FRONTEND_ORIGIN  # type: ignore
except ImportError:
    FRONTEND_ORIGIN = "https://campusrankers.com"


# --------------------------------------------------------------------
# Router imports — narrowed Option Z guard (Phase 2)
#
# _try_router() tolerates ImportError on TWO specific signals, both of
# which mean "this router still has Mongo-era dependencies":
#
#   (a) `e.name in LEGACY_MONGO_MODULES` (pymongo/bson/certifi) — the
#       three transitive deps the old Mongo data layer depended on,
#       removed from requirements.txt in Phase 2. This catches any
#       router that does `from pymongo import ...`, `from bson import
#       ObjectId`, or `import certifi` at module level.
#
#   (b) `e.name == "core.db" and "get_db" in str(e)` — three routers
#       (leagues/tournaments/teams) have NO direct legacy module-level
#       import; their only Mongo dep is the Phase-2-removed `get_db()`
#       helper. Their `from core.db import get_db` raises ImportError
#       here. We do NOT carry a `get_db` stub in core/db.py — verified
#       during Phase 2 that a stub would let those three routers
#       register and crash at request time, which is worse than 404.
#
# Any OTHER missing module is a real bug (typo, broken transitive dep,
# busted core.db for any other reason). We log ERROR + re-raise so the
# app fails fast.
#
# Each Phase 3 router-port PR removes ITS specific _try_router() line
# as the router stops needing the legacy signals.
# --------------------------------------------------------------------
LEGACY_MONGO_MODULES = {"pymongo", "bson", "certifi"}


def _try_router(module_path: str, name: str) -> Any:
    """Import a router module's `router` attribute, tolerating ImportError
    only when the failure is a known legacy-Mongo signal (Option Z, Phase 2):

      (a) the missing module is in LEGACY_MONGO_MODULES (pymongo/bson/certifi)
          — direct legacy imports, e.g. `from pymongo import MongoClient`.
      (b) the failure is `from core.db import get_db` — the routers without a
          direct pymongo/bson/certifi import still depend on the Mongo-era
          `get_db()` helper that Phase 2 removed. This shows up as
          ImportError(name='core.db') with message containing 'get_db'.

    Both signals mean the router still has Mongo-era dependencies and must
    not be registered. Re-raises any OTHER ImportError so real bugs (typos,
    busted transitive deps, broken core.db import for any other reason) fail
    the app boot loudly.
    """
    try:
        module = importlib.import_module(module_path)
        return getattr(module, "router")
    except ImportError as e:
        if e.name in LEGACY_MONGO_MODULES:
            logger.info(
                "router %r skipped: legacy module %r not installed "
                "(Phase 2 Option Z; will be re-enabled when this router is "
                "ported in Phase 3).",
                name, e.name,
            )
            return None
        if e.name == "core.db" and "get_db" in str(e):
            logger.info(
                "router %r skipped: still depends on core.db.get_db "
                "(Phase 2 Option Z; the Mongo-era helper was removed; this "
                "router will be re-enabled when ported in Phase 3).",
                name,
            )
            return None
        logger.error(
            "router %r failed to import for a non-legacy reason "
            "(missing module: %r) — this is NOT Option Z, it's a real bug. Re-raising.",
            name, e.name,
        )
        raise


valorant_router    = _try_router("valorant.routes",         "valorant_router")
tournaments_router = _try_router("core.tournaments_router", "tournaments_router")
teams_router       = _try_router("core.teams_router",       "teams_router")
players_router     = _try_router("core.players_router",     "players_router")
admin_router       = _try_router("core.admin_router",       "admin_router")
matches_router     = _try_router("core.matches_router",     "matches_router")
# (Phase 3a deleted the leagues route — the Mongo `leagues` collection has no
# Postgres equivalent; replaced by organizations/seasons/conferences hierarchy.)


# --------------------------------------------------------------------
# FastAPI app
# --------------------------------------------------------------------
app = FastAPI(
    title="Campus Rankers Hub API",
    description="Backend for collegiate esports stats (Valorant + LoL).",
    version="0.2.0",
)


# --------------------------------------------------------------------
# Pool lifecycle — init at startup, close at shutdown
# --------------------------------------------------------------------
@app.on_event("startup")
def _startup() -> None:
    init_pool()


@app.on_event("shutdown")
def _shutdown() -> None:
    close_pool()


# --------------------------------------------------------------------
# CORS — restrict to env-configured origins in prod
# --------------------------------------------------------------------
_env_origins = os.getenv("ALLOWED_ORIGINS", "")
_allowed_origins: list[str]
if _env_origins.strip():
    _allowed_origins = [o.strip() for o in _env_origins.split(",") if o.strip()]
else:
    _allowed_origins = [
        o.strip() for o in FRONTEND_ORIGIN.split(",") if o.strip()
    ] + ["http://localhost:3000", "http://localhost:3001"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------
# Rate limiting (slowapi) — 60 req/min/IP default on public read endpoints
# --------------------------------------------------------------------
if _HAS_SLOWAPI:
    _rate = os.getenv("RATE_LIMIT_DEFAULT", "60/minute")
    limiter = Limiter(key_func=get_remote_address, default_limits=[_rate])
    app.state.limiter = limiter

    @app.exception_handler(RateLimitExceeded)
    def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Slow down and try again shortly."},
        )

    app.add_middleware(SlowAPIMiddleware)
else:
    logger.warning("slowapi not installed — rate limiting disabled")


# ============================================================================
# Phase 2 (Option Z): all routers below are intentionally NOT registered for
# the routers whose imports failed in _try_router() above (pymongo missing).
#
# The `if <name>_router is not None: app.include_router(...)` guards skip
# registration for every router that returned None. The result: the app
# boots cleanly with only /, /health, /api/health (plus FastAPI's framework
# /docs, /redoc, /openapi.json). Every business endpoint returns 404.
#
# Phase 3 ports routers one at a time. Each ported router stops needing
# pymongo, _try_router() returns the real router, and registration happens
# automatically.
# ============================================================================
if valorant_router is not None:
    app.include_router(valorant_router, prefix="/api/valorant")

if tournaments_router is not None:
    app.include_router(tournaments_router, prefix="/api/tournaments")

if teams_router is not None:
    app.include_router(teams_router, prefix="/api/teams")

if players_router is not None:
    app.include_router(players_router, prefix="/api/players")

if admin_router is not None:
    app.include_router(admin_router, prefix="/api/admin")

if matches_router is not None:
    app.include_router(matches_router, prefix="/api/matches")


# --------------------------------------------------------------------
# Basic routes
# --------------------------------------------------------------------
@app.get("/")
def root():
    return {"status": "ok", "message": "Campus Rankers Hub API is running."}


@app.get("/health")
def health():
    if db_ping():
        return {"status": "healthy", "db": "connected"}
    raise HTTPException(status_code=500, detail="Postgres unreachable")


@app.get("/api/health")
def api_health():
    """Public health probe used by the frontend status indicator.

    Always returns 200 so the frontend can render a status pill rather than
    hitting an error boundary; the `db` field reflects Postgres reachability.
    """
    if db_ping():
        return {"status": "ok", "db": "connected"}
    return {"status": "degraded", "db": "disconnected"}
