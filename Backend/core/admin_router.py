"""Admin router: password-gated endpoints for manual match data entry.

Auth model:
- Single shared admin password (env: ADMIN_PASSWORD).
- POST /api/admin/login exchanges password for a short-lived HMAC token.
- All other /api/admin/* endpoints require Authorization: Bearer <token>.

Storage is PostgreSQL via core.db (psycopg2 ThreadedConnectionPool). All
writes that span multiple tables run inside a single transaction so team
W/L counters stay consistent with the matches / player_match_stats rows.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from psycopg2 import errors as pg_errors
from psycopg2.extras import Json, RealDictCursor
from pydantic import BaseModel, Field

from core.db import get_conn, get_cursor

router = APIRouter()

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
ADMIN_SECRET = os.getenv("ADMIN_SECRET", ADMIN_PASSWORD or "dev-insecure-secret")
TOKEN_TTL_SECONDS = 60 * 60 * 12  # 12h


# ---------- auth helpers ----------

def _sign(payload: str) -> str:
    return hmac.new(ADMIN_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()


def issue_token() -> str:
    exp = int(time.time()) + TOKEN_TTL_SECONDS
    payload = f"admin:{exp}"
    return f"{payload}.{_sign(payload)}"


def verify_token(token: str) -> bool:
    try:
        payload, sig = token.rsplit(".", 1)
        if not hmac.compare_digest(sig, _sign(payload)):
            return False
        _, exp_str = payload.split(":")
        return int(exp_str) > int(time.time())
    except Exception:
        return False


def require_admin(authorization: Optional[str] = Header(None)) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    if not verify_token(authorization.split(" ", 1)[1]):
        raise HTTPException(status_code=401, detail="Invalid or expired token")


# ---------- serialization helpers ----------

def _slugify(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def _int_id(s: str, field: str = "id") -> int:
    try:
        return int(s)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"Invalid {field}: {s}")


# Map snake_case DB columns → camelCase JSON keys the frontend already uses.
_SCHOOL_JSON_KEYS = {
    "id": "_id",
    "slug": "slug",
    "name": "name",
    "created_at": "createdAt",
}
_LEAGUE_JSON_KEYS = {
    "id": "_id",
    "slug": "slug",
    "name": "name",
    "abbreviation": "abbreviation",
    "game": "game",
    "season": "season",
    "conference": "conference",
    "description": "description",
    "created_at": "createdAt",
}
_TEAM_JSON_KEYS = {
    "id": "_id",
    "slug": "slug",
    "name": "teamName",
    "school_id": "schoolId",
    "school_name": "school",
    "game": "game",
    "tier": "tier",
    "wins": "wins",
    "losses": "losses",
    "map_wins": "mapWins",
    "map_losses": "mapLosses",
}
_PLAYER_JSON_KEYS = {
    "id": "_id",
    "slug": "slug",
    "display_name": "displayName",
    "riot_id": "riotId",
    "role": "role",
    "active": "active",
    "last_updated": "lastUpdated",
}


def _project(row: dict, mapping: dict[str, str]) -> dict:
    """Return a new dict with DB columns renamed via mapping, skipping unset cols."""
    out: dict[str, Any] = {}
    for col, json_key in mapping.items():
        if col not in row:
            continue
        val = row[col]
        if col == "id" or col.endswith("_id"):
            val = str(val) if val is not None else None
        elif isinstance(val, datetime):
            val = val.isoformat()
        out[json_key] = val
    return out


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat()


# ---------- models ----------

class LoginReq(BaseModel):
    password: str


class SchoolCreate(BaseModel):
    name: str


class TeamCreate(BaseModel):
    schoolId: str
    name: str
    game: Literal["Valorant", "League of Legends"]
    tier: Optional[str] = None


class PlayerCreate(BaseModel):
    displayName: str
    riotId: Optional[str] = None
    role: Optional[str] = None
    teamIds: list[str] = Field(default_factory=list)


class PlayerLink(BaseModel):
    teamId: str


class ValPlayerStat(BaseModel):
    playerId: str
    agent: str
    kills: int
    deaths: int
    assists: int
    acs: int
    firstKills: int = 0
    plants: int = 0
    defuses: int = 0


class ValMap(BaseModel):
    mapName: str
    team1Score: int
    team2Score: int
    team1Players: list[ValPlayerStat]
    team2Players: list[ValPlayerStat]


class LolPlayerStat(BaseModel):
    playerId: str
    champion: str
    role: str
    kills: int
    deaths: int
    assists: int
    cs: int
    gold: int
    damage: int
    vision: int = 0
    wards: int = 0


class LeagueCreate(BaseModel):
    name: str
    abbreviation: str
    game: Literal["Valorant", "League of Legends"]
    season: str = ""
    conference: Optional[str] = None


class MatchCreate(BaseModel):
    game: Literal["Valorant", "League of Legends"]
    team1Id: str
    team2Id: str
    date: Optional[str] = None
    format: Literal["BO1", "BO3", "BO5"] = "BO1"
    leagueId: Optional[str] = None
    maps: list[ValMap] = Field(default_factory=list)
    team1Score: Optional[int] = None
    team2Score: Optional[int] = None
    lolTeam1Players: list[LolPlayerStat] = Field(default_factory=list)
    lolTeam2Players: list[LolPlayerStat] = Field(default_factory=list)


# ---------- auth routes ----------

@router.post("/login")
def login(req: LoginReq):
    if not ADMIN_PASSWORD:
        raise HTTPException(status_code=500, detail="ADMIN_PASSWORD not configured")
    if not hmac.compare_digest(req.password, ADMIN_PASSWORD):
        raise HTTPException(status_code=401, detail="Invalid password")
    return {"token": issue_token(), "expiresIn": TOKEN_TTL_SECONDS}


@router.get("/me", dependencies=[Depends(require_admin)])
def me():
    return {"ok": True}


# ---------- schools ----------

@router.get("/schools", dependencies=[Depends(require_admin)])
def list_schools(q: str = Query("", max_length=100), limit: int = 20):
    with get_cursor() as cur:
        if q:
            cur.execute(
                "SELECT id, slug, name, created_at FROM schools "
                "WHERE name ILIKE %s ORDER BY name LIMIT %s",
                (f"%{q}%", limit),
            )
        else:
            cur.execute(
                "SELECT id, slug, name, created_at FROM schools ORDER BY name LIMIT %s",
                (limit,),
            )
        rows = cur.fetchall()
    return [_project(r, _SCHOOL_JSON_KEYS) for r in rows]


@router.post("/schools", dependencies=[Depends(require_admin)])
def create_school(req: SchoolCreate):
    name = req.name.strip()
    if not name:
        raise HTTPException(400, "name required")
    slug = _slugify(name)
    with get_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO schools (slug, name)
            VALUES (%s, %s)
            ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name
            RETURNING id, slug, name, created_at
            """,
            (slug, name),
        )
        row = cur.fetchone()
    return _project(row, _SCHOOL_JSON_KEYS)


# ---------- leagues ----------

@router.get("/leagues", dependencies=[Depends(require_admin)])
def list_leagues(
    q: str = Query("", max_length=100),
    game: Optional[str] = None,
    limit: int = 20,
):
    sql = (
        "SELECT id, slug, name, abbreviation, game, season, conference, "
        "description, created_at FROM leagues"
    )
    clauses: list[str] = []
    params: list[Any] = []
    if q:
        clauses.append("(name ILIKE %s OR abbreviation ILIKE %s)")
        params.extend([f"%{q}%", f"%{q}%"])
    if game:
        clauses.append("game = %s")
        params.append(game)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY name LIMIT %s"
    params.append(limit)

    with get_cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return [_project(r, _LEAGUE_JSON_KEYS) for r in rows]


@router.post("/leagues", dependencies=[Depends(require_admin)])
def create_league(req: LeagueCreate):
    name = req.name.strip()
    if not name:
        raise HTTPException(400, "name required")
    abbreviation = req.abbreviation.strip() or name.upper()[:6]
    slug = _slugify(abbreviation or name)
    conference = (req.conference or "").strip() or None

    with get_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO leagues (slug, name, abbreviation, game, season, conference, description)
            VALUES (%s, %s, %s, %s, %s, %s, '')
            ON CONFLICT ON CONSTRAINT leagues_slug_game_unique DO UPDATE
                SET name = EXCLUDED.name,
                    abbreviation = EXCLUDED.abbreviation,
                    season = EXCLUDED.season,
                    conference = EXCLUDED.conference
            RETURNING id, slug, name, abbreviation, game, season, conference, description, created_at
            """,
            (slug, name, abbreviation, req.game, req.season.strip(), conference),
        )
        row = cur.fetchone()
    return _project(row, _LEAGUE_JSON_KEYS)


# ---------- teams ----------

@router.get("/teams", dependencies=[Depends(require_admin)])
def list_teams(
    q: str = Query("", max_length=100),
    schoolId: Optional[str] = None,
    game: Optional[str] = None,
    limit: int = 50,
):
    sql = (
        "SELECT id, slug, name, school_id, school_name, game, tier, "
        "wins, losses, map_wins, map_losses FROM teams"
    )
    clauses: list[str] = []
    params: list[Any] = []
    if q:
        clauses.append("(name ILIKE %s OR school_name ILIKE %s)")
        params.extend([f"%{q}%", f"%{q}%"])
    if schoolId:
        clauses.append("school_id = %s")
        params.append(_int_id(schoolId, "schoolId"))
    if game:
        clauses.append("game = %s")
        params.append(game)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY name LIMIT %s"
    params.append(limit)

    with get_cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return [_project(r, _TEAM_JSON_KEYS) for r in rows]


@router.post("/teams", dependencies=[Depends(require_admin)])
def create_team(req: TeamCreate):
    school_id = _int_id(req.schoolId, "schoolId")
    name = req.name.strip()
    if not name:
        raise HTTPException(400, "name required")
    slug = _slugify(name)

    with get_cursor(commit=True) as cur:
        cur.execute("SELECT id, name FROM schools WHERE id = %s", (school_id,))
        school = cur.fetchone()
        if not school:
            raise HTTPException(404, "School not found")

        cur.execute(
            """
            INSERT INTO teams (slug, name, school_id, school_name, game, tier)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT ON CONSTRAINT teams_slug_game_unique DO UPDATE
                SET name = EXCLUDED.name,
                    school_id = EXCLUDED.school_id,
                    school_name = EXCLUDED.school_name,
                    tier = EXCLUDED.tier
            RETURNING id, slug, name, school_id, school_name, game, tier,
                      wins, losses, map_wins, map_losses
            """,
            (slug, name, school_id, school["name"], req.game, req.tier),
        )
        row = cur.fetchone()
    return _project(row, _TEAM_JSON_KEYS)


# ---------- players ----------

def _player_row_with_team_ids(cur, row: dict) -> dict:
    cur.execute(
        "SELECT team_id FROM team_players WHERE player_id = %s ORDER BY joined_at",
        (row["id"],),
    )
    team_ids = [str(r["team_id"]) for r in cur.fetchall()]
    projected = _project(row, _PLAYER_JSON_KEYS)
    projected["teamIds"] = team_ids
    return projected


@router.get("/players", dependencies=[Depends(require_admin)])
def list_players(
    q: str = Query("", max_length=100),
    teamId: Optional[str] = None,
    freeAgent: bool = False,
    limit: int = 50,
):
    sql_parts: list[str] = [
        "SELECT p.id, p.slug, p.display_name, p.riot_id, p.role, p.active, p.last_updated "
        "FROM players p"
    ]
    joins: list[str] = []
    clauses: list[str] = []
    params: list[Any] = []

    if teamId:
        joins.append("JOIN team_players tp ON tp.player_id = p.id")
        clauses.append("tp.team_id = %s")
        params.append(_int_id(teamId, "teamId"))
    elif freeAgent:
        clauses.append("NOT EXISTS (SELECT 1 FROM team_players WHERE player_id = p.id)")

    if q:
        clauses.append("(p.display_name ILIKE %s OR p.riot_id ILIKE %s)")
        params.extend([f"%{q}%", f"%{q}%"])

    if joins:
        sql_parts.extend(joins)
    if clauses:
        sql_parts.append("WHERE " + " AND ".join(clauses))
    sql_parts.append("ORDER BY p.display_name LIMIT %s")
    params.append(limit)

    with get_cursor() as cur:
        cur.execute(" ".join(sql_parts), params)
        rows = cur.fetchall()
        return [_player_row_with_team_ids(cur, r) for r in rows]


@router.post("/players", dependencies=[Depends(require_admin)])
def create_player(req: PlayerCreate):
    display_name = req.displayName.strip()
    if not display_name:
        raise HTTPException(400, "displayName required")
    riot_id = (req.riotId or "").strip() or None
    role = (req.role or "").strip() or None
    team_ids = [_int_id(t, "teamId") for t in req.teamIds]
    active = len(team_ids) > 0

    with get_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO players (display_name, riot_id, role, active)
            VALUES (%s, %s, %s, %s)
            RETURNING id, slug, display_name, riot_id, role, active, last_updated
            """,
            (display_name, riot_id, role, active),
        )
        row = cur.fetchone()
        player_id = row["id"]

        for tid in team_ids:
            cur.execute(
                "INSERT INTO team_players (team_id, player_id) VALUES (%s, %s) "
                "ON CONFLICT DO NOTHING",
                (tid, player_id),
            )

        return _player_row_with_team_ids(cur, row)


@router.patch("/players/{player_id}/link", dependencies=[Depends(require_admin)])
def link_player(player_id: str, req: PlayerLink):
    pid = _int_id(player_id, "player_id")
    tid = _int_id(req.teamId, "teamId")
    with get_cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO team_players (team_id, player_id) VALUES (%s, %s) "
            "ON CONFLICT DO NOTHING",
            (tid, pid),
        )
        cur.execute(
            "UPDATE players SET active = TRUE, last_updated = NOW() WHERE id = %s "
            "RETURNING id, slug, display_name, riot_id, role, active, last_updated",
            (pid,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Player not found")
        return _player_row_with_team_ids(cur, row)


@router.patch("/players/{player_id}/unlink", dependencies=[Depends(require_admin)])
def unlink_player(player_id: str, req: PlayerLink):
    pid = _int_id(player_id, "player_id")
    tid = _int_id(req.teamId, "teamId")
    with get_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM team_players WHERE player_id = %s AND team_id = %s",
            (pid, tid),
        )
        cur.execute(
            "SELECT COUNT(*) AS n FROM team_players WHERE player_id = %s",
            (pid,),
        )
        remaining = cur.fetchone()["n"]
        if remaining == 0:
            cur.execute(
                "UPDATE players SET active = FALSE, last_updated = NOW() WHERE id = %s",
                (pid,),
            )
        cur.execute(
            "SELECT id, slug, display_name, riot_id, role, active, last_updated "
            "FROM players WHERE id = %s",
            (pid,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Player not found")
        return _player_row_with_team_ids(cur, row)


# ---------- matches ----------

def _apply_record_update(cur, team_id: int, won: bool, map_wins: int, map_losses: int) -> None:
    cur.execute(
        """
        UPDATE teams
           SET wins = wins + %s,
               losses = losses + %s,
               map_wins = map_wins + %s,
               map_losses = map_losses + %s
         WHERE id = %s
        """,
        (1 if won else 0, 0 if won else 1, map_wins, map_losses, team_id),
    )


def _reverse_record_update(cur, team_id: int, won: bool, map_wins: int, map_losses: int) -> None:
    cur.execute(
        """
        UPDATE teams
           SET wins = wins - %s,
               losses = losses - %s,
               map_wins = map_wins - %s,
               map_losses = map_losses - %s
         WHERE id = %s
        """,
        (1 if won else 0, 0 if won else 1, map_wins, map_losses, team_id),
    )


def _resolve_league(cur, league_id_str: Optional[str]) -> tuple[Optional[int], Optional[str]]:
    if not league_id_str:
        return None, None
    lid = _int_id(league_id_str, "leagueId")
    cur.execute(
        "SELECT id, COALESCE(NULLIF(abbreviation, ''), name) AS label "
        "FROM leagues WHERE id = %s",
        (lid,),
    )
    row = cur.fetchone()
    if not row:
        return None, None
    return row["id"], row["label"]


def _parse_match_date(s: Optional[str]) -> datetime:
    if not s:
        return datetime.now(timezone.utc)
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(400, f"Invalid date: {s}")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


@router.post("/matches", dependencies=[Depends(require_admin)])
def create_match(req: MatchCreate):
    t1_id = _int_id(req.team1Id, "team1Id")
    t2_id = _int_id(req.team2Id, "team2Id")
    match_date = _parse_match_date(req.date)

    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute(
                "SELECT id, name, game FROM teams WHERE id IN (%s, %s)",
                (t1_id, t2_id),
            )
            teams_by_id = {r["id"]: r for r in cur.fetchall()}
            t1 = teams_by_id.get(t1_id)
            t2 = teams_by_id.get(t2_id)
            if not t1 or not t2:
                raise HTTPException(404, "Team not found")
            if t1["game"] != req.game or t2["game"] != req.game:
                raise HTTPException(400, "Team game mismatch")

            league_id, league_name = _resolve_league(cur, req.leagueId)

            if req.game == "Valorant":
                if not req.maps:
                    raise HTTPException(400, "At least one map required")
                t1_maps = sum(1 for m in req.maps if m.team1Score > m.team2Score)
                t2_maps = sum(1 for m in req.maps if m.team2Score > m.team1Score)
                winner_id = t1["id"] if t1_maps > t2_maps else t2["id"]

                maps_payload = [m.model_dump() for m in req.maps]
                try:
                    cur.execute(
                        """
                        INSERT INTO matches (
                            game, team1_id, team2_id, team1_name, team2_name,
                            team1_score, team2_score, winner_team_id, format,
                            match_date, league_id, league_name, maps, source
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'admin')
                        RETURNING id
                        """,
                        (
                            "Valorant", t1["id"], t2["id"], t1["name"], t2["name"],
                            t1_maps, t2_maps, winner_id, req.format,
                            match_date, league_id, league_name, Json(maps_payload),
                        ),
                    )
                except pg_errors.UniqueViolation:
                    conn.rollback()
                    raise HTTPException(409, "A match between these teams on this date already exists")
                match_id = cur.fetchone()["id"]

                for m in req.maps:
                    for side, players in (("team1", m.team1Players), ("team2", m.team2Players)):
                        team = t1 if side == "team1" else t2
                        team_score = m.team1Score if side == "team1" else m.team2Score
                        opp_score = m.team2Score if side == "team1" else m.team1Score
                        won = team_score > opp_score
                        for p in players:
                            cur.execute(
                                """
                                INSERT INTO player_match_stats (
                                    match_id, player_id, team_id, team_name, game, map_name,
                                    agent, kills, deaths, assists, acs,
                                    first_kills, plants, defuses, win
                                )
                                VALUES (%s, %s, %s, %s, 'Valorant', %s,
                                        %s, %s, %s, %s, %s,
                                        %s, %s, %s, %s)
                                ON CONFLICT ON CONSTRAINT pms_unique DO UPDATE SET
                                    team_id = EXCLUDED.team_id,
                                    team_name = EXCLUDED.team_name,
                                    agent = EXCLUDED.agent,
                                    kills = EXCLUDED.kills,
                                    deaths = EXCLUDED.deaths,
                                    assists = EXCLUDED.assists,
                                    acs = EXCLUDED.acs,
                                    first_kills = EXCLUDED.first_kills,
                                    plants = EXCLUDED.plants,
                                    defuses = EXCLUDED.defuses,
                                    win = EXCLUDED.win
                                """,
                                (
                                    match_id, _int_id(p.playerId, "playerId"),
                                    team["id"], team["name"], m.mapName,
                                    p.agent, p.kills, p.deaths, p.assists, p.acs,
                                    p.firstKills, p.plants, p.defuses, won,
                                ),
                            )

                _apply_record_update(cur, t1["id"], winner_id == t1["id"], t1_maps, t2_maps)
                _apply_record_update(cur, t2["id"], winner_id == t2["id"], t2_maps, t1_maps)
                conn.commit()
                return {"ok": True, "matchId": str(match_id), "winnerTeamId": str(winner_id)}

            # League of Legends
            if req.team1Score is None or req.team2Score is None:
                raise HTTPException(400, "team1Score/team2Score required for LoL")
            winner_id = t1["id"] if req.team1Score > req.team2Score else t2["id"]
            lol_payload = {
                "team1": [p.model_dump() for p in req.lolTeam1Players],
                "team2": [p.model_dump() for p in req.lolTeam2Players],
            }
            try:
                cur.execute(
                    """
                    INSERT INTO matches (
                        game, team1_id, team2_id, team1_name, team2_name,
                        team1_score, team2_score, winner_team_id, format,
                        match_date, league_id, league_name, lol_players, source
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'admin')
                    RETURNING id
                    """,
                    (
                        "League of Legends", t1["id"], t2["id"], t1["name"], t2["name"],
                        req.team1Score, req.team2Score, winner_id, req.format,
                        match_date, league_id, league_name, Json(lol_payload),
                    ),
                )
            except pg_errors.UniqueViolation:
                conn.rollback()
                raise HTTPException(409, "A match between these teams on this date already exists")
            match_id = cur.fetchone()["id"]

            for side, players in (("team1", req.lolTeam1Players), ("team2", req.lolTeam2Players)):
                team = t1 if side == "team1" else t2
                team_score = req.team1Score if side == "team1" else req.team2Score
                opp_score = req.team2Score if side == "team1" else req.team1Score
                won = team_score > opp_score
                for p in players:
                    cur.execute(
                        """
                        INSERT INTO player_match_stats (
                            match_id, player_id, team_id, team_name, game,
                            champion, role, kills, deaths, assists,
                            cs, gold, damage, vision, wards, win
                        )
                        VALUES (%s, %s, %s, %s, 'League of Legends',
                                %s, %s, %s, %s, %s,
                                %s, %s, %s, %s, %s, %s)
                        ON CONFLICT ON CONSTRAINT pms_unique DO UPDATE SET
                            team_id = EXCLUDED.team_id,
                            team_name = EXCLUDED.team_name,
                            champion = EXCLUDED.champion,
                            role = EXCLUDED.role,
                            kills = EXCLUDED.kills,
                            deaths = EXCLUDED.deaths,
                            assists = EXCLUDED.assists,
                            cs = EXCLUDED.cs,
                            gold = EXCLUDED.gold,
                            damage = EXCLUDED.damage,
                            vision = EXCLUDED.vision,
                            wards = EXCLUDED.wards,
                            win = EXCLUDED.win
                        """,
                        (
                            match_id, _int_id(p.playerId, "playerId"),
                            team["id"], team["name"],
                            p.champion, p.role, p.kills, p.deaths, p.assists,
                            p.cs, p.gold, p.damage, p.vision, p.wards, won,
                        ),
                    )

            _apply_record_update(cur, t1["id"], winner_id == t1["id"], req.team1Score, req.team2Score)
            _apply_record_update(cur, t2["id"], winner_id == t2["id"], req.team2Score, req.team1Score)
            conn.commit()
            return {"ok": True, "matchId": str(match_id), "winnerTeamId": str(winner_id)}
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()


# ---------- match edit / delete ----------

class MatchScorePatch(BaseModel):
    team1Score: int
    team2Score: int


@router.patch("/matches/{match_id}", dependencies=[Depends(require_admin)])
def update_match(match_id: str, req: MatchScorePatch):
    """Correct a mis-entered series score and adjust team W/L counters."""
    mid = _int_id(match_id, "match_id")
    if req.team1Score == req.team2Score:
        raise HTTPException(400, "Scores cannot be tied")

    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute(
                "SELECT id, team1_id, team2_id, team1_score, team2_score, winner_team_id "
                "FROM matches WHERE id = %s",
                (mid,),
            )
            match = cur.fetchone()
            if not match:
                raise HTTPException(404, "Match not found")

            t1_id = match["team1_id"]
            t2_id = match["team2_id"]
            old_t1 = int(match["team1_score"] or 0)
            old_t2 = int(match["team2_score"] or 0)
            old_winner = match["winner_team_id"]

            if t1_id:
                _reverse_record_update(cur, t1_id, old_winner == t1_id, old_t1, old_t2)
            if t2_id:
                _reverse_record_update(cur, t2_id, old_winner == t2_id, old_t2, old_t1)

            new_winner = t1_id if req.team1Score > req.team2Score else t2_id
            cur.execute(
                """
                UPDATE matches
                   SET team1_score = %s, team2_score = %s, winner_team_id = %s
                 WHERE id = %s
                """,
                (req.team1Score, req.team2Score, new_winner, mid),
            )
            if t1_id:
                _apply_record_update(cur, t1_id, new_winner == t1_id, req.team1Score, req.team2Score)
            if t2_id:
                _apply_record_update(cur, t2_id, new_winner == t2_id, req.team2Score, req.team1Score)
            conn.commit()
            return {"ok": True, "matchId": str(mid), "winnerTeamId": str(new_winner) if new_winner else None}
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()


@router.delete("/matches/{match_id}", dependencies=[Depends(require_admin)])
def delete_match(match_id: str):
    """Hard-delete a match. Reverses team W/L and removes player stat rows."""
    mid = _int_id(match_id, "match_id")

    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute(
                "SELECT id, team1_id, team2_id, team1_score, team2_score, winner_team_id "
                "FROM matches WHERE id = %s",
                (mid,),
            )
            match = cur.fetchone()
            if not match:
                raise HTTPException(404, "Match not found")

            t1_id = match["team1_id"]
            t2_id = match["team2_id"]
            t1_score = int(match["team1_score"] or 0)
            t2_score = int(match["team2_score"] or 0)
            winner = match["winner_team_id"]

            if t1_id:
                _reverse_record_update(cur, t1_id, winner == t1_id, t1_score, t2_score)
            if t2_id:
                _reverse_record_update(cur, t2_id, winner == t2_id, t2_score, t1_score)

            cur.execute(
                "DELETE FROM player_match_stats WHERE match_id = %s",
                (mid,),
            )
            removed = cur.rowcount
            cur.execute("DELETE FROM matches WHERE id = %s", (mid,))
            conn.commit()
            return {"ok": True, "deletedStatRows": removed}
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()


# ---------- admin dashboard stats ----------

@router.get("/stats", dependencies=[Depends(require_admin)])
def admin_stats():
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT
              (SELECT COUNT(*) FROM matches)  AS matches,
              (SELECT COUNT(*) FROM players)  AS players,
              (SELECT COUNT(*) FROM teams)    AS teams,
              (SELECT COUNT(*) FROM schools)  AS schools,
              (SELECT COUNT(*) FROM leagues)  AS leagues
            """
        )
        counts = cur.fetchone()

        cur.execute(
            """
            SELECT id, game, team1_name, team2_name, team1_score, team2_score,
                   format, match_date
              FROM matches
             ORDER BY match_date DESC
             LIMIT 5
            """
        )
        recent = cur.fetchall()

    return {
        "counts": {
            "matches": int(counts["matches"]),
            "players": int(counts["players"]),
            "teams": int(counts["teams"]),
            "schools": int(counts["schools"]),
            "leagues": int(counts["leagues"]),
        },
        "recent_matches": [
            {
                "_id": str(r["id"]),
                "game": r["game"],
                "team1Name": r["team1_name"],
                "team2Name": r["team2_name"],
                "team1Score": r["team1_score"],
                "team2Score": r["team2_score"],
                "format": r["format"],
                "date": _iso(r["match_date"]),
            }
            for r in recent
        ],
    }
