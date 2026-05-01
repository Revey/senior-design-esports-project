"""API routes for players."""

from collections import Counter
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from core.db import get_cursor

router = APIRouter()

_SORT_COLUMNS = {
    "rating": "p.rating",
    "name": "p.display_name",
}


def _project_player(row: dict) -> dict:
    return {
        "slug": row["slug"] or "",
        "name": row["display_name"],
        "team_name": row.get("team_name") or "",
        "team_slug": row.get("team_slug") or "",
        "game": row["game"],
        "role": row["role"] or "",
        "stats": row["stats"] or {},
        "rating": int(row["rating"] or 0),
    }


@router.get("/")
def list_players(
    game: Optional[str] = Query(None),
    team: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    sort: str = Query("rating"),
    order: str = Query("desc"),
    limit: int = Query(50, ge=1, le=200),
):
    sort_col = _SORT_COLUMNS.get(sort, "p.rating")
    sort_dir = "DESC" if order.lower() == "desc" else "ASC"

    sql = [
        "SELECT p.slug, p.display_name, p.game, p.role, p.stats, p.rating,",
        "       t.name AS team_name, t.slug AS team_slug",
        "  FROM players p",
        "  LEFT JOIN LATERAL (",
        "    SELECT tp.team_id FROM team_players tp WHERE tp.player_id = p.id",
        "    ORDER BY tp.joined_at LIMIT 1",
        "  ) tp ON TRUE",
        "  LEFT JOIN teams t ON t.id = tp.team_id",
    ]
    clauses: list[str] = []
    params: list[Any] = []
    if game:
        clauses.append("p.game = %s")
        params.append(game)
    if team:
        clauses.append("t.slug = %s")
        params.append(team)
    if role:
        clauses.append("p.role = %s")
        params.append(role)
    if clauses:
        sql.append("WHERE " + " AND ".join(clauses))
    sql.append(f"ORDER BY {sort_col} {sort_dir} NULLS LAST LIMIT %s")
    params.append(limit)

    with get_cursor() as cur:
        cur.execute(" ".join(sql), params)
        return [_project_player(r) for r in cur.fetchall()]


@router.get("/{slug}")
def get_player(slug: str):
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT p.id, p.slug, p.display_name, p.game, p.role, p.stats, p.rating,
                   t.name AS team_name, t.slug AS team_slug
              FROM players p
              LEFT JOIN LATERAL (
                SELECT tp.team_id FROM team_players tp WHERE tp.player_id = p.id
                ORDER BY tp.joined_at LIMIT 1
              ) tp ON TRUE
              LEFT JOIN teams t ON t.id = tp.team_id
             WHERE p.slug = %s
             LIMIT 1
            """,
            (slug,),
        )
        player = cur.fetchone()
        if not player:
            raise HTTPException(404, f"Player '{slug}' not found")

        cur.execute(
            """
            SELECT id, match_id, team_id, team_name, game, map_name,
                   agent, champion, role, kills, deaths, assists, acs,
                   first_kills, plants, defuses, cs, gold, damage,
                   vision, wards, win
              FROM player_match_stats
             WHERE player_id = %s
             ORDER BY id DESC
             LIMIT 25
            """,
            (player["id"],),
        )
        stat_rows = cur.fetchall()

    recent_matches = []
    for r in stat_rows:
        cleaned = {
            "_id": str(r["id"]),
            "matchId": str(r["match_id"]),
            "teamId": str(r["team_id"]) if r["team_id"] is not None else None,
            "teamName": r["team_name"],
            "game": r["game"],
            "mapName": r["map_name"] or None,
            "kills": r["kills"],
            "deaths": r["deaths"],
            "assists": r["assists"],
            "win": bool(r["win"]),
        }
        if r["game"] == "Valorant":
            cleaned.update({
                "agent": r["agent"],
                "acs": r["acs"],
                "firstKills": r["first_kills"],
                "plants": r["plants"],
                "defuses": r["defuses"],
            })
        else:
            cleaned.update({
                "champion": r["champion"],
                "role": r["role"],
                "cs": r["cs"],
                "gold": r["gold"],
                "damage": r["damage"],
                "vision": r["vision"],
                "wards": r["wards"],
            })
        recent_matches.append(cleaned)

    freq_field = "agent" if player["game"] == "Valorant" else "champion"
    freq = Counter(r[freq_field] for r in stat_rows if r.get(freq_field))
    frequency = [{"name": name, "count": count} for name, count in freq.most_common()]

    projected = _project_player(player)
    return {
        **projected,
        "recent_matches": recent_matches,
        "frequency": frequency,
        "frequency_field": freq_field,
    }
