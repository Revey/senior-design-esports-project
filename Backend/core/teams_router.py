"""API routes for teams."""

from fastapi import APIRouter, HTTPException, Query
from typing import Any, Optional

from core.db import get_db

router = APIRouter()


def _team_to_ranked(doc: dict[str, Any]) -> dict[str, Any]:
    wins = int(doc.get("wins") or 0)
    losses = int(doc.get("losses") or 0)
    total = wins + losses
    win_rate = round((wins / total) * 100, 1) if total > 0 else 0.0
    rating = 1000 + wins * 100 - losses * 50
    return {
        "slug": doc.get("slug", ""),
        "name": doc.get("teamName", ""),
        "school": doc.get("school", ""),
        "game": doc.get("game", ""),
        "record": {"wins": wins, "losses": losses},
        "win_rate": win_rate,
        "rating": rating,
        "region": "",
        "league_slug": "",
    }


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
    filt: dict[str, Any] = {}
    if game:
        filt["game"] = game

    admin_teams = list(db["teams"].find(filt).limit(limit))
    if admin_teams:
        docs = [_team_to_ranked(t) for t in admin_teams]
        reverse = order == "desc"
        if sort == "win_rate":
            docs.sort(key=lambda t: t["win_rate"], reverse=reverse)
        elif sort == "record.wins":
            docs.sort(key=lambda t: t["record"]["wins"], reverse=reverse)
        else:
            docs.sort(key=lambda t: t["rating"], reverse=reverse)
        return docs

    # Fallback to seeded ranked_teams if no admin teams exist yet.
    sort_dir = -1 if order == "desc" else 1
    return list(
        db["ranked_teams"]
        .find(filt, {"_id": 0})
        .sort(sort, sort_dir)
        .limit(limit)
    )


def _clean(row: dict[str, Any]) -> dict[str, Any]:
    row = dict(row)
    for k, v in list(row.items()):
        if k == "_id" or k.endswith("Id"):
            row[k] = str(v) if v is not None else None
    return row


@router.get("/{slug}")
def get_team(slug: str):
    db = get_db()
    if db is None:
        raise HTTPException(503, "Database unavailable")

    team = db["ranked_teams"].find_one({"slug": slug}, {"_id": 0})
    if not team:
        raise HTTPException(404, f"Team '{slug}' not found")

    # Roster: prefer admin `teams` → `players.teamIds`; fall back to seeded `ranked_players.team_slug`.
    admin_team = db["teams"].find_one({"slug": slug, "game": team["game"]})
    roster: list[dict[str, Any]] = []
    recent_matches: list[dict[str, Any]] = []
    map_wins = 0
    map_losses = 0

    if admin_team is not None:
        team_oid = admin_team["_id"]
        map_wins = int(admin_team.get("mapWins", 0) or 0)
        map_losses = int(admin_team.get("mapLosses", 0) or 0)

        player_rows = list(db["players"].find({"teamIds": team_oid}))
        for p in player_rows:
            roster.append({
                "name": p.get("displayName"),
                "role": p.get("role"),
                "riotId": p.get("riotId"),
                "active": p.get("active", True),
            })

        match_rows = list(
            db["matches"]
            .find({"$or": [{"team1Id": team_oid}, {"team2Id": team_oid}]})
            .sort("date", -1)
            .limit(15)
        )
        for m in match_rows:
            is_team1 = m.get("team1Id") == team_oid
            opp_name = m.get("team2Name") if is_team1 else m.get("team1Name")
            own_score = m.get("team1Score") if is_team1 else m.get("team2Score")
            opp_score = m.get("team2Score") if is_team1 else m.get("team1Score")
            winner = m.get("winnerTeamId")
            recent_matches.append({
                "matchId": str(m.get("_id")),
                "date": m.get("date"),
                "game": m.get("game"),
                "format": m.get("format"),
                "opponent": opp_name,
                "own_score": own_score,
                "opp_score": opp_score,
                "win": winner == team_oid if winner is not None else None,
            })

    # Seed-data fallback: ranked_players keyed by team_slug.
    if not roster:
        seeded = list(db["ranked_players"].find({"team_slug": slug}, {"_id": 0}))
        roster = [
            {
                "name": p.get("name"),
                "role": p.get("role"),
                "slug": p.get("slug"),
                "active": True,
            }
            for p in seeded
        ]

    return {
        **team,
        "roster": roster,
        "recent_matches": recent_matches,
        "map_record": {"wins": map_wins, "losses": map_losses},
    }
