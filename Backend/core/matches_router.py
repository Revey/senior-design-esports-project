"""API routes for match history (read-only public endpoints)."""

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from core.db import get_cursor

router = APIRouter()


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _int_id(s: str, field: str) -> int:
    try:
        return int(s)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"Invalid {field}: {s}")


def _list_row(row: dict) -> dict:
    return {
        "_id": str(row["id"]),
        "game": row["game"],
        "format": row["format"],
        "date": _iso(row["match_date"]),
        "team1Id": str(row["team1_id"]) if row["team1_id"] is not None else None,
        "team2Id": str(row["team2_id"]) if row["team2_id"] is not None else None,
        "team1Name": row["team1_name"],
        "team2Name": row["team2_name"],
        "team1Score": row["team1_score"],
        "team2Score": row["team2_score"],
        "winnerTeamId": str(row["winner_team_id"]) if row["winner_team_id"] is not None else None,
        "leagueId": str(row["league_id"]) if row["league_id"] is not None else None,
        "leagueName": row["league_name"],
    }


@router.get("/")
def list_matches(
    game: Optional[str] = Query(None),
    team: Optional[str] = Query(None, description="team id (team1 or team2)"),
    limit: int = Query(25, ge=1, le=100),
    page: int = Query(1, ge=1),
):
    clauses: list[str] = []
    params: list[Any] = []
    if game:
        clauses.append("game = %s")
        params.append(game)
    if team:
        tid = _int_id(team, "team")
        clauses.append("(team1_id = %s OR team2_id = %s)")
        params.extend([tid, tid])
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

    with get_cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS n FROM matches{where}", params)
        total = int(cur.fetchone()["n"])

        offset = (page - 1) * limit
        cur.execute(
            f"""
            SELECT id, game, format, match_date,
                   team1_id, team2_id, team1_name, team2_name,
                   team1_score, team2_score, winner_team_id,
                   league_id, league_name
              FROM matches
             {where}
             ORDER BY match_date DESC
             LIMIT %s OFFSET %s
            """,
            [*params, limit, offset],
        )
        items = [_list_row(r) for r in cur.fetchall()]
    return {"items": items, "total": total, "page": page, "limit": limit}


@router.get("/{match_id}")
def get_match(match_id: str):
    mid = _int_id(match_id, "match_id")
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id, game, format, match_date, source,
                   team1_id, team2_id, team1_name, team2_name,
                   team1_score, team2_score, winner_team_id,
                   league_id, league_name, maps, lol_players
              FROM matches
             WHERE id = %s
            """,
            (mid,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Match not found")

    doc = _list_row(row)
    doc["maps"] = row["maps"] or []
    if row["game"] == "League of Legends":
        doc["players"] = row["lol_players"] or {}
    doc["source"] = row["source"]
    return doc
