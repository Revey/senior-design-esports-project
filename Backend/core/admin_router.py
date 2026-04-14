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


class MatchCreate(BaseModel):
    game: Literal["Valorant", "League of Legends"]
    team1Id: str
    team2Id: str
    date: Optional[str] = None
    format: Literal["BO1", "BO3", "BO5"] = "BO1"
    leagueId: Optional[str] = None
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
):
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
    rows = list(db["players"].find(flt).limit(limit))
    return [_doc(r) for r in rows]


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

    # Resolve league reference if provided
    league_oid: Optional[ObjectId] = None
    league_name: Optional[str] = None
    if req.leagueId:
        league_doc = _db()["leagues"].find_one({"_id": _oid(req.leagueId)})
        if league_doc:
            league_oid = league_doc["_id"]
            league_name = league_doc.get("abbreviation") or league_doc.get("name")

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
            "maps": [m.model_dump() for m in req.maps],
        }
        res = db["matches"].insert_one(match_doc)

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
        "players": {
            "team1": [p.model_dump() for p in req.lolTeam1Players],
            "team2": [p.model_dump() for p in req.lolTeam2Players],
        },
    }
    res = db["matches"].insert_one(match_doc)

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
