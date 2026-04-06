"""
RSO token storage in MongoDB.

Stores per-player OAuth tokens (access, refresh, id) obtained from
Riot Sign On, and handles token refresh when access tokens expire.
"""

import base64
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import certifi
import requests
from pymongo import MongoClient

from .config import (
    MONGO_URI,
    MONGO_DB,
    RSO_CLIENT_ID,
    RSO_CLIENT_SECRET,
    RSO_REDIRECT_URI,
)

logger = logging.getLogger(__name__)

_RSO_TOKEN_URL = "https://auth.riotgames.com/token"
_COLLECTION = "rso_tokens"

# ---------------------------------------------------------------------------
# MongoDB connection (lazy singleton)
# ---------------------------------------------------------------------------

_mongo_client: Optional[MongoClient] = None


def _get_db():
    global _mongo_client
    if not MONGO_URI:
        return None
    if _mongo_client is None:
        _mongo_client = MongoClient(MONGO_URI, tls=True, tlsCAFile=certifi.where())
    return _mongo_client[MONGO_DB]


def _col():
    db = _get_db()
    if db is None:
        return None
    return db[_COLLECTION]


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def store_tokens(
    puuid: str,
    token_response: dict,
    game_name: str = "",
    tag_line: str = "",
) -> None:
    """Upsert RSO tokens for a player."""
    col = _col()
    if col is None:
        logger.warning("MongoDB not configured — skipping token storage")
        return

    now = datetime.now(timezone.utc)
    expires_in = token_response.get("expires_in", 3600)

    doc = {
        "puuid": puuid,
        "access_token": token_response["access_token"],
        "refresh_token": token_response.get("refresh_token", ""),
        "id_token": token_response.get("id_token", ""),
        "token_type": token_response.get("token_type", "Bearer"),
        "scope": token_response.get("scope", ""),
        "expires_at": now + timedelta(seconds=expires_in),
        "game_name": game_name,
        "tag_line": tag_line,
        "updated_at": now,
    }

    col.update_one(
        {"puuid": puuid},
        {"$set": doc, "$setOnInsert": {"linked_at": now}},
        upsert=True,
    )
    logger.info("Stored RSO tokens for %s#%s (%s)", game_name, tag_line, puuid[:8])


def get_tokens(puuid: str) -> Optional[dict]:
    """Retrieve stored tokens for a player."""
    col = _col()
    if col is None:
        return None
    return col.find_one({"puuid": puuid}, {"_id": 0})


def delete_tokens(puuid: str) -> None:
    """Remove stored tokens (account unlink)."""
    col = _col()
    if col is None:
        return
    col.delete_one({"puuid": puuid})
    logger.info("Deleted RSO tokens for %s", puuid[:8])


def list_linked_players() -> list[dict]:
    """Return summary of all players with linked RSO accounts."""
    col = _col()
    if col is None:
        return []
    return list(col.find(
        {},
        {"_id": 0, "puuid": 1, "game_name": 1, "tag_line": 1, "linked_at": 1},
    ))


# ---------------------------------------------------------------------------
# Token refresh
# ---------------------------------------------------------------------------

def _do_refresh(refresh_token: str) -> Optional[dict]:
    """Exchange a refresh token for a new access token via Riot's token endpoint."""
    credentials = base64.b64encode(
        f"{RSO_CLIENT_ID}:{RSO_CLIENT_SECRET}".encode()
    ).decode()

    try:
        resp = requests.post(
            _RSO_TOKEN_URL,
            headers={"Authorization": f"Basic {credentials}"},
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        logger.error("RSO token refresh failed: %s", exc)
        return None


def refresh_if_expired(puuid: str) -> Optional[str]:
    """
    Return a valid access token for the player, refreshing if expired.

    Returns None if no tokens stored or refresh fails.
    """
    tokens = get_tokens(puuid)
    if not tokens:
        return None

    now = datetime.now(timezone.utc)
    expires_at = tokens.get("expires_at")

    # If token is still valid (with 60s buffer), return it
    if expires_at and expires_at.replace(tzinfo=timezone.utc) > now + timedelta(seconds=60):
        return tokens["access_token"]

    # Attempt refresh
    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        logger.warning("No refresh token for %s — cannot refresh", puuid[:8])
        return None

    new_tokens = _do_refresh(refresh_token)
    if not new_tokens:
        return None

    # Update stored tokens
    store_tokens(
        puuid,
        new_tokens,
        game_name=tokens.get("game_name", ""),
        tag_line=tokens.get("tag_line", ""),
    )
    return new_tokens["access_token"]
