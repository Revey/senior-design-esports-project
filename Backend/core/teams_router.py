"""API routes for teams (Postgres-backed; Phase 4 wire-format standardized).

Wire format:
  - Game enum: lowercase 'valorant' / 'lol' on the wire (matches DB).
  - All response field names: camelCase (winRate, leagueSlug, recentMatches,
    mapRecord, ownScore, oppScore, teamName, mapWins/Losses).
  - Frontend handles display-label mapping ('valorant' → 'Valorant' UI label).

The Path A snake_case + TitleCase shims were dropped in Phase 4 once Phase 3
established the full Postgres surface.
"""

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from core.db import get_cursor

router = APIRouter()

_VALID_GAMES = {"valorant", "lol"}

_SORT_COLUMNS = {
    "rating":      "rating",
    "record.wins": "wins",
    "winRate":     ("CASE WHEN (wins + losses) > 0 "
                    "THEN (wins::float / (wins + losses)) ELSE 0 END"),
}
_SORT_ORDERS = {"asc", "desc"}


def _team_row_to_response(row: dict) -> dict:
    wins = int(row.get("wins") or 0)
    losses = int(row.get("losses") or 0)
    total = wins + losses
    win_rate = round((wins / total) * 100, 1) if total > 0 else 0.0
    rating = row.get("rating")
    return {
        "slug":       row.get("slug", ""),
        "name":       row.get("name", ""),
        "school":     row.get("school_name") or "",
        "game":       row.get("game", ""),
        "record":     {"wins": wins, "losses": losses},
        "winRate":    win_rate,
        "rating":     float(rating) if rating is not None else None,
        "region":     row.get("region") or "",
        "leagueSlug": "",
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
        "matchId":  str(m["id"]),
        "date":     m["match_date"].isoformat() if m.get("match_date") else None,
        "game":     m.get("game", ""),
        "format":   m.get("format"),
        "opponent": opp_name or "",
        "ownScore": own_score,
        "oppScore": opp_score,
        "win":      win,
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
    if game is not None and game != "" and game not in _VALID_GAMES:
        # Pass-through unknown values; SQL CHECK constraint produces empty
        # results. Preserves "filter on this string, get nothing if it doesn't
        # match" behavior.
        pass

    direction = "DESC" if order == "desc" else "ASC"
    sort_expr = _SORT_COLUMNS[sort]
    db_game = game if game else None

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
    """Get one team by slug. Slug is unique within (slug, game); on cross-game
    collision we return the earliest by id ASC. Frontend may switch to
    game-qualified URLs in a future phase."""
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
            "name":   r["display_name"],
            "role":   r["role"],
            "riotId": r["riot_id"],
            "active": r["active"],
        }
        for r in roster_rows
    ]
    response["recentMatches"] = [
        _match_row_to_recent(m, team["id"]) for m in match_rows
    ]
    response["mapRecord"] = {
        "wins":   int(team.get("map_wins") or 0),
        "losses": int(team.get("map_losses") or 0),
    }
    return response
