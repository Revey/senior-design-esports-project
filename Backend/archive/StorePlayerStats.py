"""
StorePlayerStats.py
-------------------
For each player in necc_val_teams_puuids.json, scrapes tracker.gg for
Valorant stats (KD, ACS, HS%, ADR) and merges the aggregate stats into
`players.stats` (JSONB) in Postgres, keyed on riot_puuid.

Mirrors the structure of League/StoreScrapePlayerStats.py.

Run from the Backend/ directory:
    python archive/StorePlayerStats.py
"""

import json
import os
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.db import get_cursor  # noqa: E402

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────

SCRIPT_DIR       = Path(__file__).resolve().parent
JSON_SOURCE_PATH = SCRIPT_DIR / "necc_val_teams_puuids.json"

RIOT_API_KEY        = os.getenv("RIOT_API_KEY", "")
RIOT_ACCOUNT_REGION = os.getenv("RIOT_ACCOUNT_REGION", "americas")
RIOT_REGION         = os.getenv("RIOT_REGION", "na1")
RIOT_ACCOUNT_BASE   = f"https://{RIOT_ACCOUNT_REGION}.api.riotgames.com"
RIOT_VAL_BASE       = f"https://{RIOT_REGION}.api.riotgames.com"

TRACKER_BASE_URL  = "https://tracker.gg/valorant/profile/riot"
SCRAPE_DELAY      = float(os.getenv("SCRAPE_DELAY", "2.0"))
NUM_MATCHES       = 20   # matches to pull for Riot API aggregate stats

_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
})

_RIOT_HEADERS = {"X-Riot-Token": RIOT_API_KEY}


# ── tracker.gg scraping ───────────────────────────────────────────────────────

def _build_tracker_url(game_name: str, tag_line: str) -> str:
    riot_id = f"{game_name}#{tag_line}"
    encoded = urllib.parse.quote(riot_id, safe="")
    return f"{TRACKER_BASE_URL}/{encoded}/overview"


def scrape_tracker(game_name: str, tag_line: str) -> dict:
    """
    Scrape tracker.gg overview page for a Valorant player.
    Returns a dict with KD, ACS, HSPercent, ADR (or empty dict on failure).
    """
    time.sleep(SCRAPE_DELAY)
    url = _build_tracker_url(game_name, tag_line)

    try:
        resp = _SESSION.get(url, timeout=15)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"    tracker.gg request failed: {e}")
        return {}

    soup   = BeautifulSoup(resp.text, "html.parser")
    stats  = {}

    stat_blocks = soup.select("div.stat")
    for block in stat_blocks:
        label_el = block.select_one("span.name, div.name, .stat__name")
        value_el = block.select_one("span.value, div.value, .stat__value")
        if not label_el or not value_el:
            continue

        label      = label_el.get_text(strip=True).lower()
        value_text = value_el.get_text(strip=True).replace(",", "")

        try:
            if "k/d" in label or "kd" in label:
                stats["KD"] = float(value_text)
            elif "acs" in label or "combat score" in label:
                stats["ACS"] = float(value_text)
            elif "headshot" in label:
                stats["HSPercent"] = float(value_text.replace("%", ""))
            elif "damage" in label and "delta" not in label:
                stats["ADR"] = float(value_text)
            elif "damage delta" in label or label == "dd":
                stats["damageDelta"] = value_text
            elif "win" in label and "%" in value_text:
                stats["winRate"] = float(value_text.replace("%", ""))
        except ValueError:
            pass

    return stats


# ── Riot API stats ────────────────────────────────────────────────────────────

def riot_aggregate_stats(puuid: str) -> dict:
    """
    Fetch recent matches and compute aggregate KD, ACS, HS%, ADR.
    Returns an empty dict if the API call fails or no matches are found.
    """
    if not RIOT_API_KEY or not puuid:
        return {}

    try:
        # Fetch match list
        matches_url = f"{RIOT_VAL_BASE}/val/match/v1/matchlists/by-puuid/{puuid}"
        resp = requests.get(matches_url, headers=_RIOT_HEADERS, timeout=10)
        if resp.status_code == 429:
            print("    Riot API rate-limited (match list)")
            return {}
        resp.raise_for_status()
        match_ids = [m["matchId"] for m in resp.json().get("history", [])[:NUM_MATCHES]]
    except Exception as e:
        print(f"    Riot match list error: {e}")
        return {}

    if not match_ids:
        return {}

    kills = deaths = assists = combat_scores = hs_shots = total_shots = damage_rounds = 0
    rounds_played = 0

    for match_id in match_ids:
        try:
            match_url = f"{RIOT_VAL_BASE}/val/match/v1/matches/{match_id}"
            resp = requests.get(match_url, headers=_RIOT_HEADERS, timeout=10)
            if resp.status_code == 429:
                print("    Riot API rate-limited (match detail) — stopping")
                break
            resp.raise_for_status()
            match_data = resp.json()
        except Exception:
            continue

        num_rounds = len(match_data.get("roundResults", []))

        for player in match_data.get("players", []):
            if player.get("puuid") != puuid:
                continue
            stats = player.get("stats", {})
            kills          += stats.get("kills", 0)
            deaths         += stats.get("deaths", 0)
            assists        += stats.get("assists", 0)
            combat_scores  += stats.get("score", 0)
            hs_shots       += stats.get("headshots", 0)
            total_shots    += stats.get("headshots", 0) + stats.get("bodyshots", 0) + stats.get("legshots", 0)
            damage_rounds  += stats.get("damage", 0)
            rounds_played  += num_rounds

        time.sleep(0.3)

    if deaths == 0:
        return {}

    return {
        "KD":         round(kills / deaths, 2),
        "ACS":        round(combat_scores / max(rounds_played, 1), 1),
        "HSPercent":  round(hs_shots / max(total_shots, 1) * 100, 1),
        "ADR":        round(damage_rounds / max(rounds_played, 1), 1),
    }


# ── Postgres upsert ───────────────────────────────────────────────────────────

def upsert_player_stats(puuid: str, riot_id: str, payload: dict) -> str:
    """Merge `payload` into players.stats (JSONB) for the given puuid.

    Returns one of: "updated", "not_found", "error".
    """
    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                UPDATE players
                   SET stats = COALESCE(stats, '{}'::jsonb) || %s::jsonb,
                       last_updated = NOW()
                 WHERE riot_puuid = %s
                    OR (riot_puuid IS NULL AND riot_id = %s)
                 RETURNING id
                """,
                (json.dumps(payload), puuid, riot_id),
            )
            row = cur.fetchone()
            return "updated" if row else "not_found"
    except Exception as exc:
        print(f"  Postgres upsert failed: {exc}")
        return "error"


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 72)
    print("NECC Valorant Player Stats Scraper → Postgres (players.stats)")
    print("=" * 72)

    if not os.getenv("DATABASE_URL"):
        raise SystemExit("Missing DATABASE_URL in environment")

    if not JSON_SOURCE_PATH.exists():
        print(f"ERROR: {JSON_SOURCE_PATH} not found. Run BuildNecc_val_teams_puuids.py first.")
        return

    with JSON_SOURCE_PATH.open("r", encoding="utf-8") as f:
        teams = json.load(f)

    all_players = [
        p | {"school": t["school"], "logo_url": t.get("logo_url")}
        for t in teams
        for p in t["players"]
        if p.get("puuid_status") == "found"
    ]

    total = len(all_players)
    print(f"\nPlayers to process: {total}")

    if total == 0:
        print("No players with resolved PUUIDs. Run BuildNecc_val_teams_puuids.py first.")
        return

    ok_count = 0
    missing_count = 0
    fail_count = 0

    for i, player in enumerate(all_players, 1):
        game_name    = player.get("game_name", "")
        tag_line     = player.get("tag_line", "")
        puuid        = player.get("puuid", "")
        riot_id      = player.get("riot_id") or f"{game_name}#{tag_line}"
        team_name    = player.get("team_name", "")

        print(f"\n[{i}/{total}] {riot_id}  ({team_name})")

        print("  Scraping tracker.gg …", end=" ", flush=True)
        tracker_stats = scrape_tracker(game_name, tag_line)
        print("OK" if tracker_stats else "no data")

        print("  Riot API stats …", end=" ", flush=True)
        riot_stats = riot_aggregate_stats(puuid)
        print("OK" if riot_stats else "no data")

        scrape_status = "OK" if (tracker_stats or riot_stats) else "FAILED"

        payload = {
            "tracker_stats": tracker_stats,
            "riot_stats":    riot_stats,
            "scrape_status": scrape_status,
            "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        }

        result = upsert_player_stats(puuid, riot_id, payload)
        if result == "updated":
            ok_count += 1
        elif result == "not_found":
            missing_count += 1
            print("  No matching player row — skipped (run StorePlayer.py first).")
        else:
            fail_count += 1

    print(f"\n{'='*72}")
    print(f"Done. Updated: {ok_count}  Missing: {missing_count}  Failed: {fail_count}")


if __name__ == "__main__":
    main()
