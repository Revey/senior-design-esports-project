"""API routes for tournaments."""

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from core.db import get_cursor

router = APIRouter()


def _project(row: dict) -> dict:
    return {
        "slug": row["slug"],
        "name": row["name"],
        "game": row["game"],
        "format": row["format"],
        "status": row["status"],
        "start_date": row["start_date"].isoformat() if row["start_date"] else "",
        "end_date": row["end_date"].isoformat() if row["end_date"] else "",
        "teams": row["teams"] or [],
        "matches": row["matches"] or [],
    }


@router.get("/")
def list_tournaments(
    status: Optional[str] = Query(None),
    game: Optional[str] = Query(None),
):
    sql = (
        "SELECT slug, name, game, format, status, start_date, end_date, teams, matches "
        "FROM tournaments"
    )
    clauses: list[str] = []
    params: list[Any] = []
    if status:
        clauses.append("status = %s")
        params.append(status)
    if game:
        clauses.append("game = %s")
        params.append(game)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY start_date DESC NULLS LAST"
    with get_cursor() as cur:
        cur.execute(sql, params)
        return [_project(r) for r in cur.fetchall()]


@router.get("/{slug}")
def get_tournament(slug: str):
    with get_cursor() as cur:
        cur.execute(
            "SELECT slug, name, game, format, status, start_date, end_date, teams, matches "
            "FROM tournaments WHERE slug = %s",
            (slug,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, f"Tournament '{slug}' not found")
        return _project(row)
