"""API routes for teams (Postgres-backed; Phase 3c of postgres-migration-v2).

Wire contract during Phase 3 (Path A — preserve existing frontend contract):
  - snake_case for win_rate / league_slug / recent_matches / map_record /
    own_score / opp_score (matches Frontend/app/teams/{page,[slug]/page}.tsx).
  - camelCase for matchId, riotId.
  - game enum mapped at the router boundary: DB stores 'valorant'/'lol' (per
    Phase 1 schema CHECK constraint); frontend uses 'Valorant'/'League of
    Legends' display labels. Phase 4 will standardize the frontend to the
    canonical lowercase form and drop these case-mapping shims.

The mixed-case shape is intentional Phase-3 backward compat — Phase 4 is the
wire-format standardization phase.
"""

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from core.db import get_cursor

router = APIRouter()

_GAME_LABEL_TO_DB = {"Valorant": "valorant", "League of Legends": "lol"}
_GAME_DB_TO_LABEL = {v: k for k, v in _GAME_LABEL_TO_DB.items()}

# Sort whitelist matches the frontend's SortField type exactly:
#   "rating" | "win_rate" | "record.wins"
# `name` is NOT included — the frontend never sorts by it.
_SORT_COLUMNS = {
    "rating":      "rating",
    "record.wins": "wins",
    "win_rate":    ("CASE WHEN (wins + losses) > 0 "
                    "THEN (wins::float / (wins + losses)) ELSE 0 END"),
}
_SORT_ORDERS = {"asc", "desc"}


def _normalize_game_filter(label: Optional[str]) -> Optional[str]:
    """Convert frontend label → DB enum value.

    None / 'All' → no filter (returns None, callers skip the WHERE clause).
    Known label → mapped lowercase enum.
    Unknown label → lowercased and passed through. The CHECK constraint on
        teams.game ensures the SQL returns zero rows. This matches the Mongo
        router's "filter on this string, get nothing if it doesn't match"
        behavior rather than silently ignoring the filter.
    """
    if label is None or label == "All":
        return None
    if label in _GAME_LABEL_TO_DB:
        return _GAME_LABEL_TO_DB[label]
    return label.lower()


def _label_game(db_value: str) -> str:
    """Reverse map for response shape: 'valorant' → 'Valorant', etc."""
    return _GAME_DB_TO_LABEL.get(db_value, db_value)


def _team_row_to_response(row: dict) -> dict:
    """Shape a `teams` row into the existing frontend wire contract.

    Note the snake_case/camelCase mix — that's the existing Mongo contract,
    preserved here. Phase 4 standardizes.
    """
    wins = int(row.get("wins") or 0)
    losses = int(row.get("losses") or 0)
    total = wins + losses
    win_rate = round((wins / total) * 100, 1) if total > 0 else 0.0
    rating = row.get("rating")
    return {
        "slug": row.get("slug", ""),
        "name": row.get("name", ""),
        "school": row.get("school_name") or "",
        "game": _label_game(row.get("game", "")),
        "record": {"wins": wins, "losses": losses},
        "win_rate": win_rate,
        "rating": float(rating) if rating is not None else None,
        "region": row.get("region") or "",
        "league_slug": "",
    }


def _match_row_to_recent(m: dict, own_team_id: int) -> dict:
    is_team1 = m["team1_id"] == own_team_id
    opp_name = m["team2_name"] if is_team1 else m["team1_name"]
    own_score = m["team1_score"] if is_team1 else m["team2_score"]
    opp_score = m["team2_score"] if is_team1 else m["team1_score"]
    if own_score is None or opp_score is None or own_score == opp_score:
        win = None
    else:
        win = own_score > opp_score
    return {
        "matchId": str(m["id"]),
        "date": m["match_date"].isoformat() if m.get("match_date") else None,
        "game": _label_game(m.get("game", "")),
        "format": m.get("format"),
        "opponent": opp_name or "",
        "own_score": own_score,
        "opp_score": opp_score,
        "win": win,
    }


@router.get("/")
def list_teams(
    game: Optional[str] = Query(None),
    sort: str = Query("rating"),
    order: str = Query("desc"),
    limit: int = Query(50, ge=1, le=100),
):
    if sort not in _SORT_COLUMNS:
        raise HTTPException(status_code=400, detail=f"Invalid sort: {sort!r}")
    if order not in _SORT_ORDERS:
        raise HTTPException(status_code=400, detail=f"Invalid order: {order!r}")

    direction = "DESC" if order == "desc" else "ASC"
    sort_expr = _SORT_COLUMNS[sort]  # whitelisted SQL fragment, never user input
    db_game = _normalize_game_filter(game)

    sql = (
        f"SELECT * FROM teams "
        f"WHERE (%s::text IS NULL OR game = %s::text) "
        f"ORDER BY {sort_expr} {direction} NULLS LAST, name "
        f"LIMIT %s"
    )
    with get_cursor() as cur:
        cur.execute(sql, (db_game, db_game, limit))
        rows = cur.fetchall()
    return [_team_row_to_response(r) for r in rows]


@router.get("/{slug}")
def get_team(slug: str):
    """Get one team by slug.

    NOTE: teams.slug is UNIQUE only within (slug, game). The frontend detail
    URL carries no game qualifier, so on the rare collision (slug shared
    across Valorant + LoL teams) we deterministically return the earlier
    team (by id ASC). This matches the Mongo router's `find_one` behavior —
    neither was strictly unambiguous. Phase 4 will switch to game-qualified
    URLs and remove this caveat.
    """
    with get_cursor() as cur:
        cur.execute(
            "SELECT * FROM teams WHERE slug = %s ORDER BY id ASC LIMIT 1",
            (slug,),
        )
        team = cur.fetchone()
        if team is None:
            raise HTTPException(status_code=404, detail=f"Team '{slug}' not found")

        cur.execute(
            "SELECT p.display_name, p.role, p.riot_id, p.active "
            "FROM players p "
            "JOIN team_players tp ON tp.player_id = p.id "
            "WHERE tp.team_id = %s AND tp.left_at IS NULL "
            "ORDER BY p.display_name",
            (team["id"],),
        )
        roster_rows = cur.fetchall()

        cur.execute(
            "SELECT m.id, m.match_date, m.game, m.format, "
            "       m.team1_id, m.team2_id, m.team1_score, m.team2_score, "
            "       t1.name AS team1_name, t2.name AS team2_name "
            "FROM matches m "
            "LEFT JOIN teams t1 ON t1.id = m.team1_id "
            "LEFT JOIN teams t2 ON t2.id = m.team2_id "
            "WHERE m.team1_id = %s OR m.team2_id = %s "
            "ORDER BY m.match_date DESC "
            "LIMIT 15",
            (team["id"], team["id"]),
        )
        match_rows = cur.fetchall()

    response = _team_row_to_response(team)
    response["roster"] = [
        {
            "name": r["display_name"],
            "role": r["role"],
            "riotId": r["riot_id"],
            "active": r["active"],
        }
        for r in roster_rows
    ]
    response["recent_matches"] = [
        _match_row_to_recent(m, team["id"]) for m in match_rows
    ]
    response["map_record"] = {
        "wins": int(team.get("map_wins") or 0),
        "losses": int(team.get("map_losses") or 0),
    }
    return response
