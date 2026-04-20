"""API routes for match history (read-only public endpoints)."""

from fastapi import APIRouter, HTTPException, Query
from typing import Any, Optional

from bson import ObjectId
from bson.errors import InvalidId

from core.db import get_db

router = APIRouter()


def _clean(row: dict[str, Any]) -> dict[str, Any]:
    row = dict(row)
    for k, v in list(row.items()):
        if k == "_id" or k.endswith("Id"):
            row[k] = str(v) if v is not None else None
        elif isinstance(v, ObjectId):
            row[k] = str(v)
    return row


@router.get("/")
def list_matches(
    game: Optional[str] = Query(None),
    team: Optional[str] = Query(None, description="team ObjectId (team1 or team2)"),
    limit: int = Query(25, ge=1, le=100),
    page: int = Query(1, ge=1),
):
    db = get_db()
    if db is None:
        raise HTTPException(503, "Database unavailable")

    filt: dict[str, Any] = {}
    if game:
        filt["game"] = game
    if team:
        try:
            tid = ObjectId(team)
        except InvalidId:
            raise HTTPException(400, f"Invalid team id: {team}")
        filt["$or"] = [{"team1Id": tid}, {"team2Id": tid}]

    total = db["matches"].count_documents(filt)
    skip = (page - 1) * limit
    rows = list(
        db["matches"]
        .find(filt)
        .sort("date", -1)
        .skip(skip)
        .limit(limit)
    )
    # Strip heavy nested arrays for list view.
    items = []
    for r in rows:
        r = _clean(r)
        r.pop("maps", None)
        r.pop("players", None)
        items.append(r)
    return {"items": items, "total": total, "page": page, "limit": limit}


def _enrich_players(db, doc: dict) -> dict:
    """Replace playerId strings in maps/players with {id, name} objects."""
    player_ids: set[ObjectId] = set()

    for m in doc.get("maps", []):
        for side in ("team1Players", "team2Players"):
            for p in m.get(side, []):
                try:
                    player_ids.add(ObjectId(p["playerId"]))
                except Exception:
                    pass

    players_blob = doc.get("players", {})
    for side in ("team1", "team2"):
        for p in players_blob.get(side, []):
            try:
                player_ids.add(ObjectId(p["playerId"]))
            except Exception:
                pass

    if not player_ids:
        return doc

    name_map: dict[str, str] = {}
    for row in db["players"].find({"_id": {"$in": list(player_ids)}}):
        name_map[str(row["_id"])] = row.get("displayName") or row.get("riotId") or str(row["_id"])

    for m in doc.get("maps", []):
        for side in ("team1Players", "team2Players"):
            for p in m.get(side, []):
                pid = str(p.get("playerId", ""))
                p["playerName"] = name_map.get(pid, pid)

    for side in ("team1", "team2"):
        for p in players_blob.get(side, []):
            pid = str(p.get("playerId", ""))
            p["playerName"] = name_map.get(pid, pid)

    return doc


@router.get("/{match_id}")
def get_match(match_id: str):
    db = get_db()
    if db is None:
        raise HTTPException(503, "Database unavailable")
    try:
        oid = ObjectId(match_id)
    except InvalidId:
        raise HTTPException(400, "Invalid match id")
    doc = db["matches"].find_one({"_id": oid})
    if not doc:
        raise HTTPException(404, "Match not found")
    doc = _clean(doc)
    doc = _enrich_players(db, doc)
    return doc
