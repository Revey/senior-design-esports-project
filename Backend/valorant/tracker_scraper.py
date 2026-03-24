"""
Tracker.gg scraper for Valorant player stats.

Used as a fallback / supplement when the Riot API doesn't expose a stat
(e.g. damage delta) or when a player hasn't authorized third-party access.

Tracker.gg URL pattern:
  https://tracker.gg/valorant/profile/riot/{name}%23{tag}/overview

IMPORTANT: Respect tracker.gg's Terms of Service. Use rate limiting and only
scrape data you have a legitimate reason to access. The SCRAPE_DELAY config
value enforces a pause between requests.
"""

import logging
import time
import urllib.parse
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .config import TRACKER_BASE_URL, SCRAPE_DELAY

logger = logging.getLogger(__name__)

_SESSION = requests.Session()
_SESSION.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_profile_url(game_name: str, tag_line: str) -> str:
    riot_id = f"{game_name}#{tag_line}"
    encoded = urllib.parse.quote(riot_id, safe="")
    return f"{TRACKER_BASE_URL}/{encoded}/overview"


def _fetch_page(url: str) -> Optional[BeautifulSoup]:
    """Fetch a tracker.gg page and return a BeautifulSoup object, or None on failure."""
    time.sleep(SCRAPE_DELAY)
    try:
        resp = _SESSION.get(url, timeout=15)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except requests.exceptions.RequestException as exc:
        logger.error("Scrape failed for %s: %s", url, exc)
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def scrape_player_overview(game_name: str, tag_line: str) -> dict:
    """
    Scrape the overview page on tracker.gg for a Valorant player.

    Returns a dict with stat keys matching the frontend PlayerStats model.
    Falls back to empty dict if the page can't be parsed.
    """
    url = _build_profile_url(game_name, tag_line)
    logger.info("Scraping tracker.gg: %s", url)
    soup = _fetch_page(url)
    if soup is None:
        return {}

    stats: dict = {}

    # tracker.gg renders stats inside elements with class "stat" or "value"
    # Structure may change; key stat blocks have a <span class="name"> label
    # and a <span class="value"> / <div class="value"> for the number.
    stat_blocks = soup.select("div.stat")
    for block in stat_blocks:
        label_el = block.select_one("span.name, div.name, .stat__name")
        value_el = block.select_one("span.value, div.value, .stat__value")
        if not label_el or not value_el:
            continue

        label = label_el.get_text(strip=True).lower()
        value_text = value_el.get_text(strip=True).replace(",", "")

        try:
            if "k/d" in label or "kd" in label:
                stats["KD"] = float(value_text)
            elif "acs" in label or "combat score" in label:
                stats["ACS"] = float(value_text)
            elif "headshot" in label:
                # Stored as "24.6%" — strip the %
                stats["HSPercent"] = float(value_text.replace("%", ""))
            elif "damage" in label and "delta" not in label:
                stats["ADR"] = float(value_text)
            elif "damage delta" in label or "dd" == label:
                # Stored as "+8.3" or "-3.2"
                stats["damageDelta"] = value_text
            elif "win" in label and "%" in value_text:
                stats["winRate"] = float(value_text.replace("%", ""))
        except ValueError:
            pass

    if not stats:
        logger.warning("No stats parsed from tracker.gg for %s#%s — page structure may have changed.", game_name, tag_line)

    return stats


def scrape_team_overview(roster: list[dict]) -> list[dict]:
    """
    Scrape overview stats for a list of players.

    Args:
        roster: List of dicts with keys "name", "gameName", "tagLine", "role".

    Returns:
        List of dicts ready to be used as PlayerStats objects.
    """
    results = []
    for player in roster:
        game_name = player.get("gameName", "")
        tag_line = player.get("tagLine", "")
        if not game_name or not tag_line:
            logger.warning("Skipping player with missing Riot ID: %s", player)
            continue

        scraped = scrape_player_overview(game_name, tag_line)

        results.append(
            {
                "name": player.get("name", f"{game_name}#{tag_line}"),
                "role": player.get("role", "Unknown"),
                "KD": scraped.get("KD", 0.0),
                "ACS": scraped.get("ACS", 0.0),
                "HSPercent": scraped.get("HSPercent", 0.0),
                "ADR": scraped.get("ADR", 0.0),
                "damageDelta": scraped.get("damageDelta", "N/A"),
            }
        )
    return results


def scrape_match_history(game_name: str, tag_line: str) -> list[dict]:
    """
    Scrape recent match history from tracker.gg.

    Returns a list of match result dicts with basic info.
    """
    url = _build_profile_url(game_name, tag_line)
    soup = _fetch_page(url)
    if soup is None:
        return []

    matches = []
    match_rows = soup.select("div.match, article.match, .matches__match")
    for row in match_rows:
        match_data: dict = {}

        map_el = row.select_one(".map, .match__map, [data-map]")
        if map_el:
            match_data["map"] = map_el.get_text(strip=True)

        result_el = row.select_one(".result, .match__result, .won, .lost")
        if result_el:
            match_data["result"] = result_el.get_text(strip=True)

        score_el = row.select_one(".score, .match__score")
        if score_el:
            match_data["score"] = score_el.get_text(strip=True)

        if match_data:
            matches.append(match_data)

    return matches
