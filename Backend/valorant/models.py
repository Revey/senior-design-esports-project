"""
Pydantic models for Valorant player/team data.
Shapes match the JSON consumed by the Next.js frontend.
"""

from typing import Optional
from pydantic import BaseModel


# ── Player ────────────────────────────────────────────────────────────────────

class PlayerStats(BaseModel):
    """Per-player stats displayed in the frontend player table."""
    name: str
    role: str
    KD: float
    ACS: float
    HSPercent: float
    ADR: float
    damageDelta: str


class PlayerProfile(BaseModel):
    """Extended player profile from Riot Account API."""
    gameName: str
    tagLine: str
    puuid: str
    region: Optional[str] = None


# ── Map pool ──────────────────────────────────────────────────────────────────

class MapInfo(BaseModel):
    record: str        # e.g. "6-1"
    winRate: float     # e.g. 85.7


# ── Team ──────────────────────────────────────────────────────────────────────

class TeamStats(BaseModel):
    """Team-level aggregate stats."""
    name: str
    game: str = "Valorant"
    season: str
    overallRecord: str
    winRate: float
    roundWinRate: float
    pistolRoundWinRate: float
    attackWinRate: float
    defenseWinRate: float
    averageTeamACS: float
    averageTeamKD: float
    averageHSPercent: float
    averageDamageDelta: str
    bestMap: str
    worstMap: str
    mapPool: dict[str, MapInfo]


class ValorantTeamPayload(BaseModel):
    """Full payload returned by /api/valorant/team/{team_id} — mirrors the frontend JSON shape."""
    team: TeamStats
    players: list[PlayerStats]


# ── Match (raw Riot API) ──────────────────────────────────────────────────────

class MatchReference(BaseModel):
    matchId: str
    gameStartTimeMillis: Optional[int] = None
    teamId: Optional[str] = None


class RoundResult(BaseModel):
    roundNum: int
    roundResult: str       # "Eliminated", "Bomb defused", "Bomb detonated", "Surrendered"
    winningTeam: str       # "Red" or "Blue"
    bombPlanted: bool
    bombDefused: bool


class MatchPlayerStats(BaseModel):
    """Relevant per-player data extracted from a Riot match response."""
    puuid: str
    gameName: str
    tagLine: str
    teamId: str
    characterId: str       # agent UUID
    kills: int
    deaths: int
    assists: int
    score: int             # combat score
    headshots: int
    bodyshots: int
    legshots: int
    damage: int
    roundsPlayed: int

    @property
    def kd(self) -> float:
        return round(self.kills / max(self.deaths, 1), 2)

    @property
    def acs(self) -> float:
        return round(self.score / max(self.roundsPlayed, 1), 1)

    @property
    def hs_percent(self) -> float:
        total_shots = self.headshots + self.bodyshots + self.legshots
        return round((self.headshots / max(total_shots, 1)) * 100, 1)

    @property
    def adr(self) -> float:
        return round(self.damage / max(self.roundsPlayed, 1), 1)


class MatchSummary(BaseModel):
    matchId: str
    mapId: str
    gameStartTimeMillis: int
    gameLengthMillis: int
    winningTeam: str
    rounds: list[RoundResult]
    players: list[MatchPlayerStats]
