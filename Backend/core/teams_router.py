"""API routes for teams."""

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from core.db import get_cursor

router = APIRouter()

_SORT_COLUMNS = {
    "rating": "rating",
    "wins": "wins",
    "losses": "losses",
    "name": "name",
}


def _project_team(row: dict) -> dict:
    wins = int(row["wins"] or 0)
    losses = int(row["losses"] or 0)
    played = wins + losses
    win_rate = round((wins / played) * 100, 1) if played else 0.0
    return {
        "slug": row["slug"],
        "name": row["name"],
        "school": row["school_name"] or "",
        "game": row["game"],
        "record": {"wins": wins, "losses": losses},
        "win_rate": win_rate,
        "rating": int(row["rating"] or 0),
        "region": row["region"] or "",
        "league_slug": row["league_slug"] or "",
    }


@router.get("/")
def list_teams(
    game: Optional[str] = Query(None),
    sort: str = Query("rating"),
    order: str = Query("desc"),
    limit: int = Query(50, ge=1, le=100),
):
    sort_col = _SORT_COLUMNS.get(sort, "rating")
    sort_dir = "DESC" if order.lower() == "desc" else "ASC"
    sql = (
        "SELECT slug, name, school_name, game, region, league_slug, "
        "wins, losses, map_wins, map_losses, rating FROM teams"
    )
    params: list[Any] = []
    if game:
        sql += " WHERE game = %s"
        params.append(game)
    sql += f" ORDER BY {sort_col} {sort_dir} NULLS LAST LIMIT %s"
    params.append(limit)

    with get_cursor() as cur:
        cur.execute(sql, params)
        return [_project_team(r) for r in cur.fetchall()]


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


@router.get("/{slug}")
def get_team(slug: str):
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id, slug, name, school_name, game, region, league_slug,
                   wins, losses, map_wins, map_losses, rating
              FROM teams
             WHERE slug = %s
             LIMIT 1
            """,
            (slug,),
        )
        team = cur.fetchone()
        if not team:
            raise HTTPException(404, f"Team '{slug}' not found")

        team_id = team["id"]

        cur.execute(
            """
            SELECT p.id, p.display_name, p.role, p.riot_id, p.active
              FROM team_players tp
              JOIN players p ON p.id = tp.player_id
             WHERE tp.team_id = %s
             ORDER BY tp.joined_at
            """,
            (team_id,),
        )
        roster = [
            {
                "name": r["display_name"],
                "role": r["role"],
                "riotId": r["riot_id"],
                "active": bool(r["active"]),
            }
            for r in cur.fetchall()
        ]

        cur.execute(
            """
            SELECT id, game, format, match_date,
                   team1_id, team2_id, team1_name, team2_name,
                   team1_score, team2_score, winner_team_id
              FROM matches
             WHERE team1_id = %s OR team2_id = %s
             ORDER BY match_date DESC
             LIMIT 15
            """,
            (team_id, team_id),
        )
        recent_matches = []
        for m in cur.fetchall():
            is_team1 = m["team1_id"] == team_id
            opp_name = m["team2_name"] if is_team1 else m["team1_name"]
            own_score = m["team1_score"] if is_team1 else m["team2_score"]
            opp_score = m["team2_score"] if is_team1 else m["team1_score"]
            winner = m["winner_team_id"]
            recent_matches.append({
                "matchId": str(m["id"]),
                "date": _iso(m["match_date"]),
                "game": m["game"],
                "format": m["format"],
                "opponent": opp_name,
                "own_score": own_score,
                "opp_score": opp_score,
                "win": winner == team_id if winner is not None else None,
            })

    projected = _project_team(team)
    return {
        **projected,
        "roster": roster,
        "recent_matches": recent_matches,
        "map_record": {
            "wins": int(team["map_wins"] or 0),
            "losses": int(team["map_losses"] or 0),
        },
    }
