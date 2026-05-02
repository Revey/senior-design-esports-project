# Phase 2 — Postgres data layer (`core/db.py` + deps + env + `main.py` startup)

**Migration:** Postgres v2 (Mongo → DigitalOcean Managed Postgres)
**Branch:** `postgres-migration-v2` (continues from Phase 1 commit `122ce4e`)
**Phase order:** Phase 2 of seven (Phases 0–6)
**Status:** Draft, awaiting approval

## Approval Flow (two gates)

1. **Spec approval (gate A)** — Developer reviews this SPEC + the `codex exec` critique. On approval, implementation begins.
2. **Pre-commit approval (gate B)** — After implementation, developer reviews the diff + `docker compose up --build` log + codex verdict. On approval, the commit lands.

---

## Phase Goal

Switch the application data layer from MongoDB to PostgreSQL **without porting any router code**. After Phase 2:

- The FastAPI app **boots cleanly** with a Postgres connection pool — no `MongoClient`, no `pymongo`, no `certifi` anywhere in the runtime path.
- `/api/health` pings the Postgres DB instead of Mongo and returns `{"status":"ok","db":"connected"}` when the pool is healthy.
- All 7 routers (leagues, teams, players, matches, tournaments, admin, valorant) are **intentionally not registered** because their internal `pymongo` imports will fail once `pymongo` is removed from `requirements.txt`. The existing `try/except ImportError` wrappers in `main.py` are the de-facto Option Z mechanism — they cause each `<name>_router` to resolve to `None`, and the existing `if <name>_router is not None:` guard skips registration. We make this **explicit** with a comment block; we do not delete the routers themselves (Phase 3 ports them).
- Public endpoints exposed in Phase 2: `/`, `/health`, `/api/health`. Everything else returns 404 until its router is ported.

The point of Phase 2 is to **decouple the data layer from the router layer** so Phase 3 can port routers one at a time, each as its own SDD-gated PR, against a clean Postgres-bound `db.py`.

## User Story

> As **the developer (and Phase 3 router porting work)**, I want **the application to run on Postgres with a working connection pool, even if no business endpoints are live yet**, so that **I can port routers one at a time against a stable data layer instead of doing a high-risk all-at-once cutover.**

---

## Technical Requirements

### File Manifest

The diff allow-list for Phase 2 is exactly these four files. Anything else changed = scope creep, fail the acceptance check.

| Action | Path | Purpose |
|---|---|---|
| **Modify** | `Backend/requirements.txt` | Drop `pymongo`, `certifi`. Add `psycopg2-binary`. |
| **Rewrite** | `Backend/core/db.py` | Replace MongoClient singleton with psycopg2 `ThreadedConnectionPool` + helper functions. |
| **Rewrite** | `Backend/.env.example` | Drop `MONGO_URI`, `MONGO_DB`, `MONGO_COLLECTION`, `MONGO_TARGET_COLLECTION`, `VAL_CUSTOM_STATS_COLLECTION`. Add `DATABASE_URL`, `DB_POOL_MIN`, `DB_POOL_MAX`. |
| **Rewrite** | `Backend/main.py` | Strip all Mongo. Add pool startup/shutdown events. Ping-Postgres health endpoints. Delete inline `/api/league/*` endpoints. Add explicit Option Z comment block. |

The phase SPEC itself (`migrations/postgres-v2/phase-2-SPEC.md`) is committed alongside, making 5 paths in the final commit.

### `Backend/core/db.py` — required shape

The exact signatures Phase 3 routers will import. **Lock these now**; changing them later is a refactor across every router.

```python
"""Postgres connection pool + cursor helpers for Campus Rankers Hub."""

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
    """Initialize the threaded connection pool. Idempotent (safe to call twice).
    Called from main.py FastAPI startup event.

    Raises:
        RuntimeError: if DATABASE_URL is missing, or pool sizing is invalid
            (DB_POOL_MIN < 1 or DB_POOL_MAX < DB_POOL_MIN).
    """
    ...


def close_pool() -> None:
    """Close all pooled connections. Idempotent. Called from FastAPI shutdown."""
    ...


@contextmanager
def get_conn():
    """Yield a raw psycopg2 connection from the pool.

    The caller manages the transaction explicitly (commit / rollback) and is
    responsible for closing any cursors it creates against the connection. The
    connection is ALWAYS returned to the pool in `finally`, with a rollback
    first if the body raised, so a poisoned-state connection never leaks back
    to the pool.

    DO NOT call get_cursor() while a get_conn() context is open — get_cursor()
    requests its own connection from the pool, which (a) creates a separate
    transaction divorced from your outer one and (b) can deadlock if the pool
    is exhausted. Inside get_conn(), use `conn.cursor(...)` directly. See the
    "Multi-statement transaction pattern" §below for the canonical idiom.
    """
    ...


@contextmanager
def get_cursor(dict_rows: bool = True):
    """Yield a cursor; commit on success, rollback on exception.

    `dict_rows=True` (default) returns RealDictCursor rows (snake_case keys).
    `dict_rows=False` returns plain tuple rows (used by ping()).

    The cursor's connection is always rolled-back-then-returned-to-pool on
    exception so the pool never holds a poisoned connection.

    USE THIS FOR: single-statement reads, single-statement writes that fit one
    SQL statement. For anything spanning multiple SQL statements that must be
    atomic together, use get_conn() instead.
    """
    ...


def ping() -> bool:
    """Cheap connectivity check used by /api/health. Returns False on any
    pool/network/SQL failure (does not raise). Uses `SELECT 1` with
    dict_rows=False; the result is discarded.
    """
    ...
```

**Module-level invariants (REQUIRED for boot path safety):**

- `core/db.py` is **side-effect-free at import time**, except for: `load_dotenv()`, reading the three env vars into module-level constants, and initializing `_pool = None`. **No** network calls, **no** pool initialization, **no** psycopg2 connection attempts at import.
- `init_pool()` is called from `main.py`'s startup event, NOT at module import. This lets pytest, lint tools, and IDE introspection import `db.py` without a live database.
- Phase 3 routers MUST NOT call `get_conn()`, `get_cursor()`, or `ping()` at module import time. All DB usage lives inside request handlers / services. (This invariant is captured in the Phase 3 SPEC's per-router checklist; we mention it here because Phase 2 sets the contract.)

**Key design notes:**

- **`get_conn()` returns the connection** so the caller controls transaction boundaries. Always returns the conn to the pool in `finally`, with rollback before put-back if the body raised.
- **`get_cursor()` auto-commits** on successful exit and auto-rollbacks on exception. Auto-commit on a pure read is a no-op semantically and matches standard psycopg2 idioms.
- **`RealDictCursor` is the default**: returns snake_case dict rows. The router layer converts snake_case → camelCase on the wire (CONSTITUTION §4 `_project()` pattern).
- **`ping()` swallows exceptions** so `/api/health` returns a degraded status instead of 500ing. Frontend footer status pill polls every 60s.
- **Pool sizing validation:** `init_pool()` validates `DB_POOL_MIN >= 1`, `DB_POOL_MAX >= DB_POOL_MIN`. A misconfigured env fails startup with a clear `RuntimeError` rather than producing a quietly-broken pool.

### Multi-statement transaction pattern (canonical for Phase 3)

For atomic multi-statement writes (e.g. admin match insert: insert match + update both teams' W/L + insert N player_match_stats rows), Phase 3 routers MUST use this exact shape:

```python
from core.db import get_conn

with get_conn() as conn:
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("INSERT INTO matches (...) VALUES (...) RETURNING id", (...))
            match_id = cur.fetchone()["id"]
            cur.execute("UPDATE teams SET wins = wins + 1 WHERE id = %s", (team1_id,))
            cur.execute("UPDATE teams SET losses = losses + 1 WHERE id = %s", (team2_id,))
            # ... insert player_match_stats rows ...
        conn.commit()
    except Exception:
        conn.rollback()
        raise
```

**Anti-pattern (DO NOT do this):**

```python
# WRONG — get_cursor() inside get_conn() opens a separate connection,
# its commit happens independently of the outer transaction, atomicity broken.
with get_conn() as conn:
    with get_cursor() as cur:   # ← BUG
        cur.execute(...)
```

The Phase 3 router-port checklist will include "no nested get_cursor inside get_conn" as a review item.

### `Backend/main.py` — required changes

#### Removed (Mongo cleanup)

- Imports: `pymongo`, `certifi` (and any `pymongo.errors` references — none currently in `main.py`, but verify).
- Env reads: `MONGO_URI`, `MONGO_DB`, `MONGO_TARGET_COLLECTION`. Delete the validation `if not MONGO_URI: raise RuntimeError(...)`.
- Block: `client = MongoClient(MONGO_URI, tls=True, tlsCAFile=certifi.where(), …)`.
- Block: `db = client[MONGO_DB]`, `players_collection = db[MONGO_TARGET_COLLECTION]`.
- Helper: `normalize_player_doc()` — only used by the inline `/api/league/team-players` endpoint that's also being deleted.
- Endpoint: `/api/league/health` (the Mongo-bound league health probe).
- Endpoint: `/api/league/team-players` (the inline Mongo `players_collection.find` endpoint).

#### Added (Postgres data-layer wiring)

- Import: `from core.db import init_pool, close_pool, ping as db_ping`.
- FastAPI startup event: calls `init_pool()`. Registered via `@app.on_event("startup")` (or the modern lifespan API — see Open Q §1).
- FastAPI shutdown event: calls `close_pool()`. Registered via `@app.on_event("shutdown")`.
- `/health` endpoint rewritten:
  ```python
  @app.get("/health")
  def health():
      if db_ping():
          return {"status": "healthy", "db": "connected"}
      raise HTTPException(status_code=500, detail="Postgres unreachable")
  ```
- `/api/health` endpoint rewritten (preserves existing always-200 contract for the frontend footer):
  ```python
  @app.get("/api/health")
  def api_health():
      if db_ping():
          return {"status": "ok", "db": "connected"}
      return {"status": "degraded", "db": "disconnected"}
  ```
- **Narrowed router import guards** (this is a CHANGE from the existing pattern).
  The current `try/except ImportError: <name>_router = None` is too broad — it silently swallows ANY ImportError, hiding real bugs (e.g. typos, broken transitive deps, a busted `core.db` import). Phase 2 narrows it to a **logged, legacy-Mongo-set-tolerant** wrapper, applied uniformly to all 7 router imports.

  **Deviation from initial draft (locked at gate-A "Option A" approval, then refined during implementation):** the tolerant set is `{"pymongo", "bson", "certifi"}` AND a second, narrower signal for `from core.db import get_db` failures. Investigation of the actual router source revealed:

  - Three transitive Mongo modules: `pymongo` (direct, every Mongo router), `bson` (admin_router does `from bson import ObjectId` — bson ships with pymongo), `certifi` (valorant uses it for the Mongo TLS CA bundle).
  - **Plus**, three routers (`leagues_router`, `tournaments_router`, `teams_router`) have *no* direct pymongo/bson/certifi import at module level — their only Mongo dependency is `from core.db import get_db` followed by runtime `get_db()["collection"]` calls. The new Phase 2 `db.py` does NOT export `get_db`, so the from-import fails with `ImportError(name='core.db')` and message `"cannot import name 'get_db' from 'core.db'"`.

  Earlier intermediate plan was a `get_db` stub in `db.py`; it was rejected during verification because it allowed those three routers to import successfully and become registered, only to crash with `NotImplementedError` at request time (worse than 404). Final plan: **no stub.** `_try_router()` recognizes BOTH signal types and skips both. Phase 3 router-port PRs each remove their `_try_router(...)` line as the router stops needing both legacy-module and `get_db` imports.

  Pseudocode:
  ```python
  LEGACY_MONGO_MODULES = {"pymongo", "bson", "certifi"}

  def _try_router(import_fn, name):
      """Import a router module, tolerating two known legacy-Mongo signals:
      (a) e.name in {pymongo, bson, certifi} — direct module-level legacy import.
      (b) e.name == 'core.db' and 'get_db' in str(e) — the router uses the
          Mongo-era core.db.get_db() helper that Phase 2 removed.
      Any other ImportError logs ERROR + re-raises (real bug, not Option Z).
      """
      try:
          return import_fn()
      except ImportError as e:
          if e.name in LEGACY_MONGO_MODULES:
              logger.info("router %r skipped: legacy module %r not installed (Phase 2 Option Z; ...)", name, e.name)
              return None
          if e.name == "core.db" and "get_db" in str(e):
              logger.info("router %r skipped: still depends on core.db.get_db (Phase 2 Option Z; ...)", name)
              return None
          logger.error("router %r failed for a non-legacy reason. Re-raising.", name)
          raise

  valorant_router    = _try_router(lambda: __import__('valorant.routes',         fromlist=['router']).router, 'valorant_router')
  leagues_router     = _try_router(lambda: __import__('core.leagues_router',     fromlist=['router']).router, 'leagues_router')
  tournaments_router = _try_router(lambda: __import__('core.tournaments_router', fromlist=['router']).router, 'tournaments_router')
  teams_router       = _try_router(lambda: __import__('core.teams_router',       fromlist=['router']).router, 'teams_router')
  players_router     = _try_router(lambda: __import__('core.players_router',     fromlist=['router']).router, 'players_router')
  admin_router       = _try_router(lambda: __import__('core.admin_router',       fromlist=['router']).router, 'admin_router')
  matches_router     = _try_router(lambda: __import__('core.matches_router',     fromlist=['router']).router, 'matches_router')
  ```
  (The implementer may use a cleaner form — e.g. `importlib.import_module` and a try/except around `getattr(..., 'router')` — as long as the **observed behavior** matches: ImportError with `e.name in LEGACY_MONGO_MODULES` → INFO log + skip; any other ImportError → ERROR log + re-raise.)

- Comment block above the `app.include_router(...)` calls explaining Option Z:
  ```python
  # ============================================================================
  # Phase 2 (Option Z): all routers below are intentionally NOT registered.
  #
  # _try_router() above tolerates ImportError ONLY when the missing module
  # is in LEGACY_MONGO_MODULES = {pymongo, bson, certifi} — the three
  # transitive deps the old Mongo data layer used. All three were removed
  # from requirements.txt in Phase 2. Any OTHER ImportError fails app boot
  # loudly, as it should.
  #
  # The `if <name>_router is not None: app.include_router(...)` guards then
  # skip registration for the routers that failed on legacy imports. The
  # result: the app boots cleanly with only /, /health, /api/health (plus
  # /docs and /openapi.json from FastAPI defaults). Every business endpoint
  # returns 404.
  #
  # Phase 3 ports routers one at a time. Each ported router stops needing
  # the legacy modules, _try_router() returns the real router, registration
  # happens.
  # ============================================================================
  ```

#### Unchanged (do not touch in Phase 2)

- CORS middleware setup (`ALLOWED_ORIGINS`, `FRONTEND_ORIGIN` resolution).
- Rate-limiting setup (slowapi `Limiter`, `RateLimitExceeded` handler).
- Logging setup.
- The **mechanism** of guarded router imports stays — but Phase 2 NARROWS it from a broad `except ImportError` to a logged, pymongo-name-checked `_try_router()` helper (per "Added" section above). The `if <name>_router is not None: app.include_router(...)` guard pattern in main.py is unchanged.

### `Backend/requirements.txt` — required final state

```
fastapi==0.115.0
uvicorn[standard]==0.30.6
requests==2.32.3
beautifulsoup4==4.12.3
lxml==5.3.0
pydantic==2.9.2
python-dotenv==1.0.1
psycopg2-binary==2.9.9
itsdangerous==2.2.0
slowapi==0.1.9
```

Removed: `pymongo==4.8.0`, `certifi==2024.8.30`.
Added: `psycopg2-binary==2.9.9`.

### `Backend/.env.example` — required final state

```
# --- Riot Games API ---
# Get your key at: https://developer.riotgames.com/
RIOT_API_KEY=RGAPI-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# Valorant region for match/ranked endpoints (na1, eu, ap, kr, br1, la1, la2)
RIOT_REGION=na1

# Account API region (americas, europe, asia, sea)
RIOT_ACCOUNT_REGION=americas

# --- Scraping ---
# Seconds to wait between tracker.gg requests (be respectful)
SCRAPE_DELAY=2.0

# --- Server ---
HOST=0.0.0.0
PORT=8000
DEBUG=false

# --- Cache ---
# Time-to-live for in-memory cache in seconds
CACHE_TTL=300

# --- PostgreSQL connection ---
# Inside Docker (docker compose up), the backend reaches the db service at
# host `db` — that URL is set in docker-compose.yml's environment block and
# you do NOT need to set DATABASE_URL here. Compose's env block takes
# precedence over .env, and overriding here with a host-machine URL like
# localhost:5432 will break the in-docker network.
#
# Only set DATABASE_URL here if you're running the backend directly on your
# host machine (no docker compose for backend) against either:
#   - a host-installed Postgres:                    postgresql://esports:esports@localhost:5432/esports
#   - the docker-compose db port-mapped to host:    postgresql://esports:esports@localhost:5432/esports
#   - a managed cloud Postgres (DO):                postgresql://USER:PASS@HOST:25060/DB?sslmode=require
DATABASE_URL=

# Connection pool sizing (defaults: MIN=1, MAX=10).
# init_pool() validates: MIN >= 1, MAX >= MIN. Otherwise startup fails fast.
DB_POOL_MIN=1
DB_POOL_MAX=10
```

Removed: `MONGO_URI`, `MONGO_DB`, `MONGO_COLLECTION`, `MONGO_TARGET_COLLECTION`, `VAL_CUSTOM_STATS_COLLECTION`.
Added: `DATABASE_URL`, `DB_POOL_MIN`, `DB_POOL_MAX`.

### Out of Scope (explicitly NOT in Phase 2)

- **Any router code change** (`Backend/core/*_router.py`, `Backend/valorant/routes.py`). Phase 3 ports them one at a time.
- **`Backend/valorant/rso_store.py`** — still a Mongo-bound module. Phase 5 (RSO consent gate) will rewrite it.
- **Standalone scripts** (`Backend/IngestCVALMatches.py`, `Backend/migrate.py`, `Backend/migrate_leagues.py`, `Backend/valorant/ScrapeCSUCustomGames.py`, `Backend/League/*.py`). They're not on the FastAPI import path and don't break the app boot. Move-or-rewrite is a future cleanup.
- **`ADMIN_PASSWORD` / `ADMIN_SECRET` env vars** — used by the (currently-unported) `admin_router`. Phase 3's admin-router PR adds them to `.env.example` when admin auth is wired up.
- **`seed_data.py`** — its own future task, not migration-critical.
- **DigitalOcean Managed Postgres provisioning** — Phase 6.
- **Frontend changes** — Phase 4.

## API Contract

### Endpoints alive after Phase 2

| Method | Path | Behavior |
|---|---|---|
| `GET` | `/` | Returns `{"status":"ok","message":"…"}` (unchanged from current). |
| `GET` | `/health` | Returns `{"status":"healthy","db":"connected"}` on pool ping success; raises 500 on failure. |
| `GET` | `/api/health` | Returns `{"status":"ok","db":"connected"}` on success; `{"status":"degraded","db":"disconnected"}` on failure. **Always 200** (frontend footer pill contract). |

### Endpoints 404 after Phase 2 (until their phase 3 sub-task)

`/api/leagues/*`, `/api/teams/*`, `/api/players/*`, `/api/matches/*`, `/api/tournaments/*`, `/api/admin/*`, `/api/valorant/*`, `/api/league/team-players`, `/api/league/health`.

## Acceptance Criteria

- [ ] `git diff --name-only main..HEAD` for Phase 2's commit lists exactly: `Backend/requirements.txt`, `Backend/core/db.py`, `Backend/.env.example`, `Backend/main.py`, `migrations/postgres-v2/phase-2-SPEC.md`. **No other paths.**
- [ ] `grep -nE '(^import certifi|^from certifi|import pymongo|from pymongo|MongoClient)' Backend/main.py Backend/core/db.py` returns **zero hits**.
- [ ] `grep -rnE '(^import certifi|^from certifi|import pymongo|from pymongo|MongoClient)' Backend/ --include='*.py' | grep -v -E '(valorant/|core/admin_router|core/leagues_router|core/teams_router|core/players_router|core/matches_router|core/tournaments_router|core/models|League/|archive/|migrate)'` returns **zero hits** — the runtime import path (main.py + core/db.py + anything they import non-conditionally) is Mongo-free. Routers and standalone scripts may still contain pymongo references; those are Phase 3 / future cleanup.
- [ ] `grep -n 'psycopg2' Backend/core/db.py` returns at least one hit (the import).
- [ ] `Backend/requirements.txt` contains `psycopg2-binary==2.9.9` and does NOT contain a top-level `pymongo` or `certifi` line. (Note: `certifi` may still appear in `pip freeze` as a transitive of `requests` — that's fine; we only require it absent from `requirements.txt` and from direct app code.)
- [ ] `Backend/.env.example` does NOT contain `MONGO_URI`, `MONGO_DB`, `MONGO_COLLECTION`, `MONGO_TARGET_COLLECTION`, or `VAL_CUSTOM_STATS_COLLECTION`. Does contain `DATABASE_URL`, `DB_POOL_MIN`, `DB_POOL_MAX`.
- [ ] `Backend/core/db.py` defines: `init_pool`, `close_pool`, `get_conn`, `get_cursor`, `ping` — exact names and signatures per §"Required shape" above.
- [ ] **Module-level side-effect check:** `python -c "import core.db"` (run inside the backend container with no DB available) succeeds — no network call, no pool init.
- [ ] **Boot test:** `docker compose down -v && docker compose up --build` completes with backend healthy. Backend logs show exactly 7 INFO router-skipped lines from `_try_router`, with this expected breakdown:
  - `valorant_router` → `"legacy module 'pymongo' not installed"`
  - `leagues_router` → `"still depends on core.db.get_db"`
  - `tournaments_router` → `"still depends on core.db.get_db"`
  - `teams_router` → `"still depends on core.db.get_db"`
  - `players_router` → `"legacy module 'bson' not installed"`
  - `admin_router` → `"legacy module 'bson' not installed"`
  - `matches_router` → `"legacy module 'bson' not installed"`
  - **Zero** ERROR lines from `_try_router`. (If you see one, that's NOT Option Z — investigate before merging.)
- [ ] **Missing-DATABASE-URL test:** `docker compose run --rm -e DATABASE_URL= backend python -c "from core.db import init_pool; init_pool()"` raises `RuntimeError` with a message naming `DATABASE_URL`. Backend startup with empty DATABASE_URL fails fast.
- [ ] **Bad pool sizing test:** `docker compose run --rm -e DB_POOL_MIN=10 -e DB_POOL_MAX=1 backend python -c "from core.db import init_pool; init_pool()"` raises `RuntimeError` complaining about pool sizing.
- [ ] **Route table check:** `curl -s http://localhost:8000/openapi.json | jq -r '.paths | keys | .[]'` returns exactly: `/`, `/health`, `/api/health`. (FastAPI's `/docs`, `/redoc`, `/openapi.json` are framework-served, not in the user paths list.) No business endpoints registered.
- [ ] **Health endpoint test:** `curl http://localhost:8000/api/health` returns `{"status":"ok","db":"connected"}` (HTTP 200).
- [ ] **DB-down degraded test:** `docker compose stop db && curl http://localhost:8000/api/health` returns `{"status":"degraded","db":"disconnected"}` (still HTTP 200, frontend pill contract preserved). Restart with `docker compose start db` after.
- [ ] **404 test:** `curl -i http://localhost:8000/api/teams` returns HTTP 404. Same for `/api/players`, `/api/matches`, `/api/leagues`, `/api/tournaments`, `/api/admin/whatever`, `/api/valorant/whatever`, `/api/league/team-players`, `/api/league/health`. (Option Z verification + deleted-endpoint verification.)
- [ ] **Manual sensitive-info pass:** no real PUUIDs, tokens, or production hostnames in the diff. Documented in commit message.
- [ ] **Codex advisory review:** APPROVE or APPROVE-WITH-NITS verdict (any nits addressed before commit).
- [ ] **Pre-commit (gate B):** developer reviews the docker-compose-up log, the curl outputs, and the codex verdict before commit.

## Verification Plan

```bash
# 1. Clean slate (Phase 1's pgdata is fine — schema persists across `up`).
docker compose down -v
docker compose up --build -d

# 2. Wait for backend healthy.
until curl -fs http://localhost:8000/api/health > /dev/null; do sleep 2; done
echo "backend up"

# 3. Health endpoint (DB connected).
curl -s http://localhost:8000/api/health | jq
# Expect: {"status":"ok","db":"connected"}

# 4. Verify deps. We require psycopg2-binary present and pymongo absent. We do
#    NOT require certifi absent: it remains a transitive dep of `requests`,
#    which is still in requirements. The acceptance criterion is "no top-level
#    certifi line in requirements.txt and no `import certifi` in app code"
#    (checked separately below in step 4b).
docker compose exec -T backend pip freeze | grep -iE 'pymongo|psycopg2'
# Expect: psycopg2-binary==2.9.9 present; zero pymongo line.

# 4b. Confirm no direct certifi/pymongo references in the runtime app path.
grep -nE '(^import certifi|^from certifi|import pymongo|from pymongo|MongoClient)' \
  Backend/main.py Backend/core/db.py
# Expect: zero hits.

# 4c. Confirm requirements.txt has neither pymongo nor a top-level certifi line.
grep -E '^(pymongo|certifi)' Backend/requirements.txt && echo "FAIL" || echo "OK"

# 5a. Confirm only the expected paths exist (route-table check via OpenAPI).
curl -s http://localhost:8000/openapi.json | jq -r '.paths | keys | .[]' | sort
# Expect exactly: /, /api/health, /health

# 5b. Confirm Option Z by REASON — each of the 7 routers should be skipped.
LEGACY_HITS=$(docker compose logs backend 2>&1 | grep -E "router '.+_router' skipped: legacy module '(pymongo|bson|certifi)' not installed" | wc -l)
GETDB_HITS=$(docker compose logs backend 2>&1  | grep -E "router '.+_router' skipped: still depends on core.db.get_db" | wc -l)
echo "legacy-module skips: $LEGACY_HITS  |  core.db.get_db skips: $GETDB_HITS  |  total: $((LEGACY_HITS + GETDB_HITS))"
# Expect: 4 + 3 = 7 total skips.
# Specifically: valorant=pymongo; players/admin/matches=bson; leagues/tournaments/teams=core.db.get_db

docker compose logs backend 2>&1 | grep -E "router '.+_router' failed to import for a non-legacy reason"
# Expect: nothing. If you see this, investigate — it's a real bug, NOT Option Z.

# 5c. Sanity: every business endpoint returns 404.
for path in \
  /api/teams /api/players /api/matches /api/leagues /api/tournaments \
  /api/admin/stats /api/valorant/anything \
  /api/league/team-players /api/league/health
do
  printf '%-40s ' "$path"
  curl -s -o /dev/null -w '%{http_code}\n' "http://localhost:8000$path"
done
# Expect: 404 on every line.

# 6. DB-down degraded test.
docker compose stop db
sleep 2
curl -s http://localhost:8000/api/health | jq
# Expect: {"status":"degraded","db":"disconnected"} — HTTP still 200.
docker compose start db

# 7. Backend-side: confirm no pymongo errors except the expected import-guard
#    warnings (one per router that fails to import — that IS Option Z working).
docker compose logs backend 2>&1 | grep -iE 'pymongo|MongoClient' || echo "no Mongo references in backend logs"

# 8. Outside review.
{ echo "=== STAGED DIFF FOR PHASE 2 ==="; git diff --cached; } | \
  codex exec --sandbox read-only "Review Phase 2 of a Mongo→Postgres migration. Verify: psycopg2 ThreadedConnectionPool used correctly, get_conn yields a connection (not cursor), get_cursor commits on success and rolls back on exception, no leaked pymongo imports anywhere, .env.example is sane, main.py CORS/rate-limiting unchanged, Option Z documented. Output critical issues, then nits. End with verdict."
```

## Rollback Plan

```bash
# Local Postgres state — no schema changes in Phase 2; volume can stay.

# Preferred: revert the Phase 2 commit (preserves history; works pre- or post-push):
git revert <phase-2-commit-sha>

# Local-only escape hatch (pre-push only — destructive to local commits):
#   git reset --hard 122ce4e   # back to Phase 1 commit
# Use only if you are absolutely sure the commit hasn't been pushed.
```

If Phase 2 has been pushed and a problem is found later, prefer `git revert` over `git reset` so the rollback is auditable in history. Phase 1 (schema) does not need rollback for Phase 2 issues — schema and data layer are independent.

## Risks & Open Questions

### §1 FastAPI startup events: `@app.on_event` vs lifespan API

FastAPI deprecated `@app.on_event("startup")` / `@app.on_event("shutdown")` in favor of the `lifespan` async context manager (Starlette pattern). Both still work in `fastapi==0.115.0`. **Recommend keeping `@app.on_event` for Phase 2** — the existing main.py style is sync, lifespan adds an async-context wrinkle, and we don't gain anything in Phase 2 by switching. If FastAPI removes `@app.on_event` in a future minor, we migrate then. Document the choice.

### §2 Connection-pool error on first request after DB restart

`ThreadedConnectionPool` may hand out a stale connection after the DB restarts. The standard fix is to `SET keepalives` on the pool or use `psycopg2.pool.PersistentConnectionPool` with reconnect logic. **Out of scope for Phase 2** — `ping()` returns False on stale connections so `/api/health` will report degraded; routers in Phase 3 may need a retry wrapper. Document for Phase 3.

### §3 `psycopg2-binary` vs `psycopg2` (source build) for production

`psycopg2-binary` is convenient (no system libpq needed) but psycopg's docs recommend the source build for production. DO Managed Postgres' libpq version is unknown to us today; binary is the safe v1 choice. **Lock `psycopg2-binary==2.9.9` for Phase 2**; revisit at Phase 6 (DO provisioning) if there's a libpq mismatch.

### §4 Should `Backend/core/__init__.py` be touched?

No. The current `core/` is already a package; we are rewriting `core/db.py` in place. `__init__.py` does not need to expose `init_pool`/etc. — Phase 3 routers will `from core.db import get_cursor` directly.

### §5 What if a router import fails for a non-pymongo reason?

The previous main.py used a broad `try/except ImportError: <name>_router = None` wrapper that silently swallowed ANY ImportError, hiding real bugs (typos, broken transitive deps, busted `core.db` imports). **Phase 2 narrows this** via the `_try_router()` helper specified in §"Required changes" above: ImportError is tolerated ONLY when `e.name == "pymongo"`; any other ImportError is logged at ERROR level (with the missing module name) and re-raised so the app fails fast. This makes Option Z observable and rules out the "silently broken router" failure mode. Each Phase 3 router-port PR removes ITS specific `_try_router(...)` line as the router stops needing pymongo.

### Risk: an environment-variable typo would silently use defaults

`DB_POOL_MIN` / `DB_POOL_MAX` fall back to `1` / `10` if unset. `DATABASE_URL` is required and `init_pool()` raises if missing — that's a hard fail at startup, which is correct. App-side validation of the other two beyond their defaults is unnecessary for Phase 2.

### Risk: Phase 2 looks like a "small" phase but touches the application's startup path

Anything broken in `init_pool()` blocks the whole app, including health endpoints. Mitigation: full `docker compose up --build` verification before commit, with explicit DB-up/DB-down test cases.

---

## Decisions Made (locked at gate-A)

| # | Decision | Choice |
|---|---|---|
| 1 | Routers in Phase 2 | **Option Z** — all 7 routers (leagues, teams, players, matches, tournaments, admin, valorant) skipped via narrowed `_try_router()` helper that tolerates two specific legacy-Mongo signals: (a) `ImportError` whose missing module is in `LEGACY_MONGO_MODULES = {"pymongo", "bson", "certifi"}`; (b) `ImportError(name='core.db')` with `'get_db'` in the message (routers depending on the Mongo-era `get_db()` helper that Phase 2 removed). Any other ImportError logs ERROR and re-raises (fails app boot). The `db.py` does NOT carry a `get_db` stub — that path was tried and rejected during verification (it would let three routers register successfully and crash at request time). Phase 3 ports each router and removes its `_try_router()` line. |
| 2 | Inline `/api/league/*` endpoints in `main.py` | **Delete** in Phase 2. They're tiny; Phase 3 router work can recreate against Postgres if needed. |
| 3 | `db.py` helper signatures | Locked: `init_pool() / close_pool() / get_conn() / get_cursor(dict_rows=True) / ping()`. Plus the **multi-statement transaction pattern** (use `get_conn() + conn.cursor()` directly, NOT `get_cursor()` inside `get_conn()`) is the Phase 3 contract. |
| 4 | psycopg2 distribution | `psycopg2-binary==2.9.9` for v1; revisit at Phase 6 if DO libpq mismatch. |
| 5 | FastAPI startup hooks | Keep `@app.on_event("startup"/"shutdown")` (sync) — don't switch to `lifespan` API in Phase 2. Acknowledge deprecation noise in logs is acceptable. |
| 6 | `core/__init__.py` | Not touched. |
| 7 | Router import-guard pattern | **Narrowed** from broad `except ImportError` to two-signal `_try_router()`: (a) `e.name in {pymongo, bson, certifi}`; (b) `e.name == 'core.db'` AND `'get_db' in str(e)`. Both produce INFO log + skip; anything else is ERROR + re-raise. Each Phase 3 router-port PR removes its specific `_try_router(...)` call as the router stops needing both signal sources. |
| 8 | `pip freeze` certifi check | **Dropped from acceptance.** `certifi` is a transitive dep of `requests`; we only require it absent from `requirements.txt` and from `import` statements in app code. |
| 9 | Multi-statement transaction shape | `with get_conn() as conn:` + explicit `conn.cursor()` + caller commits/rollbacks. Documented in §"Multi-statement transaction pattern" above. Phase 3 PRs that violate (nested `get_cursor()` inside `get_conn()`) will be rejected at gate-B. |
