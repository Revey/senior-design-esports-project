"""API routes for tournaments (Postgres-backed; Phase 3b of postgres-migration-v2).

Two endpoints:
  GET /api/tournaments               — list, optional ?game= filter
  GET /api/tournaments/{slug}        — single by slug, 404 on miss

Wire format: camelCase per CONSTITUTION §4 (snake_case DB columns → camelCase
JSON via core.projection.to_camel). JSONB columns (`teams`, `matches`) pass
through unchanged.

Note: the Mongo predecessor accepted a `status` query param; the Phase 1
schema does not have a `status` column on `tournaments`. The param is dropped
in Phase 3b. If a future feature needs it, that's a schema-migration phase.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from core.db import get_cursor
from core.projection import to_camel

router = APIRouter()


@router.get("/")
def list_tournaments(game: Optional[str] = Query(None)):
    """List tournaments. Optional `game` filter ('valorant' | 'lol').
    Returns [] when none match.
    """
    with get_cursor() as cur:
        if game is not None:
            cur.execute(
                "SELECT * FROM tournaments WHERE game = %s "
                "ORDER BY start_date DESC NULLS LAST, name",
                (game,),
            )
        else:
            cur.execute(
                "SELECT * FROM tournaments "
                "ORDER BY start_date DESC NULLS LAST, name"
            )
        rows = cur.fetchall()
    return [to_camel(r) for r in rows]


@router.get("/{slug}")
def get_tournament(slug: str):
    """Get one tournament by slug. 404 if not found."""
    with get_cursor() as cur:
        cur.execute("SELECT * FROM tournaments WHERE slug = %s", (slug,))
        row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Tournament '{slug}' not found")
    return to_camel(row)
