"""API routes for match history (Postgres-backed; Phase 3e of postgres-migration-v2).

Two endpoints:
  GET /api/matches               — paginated list (game/team filter)
  GET /api/matches/{match_id}    — single match with player breakdown

Wire contract preserves the existing frontend Match / ValMap / ValPlayer /
LolPlayer types from Frontend/app/matches/{page,[id]/page}.tsx — mostly
camelCase. _id is a numeric string of matches.id.

Known scope gap: the Phase 1 schema doesn't store per-map team1Score /
team2Score. Val maps[] in the detail response include mapName +
team1Players + team2Players but omit per-map scores. Phase 4 either
redesigns the detail page or a follow-up adds per-map score columns.
"""

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from core.db import get_cursor

router = APIRouter()

def _winner_id(team1_id: int, team2_id: int, t1_score: Optional[int], t2_score: Optional[int]) -> Optional[str]:
    if t1_score is None or t2_score is None or t1_score == t2_score:
        return None
    return str(team1_id) if t1_score > t2_score else str(team2_id)


def _list_row_to_response(row: dict) -> dict:
    return {
        "_id":          str(row["id"]),
        "game":         row.get("game", ""),
        "team1Name":    row.get("team1_name") or "",
        "team2Name":    row.get("team2_name") or "",
        "team1Score":   row.get("team1_score"),
        "team2Score":   row.get("team2_score"),
        "team1Id":      str(row["team1_id"]) if row.get("team1_id") is not None else None,
        "winnerTeamId": _winner_id(row["team1_id"], row["team2_id"], row.get("team1_score"), row.get("team2_score")),
        "format":       row.get("format"),
        "date":         row["match_date"].isoformat() if row.get("match_date") else None,
        "leagueName":   row.get("league_name") or "",
    }


@router.get("/")
def list_matches(
    game: Optional[str] = Query(None),
    team: Optional[str] = Query(None, description="numeric team id"),
    limit: int = Query(25, ge=1, le=100),
    page: int = Query(1, ge=1),
):
    db_game = game if game else None
    db_team: Optional[int] = None
    if team is not None and team != "":
        try:
            db_team = int(team)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid team id: {team!r}")

    offset = (page - 1) * limit

    with get_cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS n FROM matches m "
            "WHERE (%s::text IS NULL OR m.game = %s::text) "
            "  AND (%s::bigint IS NULL OR m.team1_id = %s::bigint OR m.team2_id = %s::bigint)",
            (db_game, db_game, db_team, db_team, db_team),
        )
        total = cur.fetchone()["n"]

        cur.execute(
            "SELECT m.*, t1.name AS team1_name, t2.name AS team2_name "
            "FROM matches m "
            "LEFT JOIN teams t1 ON t1.id = m.team1_id "
            "LEFT JOIN teams t2 ON t2.id = m.team2_id "
            "WHERE (%s::text IS NULL OR m.game = %s::text) "
            "  AND (%s::bigint IS NULL OR m.team1_id = %s::bigint OR m.team2_id = %s::bigint) "
            "ORDER BY m.match_date DESC, m.id DESC "
            "LIMIT %s OFFSET %s",
            (db_game, db_game, db_team, db_team, db_team, limit, offset),
        )
        rows = cur.fetchall()

    return {
        "items": [_list_row_to_response(r) for r in rows],
        "total": total,
        "page":  page,
        "limit": limit,
    }


@router.get("/{match_id}")
def get_match(match_id: str):
    """Get one match by numeric id with player breakdown.

    For Val: returns `maps: [{mapName, team1Players, team2Players}]` (no per-map
    scores; known schema gap — see SPEC).
    For LoL: returns `players: {team1: [...], team2: [...]}` (one row per
    player per series).
    """
    try:
        m_id = int(match_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid match id")

    with get_cursor() as cur:
        cur.execute(
            "SELECT m.*, t1.name AS team1_name, t2.name AS team2_name, "
            "       o.abbreviation AS org_abbreviation, "
            "       s.label AS season_label, "
            "       c.name AS conference_name "
            "FROM matches m "
            "LEFT JOIN teams t1 ON t1.id = m.team1_id "
            "LEFT JOIN teams t2 ON t2.id = m.team2_id "
            "LEFT JOIN organizations o ON o.id = m.org_id "
            "LEFT JOIN seasons s ON s.id = m.season_id "
            "LEFT JOIN conferences c ON c.id = m.conference_id "
            "WHERE m.id = %s",
            (m_id,),
        )
        match = cur.fetchone()
        if match is None:
            raise HTTPException(status_code=404, detail="Match not found")

        if match.get("game") == "valorant":
            cur.execute(
                "SELECT pms.id AS pms_id, pms.player_id, pms.team_id, pms.map_name, "
                "       p.display_name, p.name AS player_name_fallback, "
                "       v.kills, v.deaths, v.assists, v.agent, v.acs, v.details "
                "FROM player_match_stats pms "
                "JOIN players p ON p.id = pms.player_id "
                "LEFT JOIN pms_valorant_details v ON v.pms_id = pms.id "
                "WHERE pms.match_id = %s "
                "ORDER BY pms.map_name, pms.id",
                (m_id,),
            )
            pms_rows = cur.fetchall()
        elif match.get("game") == "lol":
            cur.execute(
                "SELECT pms.id AS pms_id, pms.player_id, pms.team_id, "
                "       p.display_name, p.name AS player_name_fallback, "
                "       l.kills, l.deaths, l.assists, l.champion, l.cs, l.gold, l.lane, l.details "
                "FROM player_match_stats pms "
                "JOIN players p ON p.id = pms.player_id "
                "LEFT JOIN pms_lol_details l ON l.pms_id = pms.id "
                "WHERE pms.match_id = %s "
                "ORDER BY pms.id",
                (m_id,),
            )
            pms_rows = cur.fetchall()
        else:
            pms_rows = []

    response = _list_row_to_response(match)
    response.update({
        "orgAbbreviation": match.get("org_abbreviation") or "",
        "seasonLabel":     match.get("season_label") or "",
        "conferenceName":  match.get("conference_name") or "",
    })

    if match.get("game") == "valorant":
        response["maps"] = _build_val_maps(pms_rows, match["team1_id"], match["team2_id"])
    elif match.get("game") == "lol":
        response["players"] = _build_lol_players(pms_rows, match["team1_id"], match["team2_id"])

    return response


def _build_val_maps(pms_rows: list[dict], team1_id: int, team2_id: int) -> list[dict]:
    """Group Val pms rows by map_name; split players by team."""
    by_map: dict[str, dict[str, list[dict]]] = {}
    for r in pms_rows:
        map_name = r.get("map_name") or ""
        bucket = by_map.setdefault(map_name, {"team1Players": [], "team2Players": []})
        if r.get("team_id") == team1_id:
            bucket["team1Players"].append(_val_player_row(r))
        elif r.get("team_id") == team2_id:
            bucket["team2Players"].append(_val_player_row(r))
        # else: mismatched team_id — skip silently

    return [
        {
            "mapName":      map_name,
            "team1Players": entry["team1Players"],
            "team2Players": entry["team2Players"],
        }
        for map_name, entry in by_map.items()
    ]


def _build_lol_players(pms_rows: list[dict], team1_id: int, team2_id: int) -> dict:
    team1: list[dict] = []
    team2: list[dict] = []
    for r in pms_rows:
        if r.get("team_id") == team1_id:
            team1.append(_lol_player_row(r))
        elif r.get("team_id") == team2_id:
            team2.append(_lol_player_row(r))
    return {"team1": team1, "team2": team2}


def _val_player_row(r: dict) -> dict:
    name = r.get("display_name") or r.get("player_name_fallback") or ""
    extras = r.get("details") or {}
    out: dict[str, Any] = {
        "playerId":   str(r["player_id"]),
        "playerName": name,
        "agent":      r.get("agent") or "",
        "kills":      r.get("kills") or 0,
        "deaths":     r.get("deaths") or 0,
        "assists":    r.get("assists") or 0,
        "acs":        r.get("acs") or 0,
    }
    if isinstance(extras, dict):
        for key in ("firstKills", "plants", "defuses"):
            if key in extras:
                out[key] = extras[key]
    return out


def _lol_player_row(r: dict) -> dict:
    name = r.get("display_name") or r.get("player_name_fallback") or ""
    extras = r.get("details") or {}
    out: dict[str, Any] = {
        "playerId":   str(r["player_id"]),
        "playerName": name,
        "champion":   r.get("champion") or "",
        "role":       r.get("lane") or "",
        "kills":      r.get("kills") or 0,
        "deaths":     r.get("deaths") or 0,
        "assists":    r.get("assists") or 0,
        "cs":         r.get("cs") or 0,
        "gold":       r.get("gold") or 0,
        "damage":     extras.get("damage") if isinstance(extras, dict) else None,
    }
    if isinstance(extras, dict):
        for key in ("vision", "wards"):
            if key in extras:
                out[key] = extras[key]
    return out
