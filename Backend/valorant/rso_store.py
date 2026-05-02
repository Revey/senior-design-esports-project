"""RSO token storage in Postgres (Phase 3g of postgres-migration-v2).

Stores per-player OAuth tokens (access, refresh) obtained from Riot Sign On,
and handles token refresh when access tokens expire.

Phase 5 will layer on the consent-gating model — this file only handles the
mechanical token storage / refresh. Phase 1 schema's `rso_tokens` table:

    rso_tokens (
      puuid          TEXT PRIMARY KEY,
      access_token   TEXT NOT NULL,
      refresh_token  TEXT,
      expires_at     TIMESTAMPTZ NOT NULL,
      created_at, updated_at
    )

The Mongo predecessor stored extra fields (id_token, token_type, scope,
game_name, tag_line, linked_at). These are not in the Phase 1 schema and are
dropped here. game_name/tag_line can be re-resolved via Riot API from puuid
when needed; id_token is unused outside the immediate callback flow.
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
    """Upsert RSO tokens for a player.

    `game_name` / `tag_line` are accepted for caller compatibility but not
    persisted (Phase 1 schema doesn't carry those columns). Re-resolve via
    Riot API when needed.
    """
    expires_in = token_response.get("expires_in", 3600)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    access = token_response["access_token"]
    refresh = token_response.get("refresh_token") or None

    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO rso_tokens (puuid, access_token, refresh_token, expires_at) "
            "VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (puuid) DO UPDATE SET "
            "  access_token = EXCLUDED.access_token, "
            "  refresh_token = EXCLUDED.refresh_token, "
            "  expires_at    = EXCLUDED.expires_at",
            (puuid, access, refresh, expires_at),
        )
    logger.info(
        "Stored RSO tokens for %s#%s (puuid=%s)",
        game_name or "?", tag_line or "?", puuid[:8] if puuid else "",
    )


def get_tokens(puuid: str) -> Optional[dict]:
    """Retrieve stored tokens for a player. Returns None if not found.

    The returned dict mirrors the Mongo-era shape (puuid, access_token,
    refresh_token, expires_at, plus empty strings for the dropped fields)
    so callers don't need to change.
    """
    with get_cursor() as cur:
        cur.execute(
            "SELECT puuid, access_token, refresh_token, expires_at "
            "FROM rso_tokens WHERE puuid = %s",
            (puuid,),
        )
        row = cur.fetchone()
    if row is None:
        return None
    return {
        "puuid":         row["puuid"],
        "access_token":  row["access_token"],
        "refresh_token": row["refresh_token"] or "",
        "expires_at":    row["expires_at"],
        # Dropped Mongo-era fields, kept as empty strings for caller compat:
        "id_token":   "",
        "token_type": "Bearer",
        "scope":      "",
        "game_name":  "",
        "tag_line":   "",
    }


def delete_tokens(puuid: str) -> None:
    """Remove stored tokens (account unlink)."""
    with get_cursor() as cur:
        cur.execute("DELETE FROM rso_tokens WHERE puuid = %s", (puuid,))
    logger.info("Deleted RSO tokens for puuid=%s", puuid[:8] if puuid else "")


def list_linked_players() -> list[dict]:
    """Summary of all players with linked RSO accounts (puuid + linked_at).

    Phase 1 schema doesn't carry game_name/tag_line; we return puuid + the
    row's created_at as `linked_at` for caller compatibility.
    """
    with get_cursor() as cur:
        cur.execute(
            "SELECT puuid, created_at FROM rso_tokens ORDER BY created_at DESC"
        )
        rows = cur.fetchall()
    return [
        {
            "puuid":     r["puuid"],
            "game_name": "",
            "tag_line":  "",
            "linked_at": r["created_at"],
        }
        for r in rows
    ]


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
                "grant_type":    "refresh_token",
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
    Returns None if no tokens stored or refresh fails."""
    tokens = get_tokens(puuid)
    if not tokens:
        return None

    now = datetime.now(timezone.utc)
    expires_at = tokens.get("expires_at")
    if expires_at is not None:
        # tokens already expires_at-aware (TIMESTAMPTZ).
        if expires_at > now + timedelta(seconds=60):
            return tokens["access_token"]

    refresh_token = tokens.get("refresh_token") or ""
    if not refresh_token:
        logger.warning("No refresh token for puuid=%s — cannot refresh", puuid[:8])
        return None

    new_tokens = _do_refresh(refresh_token)
    if not new_tokens:
        return None

    store_tokens(puuid, new_tokens)
    return new_tokens["access_token"]
