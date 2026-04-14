"""
Entry point for the esports backend server.

Run with:
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""
"""
Entry point for the esports backend server.

Run locally with:
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""

import logging
import os
import certifi
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient

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

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "senior_design_esports")
MONGO_TARGET_COLLECTION = os.getenv("MONGO_TARGET_COLLECTION", "CLOL_player_stats")

if not MONGO_URI:
    raise RuntimeError("Missing MONGO_URI environment variable.")


# --------------------------------------------------------------------
# MongoDB
# --------------------------------------------------------------------
client = MongoClient(
    MONGO_URI,
    tls=True,
    tlsCAFile=certifi.where(),
    serverSelectionTimeoutMS=5000,
    connectTimeoutMS=5000,
    socketTimeoutMS=5000,
)

db = client[MONGO_DB]
players_collection = db[MONGO_TARGET_COLLECTION]


# --------------------------------------------------------------------
# FastAPI app
# --------------------------------------------------------------------
app = FastAPI(
    title="Esports Stats API",
    description="Backend for college esports stats.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in FRONTEND_ORIGIN.split(",") if o.strip()]
    + ["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------
def normalize_player_doc(doc: dict) -> dict:
    if "_id" in doc:
        doc["_id"] = str(doc["_id"])

    defaults = {
        "team_name": None,
        "school": None,
        "display_name": None,
        "team_role_from_clol": None,
        "riot_id": None,
        "game_name": None,
        "tag_line": None,
        "puuid": None,
        "updated_at_utc": None,
        "scrape_status": None,
        "source": None,
        "opgg_url": None,
        "summoner_name": None,
        "ladder_rank": None,
        "error": None,
        "solo_duo_rank": None,
        "highest_rank": None,
        "flex_rank": None,
        "top_roles": [],
        "main_role": None,
        "top_5_masteries": [],
    }

    for key, value in defaults.items():
        doc.setdefault(key, value)

    return doc


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


# --------------------------------------------------------------------
# Basic routes
# --------------------------------------------------------------------
@app.get("/")
def root():
    return {"status": "ok", "message": "Esports Stats API is running."}


@app.get("/health")
def health():
    try:
        client.admin.command("ping")
        return {"status": "healthy", "mongo": "connected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MongoDB error: {str(e)}")


# --------------------------------------------------------------------
# League routes
# --------------------------------------------------------------------
@app.get("/api/league/health")
def league_health():
    try:
        client.admin.command("ping")
        return {"ok": True, "message": "League API is running", "mongo": "connected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MongoDB error: {str(e)}")


@app.get("/api/league/team-players")
def get_team_players(team: str = Query(..., min_length=1)):
    team = team.strip()

    try:
        docs = list(players_collection.find({"team_name": team}))

        if not docs:
            docs = list(
                players_collection.find(
                    {
                        "team_name": {
                            "$regex": f"^{team}$",
                            "$options": "i",
                        }
                    }
                )
            )

        players = [normalize_player_doc(doc) for doc in docs]

        return {
            "ok": True,
            "team": team,
            "count": len(players),
            "players": players,
        }

    except Exception as e:
        logger.exception("Failed to fetch team players")
        raise HTTPException(status_code=500, detail=str(e))