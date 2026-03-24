"""
Riot Games API client for Valorant.

Endpoints used:
  Account-v1  – /riot/account/v1/accounts/by-riot-id/{gameName}/{tagLine}
  Val-Match-v1 – /val/match/v1/matchlists/by-puuid/{puuid}
               – /val/match/v1/matches/{matchId}
  Val-Content-v1 – /val/content/v1/contents  (agents, maps, acts)
  Val-Ranked-v1  – /val/ranked/v1/leaderboards/by-act/{actId}

Docs: https://developer.riotgames.com/apis
"""

import time
import logging
from typing import Any, Optional

import requests

from .config import (
    RIOT_API_KEY,
    RIOT_ACCOUNT_BASE,
    RIOT_VAL_BASE,
    RIOT_REGION,
)
from .models import (
    PlayerProfile,
    MatchReference,
    MatchSummary,
    MatchPlayerStats,
    RoundResult,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_HEADERS = {"X-Riot-Token": RIOT_API_KEY}


def _get(url: str, params: Optional[dict] = None, retries: int = 3) -> Any:
    """Thin wrapper around requests.get with basic retry logic."""
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=_HEADERS, params=params, timeout=10)
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 5))
                logger.warning("Rate-limited by Riot API. Waiting %ss…", retry_after)
                time.sleep(retry_after)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as exc:
            logger.error("Riot API request failed (attempt %d/%d): %s", attempt + 1, retries, exc)
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Riot API request failed after {retries} attempts: {url}")


# ---------------------------------------------------------------------------
# Account API
# ---------------------------------------------------------------------------

def get_account_by_riot_id(game_name: str, tag_line: str) -> PlayerProfile:
    """
    Look up a player's PUUID and region from their Riot ID.

    Args:
        game_name: The in-game name (before the #).
        tag_line:  The tag (after the #).

    Returns:
        PlayerProfile with puuid, gameName, tagLine.
    """
    url = f"{RIOT_ACCOUNT_BASE}/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
    data = _get(url)
    return PlayerProfile(
        gameName=data["gameName"],
        tagLine=data["tagLine"],
        puuid=data["puuid"],
        region=RIOT_REGION,
    )


def get_account_by_puuid(puuid: str) -> PlayerProfile:
    url = f"{RIOT_ACCOUNT_BASE}/riot/account/v1/accounts/by-puuid/{puuid}"
    data = _get(url)
    return PlayerProfile(
        gameName=data["gameName"],
        tagLine=data["tagLine"],
        puuid=data["puuid"],
        region=RIOT_REGION,
    )


# ---------------------------------------------------------------------------
# Match API
# ---------------------------------------------------------------------------

def get_match_list(puuid: str, size: int = 20) -> list[MatchReference]:
    """
    Fetch the most recent matches for a player.

    Args:
        puuid: Player's PUUID.
        size:  Number of matches to return (max 20 per Riot API).
    """
    url = f"{RIOT_VAL_BASE}/val/match/v1/matchlists/by-puuid/{puuid}"
    data = _get(url)
    history = data.get("history", [])[:size]
    return [
        MatchReference(
            matchId=m["matchId"],
            gameStartTimeMillis=m.get("gameStartTimeMillis"),
            teamId=m.get("teamId"),
        )
        for m in history
    ]


def get_match(match_id: str) -> MatchSummary:
    """
    Fetch full match details and parse into a MatchSummary.
    """
    url = f"{RIOT_VAL_BASE}/val/match/v1/matches/{match_id}"
    data = _get(url)

    match_info = data["matchInfo"]
    teams = {t["teamId"]: t for t in data.get("teams", [])}

    # Determine winning team
    winning_team = next(
        (tid for tid, t in teams.items() if t.get("won")),
        "Unknown",
    )

    # Parse round results
    rounds = [
        RoundResult(
            roundNum=r["roundNum"],
            roundResult=r.get("roundResult", ""),
            winningTeam=r.get("winningTeam", ""),
            bombPlanted=r.get("bombPlanted", False),
            bombDefused=r.get("bombDefused", False),
        )
        for r in data.get("roundResults", [])
    ]

    # Parse player stats
    players = []
    for p in data.get("players", []):
        stats = p.get("stats", {})
        players.append(
            MatchPlayerStats(
                puuid=p["puuid"],
                gameName=p.get("gameName", ""),
                tagLine=p.get("tagLine", ""),
                teamId=p.get("teamId", ""),
                characterId=p.get("characterId", ""),
                kills=stats.get("kills", 0),
                deaths=stats.get("deaths", 0),
                assists=stats.get("assists", 0),
                score=stats.get("score", 0),
                headshots=stats.get("headshots", 0),
                bodyshots=stats.get("bodyshots", 0),
                legshots=stats.get("legshots", 0),
                damage=sum(d.get("damage", 0) for d in p.get("damage", [])),
                roundsPlayed=stats.get("roundsPlayed", 1),
            )
        )

    return MatchSummary(
        matchId=match_info["matchId"],
        mapId=match_info.get("mapId", ""),
        gameStartTimeMillis=match_info.get("gameStartTimeMillis", 0),
        gameLengthMillis=match_info.get("gameLengthMillis", 0),
        winningTeam=winning_team,
        rounds=rounds,
        players=players,
    )


# ---------------------------------------------------------------------------
# Content API (maps, agents, acts)
# ---------------------------------------------------------------------------

def get_content(locale: str = "en-US") -> dict:
    """Fetch all game content (agents, maps, acts, game modes)."""
    url = f"{RIOT_VAL_BASE}/val/content/v1/contents"
    return _get(url, params={"locale": locale})


def get_acts() -> list[dict]:
    content = get_content()
    return [a for a in content.get("acts", []) if a.get("isActive") is not None]


def get_current_act() -> Optional[dict]:
    acts = get_acts()
    active = [a for a in acts if a.get("isActive")]
    return active[0] if active else None


# ---------------------------------------------------------------------------
# Ranked / Leaderboard API
# ---------------------------------------------------------------------------

def get_leaderboard(act_id: str, size: int = 200, start_index: int = 0) -> list[dict]:
    """
    Fetch the competitive leaderboard for a given act.

    Args:
        act_id:      UUID of the competitive act.
        size:        Number of entries (max 200 per request).
        start_index: Pagination offset.
    """
    url = f"{RIOT_VAL_BASE}/val/ranked/v1/leaderboards/by-act/{act_id}"
    data = _get(url, params={"size": size, "startIndex": start_index})
    return data.get("players", [])


# ---------------------------------------------------------------------------
# Aggregate helpers
# ---------------------------------------------------------------------------

def aggregate_player_stats(puuid: str, num_matches: int = 20) -> dict:
    """
    Pull recent matches for a player and compute aggregate stats.

    Returns a dict compatible with the PlayerStats model.
    """
    match_refs = get_match_list(puuid, size=num_matches)
    if not match_refs:
        return {}

    totals = {
        "kills": 0, "deaths": 0, "assists": 0,
        "score": 0, "headshots": 0, "bodyshots": 0,
        "legshots": 0, "damage": 0, "rounds": 0,
        "matches": 0,
    }

    for ref in match_refs:
        try:
            match = get_match(ref.matchId)
        except Exception as exc:
            logger.warning("Skipping match %s: %s", ref.matchId, exc)
            continue

        player_data = next((p for p in match.players if p.puuid == puuid), None)
        if not player_data:
            continue

        totals["kills"]      += player_data.kills
        totals["deaths"]     += player_data.deaths
        totals["assists"]    += player_data.assists
        totals["score"]      += player_data.score
        totals["headshots"]  += player_data.headshots
        totals["bodyshots"]  += player_data.bodyshots
        totals["legshots"]   += player_data.legshots
        totals["damage"]     += player_data.damage
        totals["rounds"]     += player_data.roundsPlayed
        totals["matches"]    += 1
        time.sleep(0.05)  # stay well within rate limits between match fetches

    if totals["matches"] == 0:
        return {}

    kd = round(totals["kills"] / max(totals["deaths"], 1), 2)
    acs = round(totals["score"] / max(totals["rounds"], 1), 1)
    total_shots = totals["headshots"] + totals["bodyshots"] + totals["legshots"]
    hs_pct = round((totals["headshots"] / max(total_shots, 1)) * 100, 1)
    adr = round(totals["damage"] / max(totals["rounds"], 1), 1)

    return {
        "KD": kd,
        "ACS": acs,
        "HSPercent": hs_pct,
        "ADR": adr,
        "matchesAnalyzed": totals["matches"],
    }
