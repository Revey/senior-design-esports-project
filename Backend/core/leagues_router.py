"""API routes for leagues."""

from fastapi import APIRouter, HTTPException

from core.db import get_cursor

router = APIRouter()


def _standings(cur, league_id: int) -> list[dict]:
    cur.execute(
        """
        SELECT t.name, t.slug, t.wins, t.losses
          FROM teams t
         WHERE t.league_id = %s
         ORDER BY t.wins DESC, t.losses ASC, t.name
        """,
        (league_id,),
    )
    rows = cur.fetchall()
    standings = []
    for i, r in enumerate(rows, start=1):
        played = (r["wins"] or 0) + (r["losses"] or 0)
        win_rate = round((r["wins"] / played) * 100, 1) if played else 0.0
        standings.append({
            "rank": i,
            "team_name": r["name"],
            "team_slug": r["slug"],
            "wins": r["wins"] or 0,
            "losses": r["losses"] or 0,
            "win_rate": win_rate,
        })
    return standings


def _project(row: dict, standings: list[dict]) -> dict:
    return {
        "slug": row["slug"],
        "name": row["name"],
        "abbreviation": row["abbreviation"],
        "game": row["game"],
        "season": row["season"],
        "description": row["description"],
        "conference": row["conference"],
        "standings": standings,
    }


@router.get("/")
def list_leagues():
    with get_cursor() as cur:
        cur.execute(
            "SELECT id, slug, name, abbreviation, game, season, description, conference "
            "FROM leagues ORDER BY name"
        )
        rows = cur.fetchall()
        return [_project(r, _standings(cur, r["id"])) for r in rows]


@router.get("/{slug}")
def get_league(slug: str):
    with get_cursor() as cur:
        cur.execute(
            "SELECT id, slug, name, abbreviation, game, season, description, conference "
            "FROM leagues WHERE slug = %s",
            (slug,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, f"League '{slug}' not found")
        return _project(row, _standings(cur, row["id"]))
