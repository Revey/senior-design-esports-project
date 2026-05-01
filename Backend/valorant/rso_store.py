"""RSO token storage in PostgreSQL.

Stores per-player OAuth tokens (access, refresh, id) obtained from Riot Sign
On, and handles token refresh when access tokens expire.
"""

import base64
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests

from core.db import get_cursor
from .config import RSO_CLIENT_ID, RSO_CLIENT_SECRET

logger = logging.getLogger(__name__)

_RSO_TOKEN_URL = "https://auth.riotgames.com/token"


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
    now = datetime.now(timezone.utc)
    expires_in = token_response.get("expires_in", 3600)
    expires_at = now + timedelta(seconds=expires_in)

    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO rso_tokens (
                    puuid, access_token, refresh_token, id_token, token_type,
                    scope, expires_at, game_name, tag_line, linked_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (puuid) DO UPDATE SET
                    access_token = EXCLUDED.access_token,
                    refresh_token = EXCLUDED.refresh_token,
                    id_token = EXCLUDED.id_token,
                    token_type = EXCLUDED.token_type,
                    scope = EXCLUDED.scope,
                    expires_at = EXCLUDED.expires_at,
                    game_name = EXCLUDED.game_name,
                    tag_line = EXCLUDED.tag_line,
                    updated_at = EXCLUDED.updated_at
                """,
                (
                    puuid,
                    token_response["access_token"],
                    token_response.get("refresh_token", ""),
                    token_response.get("id_token", ""),
                    token_response.get("token_type", "Bearer"),
                    token_response.get("scope", ""),
                    expires_at,
                    game_name,
                    tag_line,
                    now,
                    now,
                ),
            )
        logger.info("Stored RSO tokens for %s#%s (%s)", game_name, tag_line, puuid[:8])
    except RuntimeError as exc:
        logger.warning("DATABASE_URL not set — skipping token storage: %s", exc)


def get_tokens(puuid: str) -> Optional[dict]:
    """Retrieve stored tokens for a player."""
    try:
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT puuid, access_token, refresh_token, id_token, token_type,
                       scope, expires_at, game_name, tag_line, linked_at, updated_at
                  FROM rso_tokens WHERE puuid = %s
                """,
                (puuid,),
            )
            row = cur.fetchone()
            return dict(row) if row else None
    except RuntimeError:
        return None


def delete_tokens(puuid: str) -> None:
    """Remove stored tokens (account unlink)."""
    try:
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM rso_tokens WHERE puuid = %s", (puuid,))
        logger.info("Deleted RSO tokens for %s", puuid[:8])
    except RuntimeError:
        pass


def list_linked_players() -> list[dict]:
    """Return summary of all players with linked RSO accounts."""
    try:
        with get_cursor() as cur:
            cur.execute(
                "SELECT puuid, game_name, tag_line, linked_at FROM rso_tokens ORDER BY linked_at DESC"
            )
            return [dict(r) for r in cur.fetchall()]
    except RuntimeError:
        return []


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
    """Return a valid access token for the player, refreshing if expired.

    Returns None if no tokens are stored or refresh fails.
    """
    tokens = get_tokens(puuid)
    if not tokens:
        return None

    now = datetime.now(timezone.utc)
    expires_at = tokens.get("expires_at")
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at and expires_at > now + timedelta(seconds=60):
        return tokens["access_token"]

    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        logger.warning("No refresh token for %s — cannot refresh", puuid[:8])
        return None

    new_tokens = _do_refresh(refresh_token)
    if not new_tokens:
        return None

    store_tokens(
        puuid,
        new_tokens,
        game_name=tokens.get("game_name", ""),
        tag_line=tokens.get("tag_line", ""),
    )
    return new_tokens["access_token"]
