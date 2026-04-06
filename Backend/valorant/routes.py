"""
FastAPI router for Valorant endpoints.

Mount this in main.py:
    from valorant.routes import router as val_router
    app.include_router(val_router, prefix="/api/valorant")
"""

import base64
import json
import logging
import secrets
import time
from pathlib import Path
from typing import Optional

import certifi
import requests as http_requests
from fastapi import APIRouter, Cookie, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from pymongo import MongoClient

from . import riot_api, rso_store, tracker_scraper
from .config import (
    MONGO_URI,
    MONGO_DB,
    RSO_CLIENT_ID,
    RSO_CLIENT_SECRET,
    RSO_REDIRECT_URI,
    FRONTEND_ORIGIN,
    SESSION_SECRET,
)
from .data_builder import build_team_payload
from .models import ValorantTeamPayload, PlayerProfile

logger = logging.getLogger(__name__)

router = APIRouter(tags=["valorant"])

# Simple in-memory cache: {cache_key: (timestamp, data)}
_cache: dict = {}

ROSTERS_DIR = Path(__file__).parent / "rosters"

# MongoDB client (lazy-initialized)
_mongo_client: Optional[MongoClient] = None

# RSO OAuth constants
_RSO_AUTHORIZE_URL = "https://auth.riotgames.com/authorize"
_RSO_TOKEN_URL = "https://auth.riotgames.com/token"
_RSO_USERINFO_URL = "https://auth.riotgames.com/userinfo"

# Session cookie signer
_signer = URLSafeTimedSerializer(SESSION_SECRET)
_SESSION_COOKIE = "rso_session"
_STATE_COOKIE = "rso_state"
_SESSION_MAX_AGE = 86400 * 30  # 30 days


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

    Loads team data from a static roster file.

    Example: GET /api/valorant/team/CSUValGreen
    """
    cache_key = f"team:{team_id}:{use_riot}:{use_scraper}:{num_matches}"

    def _build():
        roster_file = ROSTERS_DIR / f"{team_id}.json"
        if not roster_file.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Team not found in roster files: {team_id}",
            )
        with open(roster_file) as f:
            team_doc = json.load(f)

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
    List all available teams from static roster files.
    """
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


# ---------------------------------------------------------------------------
# RSO (Riot Sign On) endpoints
# ---------------------------------------------------------------------------

def _set_cookie(response, key: str, value: str, max_age: int = _SESSION_MAX_AGE):
    """Set a secure, HTTP-only cookie on the response."""
    response.set_cookie(
        key=key,
        value=value,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=max_age,
        path="/api/valorant/auth",
    )


def _get_session_puuid(rso_session: Optional[str]) -> Optional[str]:
    """Extract and verify the PUUID from a signed session cookie."""
    if not rso_session:
        return None
    try:
        return _signer.loads(rso_session, max_age=_SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None


@router.get("/auth/login")
def rso_login():
    """Redirect the browser to Riot Sign On to begin the OAuth flow."""
    state = secrets.token_urlsafe(32)

    authorize_url = (
        f"{_RSO_AUTHORIZE_URL}"
        f"?redirect_uri={RSO_REDIRECT_URI}"
        f"&client_id={RSO_CLIENT_ID}"
        f"&response_type=code"
        f"&scope=openid+offline_access"
        f"&state={state}"
    )

    response = RedirectResponse(url=authorize_url, status_code=302)
    # Store state in a short-lived cookie for CSRF validation in the callback
    _set_cookie(response, _STATE_COOKIE, _signer.dumps(state), max_age=600)
    return response


@router.get("/auth/callback")
def rso_callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    request: Request = None,
):
    """
    Handle the OAuth callback from Riot.

    Exchanges the authorization code for tokens, fetches userinfo,
    stores tokens in MongoDB, sets a session cookie, and redirects
    back to the frontend.
    """
    error_redirect = f"{FRONTEND_ORIGIN}/valorant/auth?status=error"

    if error or not code:
        msg = error or "no_code"
        return RedirectResponse(url=f"{error_redirect}&message={msg}")

    # --- CSRF: validate state ---
    state_cookie = request.cookies.get(_STATE_COOKIE) if request else None
    expected_state = None
    if state_cookie:
        try:
            expected_state = _signer.loads(state_cookie, max_age=600)
        except (BadSignature, SignatureExpired):
            pass

    if not expected_state or expected_state != state:
        return RedirectResponse(url=f"{error_redirect}&message=invalid_state")

    # --- Exchange code for tokens ---
    credentials = base64.b64encode(
        f"{RSO_CLIENT_ID}:{RSO_CLIENT_SECRET}".encode()
    ).decode()

    try:
        token_resp = http_requests.post(
            _RSO_TOKEN_URL,
            headers={"Authorization": f"Basic {credentials}"},
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": RSO_REDIRECT_URI,
            },
            timeout=10,
        )
        token_resp.raise_for_status()
        token_data = token_resp.json()
    except http_requests.RequestException as exc:
        logger.error("RSO token exchange failed: %s", exc)
        return RedirectResponse(url=f"{error_redirect}&message=token_exchange_failed")

    access_token = token_data.get("access_token")
    if not access_token:
        return RedirectResponse(url=f"{error_redirect}&message=no_access_token")

    # --- Fetch userinfo to get the player's PUUID ---
    try:
        userinfo_resp = http_requests.get(
            _RSO_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        userinfo_resp.raise_for_status()
        userinfo = userinfo_resp.json()
    except http_requests.RequestException as exc:
        logger.error("RSO userinfo request failed: %s", exc)
        return RedirectResponse(url=f"{error_redirect}&message=userinfo_failed")

    puuid = userinfo.get("sub", "")
    if not puuid:
        return RedirectResponse(url=f"{error_redirect}&message=no_puuid")

    # --- Look up Riot ID for display ---
    game_name, tag_line = "", ""
    try:
        profile = riot_api.get_account_by_puuid(puuid)
        game_name = profile.gameName
        tag_line = profile.tagLine
    except Exception as exc:
        logger.warning("Could not look up Riot ID for %s: %s", puuid[:8], exc)

    # --- Store tokens in MongoDB ---
    rso_store.store_tokens(puuid, token_data, game_name, tag_line)

    # --- Set session cookie and redirect to frontend ---
    response = RedirectResponse(
        url=f"{FRONTEND_ORIGIN}/valorant/auth?status=success",
        status_code=302,
    )
    _set_cookie(response, _SESSION_COOKIE, _signer.dumps(puuid))
    # Clear the state cookie
    response.delete_cookie(_STATE_COOKIE, path="/api/valorant/auth")
    return response


@router.get("/auth/status")
def rso_status(rso_session: Optional[str] = Cookie(default=None)):
    """Check whether the current user has a valid RSO session."""
    puuid = _get_session_puuid(rso_session)
    if not puuid:
        return {"authenticated": False}

    tokens = rso_store.get_tokens(puuid)
    if not tokens:
        return {"authenticated": False}

    return {
        "authenticated": True,
        "puuid": puuid,
        "gameName": tokens.get("game_name", ""),
        "tagLine": tokens.get("tag_line", ""),
    }


@router.post("/auth/logout")
def rso_logout():
    """Clear the RSO session cookie."""
    response = RedirectResponse(
        url=f"{FRONTEND_ORIGIN}/valorant/auth",
        status_code=302,
    )
    response.delete_cookie(_SESSION_COOKIE, path="/api/valorant/auth")
    return response


@router.get("/auth/linked-players")
def rso_linked_players():
    """Return all players who have linked their Riot accounts via RSO."""
    players = rso_store.list_linked_players()
    return {
        "players": [
            {
                "puuid": p.get("puuid", ""),
                "gameName": p.get("game_name", ""),
                "tagLine": p.get("tag_line", ""),
            }
            for p in players
        ]
    }
