"""API routes for tournaments."""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from core.db import get_db

router = APIRouter()


@router.get("/")
def list_tournaments(
    status: Optional[str] = Query(None),
    game: Optional[str] = Query(None),
):
    db = get_db()
    if db is None:
        raise HTTPException(503, "Database unavailable")
    filt = {}
    if status:
        filt["status"] = status
    if game:
        filt["game"] = game
    docs = list(db["tournaments"].find(filt, {"_id": 0}))
    return docs


@router.get("/{slug}")
def get_tournament(slug: str):
    db = get_db()
    if db is None:
        raise HTTPException(503, "Database unavailable")
    doc = db["tournaments"].find_one({"slug": slug}, {"_id": 0})
    if not doc:
        raise HTTPException(404, f"Tournament '{slug}' not found")
    return doc
