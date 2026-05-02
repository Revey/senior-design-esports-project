"""Admin router (Postgres-backed; Phase 3f.1 of postgres-migration-v2).

Auth model:
  - Single shared admin password (env: ADMIN_PASSWORD).
  - POST /api/admin/login exchanges password for a short-lived HMAC token.
  - All other /api/admin/* endpoints require Authorization: Bearer <token>.

Phase 3f.1 covers: auth + schools + teams + players + orgs + seasons +
conferences + memberships + leagues-tree.

Out of this slice (added later):
  - /api/admin/matches CRUD (POST/PATCH/DELETE) — Phase 3f.2 (multi-statement
    transactions with W/L delta logic).
  - /api/admin/stats (dashboard) — Phase 3f.3.
  - The legacy /api/admin/leagues endpoints — deleted entirely in Phase 3f.3
    (no Postgres equivalent, parallel to Phase 3a).

Wire contract (Path A): preserve the Mongo-era camelCase shape so the existing
admin frontend keeps working. `_id` is the numeric string of the row's id.
Aliases: teamName ← name, mapWins ← map_wins, displayName ← display_name, etc.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from psycopg2.errors import UniqueViolation
from psycopg2.extras import RealDictCursor

from core.db import get_conn, get_cursor

router = APIRouter()
logger = logging.getLogger(__name__)

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
ADMIN_SECRET = os.getenv("ADMIN_SECRET", ADMIN_PASSWORD or "dev-insecure-secret")
TOKEN_TTL_SECONDS = 60 * 60 * 12  # 12h

_VALID_GAMES = {"valorant", "lol"}
_VALID_SEMESTERS = {"fall", "spring", "summer"}


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


# ---------- shared utilities ----------

def _slugify(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def _int_id(s: str, label: str = "id") -> int:
    try:
        return int(s)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"Invalid {label}: {s!r}")


def _season_create_year(year_str: str, semester: str) -> int:
    """Phase 4: year is a 4-year-pair string like '2025-2026' (admin convention).
    Semester is now lowercase ('fall'/'spring'/'summer'). Convention: 'spring'
    keeps the second part, others keep the first.
    """
    if not re.match(r"^\d{4}-\d{4}$", year_str):
        raise HTTPException(status_code=400, detail="year must be like 2025-2026")
    parts = year_str.split("-")
    return int(parts[1] if semester == "spring" else parts[0])


def _season_year_string(year: int, semester: str) -> str:
    if semester == "spring":
        return f"{year - 1}-{year}"
    return f"{year}-{year + 1}"


def _season_label(org_abbr: str, semester: str, year_str: str) -> str:
    """Build a human-friendly label like 'CVAL Fall 2025'."""
    years = year_str.split("-")
    shown = years[0] if semester == "fall" else (years[1] if len(years) > 1 else years[0])
    return f"{org_abbr} {semester.capitalize()} {shown}"


def _get_active_season_id(cur) -> Optional[int]:
    cur.execute(
        "SELECT id FROM seasons WHERE active = TRUE ORDER BY id ASC LIMIT 1"
    )
    row = cur.fetchone()
    return row["id"] if row else None


# ---------- response shapers ----------

def _shape_school(r: dict) -> dict:
    return {
        "_id":       str(r["id"]),
        "name":      r["name"],
        "slug":      r["slug"],
        "createdAt": r["created_at"].isoformat() if r.get("created_at") else None,
    }


def _shape_team(r: dict) -> dict:
    return {
        "_id":        str(r["id"]),
        "teamName":   r["name"],                # Mongo alias
        "slug":       r["slug"],
        "school":     r.get("school_name") or "",
        "schoolId":   str(r["school_id"]) if r.get("school_id") is not None else None,
        "game":       (r.get("game") or ""),
        "tier":       r.get("tier"),
        "wins":       r.get("wins") or 0,
        "losses":     r.get("losses") or 0,
        "mapWins":    r.get("map_wins") or 0,
        "mapLosses":  r.get("map_losses") or 0,
    }


def _shape_player(r: dict, team_ids: Optional[list[int]] = None) -> dict:
    return {
        "_id":         str(r["id"]),
        "displayName": r.get("display_name") or r.get("name") or "",
        "riotId":      r.get("riot_id"),
        "role":        r.get("role"),
        "teamIds":     [str(t) for t in (team_ids or [])],
        "active":      r.get("active", True),
    }


def _shape_org(r: dict) -> dict:
    return {
        "_id":          str(r["id"]),
        "name":         r["name"],
        "abbreviation": r["abbreviation"],
        "slug":         r["slug"],
        "games":        [(g) or "" for g in (r.get("games") or [])],
    }


def _shape_season(r: dict) -> dict:
    semester_label = (r.get("semester") or "")
    year_str = _season_year_string(r["year"], semester_label) if r.get("year") else ""
    return {
        "_id":      str(r["id"]),
        "orgId":    str(r["org_id"]),
        "year":     year_str,
        "semester": semester_label,
        "label":    r.get("label") or "",
        "active":   r.get("active", False),
    }


def _shape_conference(r: dict) -> dict:
    return {
        "_id":       str(r["id"]),
        "orgId":     str(r["org_id"]),
        "name":      r["name"],
        "shortName": r.get("short_name") or r["name"],
        "slug":      r["slug"],
        "tier":      r.get("tier"),
        "kind":      r.get("kind"),
    }


def _shape_membership(r: dict) -> dict:
    return {
        "_id":             str(r["id"]),
        "teamId":          str(r["team_id"]),
        "conferenceId":    str(r["conference_id"]),
        "seasonId":        str(r["season_id"]),
        "active":          r.get("active", True),
        # enriched fields populated by the caller (list endpoint):
        "seasonLabel":     r.get("season_label"),
        "conferenceName":  r.get("conference_name"),
        "conferenceTier":  r.get("conference_tier"),
        "orgAbbreviation": r.get("org_abbreviation"),
        "teamName":        r.get("team_name_alias"),
    }


# ---------- Pydantic request models ----------

class LoginReq(BaseModel):
    password: str


class SchoolCreate(BaseModel):
    name: str


class TeamCreate(BaseModel):
    schoolId: str
    name: str
    game: Literal["valorant", "lol"]
    tier: Optional[str] = None


class PlayerCreate(BaseModel):
    displayName: str
    riotId: Optional[str] = None
    role: Optional[str] = None
    teamIds: list[str] = Field(default_factory=list)


class PlayerLink(BaseModel):
    teamId: str


class OrgCreate(BaseModel):
    name: str
    abbreviation: str
    games: list[str] = Field(default_factory=list)


class OrgUpdate(BaseModel):
    name: Optional[str] = None
    abbreviation: Optional[str] = None
    games: Optional[list[str]] = None


class SeasonCreate(BaseModel):
    orgId: str
    year: str
    semester: Literal["fall", "spring", "summer"]
    active: bool = False


class SeasonUpdate(BaseModel):
    year: Optional[str] = None
    semester: Optional[Literal["fall", "spring", "summer"]] = None
    active: Optional[bool] = None


class ConferenceCreate(BaseModel):
    orgId: str
    name: str
    shortName: Optional[str] = None
    tier: Optional[str] = None
    kind: Optional[str] = None


class ConferenceUpdate(BaseModel):
    name: Optional[str] = None
    shortName: Optional[str] = None
    tier: Optional[str] = None
    kind: Optional[str] = None


class MembershipCreate(BaseModel):
    teamId: str
    conferenceId: str
    seasonId: str
    active: bool = True


class MembershipUpdate(BaseModel):
    active: bool


# Match request models (Phase 3f.2)
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
    team1Score: int       # round score (e.g. 13)
    team2Score: int       # round score
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


class MatchCreate(BaseModel):
    game: Literal["valorant", "lol"]
    team1Id: str
    team2Id: str
    date: Optional[str] = None
    format: Literal["bo1", "bo3", "bo5"] = "bo1"
    # Optional new-hierarchy refs:
    orgId: Optional[str] = None
    seasonId: Optional[str] = None
    conferenceId: Optional[str] = None
    # Valorant payload:
    maps: list[ValMap] = Field(default_factory=list)
    # LoL payload (series totals + per-player rows):
    team1Score: Optional[int] = None
    team2Score: Optional[int] = None
    lolTeam1Players: list[LolPlayerStat] = Field(default_factory=list)
    lolTeam2Players: list[LolPlayerStat] = Field(default_factory=list)


class MatchScorePatch(BaseModel):
    team1Score: int
    team2Score: int


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
def list_schools(q: str = Query("", max_length=100), limit: int = Query(20, ge=1, le=200)):
    with get_cursor() as cur:
        if q:
            cur.execute(
                "SELECT * FROM schools WHERE name ILIKE %s ORDER BY name LIMIT %s",
                (f"%{q}%", limit),
            )
        else:
            cur.execute("SELECT * FROM schools ORDER BY name LIMIT %s", (limit,))
        rows = cur.fetchall()
    return [_shape_school(r) for r in rows]


@router.post("/schools", dependencies=[Depends(require_admin)])
def create_school(req: SchoolCreate):
    name = req.name.strip()
    if not name:
        raise HTTPException(400, "name required")
    slug = _slugify(name)
    with get_cursor() as cur:
        cur.execute("SELECT * FROM schools WHERE slug = %s", (slug,))
        existing = cur.fetchone()
        if existing:
            return _shape_school(existing)
        cur.execute(
            "INSERT INTO schools (name, slug) VALUES (%s, %s) RETURNING *",
            (name, slug),
        )
        row = cur.fetchone()
    return _shape_school(row)


# ---------- teams (admin) ----------

@router.get("/teams", dependencies=[Depends(require_admin)])
def list_admin_teams(
    q: str = Query("", max_length=100),
    schoolId: Optional[str] = None,
    game: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
):
    school_id = _int_id(schoolId, "schoolId") if schoolId else None
    db_game = game if game else None
    with get_cursor() as cur:
        cur.execute(
            "SELECT * FROM teams "
            "WHERE (%s::text IS NULL OR (name ILIKE %s OR school_name ILIKE %s)) "
            "  AND (%s::bigint IS NULL OR school_id = %s::bigint) "
            "  AND (%s::text IS NULL OR game = %s::text) "
            "ORDER BY name LIMIT %s",
            (q or None, f"%{q}%", f"%{q}%", school_id, school_id, db_game, db_game, limit),
        )
        rows = cur.fetchall()
    return [_shape_team(r) for r in rows]


@router.post("/teams", dependencies=[Depends(require_admin)])
def create_team(req: TeamCreate):
    school_id = _int_id(req.schoolId, "schoolId")
    name = req.name.strip()
    if not name:
        raise HTTPException(400, "name required")
    slug = _slugify(name)
    db_game = req.game
    with get_cursor() as cur:
        cur.execute("SELECT * FROM schools WHERE id = %s", (school_id,))
        school = cur.fetchone()
        if not school:
            raise HTTPException(404, "School not found")
        cur.execute("SELECT * FROM teams WHERE slug = %s AND game = %s", (slug, db_game))
        existing = cur.fetchone()
        if existing:
            return _shape_team(existing)
        cur.execute(
            "INSERT INTO teams (school_id, name, slug, game, tier, school_name) "
            "VALUES (%s, %s, %s, %s, %s, %s) RETURNING *",
            (school_id, name, slug, db_game, req.tier, school["name"]),
        )
        row = cur.fetchone()
    return _shape_team(row)


# ---------- players (admin) ----------

def _player_team_ids(cur, player_id: int) -> list[int]:
    cur.execute(
        "SELECT team_id FROM team_players WHERE player_id = %s AND left_at IS NULL "
        "ORDER BY joined_at ASC",
        (player_id,),
    )
    return [r["team_id"] for r in cur.fetchall()]


@router.get("/players", dependencies=[Depends(require_admin)])
def list_admin_players(
    q: str = Query("", max_length=100),
    teamId: Optional[str] = None,
    freeAgent: bool = False,
    limit: int = Query(50, ge=1, le=500),
    skip: int = Query(0, ge=0),
    paginated: bool = False,
):
    team_id = _int_id(teamId, "teamId") if teamId else None
    with get_cursor() as cur:
        if team_id is not None:
            base = (
                "FROM players p "
                "JOIN team_players tp ON tp.player_id = p.id AND tp.left_at IS NULL "
                "WHERE tp.team_id = %s "
                "  AND (%s::text IS NULL OR (p.display_name ILIKE %s OR p.riot_id ILIKE %s))"
            )
            params = (team_id, q or None, f"%{q}%", f"%{q}%")
        elif freeAgent:
            base = (
                "FROM players p "
                "WHERE NOT EXISTS ("
                "    SELECT 1 FROM team_players tp "
                "    WHERE tp.player_id = p.id AND tp.left_at IS NULL"
                ") "
                "  AND (%s::text IS NULL OR (p.display_name ILIKE %s OR p.riot_id ILIKE %s))"
            )
            params = (q or None, f"%{q}%", f"%{q}%")
        else:
            base = (
                "FROM players p "
                "WHERE (%s::text IS NULL OR (p.display_name ILIKE %s OR p.riot_id ILIKE %s))"
            )
            params = (q or None, f"%{q}%", f"%{q}%")

        if paginated:
            cur.execute(f"SELECT COUNT(*) AS n {base}", params)
            total = cur.fetchone()["n"]
        else:
            total = None

        cur.execute(
            f"SELECT p.* {base} ORDER BY p.display_name LIMIT %s OFFSET %s",
            (*params, limit, max(0, skip)),
        )
        rows = cur.fetchall()
        items = [_shape_player(r, _player_team_ids(cur, r["id"])) for r in rows]

    if paginated:
        return {"items": items, "total": total}
    return items


@router.post("/players", dependencies=[Depends(require_admin)])
def create_player(req: PlayerCreate):
    name = req.displayName.strip()
    if not name:
        raise HTTPException(400, "displayName required")
    team_ids = [_int_id(t, "teamId") for t in req.teamIds]
    riot_id = (req.riotId or "").strip() or None
    role = (req.role or "").strip() or None

    with get_conn() as conn:
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Default season for team_players inserts (if any).
                season_id = None
                if team_ids:
                    cur.execute("SELECT id FROM seasons WHERE active = TRUE ORDER BY id ASC LIMIT 1")
                    s_row = cur.fetchone()
                    if s_row is None:
                        raise HTTPException(
                            400,
                            "No active season — create one before linking players to teams "
                            "(POST /api/admin/seasons with active=true).",
                        )
                    season_id = s_row["id"]

                cur.execute(
                    "INSERT INTO players (name, display_name, riot_id, role, game, active) "
                    "VALUES (%s, %s, %s, %s, %s, %s) RETURNING *",
                    (name, name, riot_id, role, "valorant", bool(team_ids)),
                )
                player = cur.fetchone()

                for tid in team_ids:
                    cur.execute(
                        "INSERT INTO team_players (team_id, player_id, season_id) "
                        "VALUES (%s, %s, %s)",
                        (tid, player["id"], season_id),
                    )
            conn.commit()
        except HTTPException:
            conn.rollback()
            raise
        except Exception:
            conn.rollback()
            raise

    with get_cursor() as cur:
        cur.execute("SELECT * FROM players WHERE id = %s", (player["id"],))
        full = cur.fetchone()
        return _shape_player(full, _player_team_ids(cur, full["id"]))


@router.patch("/players/{player_id}/link", dependencies=[Depends(require_admin)])
def link_player(player_id: str, req: PlayerLink):
    pid = _int_id(player_id, "player_id")
    tid = _int_id(req.teamId, "teamId")

    with get_conn() as conn:
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT id FROM seasons WHERE active = TRUE ORDER BY id ASC LIMIT 1")
                s_row = cur.fetchone()
                if s_row is None:
                    raise HTTPException(
                        400,
                        "No active season — create one before linking players to teams.",
                    )
                cur.execute(
                    "INSERT INTO team_players (team_id, player_id, season_id) "
                    "VALUES (%s, %s, %s) "
                    "ON CONFLICT DO NOTHING",
                    (tid, pid, s_row["id"]),
                )
                cur.execute("UPDATE players SET active = TRUE WHERE id = %s", (pid,))
            conn.commit()
        except HTTPException:
            conn.rollback()
            raise
        except Exception:
            conn.rollback()
            raise

    with get_cursor() as cur:
        cur.execute("SELECT * FROM players WHERE id = %s", (pid,))
        player = cur.fetchone()
        if not player:
            raise HTTPException(404, "Player not found")
        return _shape_player(player, _player_team_ids(cur, pid))


@router.patch("/players/{player_id}/unlink", dependencies=[Depends(require_admin)])
def unlink_player(player_id: str, req: PlayerLink):
    pid = _int_id(player_id, "player_id")
    tid = _int_id(req.teamId, "teamId")

    with get_conn() as conn:
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "UPDATE team_players SET left_at = NOW() "
                    "WHERE player_id = %s AND team_id = %s AND left_at IS NULL",
                    (pid, tid),
                )
                cur.execute(
                    "SELECT COUNT(*) AS n FROM team_players "
                    "WHERE player_id = %s AND left_at IS NULL",
                    (pid,),
                )
                if cur.fetchone()["n"] == 0:
                    cur.execute("UPDATE players SET active = FALSE WHERE id = %s", (pid,))
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    with get_cursor() as cur:
        cur.execute("SELECT * FROM players WHERE id = %s", (pid,))
        player = cur.fetchone()
        if not player:
            raise HTTPException(404, "Player not found")
        return _shape_player(player, _player_team_ids(cur, pid))


# ---------- organizations ----------

@router.get("/orgs", dependencies=[Depends(require_admin)])
def list_orgs(q: str = Query("", max_length=100), game: Optional[str] = None, limit: int = Query(50, ge=1, le=200)):
    db_g = game if game else None
    with get_cursor() as cur:
        cur.execute(
            "SELECT * FROM organizations "
            "WHERE (%s::text IS NULL OR (name ILIKE %s OR abbreviation ILIKE %s)) "
            "  AND (%s::text IS NULL OR %s::text = ANY(games)) "
            "ORDER BY abbreviation LIMIT %s",
            (q or None, f"%{q}%", f"%{q}%", db_g, db_g, limit),
        )
        rows = cur.fetchall()
    return [_shape_org(r) for r in rows]


@router.post("/orgs", dependencies=[Depends(require_admin)])
def create_org(req: OrgCreate):
    name = req.name.strip()
    abbr = req.abbreviation.strip().upper()
    if not name or not abbr:
        raise HTTPException(400, "name and abbreviation required")
    slug = _slugify(abbr)
    games_db = [g for g in req.games if g is not None]
    if not games_db:
        raise HTTPException(400, "at least one game required (Valorant or League of Legends)")
    with get_cursor() as cur:
        cur.execute("SELECT * FROM organizations WHERE slug = %s", (slug,))
        existing = cur.fetchone()
        if existing:
            return _shape_org(existing)
        cur.execute(
            "INSERT INTO organizations (name, abbreviation, slug, games) "
            "VALUES (%s, %s, %s, %s) RETURNING *",
            (name, abbr, slug, games_db),
        )
        row = cur.fetchone()
    return _shape_org(row)


@router.patch("/orgs/{org_id}", dependencies=[Depends(require_admin)])
def update_org(org_id: str, req: OrgUpdate):
    oid = _int_id(org_id, "org_id")
    sets: list[str] = []
    params: list[Any] = []
    if req.name is not None:
        sets.append("name = %s"); params.append(req.name.strip())
    if req.abbreviation is not None:
        abbr = req.abbreviation.strip().upper()
        sets.append("abbreviation = %s"); params.append(abbr)
        sets.append("slug = %s"); params.append(_slugify(abbr))
    if req.games is not None:
        games_db = [g for g in req.games if g is not None]
        if not games_db:
            raise HTTPException(400, "games cannot be empty")
        sets.append("games = %s"); params.append(games_db)
    with get_cursor() as cur:
        if sets:
            cur.execute(f"UPDATE organizations SET {', '.join(sets)} WHERE id = %s", (*params, oid))
        cur.execute("SELECT * FROM organizations WHERE id = %s", (oid,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Organization not found")
    return _shape_org(row)


@router.delete("/orgs/{org_id}", dependencies=[Depends(require_admin)])
def delete_org(org_id: str):
    """Cascading delete: removes memberships → conferences + seasons → org.
    Phase 1 schema uses ON DELETE RESTRICT for org refs, so cascading is
    application-side.
    """
    oid = _int_id(org_id, "org_id")
    with get_conn() as conn:
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "DELETE FROM team_memberships WHERE conference_id IN "
                    "(SELECT id FROM conferences WHERE org_id = %s)",
                    (oid,),
                )
                cur.execute(
                    "DELETE FROM team_memberships WHERE season_id IN "
                    "(SELECT id FROM seasons WHERE org_id = %s)",
                    (oid,),
                )
                cur.execute("DELETE FROM conferences WHERE org_id = %s", (oid,))
                cur.execute("DELETE FROM seasons WHERE org_id = %s", (oid,))
                cur.execute("DELETE FROM organizations WHERE id = %s", (oid,))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return {"ok": True}


# ---------- seasons ----------

@router.get("/seasons", dependencies=[Depends(require_admin)])
def list_seasons(orgId: Optional[str] = None, active: Optional[bool] = None, limit: int = Query(100, ge=1, le=500)):
    oid = _int_id(orgId, "orgId") if orgId else None
    with get_cursor() as cur:
        cur.execute(
            "SELECT * FROM seasons "
            "WHERE (%s::bigint IS NULL OR org_id = %s::bigint) "
            "  AND (%s::boolean IS NULL OR active = %s::boolean) "
            "ORDER BY year DESC, semester ASC LIMIT %s",
            (oid, oid, active, active, limit),
        )
        rows = cur.fetchall()
    return [_shape_season(r) for r in rows]


@router.post("/seasons", dependencies=[Depends(require_admin)])
def create_season(req: SeasonCreate):
    oid = _int_id(req.orgId, "orgId")
    db_year = _season_create_year(req.year, req.semester)
    db_sem = req.semester

    with get_conn() as conn:
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM organizations WHERE id = %s", (oid,))
                org = cur.fetchone()
                if not org:
                    raise HTTPException(404, "Organization not found")
                cur.execute(
                    "SELECT * FROM seasons WHERE org_id = %s AND year = %s AND semester = %s",
                    (oid, db_year, db_sem),
                )
                existing = cur.fetchone()
                if existing:
                    return _shape_season(existing)
                if req.active:
                    cur.execute("UPDATE seasons SET active = FALSE WHERE org_id = %s", (oid,))
                label = _season_label(org["abbreviation"], req.semester, req.year)
                try:
                    cur.execute(
                        "INSERT INTO seasons (org_id, year, semester, label, active) "
                        "VALUES (%s, %s, %s, %s, %s) RETURNING *",
                        (oid, db_year, db_sem, label, req.active),
                    )
                    row = cur.fetchone()
                except UniqueViolation:
                    raise HTTPException(409, "Season already exists")
            conn.commit()
        except HTTPException:
            conn.rollback()
            raise
        except Exception:
            conn.rollback()
            raise
    return _shape_season(row)


@router.patch("/seasons/{season_id}", dependencies=[Depends(require_admin)])
def update_season(season_id: str, req: SeasonUpdate):
    sid = _int_id(season_id, "season_id")
    with get_conn() as conn:
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM seasons WHERE id = %s", (sid,))
                season = cur.fetchone()
                if not season:
                    raise HTTPException(404, "Season not found")
                cur.execute("SELECT * FROM organizations WHERE id = %s", (season["org_id"],))
                org = cur.fetchone()
                semester_label = (season["semester"]) or ""
                year_int = season["year"]
                sets: list[str] = []
                params: list[Any] = []
                if req.semester is not None:
                    semester_label = req.semester
                    sets.append("semester = %s"); params.append(req.semester)
                if req.year is not None:
                    year_int = _season_create_year(req.year, semester_label)
                    sets.append("year = %s"); params.append(year_int)
                if req.active is True:
                    cur.execute(
                        "UPDATE seasons SET active = FALSE WHERE org_id = %s AND id <> %s",
                        (season["org_id"], sid),
                    )
                    sets.append("active = TRUE")
                elif req.active is False:
                    sets.append("active = FALSE")
                if "year = %s" in sets or "semester = %s" in sets:
                    new_year_str = _season_year_string(year_int, semester_label)
                    sets.append("label = %s"); params.append(_season_label(org["abbreviation"], semester_label, new_year_str))
                if sets:
                    cur.execute(f"UPDATE seasons SET {', '.join(sets)} WHERE id = %s", (*params, sid))
                cur.execute("SELECT * FROM seasons WHERE id = %s", (sid,))
                row = cur.fetchone()
            conn.commit()
        except HTTPException:
            conn.rollback()
            raise
        except Exception:
            conn.rollback()
            raise
    return _shape_season(row)


@router.delete("/seasons/{season_id}", dependencies=[Depends(require_admin)])
def delete_season(season_id: str):
    sid = _int_id(season_id, "season_id")
    with get_conn() as conn:
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("DELETE FROM team_memberships WHERE season_id = %s", (sid,))
                cur.execute("DELETE FROM seasons WHERE id = %s", (sid,))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return {"ok": True}


# ---------- conferences ----------

@router.get("/conferences", dependencies=[Depends(require_admin)])
def list_conferences(orgId: Optional[str] = None, q: str = Query("", max_length=100), limit: int = Query(100, ge=1, le=500)):
    oid = _int_id(orgId, "orgId") if orgId else None
    with get_cursor() as cur:
        cur.execute(
            "SELECT * FROM conferences "
            "WHERE (%s::bigint IS NULL OR org_id = %s::bigint) "
            "  AND (%s::text IS NULL OR name ILIKE %s) "
            "ORDER BY tier NULLS LAST, name LIMIT %s",
            (oid, oid, q or None, f"%{q}%", limit),
        )
        rows = cur.fetchall()
    return [_shape_conference(r) for r in rows]


@router.post("/conferences", dependencies=[Depends(require_admin)])
def create_conference(req: ConferenceCreate):
    oid = _int_id(req.orgId, "orgId")
    name = req.name.strip()
    if not name:
        raise HTTPException(400, "name required")
    slug_input = f"{(req.tier or '').strip()} {name}".strip()
    slug = _slugify(slug_input)
    with get_cursor() as cur:
        cur.execute("SELECT * FROM organizations WHERE id = %s", (oid,))
        if not cur.fetchone():
            raise HTTPException(404, "Organization not found")
        cur.execute("SELECT * FROM conferences WHERE org_id = %s AND slug = %s", (oid, slug))
        existing = cur.fetchone()
        if existing:
            return _shape_conference(existing)
        cur.execute(
            "INSERT INTO conferences (org_id, name, short_name, slug, tier, kind) "
            "VALUES (%s, %s, %s, %s, %s, %s) RETURNING *",
            (oid, name, (req.shortName or name).strip(), slug, (req.tier or "").strip() or None, req.kind),
        )
        row = cur.fetchone()
    return _shape_conference(row)


@router.patch("/conferences/{conf_id}", dependencies=[Depends(require_admin)])
def update_conference(conf_id: str, req: ConferenceUpdate):
    cid = _int_id(conf_id, "conf_id")
    with get_conn() as conn:
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM conferences WHERE id = %s", (cid,))
                conf = cur.fetchone()
                if not conf:
                    raise HTTPException(404, "Conference not found")
                sets: list[str] = []
                params: list[Any] = []
                new_name = conf["name"]
                new_tier = conf.get("tier")
                if req.name is not None:
                    new_name = req.name.strip()
                    sets.append("name = %s"); params.append(new_name)
                if req.shortName is not None:
                    sets.append("short_name = %s"); params.append(req.shortName.strip())
                if req.tier is not None:
                    new_tier = req.tier.strip() or None
                    sets.append("tier = %s"); params.append(new_tier)
                if req.kind is not None:
                    sets.append("kind = %s"); params.append(req.kind)
                if req.name is not None or req.tier is not None:
                    new_slug = _slugify(f"{new_tier or ''} {new_name}".strip())
                    sets.append("slug = %s"); params.append(new_slug)
                if sets:
                    cur.execute(f"UPDATE conferences SET {', '.join(sets)} WHERE id = %s", (*params, cid))
                cur.execute("SELECT * FROM conferences WHERE id = %s", (cid,))
                row = cur.fetchone()
            conn.commit()
        except HTTPException:
            conn.rollback()
            raise
        except Exception:
            conn.rollback()
            raise
    return _shape_conference(row)


@router.delete("/conferences/{conf_id}", dependencies=[Depends(require_admin)])
def delete_conference(conf_id: str):
    cid = _int_id(conf_id, "conf_id")
    with get_conn() as conn:
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("DELETE FROM team_memberships WHERE conference_id = %s", (cid,))
                cur.execute("DELETE FROM conferences WHERE id = %s", (cid,))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return {"ok": True}


# ---------- team memberships ----------

@router.get("/memberships", dependencies=[Depends(require_admin)])
def list_memberships(
    teamId: Optional[str] = None,
    conferenceId: Optional[str] = None,
    seasonId: Optional[str] = None,
    active: Optional[bool] = None,
    limit: int = Query(200, ge=1, le=1000),
):
    t_id = _int_id(teamId, "teamId") if teamId else None
    c_id = _int_id(conferenceId, "conferenceId") if conferenceId else None
    s_id = _int_id(seasonId, "seasonId") if seasonId else None
    with get_cursor() as cur:
        cur.execute(
            "SELECT tm.*, "
            "       s.label AS season_label, "
            "       c.name AS conference_name, "
            "       c.tier AS conference_tier, "
            "       o.abbreviation AS org_abbreviation, "
            "       t.name AS team_name_alias "
            "FROM team_memberships tm "
            "JOIN seasons s ON s.id = tm.season_id "
            "JOIN conferences c ON c.id = tm.conference_id "
            "LEFT JOIN organizations o ON o.id = c.org_id "
            "LEFT JOIN teams t ON t.id = tm.team_id "
            "WHERE (%s::bigint IS NULL OR tm.team_id = %s::bigint) "
            "  AND (%s::bigint IS NULL OR tm.conference_id = %s::bigint) "
            "  AND (%s::bigint IS NULL OR tm.season_id = %s::bigint) "
            "  AND (%s::boolean IS NULL OR tm.active = %s::boolean) "
            "LIMIT %s",
            (t_id, t_id, c_id, c_id, s_id, s_id, active, active, limit),
        )
        rows = cur.fetchall()
    return [_shape_membership(r) for r in rows]


@router.post("/memberships", dependencies=[Depends(require_admin)])
def create_membership(req: MembershipCreate):
    tid = _int_id(req.teamId, "teamId")
    cid = _int_id(req.conferenceId, "conferenceId")
    sid = _int_id(req.seasonId, "seasonId")
    with get_cursor() as cur:
        cur.execute("SELECT * FROM teams WHERE id = %s", (tid,))
        if not cur.fetchone():
            raise HTTPException(404, "Team not found")
        cur.execute("SELECT * FROM conferences WHERE id = %s", (cid,))
        conf = cur.fetchone()
        if not conf:
            raise HTTPException(404, "Conference not found")
        cur.execute("SELECT * FROM seasons WHERE id = %s", (sid,))
        season = cur.fetchone()
        if not season:
            raise HTTPException(404, "Season not found")
        if conf["org_id"] != season["org_id"]:
            raise HTTPException(400, "conference and season must belong to the same org")
        cur.execute(
            "SELECT * FROM team_memberships "
            "WHERE team_id = %s AND conference_id = %s AND season_id = %s",
            (tid, cid, sid),
        )
        existing = cur.fetchone()
        if existing:
            return _shape_membership(existing)
        try:
            cur.execute(
                "INSERT INTO team_memberships (team_id, conference_id, season_id, active) "
                "VALUES (%s, %s, %s, %s) RETURNING *",
                (tid, cid, sid, req.active),
            )
            row = cur.fetchone()
        except UniqueViolation:
            raise HTTPException(409, "Membership already exists")
    return _shape_membership(row)


@router.patch("/memberships/{membership_id}", dependencies=[Depends(require_admin)])
def update_membership(membership_id: str, req: MembershipUpdate):
    mid = _int_id(membership_id, "membership_id")
    with get_cursor() as cur:
        cur.execute("UPDATE team_memberships SET active = %s WHERE id = %s", (req.active, mid))
        cur.execute("SELECT * FROM team_memberships WHERE id = %s", (mid,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Membership not found")
    return _shape_membership(row)


@router.delete("/memberships/{membership_id}", dependencies=[Depends(require_admin)])
def delete_membership(membership_id: str):
    mid = _int_id(membership_id, "membership_id")
    with get_cursor() as cur:
        cur.execute("DELETE FROM team_memberships WHERE id = %s", (mid,))
    return {"ok": True}


# ---------- leagues tree (nested orgs + seasons + conferences) ----------

@router.get("/leagues-tree", dependencies=[Depends(require_admin)])
def leagues_tree():
    with get_cursor() as cur:
        cur.execute("SELECT * FROM organizations ORDER BY abbreviation")
        orgs = cur.fetchall()
        cur.execute("SELECT * FROM seasons ORDER BY org_id, year DESC, semester")
        all_seasons = cur.fetchall()
        cur.execute("SELECT * FROM conferences ORDER BY org_id, tier NULLS LAST, name")
        all_confs = cur.fetchall()
    by_org_seasons: dict[int, list[dict]] = {}
    for s in all_seasons:
        by_org_seasons.setdefault(s["org_id"], []).append(_shape_season(s))
    by_org_confs: dict[int, list[dict]] = {}
    for c in all_confs:
        by_org_confs.setdefault(c["org_id"], []).append(_shape_conference(c))
    out = []
    for o in orgs:
        oid = o["id"]
        out.append({
            **_shape_org(o),
            "seasons":     by_org_seasons.get(oid, []),
            "conferences": by_org_confs.get(oid, []),
        })
    return out


# ============================================================================
# Phase 3f.2 — Match CRUD (POST/PATCH/DELETE /api/admin/matches)
#
# Multi-statement transactions throughout. Uses get_conn() + explicit
# conn.cursor() per the CONSTITUTION's "Multi-statement transaction pattern"
# (NEVER nested get_cursor inside get_conn).
#
# W/L delta logic:
#   - On insert: apply +1 win/loss + map_wins/map_losses to both teams.
#   - On score-patch: reverse old delta, apply new delta.
#   - On delete: reverse delta, cascade pms+detail rows via FK.
#
# Per-map round scores in Val (m.team1Score / m.team2Score) are NOT persisted
# to the schema (Phase 1 has no per-map score columns; the gap was documented
# in Phase 3e SPEC). The aggregate match-level score is the count of maps
# each team won (e.g. 2-1 in a bo3). Per-map round scores are dropped.
# ============================================================================

def _resolve_hierarchy(cur, org_id_str: Optional[str], season_id_str: Optional[str],
                       conf_id_str: Optional[str]) -> tuple[Optional[int], Optional[int],
                                                              Optional[int], Optional[str], Optional[str]]:
    """Validate and return (org_id, season_id, conf_id, league_name_synth, _).

    Returns the IDs (int or None) and a synthesized league_name string from
    `{abbrev} {tier?} {conference}` for legacy display fallback.
    """
    org_id = _int_id(org_id_str, "orgId") if org_id_str else None
    season_id = _int_id(season_id_str, "seasonId") if season_id_str else None
    conf_id = _int_id(conf_id_str, "conferenceId") if conf_id_str else None

    org_abbr: Optional[str] = None
    if org_id is not None:
        cur.execute("SELECT abbreviation FROM organizations WHERE id = %s", (org_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Organization not found")
        org_abbr = row["abbreviation"]
    if season_id is not None:
        cur.execute("SELECT org_id FROM seasons WHERE id = %s", (season_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Season not found")
        if org_id is not None and row["org_id"] != org_id:
            raise HTTPException(400, "Season does not belong to the selected organization")
    league_name: Optional[str] = None
    if conf_id is not None:
        cur.execute("SELECT org_id, name, tier FROM conferences WHERE id = %s", (conf_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Conference not found")
        if org_id is not None and row["org_id"] != org_id:
            raise HTTPException(400, "Conference does not belong to the selected organization")
        if org_abbr:
            tier = row["tier"]
            league_name = f"{org_abbr} {(tier + ' ') if tier else ''}{row['name']}".strip()
    return org_id, season_id, conf_id, league_name, None


def _apply_record_delta(cur, team_id: int, won: bool, map_wins: int, map_losses: int) -> None:
    cur.execute(
        "UPDATE teams SET "
        "  wins = wins + %s, losses = losses + %s, "
        "  map_wins = map_wins + %s, map_losses = map_losses + %s "
        "WHERE id = %s",
        (1 if won else 0, 0 if won else 1, map_wins, map_losses, team_id),
    )


def _reverse_record_delta(cur, team_id: int, won: bool, map_wins: int, map_losses: int) -> None:
    cur.execute(
        "UPDATE teams SET "
        "  wins = wins - %s, losses = losses - %s, "
        "  map_wins = map_wins - %s, map_losses = map_losses - %s "
        "WHERE id = %s",
        (1 if won else 0, 0 if won else 1, map_wins, map_losses, team_id),
    )


@router.post("/matches", dependencies=[Depends(require_admin)])
def create_match(req: MatchCreate):
    t1_id = _int_id(req.team1Id, "team1Id")
    t2_id = _int_id(req.team2Id, "team2Id")
    if t1_id == t2_id:
        raise HTTPException(400, "team1 and team2 must differ")
    db_game = req.game
    db_format = req.format.lower()  # frontend BO1/BO3/BO5 → schema bo1/bo3/bo5

    match_date = req.date or datetime.now(timezone.utc).isoformat()

    with get_conn() as conn:
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Validate teams + game match.
                cur.execute("SELECT id, name, game FROM teams WHERE id IN (%s, %s)", (t1_id, t2_id))
                team_rows = {r["id"]: r for r in cur.fetchall()}
                if t1_id not in team_rows or t2_id not in team_rows:
                    raise HTTPException(404, "Team not found")
                if team_rows[t1_id]["game"] != db_game or team_rows[t2_id]["game"] != db_game:
                    raise HTTPException(400, "Team game mismatch")
                t1_name = team_rows[t1_id]["name"]
                t2_name = team_rows[t2_id]["name"]

                # Hierarchy refs.
                org_id, season_id, conf_id, league_name, _ = _resolve_hierarchy(
                    cur, req.orgId, req.seasonId, req.conferenceId,
                )

                # Reversed-team duplicate pre-check (CONSTITUTION mandate).
                cur.execute(
                    "SELECT 1 FROM matches "
                    "WHERE ((team1_id = %s AND team2_id = %s) OR (team1_id = %s AND team2_id = %s)) "
                    "  AND match_date = %s AND game = %s",
                    (t1_id, t2_id, t2_id, t1_id, match_date, db_game),
                )
                if cur.fetchone():
                    raise HTTPException(409, "A match between these teams on this date already exists")

                # Compute aggregate match scores.
                if req.game == "valorant":
                    if not req.maps:
                        raise HTTPException(400, "At least one map required for Valorant")
                    t1_maps = sum(1 for m in req.maps if m.team1Score > m.team2Score)
                    t2_maps = sum(1 for m in req.maps if m.team2Score > m.team1Score)
                    match_t1_score, match_t2_score = t1_maps, t2_maps
                else:
                    if req.team1Score is None or req.team2Score is None:
                        raise HTTPException(400, "team1Score/team2Score required for LoL")
                    match_t1_score, match_t2_score = req.team1Score, req.team2Score

                # Insert match.
                try:
                    cur.execute(
                        "INSERT INTO matches "
                        "(team1_id, team2_id, team1_score, team2_score, format, match_date, game, "
                        " source, org_id, season_id, conference_id, league_name) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, 'admin', %s, %s, %s, %s) RETURNING *",
                        (t1_id, t2_id, match_t1_score, match_t2_score, db_format, match_date,
                         db_game, org_id, season_id, conf_id, league_name),
                    )
                    match_row = cur.fetchone()
                except UniqueViolation:
                    raise HTTPException(409, "A match between these teams on this date already exists")
                match_id = match_row["id"]

                # Insert per-player stats.
                if req.game == "valorant":
                    for m in req.maps:
                        for side, players in (("team1", m.team1Players), ("team2", m.team2Players)):
                            team_id = t1_id if side == "team1" else t2_id
                            team_name = t1_name if side == "team1" else t2_name
                            for p in players:
                                player_id = _int_id(p.playerId, "playerId")
                                cur.execute(
                                    "INSERT INTO player_match_stats "
                                    "(match_id, player_id, team_id, team_name, game, map_name) "
                                    "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                                    (match_id, player_id, team_id, team_name, db_game, m.mapName),
                                )
                                pms_id = cur.fetchone()["id"]
                                extras = {"firstKills": p.firstKills, "plants": p.plants, "defuses": p.defuses}
                                cur.execute(
                                    "INSERT INTO pms_valorant_details "
                                    "(pms_id, kills, deaths, assists, agent, acs, details) "
                                    "VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)",
                                    (pms_id, p.kills, p.deaths, p.assists, p.agent, p.acs,
                                     json.dumps(extras)),
                                )
                else:  # LoL
                    for side, players in (("team1", req.lolTeam1Players), ("team2", req.lolTeam2Players)):
                        team_id = t1_id if side == "team1" else t2_id
                        team_name = t1_name if side == "team1" else t2_name
                        for p in players:
                            player_id = _int_id(p.playerId, "playerId")
                            cur.execute(
                                "INSERT INTO player_match_stats "
                                "(match_id, player_id, team_id, team_name, game, map_name) "
                                "VALUES (%s, %s, %s, %s, %s, '') RETURNING id",
                                (match_id, player_id, team_id, team_name, db_game),
                            )
                            pms_id = cur.fetchone()["id"]
                            extras = {"damage": p.damage, "vision": p.vision, "wards": p.wards}
                            cur.execute(
                                "INSERT INTO pms_lol_details "
                                "(pms_id, kills, deaths, assists, champion, lane, cs, gold, details) "
                                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)",
                                (pms_id, p.kills, p.deaths, p.assists, p.champion, p.role,
                                 p.cs, p.gold, json.dumps(extras)),
                            )

                # Apply W/L delta.
                if match_t1_score == match_t2_score:
                    winner_id: Optional[int] = None
                else:
                    winner_id = t1_id if match_t1_score > match_t2_score else t2_id
                if winner_id is not None:
                    _apply_record_delta(cur, t1_id, winner_id == t1_id, match_t1_score, match_t2_score)
                    _apply_record_delta(cur, t2_id, winner_id == t2_id, match_t2_score, match_t1_score)
            conn.commit()
        except HTTPException:
            conn.rollback()
            raise
        except Exception:
            conn.rollback()
            raise

    return {
        "ok":           True,
        "matchId":      str(match_id),
        "winnerTeamId": str(winner_id) if winner_id is not None else None,
    }


@router.patch("/matches/{match_id}", dependencies=[Depends(require_admin)])
def update_match(match_id: str, req: MatchScorePatch):
    """Score-only patch: adjust team1/team2 scores and reverse+reapply W/L delta.

    Per-map / per-player edits require delete + re-create (frontend convention
    matches Mongo behavior).
    """
    mid = _int_id(match_id, "match_id")
    if req.team1Score == req.team2Score:
        raise HTTPException(400, "Scores cannot be tied")

    with get_conn() as conn:
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM matches WHERE id = %s", (mid,))
                match = cur.fetchone()
                if not match:
                    raise HTTPException(404, "Match not found")

                t1_id, t2_id = match["team1_id"], match["team2_id"]
                old_t1, old_t2 = match["team1_score"] or 0, match["team2_score"] or 0
                old_winner = (t1_id if old_t1 > old_t2 else t2_id if old_t2 > old_t1 else None)

                # Reverse old delta (if there was a winner).
                if old_winner is not None:
                    _reverse_record_delta(cur, t1_id, old_winner == t1_id, old_t1, old_t2)
                    _reverse_record_delta(cur, t2_id, old_winner == t2_id, old_t2, old_t1)

                new_winner = t1_id if req.team1Score > req.team2Score else t2_id
                cur.execute(
                    "UPDATE matches SET team1_score = %s, team2_score = %s WHERE id = %s",
                    (req.team1Score, req.team2Score, mid),
                )
                _apply_record_delta(cur, t1_id, new_winner == t1_id, req.team1Score, req.team2Score)
                _apply_record_delta(cur, t2_id, new_winner == t2_id, req.team2Score, req.team1Score)
            conn.commit()
        except HTTPException:
            conn.rollback()
            raise
        except Exception:
            conn.rollback()
            raise

    return {"ok": True, "matchId": str(mid), "winnerTeamId": str(new_winner)}


@router.delete("/matches/{match_id}", dependencies=[Depends(require_admin)])
def delete_match(match_id: str):
    """Hard-delete: reverse W/L delta, then DELETE match.
    pms + per-game detail rows cascade via FK ON DELETE CASCADE.
    """
    mid = _int_id(match_id, "match_id")

    with get_conn() as conn:
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM matches WHERE id = %s", (mid,))
                match = cur.fetchone()
                if not match:
                    raise HTTPException(404, "Match not found")
                t1_id, t2_id = match["team1_id"], match["team2_id"]
                t1, t2 = match["team1_score"] or 0, match["team2_score"] or 0
                winner = (t1_id if t1 > t2 else t2_id if t2 > t1 else None)
                if winner is not None:
                    _reverse_record_delta(cur, t1_id, winner == t1_id, t1, t2)
                    _reverse_record_delta(cur, t2_id, winner == t2_id, t2, t1)
                cur.execute(
                    "SELECT COUNT(*) AS n FROM player_match_stats WHERE match_id = %s",
                    (mid,),
                )
                deleted_pms = cur.fetchone()["n"]
                cur.execute("DELETE FROM matches WHERE id = %s", (mid,))
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    return {"ok": True, "deletedStatRows": deleted_pms}


# ============================================================================
# Phase 3f.3 — Admin dashboard stats
# Counts of core entities + 5 most recent matches.
# ============================================================================

@router.get("/stats", dependencies=[Depends(require_admin)])
def admin_stats():
    with get_cursor() as cur:
        cur.execute(
            "SELECT "
            "  (SELECT COUNT(*) FROM matches)         AS matches, "
            "  (SELECT COUNT(*) FROM players)         AS players, "
            "  (SELECT COUNT(*) FROM teams)           AS teams, "
            "  (SELECT COUNT(*) FROM schools)         AS schools, "
            "  (SELECT COUNT(*) FROM organizations)   AS organizations, "
            "  (SELECT COUNT(*) FROM conferences)     AS conferences"
        )
        counts = cur.fetchone()

        cur.execute(
            "SELECT m.id, m.match_date, m.game, m.format, "
            "       m.team1_id, m.team2_id, m.team1_score, m.team2_score, "
            "       m.league_name, "
            "       t1.name AS team1_name, t2.name AS team2_name "
            "FROM matches m "
            "LEFT JOIN teams t1 ON t1.id = m.team1_id "
            "LEFT JOIN teams t2 ON t2.id = m.team2_id "
            "ORDER BY m.match_date DESC, m.id DESC LIMIT 5"
        )
        recent_rows = cur.fetchall()

    recent = []
    for r in recent_rows:
        t1, t2 = r["team1_score"] or 0, r["team2_score"] or 0
        winner = (str(r["team1_id"]) if t1 > t2
                  else str(r["team2_id"]) if t2 > t1 else None)
        recent.append({
            "_id":          str(r["id"]),
            "game":         (r["game"]) or "",
            "team1Id":      str(r["team1_id"]),
            "team2Id":      str(r["team2_id"]),
            "team1Name":    r.get("team1_name") or "",
            "team2Name":    r.get("team2_name") or "",
            "team1Score":   r.get("team1_score"),
            "team2Score":   r.get("team2_score"),
            "winnerTeamId": winner,
            "format":       r.get("format"),
            "date":         r["match_date"].isoformat() if r.get("match_date") else None,
            "leagueName":   r.get("league_name") or "",
        })

    return {
        "counts": {
            "matches":       counts["matches"],
            "players":       counts["players"],
            "teams":         counts["teams"],
            "schools":       counts["schools"],
            "organizations": counts["organizations"],
            "conferences":   counts["conferences"],
        },
        "recentMatches": recent,
    }
