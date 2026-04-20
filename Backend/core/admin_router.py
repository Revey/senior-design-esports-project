"""Admin router: password-gated endpoints for manual match data entry.

Auth model:
- Single shared admin password (env: ADMIN_PASSWORD).
- POST /api/admin/login exchanges password for a short-lived HMAC token.
- All other /api/admin/* endpoints require Authorization: Bearer <token>.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pymongo.errors import DuplicateKeyError
from pydantic import BaseModel, Field

from core.db import get_db

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


# ---------- utilities ----------

def _slugify(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def _oid(s: str) -> ObjectId:
    try:
        return ObjectId(s)
    except InvalidId:
        raise HTTPException(status_code=400, detail=f"Invalid id: {s}")


def _doc(d: dict[str, Any]) -> dict[str, Any]:
    d = dict(d)
    if "_id" in d:
        d["_id"] = str(d["_id"])
    for k, v in list(d.items()):
        if isinstance(v, ObjectId):
            d[k] = str(v)
        elif isinstance(v, list):
            d[k] = [str(x) if isinstance(x, ObjectId) else x for x in v]
    return d


def _db():
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    return db


def _ensure_match_index():
    """Idempotent: create a unique index to prevent duplicate match entries."""
    try:
        db = get_db()
        if db is not None:
            db["matches"].create_index(
                [("team1Id", 1), ("team2Id", 1), ("date", 1), ("game", 1)],
                unique=True,
                name="dup_match_guard",
                background=True,
            )
    except Exception:
        pass  # non-fatal — guard is advisory


def _ensure_hierarchy_indexes():
    """Indexes for orgs/seasons/conferences/memberships. Idempotent."""
    try:
        db = get_db()
        if db is None:
            return
        db["organizations"].create_index("slug", unique=True, background=True)
        db["seasons"].create_index(
            [("orgId", 1), ("year", 1), ("semester", 1)],
            unique=True, name="uniq_season", background=True,
        )
        db["conferences"].create_index(
            [("orgId", 1), ("slug", 1)],
            unique=True, name="uniq_conf_slug", background=True,
        )
        db["team_memberships"].create_index(
            [("teamId", 1), ("conferenceId", 1), ("seasonId", 1)],
            unique=True, name="uniq_membership", background=True,
        )
        db["team_memberships"].create_index("teamId", background=True)
        db["team_memberships"].create_index(
            [("conferenceId", 1), ("seasonId", 1)], background=True,
        )
    except Exception:
        pass


_ensure_match_index()
_ensure_hierarchy_indexes()


# ---------- models ----------

class LoginReq(BaseModel):
    password: str


class SchoolCreate(BaseModel):
    name: str


class TeamCreate(BaseModel):
    schoolId: str
    name: str
    game: Literal["Valorant", "League of Legends"]
    tier: Optional[str] = None  # e.g., "Varsity", "JV"


class PlayerCreate(BaseModel):
    displayName: str
    riotId: Optional[str] = None
    role: Optional[str] = None
    teamIds: list[str] = Field(default_factory=list)


class PlayerLink(BaseModel):
    teamId: str


# Match models
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
    conference: Optional[str] = None  # e.g. "NECC", "NACE", "Riot"


class MatchCreate(BaseModel):
    game: Literal["Valorant", "League of Legends"]
    team1Id: str
    team2Id: str
    date: Optional[str] = None
    format: Literal["BO1", "BO3", "BO5"] = "BO1"
    # Legacy single-league reference (kept for backward compatibility).
    leagueId: Optional[str] = None
    # New hierarchy refs — any/all may be provided; frontend passes all three.
    orgId: Optional[str] = None
    seasonId: Optional[str] = None
    conferenceId: Optional[str] = None
    # Valorant only
    maps: list[ValMap] = Field(default_factory=list)
    # LoL only (per-series totals with map count)
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
    db = _db()
    flt: dict[str, Any] = {}
    if q:
        flt["name"] = {"$regex": re.escape(q), "$options": "i"}
    rows = list(db["schools"].find(flt).limit(limit))
    return [_doc(r) for r in rows]


@router.post("/schools", dependencies=[Depends(require_admin)])
def create_school(req: SchoolCreate):
    db = _db()
    name = req.name.strip()
    if not name:
        raise HTTPException(400, "name required")
    slug = _slugify(name)
    existing = db["schools"].find_one({"slug": slug})
    if existing:
        return _doc(existing)
    doc = {"name": name, "slug": slug, "createdAt": datetime.now(timezone.utc).isoformat()}
    res = db["schools"].insert_one(doc)
    doc["_id"] = res.inserted_id
    return _doc(doc)


# ---------- leagues ----------

@router.get("/leagues", dependencies=[Depends(require_admin)])
def list_leagues(
    q: str = Query("", max_length=100),
    game: Optional[str] = None,
    limit: int = 20,
):
    db = _db()
    flt: dict[str, Any] = {}
    if q:
        flt["$or"] = [
            {"name": {"$regex": re.escape(q), "$options": "i"}},
            {"abbreviation": {"$regex": re.escape(q), "$options": "i"}},
        ]
    if game:
        flt["game"] = game
    rows = list(db["leagues"].find(flt).limit(limit))
    return [_doc(r) for r in rows]


@router.post("/leagues", dependencies=[Depends(require_admin)])
def create_league(req: LeagueCreate):
    db = _db()
    name = req.name.strip()
    if not name:
        raise HTTPException(400, "name required")
    abbreviation = req.abbreviation.strip() or name.upper()[:6]
    slug = _slugify(abbreviation or name)
    existing = db["leagues"].find_one({"slug": slug, "game": req.game})
    if existing:
        return _doc(existing)
    doc = {
        "name": name,
        "abbreviation": abbreviation,
        "slug": slug,
        "game": req.game,
        "season": req.season.strip() or "",
        "conference": (req.conference or "").strip() or None,
        "description": "",
        "standings": [],
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    res = db["leagues"].insert_one(doc)
    doc["_id"] = res.inserted_id
    return _doc(doc)


# ---------- teams ----------

@router.get("/teams", dependencies=[Depends(require_admin)])
def list_teams(
    q: str = Query("", max_length=100),
    schoolId: Optional[str] = None,
    game: Optional[str] = None,
    limit: int = 50,
):
    db = _db()
    flt: dict[str, Any] = {}
    if q:
        flt["$or"] = [
            {"teamName": {"$regex": re.escape(q), "$options": "i"}},
            {"school": {"$regex": re.escape(q), "$options": "i"}},
        ]
    if schoolId:
        flt["schoolId"] = _oid(schoolId)
    if game:
        flt["game"] = game
    rows = list(db["teams"].find(flt).limit(limit))
    return [_doc(r) for r in rows]


@router.post("/teams", dependencies=[Depends(require_admin)])
def create_team(req: TeamCreate):
    db = _db()
    school = db["schools"].find_one({"_id": _oid(req.schoolId)})
    if not school:
        raise HTTPException(404, "School not found")
    name = req.name.strip()
    slug = _slugify(name)
    existing = db["teams"].find_one({"slug": slug, "game": req.game})
    if existing:
        return _doc(existing)
    doc = {
        "teamName": name,
        "slug": slug,
        "school": school["name"],
        "schoolId": school["_id"],
        "game": req.game,
        "tier": req.tier,
        "wins": 0,
        "losses": 0,
        "mapWins": 0,
        "mapLosses": 0,
    }
    res = db["teams"].insert_one(doc)
    doc["_id"] = res.inserted_id
    return _doc(doc)


# ---------- players ----------

@router.get("/players", dependencies=[Depends(require_admin)])
def list_players(
    q: str = Query("", max_length=100),
    teamId: Optional[str] = None,
    freeAgent: bool = False,
    limit: int = 50,
    skip: int = 0,
    paginated: bool = False,
):
    """List players. Legacy callers get a plain list; pass `paginated=true` to get
    `{ items, total }` so the admin table can render page numbers."""
    db = _db()
    flt: dict[str, Any] = {}
    if q:
        flt["$or"] = [
            {"displayName": {"$regex": re.escape(q), "$options": "i"}},
            {"riotId": {"$regex": re.escape(q), "$options": "i"}},
        ]
    if teamId:
        flt["teamIds"] = _oid(teamId)
    elif freeAgent:
        flt["$or"] = (flt.get("$or") or []) + [
            {"teamIds": {"$exists": False}},
            {"teamIds": {"$size": 0}},
        ]
    cursor = db["players"].find(flt).sort("displayName", 1).skip(max(0, skip)).limit(limit)
    rows = [_doc(r) for r in cursor]
    if paginated:
        return {"items": rows, "total": db["players"].count_documents(flt)}
    return rows


@router.post("/players", dependencies=[Depends(require_admin)])
def create_player(req: PlayerCreate):
    db = _db()
    team_oids = [_oid(t) for t in req.teamIds]
    doc = {
        "displayName": req.displayName.strip(),
        "riotId": (req.riotId or "").strip() or None,
        "role": (req.role or "").strip() or None,
        "teamIds": team_oids,
        "active": len(team_oids) > 0,
        "lastUpdated": datetime.now(timezone.utc).isoformat(),
    }
    res = db["players"].insert_one(doc)
    doc["_id"] = res.inserted_id
    return _doc(doc)


@router.patch("/players/{player_id}/link", dependencies=[Depends(require_admin)])
def link_player(player_id: str, req: PlayerLink):
    db = _db()
    pid = _oid(player_id)
    tid = _oid(req.teamId)
    db["players"].update_one(
        {"_id": pid},
        {"$addToSet": {"teamIds": tid}, "$set": {"active": True}},
    )
    return _doc(db["players"].find_one({"_id": pid}) or {})


@router.patch("/players/{player_id}/unlink", dependencies=[Depends(require_admin)])
def unlink_player(player_id: str, req: PlayerLink):
    db = _db()
    pid = _oid(player_id)
    tid = _oid(req.teamId)
    db["players"].update_one({"_id": pid}, {"$pull": {"teamIds": tid}})
    player = db["players"].find_one({"_id": pid})
    if player and not player.get("teamIds"):
        db["players"].update_one({"_id": pid}, {"$set": {"active": False}})
        player = db["players"].find_one({"_id": pid})
    return _doc(player or {})


# ---------- matches ----------

def _apply_record_update(db, team_id: ObjectId, won: bool, map_wins: int, map_losses: int):
    inc = {
        "wins": 1 if won else 0,
        "losses": 0 if won else 1,
        "mapWins": map_wins,
        "mapLosses": map_losses,
    }
    db["teams"].update_one({"_id": team_id}, {"$inc": inc})


@router.post("/matches", dependencies=[Depends(require_admin)])
def create_match(req: MatchCreate):
    db = _db()
    t1 = db["teams"].find_one({"_id": _oid(req.team1Id)})
    t2 = db["teams"].find_one({"_id": _oid(req.team2Id)})
    if not t1 or not t2:
        raise HTTPException(404, "Team not found")
    if t1["game"] != req.game or t2["game"] != req.game:
        raise HTTPException(400, "Team game mismatch")

    date = req.date or datetime.now(timezone.utc).isoformat()

    # Resolve legacy league reference if provided (kept for back-compat).
    league_oid: Optional[ObjectId] = None
    league_name: Optional[str] = None
    if req.leagueId:
        league_doc = _db()["leagues"].find_one({"_id": _oid(req.leagueId)})
        if league_doc:
            league_oid = league_doc["_id"]
            league_name = league_doc.get("abbreviation") or league_doc.get("name")

    # Resolve new hierarchy refs: org / season / conference.
    org_oid: Optional[ObjectId] = None
    season_oid: Optional[ObjectId] = None
    conf_oid: Optional[ObjectId] = None
    org_abbr: Optional[str] = None
    season_label: Optional[str] = None
    conf_name: Optional[str] = None
    if req.orgId:
        org_doc = db["organizations"].find_one({"_id": _oid(req.orgId)})
        if not org_doc:
            raise HTTPException(404, "Organization not found")
        org_oid = org_doc["_id"]
        org_abbr = org_doc.get("abbreviation")
    if req.seasonId:
        season_doc = db["seasons"].find_one({"_id": _oid(req.seasonId)})
        if not season_doc:
            raise HTTPException(404, "Season not found")
        if org_oid and season_doc["orgId"] != org_oid:
            raise HTTPException(400, "Season does not belong to the selected organization")
        season_oid = season_doc["_id"]
        season_label = season_doc.get("label")
    if req.conferenceId:
        conf_doc = db["conferences"].find_one({"_id": _oid(req.conferenceId)})
        if not conf_doc:
            raise HTTPException(404, "Conference not found")
        if org_oid and conf_doc["orgId"] != org_oid:
            raise HTTPException(400, "Conference does not belong to the selected organization")
        conf_oid = conf_doc["_id"]
        conf_name = conf_doc.get("name")
        # Fill in leagueName for display if legacy field is empty.
        if not league_name and org_abbr:
            tier = conf_doc.get("tier")
            league_name = (
                f"{org_abbr} {tier + ' ' if tier else ''}{conf_name}".strip()
            )

    if req.game == "Valorant":
        if not req.maps:
            raise HTTPException(400, "At least one map required")
        t1_maps = sum(1 for m in req.maps if m.team1Score > m.team2Score)
        t2_maps = sum(1 for m in req.maps if m.team2Score > m.team1Score)
        winner_id = t1["_id"] if t1_maps > t2_maps else t2["_id"]

        match_doc = {
            "game": "Valorant",
            "team1Id": t1["_id"],
            "team2Id": t2["_id"],
            "team1Name": t1["teamName"],
            "team2Name": t2["teamName"],
            "team1Score": t1_maps,
            "team2Score": t2_maps,
            "winnerTeamId": winner_id,
            "format": req.format,
            "date": date,
            "leagueId": league_oid,
            "leagueName": league_name,
            "orgId": org_oid,
            "seasonId": season_oid,
            "conferenceId": conf_oid,
            "orgAbbreviation": org_abbr,
            "seasonLabel": season_label,
            "conferenceName": conf_name,
            "maps": [m.model_dump() for m in req.maps],
        }
        _dup = db["matches"].find_one({"$or": [
            {"team1Id": t1["_id"], "team2Id": t2["_id"], "date": date, "game": "Valorant"},
            {"team1Id": t2["_id"], "team2Id": t1["_id"], "date": date, "game": "Valorant"},
        ]})
        if _dup:
            raise HTTPException(409, f"[pre-check] Duplicate match found: {str(_dup.get('_id'))} date={date}")
        try:
            res = db["matches"].insert_one(match_doc)
        except DuplicateKeyError as e:
            raise HTTPException(409, f"[index] DuplicateKeyError: {str(e)}")

        # per-player stats rows
        pms_rows = []
        for m in req.maps:
            for side, players in (("team1", m.team1Players), ("team2", m.team2Players)):
                team_doc = t1 if side == "team1" else t2
                team_score = m.team1Score if side == "team1" else m.team2Score
                opp_score = m.team2Score if side == "team1" else m.team1Score
                for p in players:
                    pms_rows.append({
                        "matchId": res.inserted_id,
                        "game": "Valorant",
                        "mapName": m.mapName,
                        "playerId": _oid(p.playerId),
                        "teamId": team_doc["_id"],
                        "teamName": team_doc["teamName"],
                        "agent": p.agent,
                        "kills": p.kills,
                        "deaths": p.deaths,
                        "assists": p.assists,
                        "acs": p.acs,
                        "firstKills": p.firstKills,
                        "plants": p.plants,
                        "defuses": p.defuses,
                        "win": team_score > opp_score,
                    })
        if pms_rows:
            db["player match stats"].insert_many(pms_rows)

        _apply_record_update(db, t1["_id"], winner_id == t1["_id"], t1_maps, t2_maps)
        _apply_record_update(db, t2["_id"], winner_id == t2["_id"], t2_maps, t1_maps)
        return {"ok": True, "matchId": str(res.inserted_id), "winnerTeamId": str(winner_id)}

    # League of Legends
    if req.team1Score is None or req.team2Score is None:
        raise HTTPException(400, "team1Score/team2Score required for LoL")
    winner_id = t1["_id"] if req.team1Score > req.team2Score else t2["_id"]
    match_doc = {
        "game": "League of Legends",
        "team1Id": t1["_id"],
        "team2Id": t2["_id"],
        "team1Name": t1["teamName"],
        "team2Name": t2["teamName"],
        "team1Score": req.team1Score,
        "team2Score": req.team2Score,
        "winnerTeamId": winner_id,
        "format": req.format,
        "date": date,
        "leagueId": league_oid,
        "leagueName": league_name,
        "orgId": org_oid,
        "seasonId": season_oid,
        "conferenceId": conf_oid,
        "orgAbbreviation": org_abbr,
        "seasonLabel": season_label,
        "conferenceName": conf_name,
        "players": {
            "team1": [p.model_dump() for p in req.lolTeam1Players],
            "team2": [p.model_dump() for p in req.lolTeam2Players],
        },
    }
    _dup = db["matches"].find_one({"$or": [
        {"team1Id": t1["_id"], "team2Id": t2["_id"], "date": date, "game": "League of Legends"},
        {"team1Id": t2["_id"], "team2Id": t1["_id"], "date": date, "game": "League of Legends"},
    ]})
    if _dup:
        raise HTTPException(409, f"[pre-check] Duplicate match found: {str(_dup.get('_id'))} date={date}")
    try:
        res = db["matches"].insert_one(match_doc)
    except DuplicateKeyError as e:
        raise HTTPException(409, f"[index] DuplicateKeyError: {str(e)}")

    pms_rows = []
    for side, players in (("team1", req.lolTeam1Players), ("team2", req.lolTeam2Players)):
        team_doc = t1 if side == "team1" else t2
        team_score = req.team1Score if side == "team1" else req.team2Score
        opp_score = req.team2Score if side == "team1" else req.team1Score
        for p in players:
            pms_rows.append({
                "matchId": res.inserted_id,
                "game": "League of Legends",
                "playerId": _oid(p.playerId),
                "teamId": team_doc["_id"],
                "teamName": team_doc["teamName"],
                "champion": p.champion,
                "role": p.role,
                "kills": p.kills,
                "deaths": p.deaths,
                "assists": p.assists,
                "cs": p.cs,
                "gold": p.gold,
                "damage": p.damage,
                "vision": p.vision,
                "wards": p.wards,
                "win": team_score > opp_score,
            })
    if pms_rows:
        db["player match stats"].insert_many(pms_rows)

    _apply_record_update(db, t1["_id"], winner_id == t1["_id"], req.team1Score, req.team2Score)
    _apply_record_update(db, t2["_id"], winner_id == t2["_id"], req.team2Score, req.team1Score)
    return {"ok": True, "matchId": str(res.inserted_id), "winnerTeamId": str(winner_id)}


# ---------- match edit / delete ----------

def _reverse_record_update(db, team_id: ObjectId, won: bool, map_wins: int, map_losses: int):
    """Undo a prior _apply_record_update."""
    inc = {
        "wins": -1 if won else 0,
        "losses": 0 if won else -1,
        "mapWins": -map_wins,
        "mapLosses": -map_losses,
    }
    db["teams"].update_one({"_id": team_id}, {"$inc": inc})


class MatchScorePatch(BaseModel):
    team1Score: int
    team2Score: int


@router.patch("/matches/{match_id}", dependencies=[Depends(require_admin)])
def update_match(match_id: str, req: MatchScorePatch):
    """Correct a mis-entered series score. Adjusts team W/L counters accordingly.

    Limited to series-level score edits (the common "wrong number on the scoreboard"
    case). Per-map / per-player edits still require a delete + re-insert.
    """
    db = _db()
    oid = _oid(match_id)
    match = db["matches"].find_one({"_id": oid})
    if not match:
        raise HTTPException(404, "Match not found")

    t1_id = match["team1Id"]
    t2_id = match["team2Id"]
    old_t1 = int(match.get("team1Score", 0))
    old_t2 = int(match.get("team2Score", 0))
    old_winner = match.get("winnerTeamId")

    # Reverse old deltas.
    _reverse_record_update(db, t1_id, old_winner == t1_id, old_t1, old_t2)
    _reverse_record_update(db, t2_id, old_winner == t2_id, old_t2, old_t1)

    # Apply new.
    if req.team1Score == req.team2Score:
        raise HTTPException(400, "Scores cannot be tied")
    new_winner = t1_id if req.team1Score > req.team2Score else t2_id
    db["matches"].update_one(
        {"_id": oid},
        {"$set": {
            "team1Score": req.team1Score,
            "team2Score": req.team2Score,
            "winnerTeamId": new_winner,
        }},
    )
    _apply_record_update(db, t1_id, new_winner == t1_id, req.team1Score, req.team2Score)
    _apply_record_update(db, t2_id, new_winner == t2_id, req.team2Score, req.team1Score)
    return {"ok": True, "matchId": str(oid), "winnerTeamId": str(new_winner)}


@router.delete("/matches/{match_id}", dependencies=[Depends(require_admin)])
def delete_match(match_id: str):
    """Hard-delete a match. Reverses team W/L and removes player stat rows."""
    db = _db()
    oid = _oid(match_id)
    match = db["matches"].find_one({"_id": oid})
    if not match:
        raise HTTPException(404, "Match not found")

    t1_id = match["team1Id"]
    t2_id = match["team2Id"]
    t1_score = int(match.get("team1Score", 0))
    t2_score = int(match.get("team2Score", 0))
    winner = match.get("winnerTeamId")

    _reverse_record_update(db, t1_id, winner == t1_id, t1_score, t2_score)
    _reverse_record_update(db, t2_id, winner == t2_id, t2_score, t1_score)

    removed = db["player match stats"].delete_many({"matchId": oid}).deleted_count
    db["matches"].delete_one({"_id": oid})
    return {"ok": True, "deletedStatRows": removed}


# ---------- admin dashboard stats ----------

@router.get("/stats", dependencies=[Depends(require_admin)])
def admin_stats():
    db = _db()
    recent = list(
        db["matches"]
        .find({}, {"maps": 0, "players": 0})
        .sort("date", -1)
        .limit(5)
    )
    return {
        "counts": {
            "matches": db["matches"].count_documents({}),
            "players": db["players"].count_documents({}),
            "teams": db["teams"].count_documents({}),
            "schools": db["schools"].count_documents({}),
            "organizations": db["organizations"].count_documents({}),
            "conferences": db["conferences"].count_documents({}),
        },
        "recent_matches": [_doc(r) for r in recent],
    }


# ====================================================================
# League hierarchy: organizations / seasons / conferences / memberships
# ====================================================================

GAME_LITERAL = Literal["Valorant", "League of Legends"]
SEMESTER_LITERAL = Literal["Fall", "Spring"]
CONF_KIND_LITERAL = Literal["regional", "division", "partner", "tier"]


# ---------- models ----------

class OrgCreate(BaseModel):
    name: str
    abbreviation: str
    games: list[GAME_LITERAL] = Field(default_factory=list)


class OrgUpdate(BaseModel):
    name: Optional[str] = None
    abbreviation: Optional[str] = None
    games: Optional[list[GAME_LITERAL]] = None


class SeasonCreate(BaseModel):
    orgId: str
    year: str  # "2025-2026"
    semester: SEMESTER_LITERAL
    active: bool = False


class SeasonUpdate(BaseModel):
    year: Optional[str] = None
    semester: Optional[SEMESTER_LITERAL] = None
    active: Optional[bool] = None


class ConferenceCreate(BaseModel):
    orgId: str
    name: str
    shortName: Optional[str] = None
    tier: Optional[str] = None
    kind: CONF_KIND_LITERAL = "regional"


class ConferenceUpdate(BaseModel):
    name: Optional[str] = None
    shortName: Optional[str] = None
    tier: Optional[str] = None
    kind: Optional[CONF_KIND_LITERAL] = None


class MembershipCreate(BaseModel):
    teamId: str
    conferenceId: str
    seasonId: str
    active: bool = True


class MembershipUpdate(BaseModel):
    active: bool


# ---------- organizations ----------

@router.get("/orgs", dependencies=[Depends(require_admin)])
def list_orgs(q: str = Query("", max_length=100), game: Optional[str] = None, limit: int = 50):
    db = _db()
    flt: dict[str, Any] = {}
    if q:
        flt["$or"] = [
            {"name": {"$regex": re.escape(q), "$options": "i"}},
            {"abbreviation": {"$regex": re.escape(q), "$options": "i"}},
        ]
    if game:
        flt["games"] = game
    rows = list(db["organizations"].find(flt).sort("abbreviation", 1).limit(limit))
    return [_doc(r) for r in rows]


@router.post("/orgs", dependencies=[Depends(require_admin)])
def create_org(req: OrgCreate):
    db = _db()
    name = req.name.strip()
    abbr = req.abbreviation.strip().upper()
    if not name or not abbr:
        raise HTTPException(400, "name and abbreviation required")
    slug = _slugify(abbr)
    existing = db["organizations"].find_one({"slug": slug})
    if existing:
        return _doc(existing)
    doc = {
        "name": name,
        "abbreviation": abbr,
        "slug": slug,
        "games": req.games,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    res = db["organizations"].insert_one(doc)
    doc["_id"] = res.inserted_id
    return _doc(doc)


@router.patch("/orgs/{org_id}", dependencies=[Depends(require_admin)])
def update_org(org_id: str, req: OrgUpdate):
    db = _db()
    oid = _oid(org_id)
    update: dict[str, Any] = {}
    if req.name is not None:
        update["name"] = req.name.strip()
    if req.abbreviation is not None:
        abbr = req.abbreviation.strip().upper()
        update["abbreviation"] = abbr
        update["slug"] = _slugify(abbr)
    if req.games is not None:
        update["games"] = req.games
    if update:
        db["organizations"].update_one({"_id": oid}, {"$set": update})
    return _doc(db["organizations"].find_one({"_id": oid}) or {})


@router.delete("/orgs/{org_id}", dependencies=[Depends(require_admin)])
def delete_org(org_id: str):
    """Cascading delete: removes seasons, conferences, and memberships for this org."""
    db = _db()
    oid = _oid(org_id)
    season_ids = [s["_id"] for s in db["seasons"].find({"orgId": oid}, {"_id": 1})]
    conf_ids = [c["_id"] for c in db["conferences"].find({"orgId": oid}, {"_id": 1})]
    db["team_memberships"].delete_many({
        "$or": [
            {"seasonId": {"$in": season_ids}},
            {"conferenceId": {"$in": conf_ids}},
        ]
    })
    db["seasons"].delete_many({"orgId": oid})
    db["conferences"].delete_many({"orgId": oid})
    db["organizations"].delete_one({"_id": oid})
    return {"ok": True}


# ---------- seasons ----------

def _season_label(org_abbr: str, semester: str, year: str) -> str:
    # year "2025-2026" — pick first year for Fall, second for Spring
    years = year.split("-")
    shown = years[0] if semester == "Fall" else (years[1] if len(years) > 1 else years[0])
    return f"{org_abbr} {semester} {shown}"


@router.get("/seasons", dependencies=[Depends(require_admin)])
def list_seasons(orgId: Optional[str] = None, active: Optional[bool] = None, limit: int = 100):
    db = _db()
    flt: dict[str, Any] = {}
    if orgId:
        flt["orgId"] = _oid(orgId)
    if active is not None:
        flt["active"] = active
    rows = list(db["seasons"].find(flt).sort([("year", -1), ("semester", 1)]).limit(limit))
    return [_doc(r) for r in rows]


@router.post("/seasons", dependencies=[Depends(require_admin)])
def create_season(req: SeasonCreate):
    db = _db()
    org = db["organizations"].find_one({"_id": _oid(req.orgId)})
    if not org:
        raise HTTPException(404, "Organization not found")
    year = req.year.strip()
    if not re.match(r"^\d{4}-\d{4}$", year):
        raise HTTPException(400, "year must be like 2025-2026")
    existing = db["seasons"].find_one({
        "orgId": org["_id"], "year": year, "semester": req.semester,
    })
    if existing:
        return _doc(existing)
    label = _season_label(org["abbreviation"], req.semester, year)
    doc = {
        "orgId": org["_id"],
        "year": year,
        "semester": req.semester,
        "label": label,
        "active": req.active,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    if req.active:
        # only one active season per org
        db["seasons"].update_many({"orgId": org["_id"]}, {"$set": {"active": False}})
    try:
        res = db["seasons"].insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(409, "Season already exists")
    doc["_id"] = res.inserted_id
    return _doc(doc)


@router.patch("/seasons/{season_id}", dependencies=[Depends(require_admin)])
def update_season(season_id: str, req: SeasonUpdate):
    db = _db()
    oid = _oid(season_id)
    season = db["seasons"].find_one({"_id": oid})
    if not season:
        raise HTTPException(404, "Season not found")
    update: dict[str, Any] = {}
    if req.year is not None:
        if not re.match(r"^\d{4}-\d{4}$", req.year):
            raise HTTPException(400, "year must be like 2025-2026")
        update["year"] = req.year
    if req.semester is not None:
        update["semester"] = req.semester
    if req.active is True:
        db["seasons"].update_many(
            {"orgId": season["orgId"], "_id": {"$ne": oid}},
            {"$set": {"active": False}},
        )
        update["active"] = True
    elif req.active is False:
        update["active"] = False
    # rebuild label if year/semester changed
    if "year" in update or "semester" in update:
        org = db["organizations"].find_one({"_id": season["orgId"]})
        if org:
            update["label"] = _season_label(
                org["abbreviation"],
                update.get("semester", season["semester"]),
                update.get("year", season["year"]),
            )
    if update:
        db["seasons"].update_one({"_id": oid}, {"$set": update})
    return _doc(db["seasons"].find_one({"_id": oid}) or {})


@router.delete("/seasons/{season_id}", dependencies=[Depends(require_admin)])
def delete_season(season_id: str):
    db = _db()
    oid = _oid(season_id)
    db["team_memberships"].delete_many({"seasonId": oid})
    db["seasons"].delete_one({"_id": oid})
    return {"ok": True}


# ---------- conferences ----------

@router.get("/conferences", dependencies=[Depends(require_admin)])
def list_conferences(
    orgId: Optional[str] = None,
    q: str = Query("", max_length=100),
    limit: int = 100,
):
    db = _db()
    flt: dict[str, Any] = {}
    if orgId:
        flt["orgId"] = _oid(orgId)
    if q:
        flt["name"] = {"$regex": re.escape(q), "$options": "i"}
    rows = list(db["conferences"].find(flt).sort([("tier", 1), ("name", 1)]).limit(limit))
    return [_doc(r) for r in rows]


@router.post("/conferences", dependencies=[Depends(require_admin)])
def create_conference(req: ConferenceCreate):
    db = _db()
    org = db["organizations"].find_one({"_id": _oid(req.orgId)})
    if not org:
        raise HTTPException(404, "Organization not found")
    name = req.name.strip()
    if not name:
        raise HTTPException(400, "name required")
    slug = _slugify(f"{req.tier or ''} {name}".strip())
    existing = db["conferences"].find_one({"orgId": org["_id"], "slug": slug})
    if existing:
        return _doc(existing)
    doc = {
        "orgId": org["_id"],
        "name": name,
        "shortName": (req.shortName or name).strip(),
        "slug": slug,
        "tier": (req.tier or "").strip() or None,
        "kind": req.kind,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    res = db["conferences"].insert_one(doc)
    doc["_id"] = res.inserted_id
    return _doc(doc)


@router.patch("/conferences/{conf_id}", dependencies=[Depends(require_admin)])
def update_conference(conf_id: str, req: ConferenceUpdate):
    db = _db()
    oid = _oid(conf_id)
    conf = db["conferences"].find_one({"_id": oid})
    if not conf:
        raise HTTPException(404, "Conference not found")
    update: dict[str, Any] = {}
    if req.name is not None:
        update["name"] = req.name.strip()
    if req.shortName is not None:
        update["shortName"] = req.shortName.strip()
    if req.tier is not None:
        update["tier"] = req.tier.strip() or None
    if req.kind is not None:
        update["kind"] = req.kind
    # rebuild slug if name or tier changed
    if "name" in update or "tier" in update:
        new_name = update.get("name", conf["name"])
        new_tier = update.get("tier", conf.get("tier"))
        update["slug"] = _slugify(f"{new_tier or ''} {new_name}".strip())
    if update:
        db["conferences"].update_one({"_id": oid}, {"$set": update})
    return _doc(db["conferences"].find_one({"_id": oid}) or {})


@router.delete("/conferences/{conf_id}", dependencies=[Depends(require_admin)])
def delete_conference(conf_id: str):
    db = _db()
    oid = _oid(conf_id)
    db["team_memberships"].delete_many({"conferenceId": oid})
    db["conferences"].delete_one({"_id": oid})
    return {"ok": True}


# ---------- team memberships ----------

@router.get("/memberships", dependencies=[Depends(require_admin)])
def list_memberships(
    teamId: Optional[str] = None,
    conferenceId: Optional[str] = None,
    seasonId: Optional[str] = None,
    active: Optional[bool] = None,
    limit: int = 200,
):
    """List memberships, denormalizing org/season/conference names for UI display."""
    db = _db()
    flt: dict[str, Any] = {}
    if teamId:
        flt["teamId"] = _oid(teamId)
    if conferenceId:
        flt["conferenceId"] = _oid(conferenceId)
    if seasonId:
        flt["seasonId"] = _oid(seasonId)
    if active is not None:
        flt["active"] = active
    rows = list(db["team_memberships"].find(flt).limit(limit))

    # Fetch referenced seasons/conferences in bulk for labels.
    season_ids = list({r["seasonId"] for r in rows})
    conf_ids = list({r["conferenceId"] for r in rows})
    team_ids = list({r["teamId"] for r in rows})
    seasons = {s["_id"]: s for s in db["seasons"].find({"_id": {"$in": season_ids}})}
    confs = {c["_id"]: c for c in db["conferences"].find({"_id": {"$in": conf_ids}})}
    teams = {t["_id"]: t for t in db["teams"].find({"_id": {"$in": team_ids}})}
    org_ids = list({c.get("orgId") for c in confs.values() if c.get("orgId")})
    orgs = {o["_id"]: o for o in db["organizations"].find({"_id": {"$in": org_ids}})}

    out = []
    for r in rows:
        d = _doc(r)
        s = seasons.get(r["seasonId"])
        c = confs.get(r["conferenceId"])
        t = teams.get(r["teamId"])
        org = orgs.get(c.get("orgId")) if c else None
        d["seasonLabel"] = s.get("label") if s else None
        d["conferenceName"] = c.get("name") if c else None
        d["conferenceTier"] = c.get("tier") if c else None
        d["orgAbbreviation"] = org.get("abbreviation") if org else None
        d["teamName"] = t.get("teamName") if t else None
        out.append(d)
    return out


@router.post("/memberships", dependencies=[Depends(require_admin)])
def create_membership(req: MembershipCreate):
    db = _db()
    team = db["teams"].find_one({"_id": _oid(req.teamId)})
    conf = db["conferences"].find_one({"_id": _oid(req.conferenceId)})
    season = db["seasons"].find_one({"_id": _oid(req.seasonId)})
    if not team or not conf or not season:
        raise HTTPException(404, "team / conference / season not found")
    if conf["orgId"] != season["orgId"]:
        raise HTTPException(400, "conference and season must belong to the same org")
    doc = {
        "teamId": team["_id"],
        "conferenceId": conf["_id"],
        "seasonId": season["_id"],
        "active": req.active,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    try:
        res = db["team_memberships"].insert_one(doc)
    except DuplicateKeyError:
        existing = db["team_memberships"].find_one({
            "teamId": team["_id"],
            "conferenceId": conf["_id"],
            "seasonId": season["_id"],
        })
        return _doc(existing or {})
    doc["_id"] = res.inserted_id
    return _doc(doc)


@router.patch("/memberships/{membership_id}", dependencies=[Depends(require_admin)])
def update_membership(membership_id: str, req: MembershipUpdate):
    db = _db()
    oid = _oid(membership_id)
    db["team_memberships"].update_one({"_id": oid}, {"$set": {"active": req.active}})
    return _doc(db["team_memberships"].find_one({"_id": oid}) or {})


@router.delete("/memberships/{membership_id}", dependencies=[Depends(require_admin)])
def delete_membership(membership_id: str):
    db = _db()
    db["team_memberships"].delete_one({"_id": _oid(membership_id)})
    return {"ok": True}


# ---------- hierarchy tree (for /admin/leagues UI) ----------

@router.get("/leagues-tree", dependencies=[Depends(require_admin)])
def leagues_tree():
    """Return orgs with their seasons and conferences nested for the management UI."""
    db = _db()
    orgs = list(db["organizations"].find({}).sort("abbreviation", 1))
    out = []
    for o in orgs:
        seasons = list(
            db["seasons"].find({"orgId": o["_id"]}).sort([("year", -1), ("semester", 1)])
        )
        confs = list(
            db["conferences"].find({"orgId": o["_id"]}).sort([("tier", 1), ("name", 1)])
        )
        out.append({
            **_doc(o),
            "seasons": [_doc(s) for s in seasons],
            "conferences": [_doc(c) for c in confs],
        })
    return out
