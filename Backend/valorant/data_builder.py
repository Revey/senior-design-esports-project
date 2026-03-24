"""
Builds the ValorantTeamPayload that the frontend expects by combining
data from the Riot API and tracker.gg scraping.

Usage:
    from valorant.data_builder import build_team_payload
    payload = build_team_payload(team_config)
"""

import logging
from typing import Any

from . import riot_api, tracker_scraper
from .models import (
    ValorantTeamPayload,
    TeamStats,
    PlayerStats,
    MapInfo,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Team config schema (loaded from a JSON roster file or passed directly)
# ---------------------------------------------------------------------------
# {
#   "teamName": "CSU Vikes Green",
#   "season": "Spring 2026",
#   "players": [
#     {
#       "name": "VIKES wyyu",
#       "gameName": "wyyu",
#       "tagLine": "NA1",
#       "role": "Duelist"
#     },
#     ...
#   ],
#   "matchIds": ["optional", "list", "of", "match-ids"]   // for offline/cached builds
# }


def _safe_float(val: Any, default: float = 0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _compute_team_aggregates(player_stats_list: list[dict]) -> dict:
    """Average per-player stats across the roster."""
    if not player_stats_list:
        return {}

    n = len(player_stats_list)
    return {
        "averageTeamACS": round(sum(_safe_float(p.get("ACS")) for p in player_stats_list) / n, 1),
        "averageTeamKD": round(sum(_safe_float(p.get("KD")) for p in player_stats_list) / n, 2),
        "averageHSPercent": round(sum(_safe_float(p.get("HSPercent")) for p in player_stats_list) / n, 1),
    }


def _compute_map_pool(match_summaries: list) -> tuple[dict, str, str]:
    """
    Derive map pool stats from a list of MatchSummary objects.
    Returns (map_pool dict, best_map str, worst_map str).
    """
    map_wins: dict[str, int] = {}
    map_total: dict[str, int] = {}

    for match in match_summaries:
        map_id = match.mapId.split("/")[-1].replace("_", " ").title()
        map_total[map_id] = map_total.get(map_id, 0) + 1
        if match.winningTeam:
            map_wins[map_id] = map_wins.get(map_id, 0) + 1

    if not map_total:
        return {}, "Unknown", "Unknown"

    pool: dict[str, MapInfo] = {}
    for m, total in map_total.items():
        wins = map_wins.get(m, 0)
        losses = total - wins
        win_rate = round((wins / total) * 100, 1)
        pool[m] = MapInfo(record=f"{wins}-{losses}", winRate=win_rate)

    sorted_maps = sorted(pool.items(), key=lambda x: x[1].winRate, reverse=True)
    best = sorted_maps[0][0] if sorted_maps else "Unknown"
    worst = sorted_maps[-1][0] if sorted_maps else "Unknown"

    return {k: v for k, v in pool.items()}, best, worst


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

def build_team_payload(
    team_config: dict,
    use_riot_api: bool = True,
    use_scraper: bool = True,
    num_matches: int = 20,
) -> ValorantTeamPayload:
    """
    Build a full ValorantTeamPayload for a team.

    Strategy:
      1. For each player, fetch stats from the Riot API (match history → aggregates).
      2. Fill any missing stats with tracker.gg scraping.
      3. Build team aggregates from per-player stats.
      4. Build map pool from match summaries (requires PUUID).

    Args:
        team_config:   Dict matching the team config schema above.
        use_riot_api:  Whether to hit the Riot API.
        use_scraper:   Whether to fall back to tracker.gg scraping.
        num_matches:   How many recent matches to analyse per player.
    """
    team_name = team_config.get("teamName", "Unknown Team")
    season = team_config.get("season", "Unknown Season")
    roster = team_config.get("players", [])

    player_stats_list: list[dict] = []
    all_match_summaries: list = []

    for player in roster:
        logger.info("Processing player: %s", player.get("name"))
        stats: dict = {
            "name": player.get("name", ""),
            "role": player.get("role", "Unknown"),
            "KD": 0.0,
            "ACS": 0.0,
            "HSPercent": 0.0,
            "ADR": 0.0,
            "damageDelta": "N/A",
        }

        # --- Riot API ---
        if use_riot_api:
            try:
                profile = riot_api.get_account_by_riot_id(
                    player["gameName"], player["tagLine"]
                )
                api_stats = riot_api.aggregate_player_stats(profile.puuid, num_matches)
                stats.update({k: v for k, v in api_stats.items() if k in stats})

                # Collect match summaries for map pool computation
                match_refs = riot_api.get_match_list(profile.puuid, size=num_matches)
                for ref in match_refs[:5]:  # limit to 5 per player to avoid too many API calls
                    try:
                        summary = riot_api.get_match(ref.matchId)
                        all_match_summaries.append(summary)
                    except Exception:
                        pass

            except Exception as exc:
                logger.warning("Riot API failed for %s: %s", player.get("name"), exc)

        # --- Tracker.gg scraper (fill gaps) ---
        if use_scraper and (stats["KD"] == 0.0 or stats["ACS"] == 0.0):
            try:
                scraped = tracker_scraper.scrape_player_overview(
                    player["gameName"], player["tagLine"]
                )
                for key in ("KD", "ACS", "HSPercent", "ADR", "damageDelta"):
                    if key in scraped and (stats.get(key) in (0.0, "N/A")):
                        stats[key] = scraped[key]
            except Exception as exc:
                logger.warning("Scraper failed for %s: %s", player.get("name"), exc)

        player_stats_list.append(stats)

    # --- Team aggregates ---
    team_agg = _compute_team_aggregates(player_stats_list)
    map_pool, best_map, worst_map = _compute_map_pool(all_match_summaries)

    # Placeholder values for stats not derivable from match data alone
    # (win/loss record must come from league data or manual input)
    overall_record = team_config.get("overallRecord", "0-0")
    wins_s, losses_s = overall_record.split("-") if "-" in overall_record else ("0", "0")
    total_games = int(wins_s) + int(losses_s)
    win_rate = round(int(wins_s) / max(total_games, 1) * 100, 1)

    team_stats = TeamStats(
        name=team_name,
        game="Valorant",
        season=season,
        overallRecord=overall_record,
        winRate=win_rate,
        roundWinRate=team_config.get("roundWinRate", 0.0),
        pistolRoundWinRate=team_config.get("pistolRoundWinRate", 0.0),
        attackWinRate=team_config.get("attackWinRate", 0.0),
        defenseWinRate=team_config.get("defenseWinRate", 0.0),
        averageTeamACS=team_agg.get("averageTeamACS", 0.0),
        averageTeamKD=team_agg.get("averageTeamKD", 0.0),
        averageHSPercent=team_agg.get("averageHSPercent", 0.0),
        averageDamageDelta=team_config.get("averageDamageDelta", "N/A"),
        bestMap=best_map if best_map != "Unknown" else team_config.get("bestMap", "Unknown"),
        worstMap=worst_map if worst_map != "Unknown" else team_config.get("worstMap", "Unknown"),
        mapPool=map_pool if map_pool else {},
    )

    players = [PlayerStats(**p) for p in player_stats_list]

    return ValorantTeamPayload(team=team_stats, players=players)
