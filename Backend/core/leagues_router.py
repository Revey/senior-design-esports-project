"""API routes for leagues."""

from fastapi import APIRouter, HTTPException
from core.db import get_db
from core.models import LeagueResponse

router = APIRouter()


@router.get("/")
def list_leagues():
    db = get_db()
    if db is None:
        raise HTTPException(503, "Database unavailable")
    docs = list(db["leagues"].find({}, {"_id": 0}))
    return docs


@router.get("/{slug}")
def get_league(slug: str):
    db = get_db()
    if db is None:
        raise HTTPException(503, "Database unavailable")
    doc = db["leagues"].find_one({"slug": slug}, {"_id": 0})
    if not doc:
        raise HTTPException(404, f"League '{slug}' not found")
    return doc
