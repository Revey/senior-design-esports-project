"""API routes for players."""

from fastapi import APIRouter, HTTPException, Query
from typing import Any, Optional
from collections import Counter
from bson import ObjectId

from core.db import get_db

router = APIRouter()

_PMS = "player match stats"


def _serialize(doc: Any) -> Any:
    """Recursively convert ObjectId and other non-JSON-safe BSON types to str."""
    if isinstance(doc, dict):
        return {k: _serialize(v) for k, v in doc.items()}
    if isinstance(doc, list):
        return [_serialize(v) for v in doc]
    if isinstance(doc, ObjectId):
        return str(doc)
    return doc


def _normalize(doc: dict[str, Any], team_name: str = "", team_slug: str = "") -> dict[str, Any]:
    """Map the players collection schema to the shape the frontend expects."""
    display_name = doc.get("displayName") or doc.get("name", "Unknown")
    slug = doc.get("slug") or display_name.lower().replace(" ", "-")

    return {
        "_id": str(doc["_id"]) if "_id" in doc else None,
        "slug": slug,
        "displayName": display_name,
        "riotId": doc.get("riotId"),
        "role": doc.get("role") or "",
        "game": doc.get("game", "Valorant"),  # all current players are Valorant
        "team_name": team_name,
        "team_slug": team_slug,
        "active": doc.get("active", True),
    }


def _resolve_teams(db: Any, docs: list[dict]) -> dict[str, tuple[str, str]]:
    """
    Given a list of player docs, collect all teamIds and resolve them
    to (team_name, team_slug) in one bulk query.
    Returns a dict keyed by str(teamId).
    """
    team_id_set: set[ObjectId] = set()
    for doc in docs:
        for tid in doc.get("teamIds", []):
            if isinstance(tid, ObjectId):
                team_id_set.add(tid)

    if not team_id_set:
        return {}

    teams = db["teams"].find(
        {"_id": {"$in": list(team_id_set)}},
        {"_id": 1, "name": 1, "slug": 1},
    )
    return {
        str(t["_id"]): (t.get("name", ""), t.get("slug", ""))
        for t in teams
    }


@router.get("/")
def list_players(
    game: Optional[str] = Query(None),
    team: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    sort: str = Query("displayName"),
    order: str = Query("asc"),
    limit: int = Query(200, ge=1, le=500),
):
    db = get_db()
    if db is None:
        raise HTTPException(503, "Database unavailable")

    filt: dict[str, Any] = {}
    # All current players are Valorant; filter out if LoL is requested
    if game == "League of Legends":
        filt["game"] = "League of Legends"
    elif game == "Valorant":
        filt["$or"] = [{"game": "Valorant"}, {"game": {"$exists": False}}]
    if team:
        filt["team_slug"] = team
    if role and role != "All":
        filt["role"] = role

    sort_dir = -1 if order == "desc" else 1
    mongo_sort = sort if sort in ("displayName", "role", "game") else "displayName"

    docs = list(db["players"].find(filt).sort(mongo_sort, sort_dir).limit(limit))

    team_map = _resolve_teams(db, docs)

    result = []
    for doc in docs:
        team_ids = doc.get("teamIds", [])
        first_tid = str(team_ids[0]) if team_ids else None
        t_name, t_slug = team_map.get(first_tid, ("", "")) if first_tid else ("", "")
        result.append(_serialize(_normalize(doc, t_name, t_slug)))

    return result


def _clean(row: dict[str, Any]) -> dict[str, Any]:
    return _serialize(row)


@router.get("/{slug}")
def get_player(slug: str):
    db = get_db()
    if db is None:
        raise HTTPException(503, "Database unavailable")

    # Try stored slug first, then derive from displayName
    player_doc = db["players"].find_one({"slug": slug})
    if not player_doc:
        for p in db["players"].find({}, {"displayName": 1, "_id": 1}):
            if (p.get("displayName") or "").lower().replace(" ", "-") == slug:
                player_doc = db["players"].find_one({"_id": p["_id"]})
                break

    if not player_doc:
        raise HTTPException(404, f"Player '{slug}' not found")

    # Resolve team name
    team_ids = player_doc.get("teamIds", [])
    t_name, t_slug = "", ""
    if team_ids:
        first_tid = team_ids[0] if isinstance(team_ids[0], ObjectId) else None
        if first_tid:
            team_doc = db["teams"].find_one({"_id": first_tid}, {"name": 1, "slug": 1})
            if team_doc:
                t_name = team_doc.get("name", "")
                t_slug = team_doc.get("slug", "")

    player = _normalize(player_doc, t_name, t_slug)
    player_oid = player_doc.get("_id")

    stats_filt: dict[str, Any] = (
        {"playerId": player_oid} if player_oid else {"riotId": player_doc.get("riotId")}
    )

    stat_rows = list(db[_PMS].find(stats_filt).sort("_id", -1).limit(25))
    recent_matches = [_clean(r) for r in stat_rows]

    freq_field = "agent" if player.get("game") == "Valorant" else "champion"
    freq = Counter(r.get(freq_field) for r in stat_rows if r.get(freq_field))
    frequency = [{"name": n, "count": c} for n, c in freq.most_common()]

    return _serialize({
        **player,
        "recent_matches": recent_matches,
        "frequency": frequency,
        "frequency_field": freq_field,
    })