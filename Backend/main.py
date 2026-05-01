"""
Entry point for the esports backend server.

Run locally with:
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""

import logging
import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from core.db import get_cursor

try:
    from slowapi import Limiter
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware
    from slowapi.util import get_remote_address
    from starlette.responses import JSONResponse
    _HAS_SLOWAPI = True
except ImportError:  # allows local dev without the dep installed
    _HAS_SLOWAPI = False

# Optional imports from your existing project structure.
# Leave these in if those folders/files already exist in your repo.
try:
    from valorant.config import FRONTEND_ORIGIN
except ImportError:
    FRONTEND_ORIGIN = "https://collegeesportstracker.netlify.app"

try:
    from valorant.routes import router as valorant_router
except ImportError:
    valorant_router = None

try:
    from core.leagues_router import router as leagues_router
except ImportError:
    leagues_router = None

try:
    from core.tournaments_router import router as tournaments_router
except ImportError:
    tournaments_router = None

try:
    from core.teams_router import router as teams_router
except ImportError:
    teams_router = None

try:
    from core.players_router import router as players_router
except ImportError:
    players_router = None

try:
    from core.admin_router import router as admin_router
except ImportError:
    admin_router = None

try:
    from core.matches_router import router as matches_router
except ImportError:
    matches_router = None


# --------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


# --------------------------------------------------------------------
# Environment variables
# --------------------------------------------------------------------
load_dotenv()

if not os.getenv("DATABASE_URL"):
    raise RuntimeError("Missing DATABASE_URL environment variable.")


# --------------------------------------------------------------------
# Postgres health check
# --------------------------------------------------------------------
def _db_ping() -> None:
    """Raise if Postgres is unreachable. Used by /health probes."""
    with get_cursor() as cur:
        cur.execute("SELECT 1")
        cur.fetchone()


# --------------------------------------------------------------------
# FastAPI app
# --------------------------------------------------------------------
app = FastAPI(
    title="Esports Stats API",
    description="Backend for college esports stats.",
    version="0.1.0",
)

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
# Rate limiting (slowapi) — 60 req/min/IP on public read endpoints
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


# --------------------------------------------------------------------
# Existing routers
# --------------------------------------------------------------------
if valorant_router is not None:
    app.include_router(valorant_router, prefix="/api/valorant")

if leagues_router is not None:
    app.include_router(leagues_router, prefix="/api/leagues")

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
    return {"status": "ok", "message": "Esports Stats API is running."}


@app.get("/health")
def health():
    try:
        _db_ping()
        return {"status": "healthy", "db": "connected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/api/health")
def api_health():
    """Public health probe used by the frontend status indicator.

    Always returns 200 so the frontend can render a status pill rather than
    hitting an error boundary; the `db` field reflects Postgres reachability.
    """
    try:
        _db_ping()
        return {"status": "ok", "db": "connected"}
    except Exception as e:
        return {"status": "degraded", "db": "disconnected", "error": str(e)}


# --------------------------------------------------------------------
# League routes
# --------------------------------------------------------------------
@app.get("/api/league/health")
def league_health():
    try:
        _db_ping()
        return {"ok": True, "message": "League API is running", "db": "connected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/api/league/team-players")
def get_team_players(team: str = Query(..., min_length=1)):
    """Return the League of Legends roster for a team name.

    Match is case-insensitive on the team's `name` column. The team_players
    join resolves the roster currently assigned to that team.
    """
    team = team.strip()
    try:
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT p.id, p.slug, p.display_name, p.riot_id, p.riot_puuid,
                       p.game_name, p.tag_line, p.role, p.game,
                       p.rating, p.active, p.stats, p.last_updated,
                       t.name AS team_name, t.slug AS team_slug
                  FROM players p
                  JOIN team_players tp ON tp.player_id = p.id
                  JOIN teams t         ON t.id = tp.team_id
                 WHERE LOWER(t.name) = LOWER(%s)
                   AND p.game = 'League of Legends'
                 ORDER BY p.display_name
                """,
                (team,),
            )
            players = []
            for row in cur.fetchall():
                players.append({
                    "_id":           str(row["id"]),
                    "slug":          row["slug"],
                    "display_name":  row["display_name"],
                    "riot_id":       row["riot_id"],
                    "puuid":         row["riot_puuid"],
                    "game_name":     row["game_name"],
                    "tag_line":      row["tag_line"],
                    "role":          row["role"],
                    "game":          row["game"],
                    "rating":        row["rating"],
                    "active":        row["active"],
                    "stats":         row["stats"] or {},
                    "team_name":     row["team_name"],
                    "team_slug":     row["team_slug"],
                    "updated_at_utc": row["last_updated"].isoformat() if row["last_updated"] else None,
                })

        return {
            "ok":      True,
            "team":    team,
            "count":   len(players),
            "players": players,
        }
    except Exception as e:
        logger.exception("Failed to fetch team players")
        raise HTTPException(status_code=500, detail=str(e))
