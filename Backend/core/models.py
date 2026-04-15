"""Pydantic models for leagues, tournaments, teams, and players."""

from pydantic import BaseModel
from typing import Optional


class StandingEntry(BaseModel):
    rank: int
    team_name: str
    team_slug: str
    wins: int
    losses: int
    win_rate: float


class LeagueResponse(BaseModel):
    slug: str
    name: str
    abbreviation: str
    game: str
    season: str
    description: str
    standings: list[StandingEntry]
    # Conference the league belongs to (e.g., "NECC", "NACE", "Riot"). Optional
    # so legacy docs without the field still validate.
    conference: Optional[str] = None


class TournamentMatch(BaseModel):
    round: str
    team_a: str
    team_b: str
    score_a: Optional[int] = None
    score_b: Optional[int] = None
    status: str  # "completed", "upcoming", "live"


class TournamentResponse(BaseModel):
    slug: str
    name: str
    game: str
    format: str
    status: str
    start_date: str
    end_date: str
    teams: list[str]
    matches: list[TournamentMatch]


class TeamRecord(BaseModel):
    wins: int
    losses: int


class TeamResponse(BaseModel):
    slug: str
    name: str
    school: str
    game: str
    record: TeamRecord
    win_rate: float
    rating: int
    region: str
    league_slug: str


class PlayerStats(BaseModel):
    kd: Optional[float] = None
    acs: Optional[float] = None
    adr: Optional[float] = None
    hs_percent: Optional[float] = None
    kda: Optional[float] = None
    kills_per_game: Optional[float] = None
    deaths_per_game: Optional[float] = None
    assists_per_game: Optional[float] = None


class PlayerResponse(BaseModel):
    slug: str
    name: str
    team_name: str
    team_slug: str
    game: str
    role: str
    stats: PlayerStats
    rating: int
