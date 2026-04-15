"""API routes for players."""

from fastapi import APIRouter, HTTPException, Query
from typing import Any, Optional
from collections import Counter

from core.db import get_db

router = APIRouter()

# Collection name contains a space (legacy). Kept consistent with admin_router.
_PMS = "player match stats"


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
    filt: dict[str, Any] = {}
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


def _clean(row: dict[str, Any]) -> dict[str, Any]:
    row = dict(row)
    for k, v in list(row.items()):
        # ObjectId and datetime-ish types → str for JSON safety
        if k == "_id" or k.endswith("Id"):
            row[k] = str(v) if v is not None else None
    return row


@router.get("/{slug}")
def get_player(slug: str):
    db = get_db()
    if db is None:
        raise HTTPException(503, "Database unavailable")
    player = db["ranked_players"].find_one({"slug": slug}, {"_id": 0})
    if not player:
        raise HTTPException(404, f"Player '{slug}' not found")

    # Try to find the admin-managed `players` doc for richer joins.
    # Legacy `ranked_players` has `name` but no `_id` link to `players`.
    admin_player = db["players"].find_one({"displayName": player["name"]})
    player_oid = admin_player["_id"] if admin_player else None

    # Build match-stats query: prefer playerId link, fall back to riotId == name.
    stats_filt: dict[str, Any]
    if player_oid is not None:
        stats_filt = {"playerId": player_oid}
    else:
        stats_filt = {"riotId": player["name"]}

    stat_rows = list(
        db[_PMS]
        .find(stats_filt)
        .sort("_id", -1)
        .limit(25)
    )

    recent_matches = [_clean(r) for r in stat_rows]

    # Frequency counts (agent for Valorant, champion for LoL).
    freq_field = "agent" if player.get("game") == "Valorant" else "champion"
    freq = Counter(r.get(freq_field) for r in stat_rows if r.get(freq_field))
    frequency = [
        {"name": name, "count": count}
        for name, count in freq.most_common()
    ]

    return {
        **player,
        "recent_matches": recent_matches,
        "frequency": frequency,
        "frequency_field": freq_field,
    }
