"""API routes for players."""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from core.db import get_db

router = APIRouter()


@router.get("/")
def list_players(
    game: Optional[str] = Query(None),
    team: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    sort: str = Query("rating"),
    order: str = Query("desc"),
    limit: int = Query(50, ge=1, le=200),
):
    db = get_db()
    if db is None:
        raise HTTPException(503, "Database unavailable")
    filt = {}
    if game:
        filt["game"] = game
    if team:
        filt["team_slug"] = team
    if role:
        filt["role"] = role
    sort_dir = -1 if order == "desc" else 1
    docs = list(
        db["ranked_players"]
        .find(filt, {"_id": 0})
        .sort(sort, sort_dir)
        .limit(limit)
    )
    return docs


@router.get("/{slug}")
def get_player(slug: str):
    db = get_db()
    if db is None:
        raise HTTPException(503, "Database unavailable")
    doc = db["ranked_players"].find_one({"slug": slug}, {"_id": 0})
    if not doc:
        raise HTTPException(404, f"Player '{slug}' not found")
    return doc
