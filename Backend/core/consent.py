"""Player consent gate (Phase 5 of postgres-migration-v2).

Per CONSTITUTION §5: player profiles default private. RSO sign-in is the
player's act of consent that flips them public. Public APIs filter on active
`player_consents` rows at the data layer (NOT the UI layer) to prevent
accidental leaks.

Usage:
  from core.consent import CONSENTED_FILTER_SQL  # ' AND EXISTS(...consent active...)'
  ...
  cur.execute(f"SELECT ... FROM players p WHERE 1=1 {CONSENTED_FILTER_SQL}", ...)

  Or wrap a helper:
  from core.consent import is_player_consented
  if not is_player_consented(cur, player_id):
      raise HTTPException(404, ...)

Admin routes (Backend/core/admin_router.py) DO NOT use these filters — admins
see all players for league bookkeeping and manual data entry.
"""

from typing import Optional

# Reusable SQL fragment for read endpoints. Inserts an EXISTS clause that
# references a `players` row alias `p`. The fragment is intentionally a SQL
# literal — there is no user-input interpolation, so it's safe to f-string in.
CONSENTED_FILTER_SQL = (
    " AND EXISTS ("
    "  SELECT 1 FROM player_consents pc "
    "  WHERE pc.player_id = p.id AND pc.revoked_at IS NULL"
    ")"
)


def is_player_consented(cur, player_id: int) -> bool:
    """Return True if the player has an active consent grant."""
    cur.execute(
        "SELECT 1 FROM player_consents "
        "WHERE player_id = %s AND revoked_at IS NULL LIMIT 1",
        (player_id,),
    )
    return cur.fetchone() is not None


def grant_consent_by_puuid(
    cur,
    puuid: str,
    display_name: str = "",
    game: str = "valorant",
) -> Optional[int]:
    """Find-or-create a `players` row matching the puuid, then ensure an
    active consent record exists. Returns the player_id.

    Idempotent: re-granting consent on an already-active record is a no-op
    (the partial unique index on `player_consents.player_id WHERE
    revoked_at IS NULL` prevents duplicates).
    """
    if not puuid:
        return None

    cur.execute("SELECT id FROM players WHERE riot_puuid = %s", (puuid,))
    row = cur.fetchone()
    if row:
        player_id = row["id"]
    else:
        # Create a minimal player record. display_name from RSO userinfo.
        name = display_name or "Unknown"
        cur.execute(
            "INSERT INTO players (name, display_name, riot_puuid, game, active) "
            "VALUES (%s, %s, %s, %s, TRUE) RETURNING id",
            (name, name, puuid, game),
        )
        player_id = cur.fetchone()["id"]

    # Idempotent consent grant: if there's already an active row, skip.
    cur.execute(
        "SELECT 1 FROM player_consents "
        "WHERE player_id = %s AND revoked_at IS NULL LIMIT 1",
        (player_id,),
    )
    if cur.fetchone() is None:
        cur.execute(
            "INSERT INTO player_consents (player_id, granted_at, riot_puuid) "
            "VALUES (%s, NOW(), %s)",
            (player_id, puuid),
        )

    return player_id


def revoke_consent_for_puuid(cur, puuid: str) -> bool:
    """Revoke the active consent for the given puuid. Returns True if a row
    was revoked, False if no active consent existed."""
    cur.execute(
        "UPDATE player_consents SET revoked_at = NOW() "
        "WHERE riot_puuid = %s AND revoked_at IS NULL",
        (puuid,),
    )
    return cur.rowcount > 0
