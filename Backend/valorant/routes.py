"""
FastAPI router for Valorant endpoints.

Mount this in main.py:
    from valorant.routes import router as val_router
    app.include_router(val_router, prefix="/api/valorant")
"""

import json
import logging
import time
from pathlib import Path
from typing import Optional

import certifi
from fastapi import APIRouter, HTTPException, Query
from pymongo import MongoClient

from . import riot_api, tracker_scraper
from .config import MONGO_URI, MONGO_DB, VAL_COLLECTION, VAL_STATS_COLLECTION
from .data_builder import build_team_payload
from .models import ValorantTeamPayload, PlayerProfile

logger = logging.getLogger(__name__)

router = APIRouter(tags=["valorant"])

# Simple in-memory cache: {cache_key: (timestamp, data)}
_cache: dict = {}

ROSTERS_DIR = Path(__file__).parent / "rosters"

# MongoDB client (lazy-initialized)
_mongo_client: Optional[MongoClient] = None


def _get_db():
    """Return the MongoDB database, creating the client on first call."""
    global _mongo_client
    if not MONGO_URI:
        return None
    if _mongo_client is None:
        _mongo_client = MongoClient(MONGO_URI, tls=True, tlsCAFile=certifi.where())
    return _mongo_client[MONGO_DB]


def _cached(key: str, ttl: int, fn):
    """Return cached result or call fn() and cache the result."""
    if key in _cache:
        ts, data = _cache[key]
        if time.time() - ts < ttl:
            return data
    result = fn()
    _cache[key] = (time.time(), result)
    return result


# ---------------------------------------------------------------------------
# Player endpoints
# ---------------------------------------------------------------------------

@router.get("/player/{game_name}/{tag_line}", response_model=dict)
def get_player(
    game_name: str,
    tag_line: str,
    num_matches: int = Query(default=20, ge=1, le=20),
):
    """
    Look up a player by Riot ID and return aggregated stats.

    Example: GET /api/valorant/player/wyyu/NA1
    """
    try:
        profile: PlayerProfile = riot_api.get_account_by_riot_id(game_name, tag_line)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Player not found: {exc}") from exc

    def _fetch():
        api_stats = riot_api.aggregate_player_stats(profile.puuid, num_matches)
        # Fall back to scraper for any missing stats
        if not api_stats or api_stats.get("KD", 0) == 0:
            scraped = tracker_scraper.scrape_player_overview(game_name, tag_line)
            api_stats.update({k: v for k, v in scraped.items() if k not in api_stats})
        return {
            "gameName": profile.gameName,
            "tagLine": profile.tagLine,
            "puuid": profile.puuid,
            **api_stats,
        }

    cache_key = f"player:{profile.puuid}:{num_matches}"
    return _cached(cache_key, ttl=300, fn=_fetch)


@router.get("/player/{game_name}/{tag_line}/matches")
def get_player_matches(game_name: str, tag_line: str, size: int = Query(default=10, ge=1, le=20)):
    """Return recent match references for a player."""
    try:
        profile = riot_api.get_account_by_riot_id(game_name, tag_line)
        matches = riot_api.get_match_list(profile.puuid, size=size)
        return {"puuid": profile.puuid, "matches": [m.model_dump() for m in matches]}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/player/{game_name}/{tag_line}/scrape")
def scrape_player(game_name: str, tag_line: str):
    """Scrape tracker.gg for a player's stats (use when Riot API is unavailable)."""
    stats = tracker_scraper.scrape_player_overview(game_name, tag_line)
    if not stats:
        raise HTTPException(status_code=404, detail="Could not scrape stats for this player.")
    return {"gameName": game_name, "tagLine": tag_line, **stats}


# ---------------------------------------------------------------------------
# Match endpoints
# ---------------------------------------------------------------------------

@router.get("/match/{match_id}")
def get_match(match_id: str):
    """Return full details for a single match."""
    try:
        match = riot_api.get_match(match_id)
        return match.model_dump()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Team endpoints
# ---------------------------------------------------------------------------

@router.get("/team/{team_id}", response_model=ValorantTeamPayload)
def get_team(
    team_id: str,
    use_riot: bool = Query(default=True),
    use_scraper: bool = Query(default=True),
    num_matches: int = Query(default=20, ge=1, le=20),
):
    """
    Build and return a full team payload for the frontend.

    Checks MongoDB VAL collection first, then falls back to a static roster file.

    Example: GET /api/valorant/team/CSUValGreen
    """
    cache_key = f"team:{team_id}:{use_riot}:{use_scraper}:{num_matches}"

    def _build():
        team_doc = None

        # Try MongoDB first
        db = _get_db()
        if db is not None:
            team_doc = db[VAL_COLLECTION].find_one(
                {"team_name": {"$regex": team_id, "$options": "i"}},
                {"_id": 0},
            )

        # Fall back to static roster file
        if team_doc is None:
            roster_file = ROSTERS_DIR / f"{team_id}.json"
            if not roster_file.exists():
                raise HTTPException(
                    status_code=404,
                    detail=f"Team not found in MongoDB or roster files: {team_id}",
                )
            with open(roster_file) as f:
                team_doc = json.load(f)

        # Enrich each player with stored stats from VAL_player_stats if available
        if db is not None:
            for player in team_doc.get("players", []):
                riot_id  = player.get("riot_id") or f"{player.get('game_name','')}#{player.get('tag_line','')}"
                stats_doc = db[VAL_STATS_COLLECTION].find_one({"riot_id": riot_id}, {"_id": 0})
                if stats_doc:
                    stored = stats_doc.get("tracker_stats") or stats_doc.get("riot_stats") or {}
                    player.update({k: v for k, v in stored.items() if k not in player})

        return build_team_payload(
            team_doc,
            use_riot_api=use_riot,
            use_scraper=use_scraper,
            num_matches=num_matches,
        )

    return _cached(cache_key, ttl=300, fn=_build)


@router.get("/teams")
def list_teams():
    """
    List all available teams.

    Returns teams from MongoDB VAL collection if available,
    otherwise falls back to static roster files.
    """
    db = _get_db()
    if db is not None:
        teams = list(
            db[VAL_COLLECTION].find({}, {"_id": 0, "team_name": 1, "school": 1, "logo_url": 1})
        )
        if teams:
            return {"teams": teams}

    # Fallback: static roster files
    if not ROSTERS_DIR.exists():
        return {"teams": []}
    return {"teams": [f.stem for f in ROSTERS_DIR.glob("*.json")]}


# ---------------------------------------------------------------------------
# Content / metadata endpoints
# ---------------------------------------------------------------------------

@router.get("/content")
def get_content(locale: str = Query(default="en-US")):
    """Return all Valorant game content (agents, maps, acts)."""
    try:
        return riot_api.get_content(locale=locale)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/acts")
def get_acts():
    """Return all competitive acts."""
    try:
        return {"acts": riot_api.get_acts()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/leaderboard/{act_id}")
def get_leaderboard(
    act_id: str,
    size: int = Query(default=200, ge=1, le=200),
    start_index: int = Query(default=0, ge=0),
):
    """Return the competitive leaderboard for an act."""
    try:
        players = riot_api.get_leaderboard(act_id, size=size, start_index=start_index)
        return {"actId": act_id, "players": players}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
