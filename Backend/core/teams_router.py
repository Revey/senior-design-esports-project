"""API routes for teams."""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from core.db import get_db

router = APIRouter()


@router.get("/")
def list_teams(
    game: Optional[str] = Query(None),
    sort: str = Query("rating"),
    order: str = Query("desc"),
    limit: int = Query(50, ge=1, le=100),
):
    db = get_db()
    if db is None:
        raise HTTPException(503, "Database unavailable")
    filt = {}
    if game:
        filt["game"] = game
    sort_dir = -1 if order == "desc" else 1
    docs = list(
        db["ranked_teams"]
        .find(filt, {"_id": 0})
        .sort(sort, sort_dir)
        .limit(limit)
    )
    return docs


@router.get("/{slug}")
def get_team(slug: str):
    db = get_db()
    if db is None:
        raise HTTPException(503, "Database unavailable")
    doc = db["ranked_teams"].find_one({"slug": slug}, {"_id": 0})
    if not doc:
        raise HTTPException(404, f"Team '{slug}' not found")
    return doc
