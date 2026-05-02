"""API routes for players (Postgres-backed; Phase 3d of postgres-migration-v2).

Wire contract during Phase 3 (Path A — preserve existing frontend contract):
  - camelCase: displayName, riotId, matchId, mapName, teamName.
  - snake_case: team_name, team_slug, recent_matches, frequency_field.
  - TitleCase game enum: 'Valorant' / 'League of Legends' on the wire.

Phase 4 standardizes everything to canonical camelCase + lowercase enum.

The Mongo predecessor split LoL through a separate CLOL_player_stats source.
The Phase 1 schema unifies both games into a single `players` table
discriminated by the `game` column. This router collapses the split.
"""

from collections import Counter
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from core.db import get_cursor

router = APIRouter()

_GAME_LABEL_TO_DB = {"Valorant": "valorant", "League of Legends": "lol"}
_GAME_DB_TO_LABEL = {v: k for k, v in _GAME_LABEL_TO_DB.items()}

_SORT_COLUMNS = {
    "displayName": "p.display_name",
    "role":        "p.role",
    "game":        "p.game",
}
_SORT_ORDERS = {"asc", "desc"}


def _normalize_game_filter(label: Optional[str]) -> Optional[str]:
    if label is None or label == "All":
        return None
    if label in _GAME_LABEL_TO_DB:
        return _GAME_LABEL_TO_DB[label]
    return label.lower()


def _label_game(db_value: Optional[str]) -> str:
    if db_value is None:
        return ""
    return _GAME_DB_TO_LABEL.get(db_value, db_value)


def _normalize(row: dict, team_name: str = "", team_slug: str = "") -> dict:
    """Map a `players` row + optional team into the existing frontend wire shape."""
    name = row.get("display_name") or row.get("name") or "Unknown"
    slug = row.get("slug") or name.lower().replace(" ", "-")
    return {
        "slug":        slug,
        "displayName": name,
        "riotId":      row.get("riot_id") or "",
        "role":        row.get("role") or "",
        "game":        _label_game(row.get("game")),
        "team_name":   team_name,
        "team_slug":   team_slug,
        "active":      row.get("active", True),
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
    if sort not in _SORT_COLUMNS:
        raise HTTPException(status_code=400, detail=f"Invalid sort: {sort!r}")
    if order not in _SORT_ORDERS:
        raise HTTPException(status_code=400, detail=f"Invalid order: {order!r}")

    direction = "DESC" if order == "desc" else "ASC"
    sort_expr = _SORT_COLUMNS[sort]
    db_game = _normalize_game_filter(game)
    db_role = None if (role is None or role == "All") else role

    if team:
        # Path B: filter via direct JOIN; team_name/team_slug = the requested team.
        sql = (
            f"SELECT p.id, p.slug, p.display_name, p.name, p.riot_id, p.role, p.game, p.active, "
            f"       t.name AS team_name, t.slug AS team_slug "
            f"FROM players p "
            f"JOIN team_players tp ON tp.player_id = p.id AND tp.left_at IS NULL "
            f"JOIN teams t ON t.id = tp.team_id "
            f"WHERE t.slug = %s "
            f"  AND (%s::text IS NULL OR p.game = %s::text) "
            f"  AND (%s::text IS NULL OR p.role = %s::text) "
            f"ORDER BY {sort_expr} {direction} NULLS LAST, p.display_name "
            f"LIMIT %s"
        )
        params: tuple = (team, db_game, db_game, db_role, db_role, limit)
    else:
        # Path A: unfiltered; CTE picks each player's earliest active team for display.
        sql = (
            f"WITH first_team AS ("
            f"  SELECT DISTINCT ON (tp.player_id) "
            f"         tp.player_id, t.name AS team_name, t.slug AS team_slug "
            f"  FROM team_players tp "
            f"  JOIN teams t ON t.id = tp.team_id "
            f"  WHERE tp.left_at IS NULL "
            f"  ORDER BY tp.player_id, tp.joined_at ASC"
            f") "
            f"SELECT p.id, p.slug, p.display_name, p.name, p.riot_id, p.role, p.game, p.active, "
            f"       COALESCE(ft.team_name, '') AS team_name, "
            f"       COALESCE(ft.team_slug, '') AS team_slug "
            f"FROM players p "
            f"LEFT JOIN first_team ft ON ft.player_id = p.id "
            f"WHERE (%s::text IS NULL OR p.game = %s::text) "
            f"  AND (%s::text IS NULL OR p.role = %s::text) "
            f"ORDER BY {sort_expr} {direction} NULLS LAST, p.display_name "
            f"LIMIT %s"
        )
        params = (db_game, db_game, db_role, db_role, limit)

    with get_cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    return [_normalize(r, r.get("team_name") or "", r.get("team_slug") or "") for r in rows]


@router.get("/{slug}")
def get_player(slug: str):
    """Get one player by slug, with recent_matches + frequency.

    Lookup tries the `slug` column first; falls back to slug derived from
    display_name (lowercased, spaces→hyphens) for legacy/admin-entered
    players that haven't been slug-normalized.

    On slug collision, deterministic ORDER BY (exact slug match wins; then
    earliest id).
    """
    with get_cursor() as cur:
        cur.execute(
            "SELECT * FROM players "
            "WHERE slug = %s "
            "   OR LOWER(REPLACE(COALESCE(display_name, name), ' ', '-')) = %s "
            "ORDER BY (slug = %s) DESC NULLS LAST, id ASC "
            "LIMIT 1",
            (slug, slug, slug),
        )
        player = cur.fetchone()
        if player is None:
            raise HTTPException(status_code=404, detail=f"Player '{slug}' not found")

        # Pick this player's earliest active team for team_name/team_slug.
        cur.execute(
            "SELECT t.name, t.slug FROM teams t "
            "JOIN team_players tp ON tp.team_id = t.id "
            "WHERE tp.player_id = %s AND tp.left_at IS NULL "
            "ORDER BY tp.joined_at ASC LIMIT 1",
            (player["id"],),
        )
        team_row = cur.fetchone()
        team_name = team_row["name"] if team_row else ""
        team_slug = team_row["slug"] if team_row else ""

        # Recent matches: per-game JOIN to the appropriate detail table.
        if player.get("game") == "valorant":
            cur.execute(
                "SELECT pms.id AS pms_id, pms.match_id, pms.map_name, pms.team_name, "
                "       pms.team_id, pms.game, "
                "       v.kills, v.deaths, v.assists, v.agent, v.acs, "
                "       m.team1_id, m.team2_id, m.team1_score, m.team2_score "
                "FROM player_match_stats pms "
                "LEFT JOIN pms_valorant_details v ON v.pms_id = pms.id "
                "LEFT JOIN matches m ON m.id = pms.match_id "
                "WHERE pms.player_id = %s AND pms.game = 'valorant' "
                "ORDER BY pms.id DESC LIMIT 25",
                (player["id"],),
            )
            stat_rows = cur.fetchall()
            freq_field = "agent"
        elif player.get("game") == "lol":
            cur.execute(
                "SELECT pms.id AS pms_id, pms.match_id, pms.map_name, pms.team_name, "
                "       pms.team_id, pms.game, "
                "       l.kills, l.deaths, l.assists, l.champion, l.cs, l.lane, "
                "       m.team1_id, m.team2_id, m.team1_score, m.team2_score "
                "FROM player_match_stats pms "
                "LEFT JOIN pms_lol_details l ON l.pms_id = pms.id "
                "LEFT JOIN matches m ON m.id = pms.match_id "
                "WHERE pms.player_id = %s AND pms.game = 'lol' "
                "ORDER BY pms.id DESC LIMIT 25",
                (player["id"],),
            )
            stat_rows = cur.fetchall()
            freq_field = "champion"
        else:
            stat_rows = []
            freq_field = "agent"  # fallback for unknown games

    # Shape recent_matches and frequency.
    recent_matches = [_match_stat_row(r) for r in stat_rows]
    freq_counter = Counter(r.get(freq_field) for r in stat_rows if r.get(freq_field))
    frequency = [{"name": n, "count": c} for n, c in freq_counter.most_common()]

    base = _normalize(player, team_name, team_slug)
    base["recent_matches"] = recent_matches
    base["frequency"] = frequency
    base["frequency_field"] = freq_field
    return base


def _match_stat_row(r: dict) -> dict:
    """Convert a recent-match row into the frontend `MatchStat` shape (camelCase)."""
    own_team_id = r.get("team_id")
    team1_id = r.get("team1_id")
    team2_id = r.get("team2_id")
    if own_team_id == team1_id:
        own_score, opp_score = r.get("team1_score"), r.get("team2_score")
    elif own_team_id == team2_id:
        own_score, opp_score = r.get("team2_score"), r.get("team1_score")
    else:
        # team_id doesn't match either side (null / stale / cross-match data) —
        # don't fabricate a win/loss.
        own_score, opp_score = None, None
    if own_score is None or opp_score is None or own_score == opp_score:
        win: Optional[bool] = None
    else:
        win = own_score > opp_score
    out: dict[str, Any] = {
        "matchId":  str(r["match_id"]) if r.get("match_id") is not None else None,
        "game":     _label_game(r.get("game")),
        "mapName":  r.get("map_name") or "",
        "teamName": r.get("team_name") or "",
        "kills":    r.get("kills"),
        "deaths":   r.get("deaths"),
        "assists":  r.get("assists"),
        "win":      win,
    }
    if r.get("agent") is not None:
        out["agent"] = r["agent"]
    if r.get("acs") is not None:
        out["acs"] = r["acs"]
    if r.get("champion") is not None:
        out["champion"] = r["champion"]
    if r.get("cs") is not None:
        out["cs"] = r["cs"]
    if r.get("lane") is not None:
        out["role"] = r["lane"]
    return out
