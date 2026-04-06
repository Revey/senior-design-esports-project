"""
ScrapeCSUCustomGames.py
-----------------------
Scrapes each CSU Valorant player's custom game match history from tracker.gg
and stores the aggregated results in MongoDB (VAL_custom_stats collection).

Uses Playwright for browser automation because tracker.gg is JavaScript-rendered.

Requirements:
    pip install playwright pymongo python-dotenv certifi
    playwright install chromium

Run from the Backend/ directory:
    python valorant/ScrapeCSUCustomGames.py

The script reads the CSU roster from valorant/rosters/CSUValGreen.json.
Add/correct player gameName and tagLine there before running.

NOTE: tracker.gg may block bots. If pages consistently fail to load stats,
try setting HEADLESS = False below to watch the browser and diagnose.

--- CHANGELOG (2026-04-05) ---
Fixed two root causes of zero results:
  1. WRONG URL: old code used /matches?playlist=custom
     Correct URL is /customs?platform=pc
  2. WRONG SELECTORS: tracker.gg redesigned their frontend.
     All selectors updated to match the current v3 DOM structure.
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import certifi
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from pymongo import MongoClient
from pymongo.errors import PyMongoError

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────

SCRIPT_DIR        = Path(__file__).resolve().parent
ROSTER_FILE       = SCRIPT_DIR / "rosters" / "CSUValGreen.json"

MONGO_URI             = os.getenv("MONGO_URI", "")
MONGO_DB              = os.getenv("MONGO_DB", "senior_design_esports")
CUSTOM_STATS_COLL     = "VAL_custom_stats"

HEADLESS          = True    # Set False to watch the browser (useful for debugging)
PAGE_TIMEOUT_MS   = 30_000
WAIT_TIMEOUT_MS   = 20_000
BETWEEN_PLAYERS_S = 4       # pause between players to avoid rate limiting

TRACKER_BASE = "https://tracker.gg/valorant/profile/riot"


# ── URL builder ───────────────────────────────────────────────────────────────

def build_custom_url(game_name: str, tag_line: str) -> str:
    """
    Build the correct tracker.gg custom games URL.

    FIXED: The old code used /matches?playlist=custom which no longer works.
    The correct path is /customs?platform=pc
    Example: https://tracker.gg/valorant/profile/riot/VIKES%20LIAN%23NUNG/customs?platform=pc
    """
    import urllib.parse
    riot_id = f"{game_name}#{tag_line}"
    encoded = urllib.parse.quote(riot_id, safe="")
    return f"{TRACKER_BASE}/{encoded}/customs?platform=pc"


# ── Playwright scraper ────────────────────────────────────────────────────────

def scrape_custom_matches(page, game_name: str, tag_line: str) -> list[dict]:
    """
    Navigate to a player's custom matches page and extract match data.
    Returns a list of match dicts.

    FIXED: Updated the wait selector and match selector to match tracker.gg's
    current v3 DOM. Match rows are now: div.v3-match-row
    """
    url = build_custom_url(game_name, tag_line)
    print(f"    Loading: {url}")

    try:
        page.goto(url, timeout=PAGE_TIMEOUT_MS, wait_until="domcontentloaded")
    except PlaywrightTimeoutError:
        print("    Page load timed out.")
        return []

    # FIXED: old selector was "div.match, article.match, .matches__match, [class*='Match__']"
    # New tracker.gg v3 uses: div.v3-match-row
    match_selector = "div.v3-match-row"

    try:
        page.wait_for_selector(match_selector, timeout=WAIT_TIMEOUT_MS)
    except PlaywrightTimeoutError:
        body_text = page.inner_text("body")[:600]
        body_lower = body_text.lower()
        if "private" in body_lower:
            print("    Profile is private — no data available.")
        elif "no matches" in body_lower or "no results" in body_lower or "no custom" in body_lower:
            print("    No custom game matches found for this player.")
        else:
            print("    Match cards (div.v3-match-row) did not load in time.")
            print(f"    Page snippet: {body_text[:300]}")
        return []

    # Scroll to trigger lazy loading of additional match cards
    for _ in range(4):
        page.evaluate("window.scrollBy(0, window.innerHeight)")
        time.sleep(1.0)

    match_elements = page.query_selector_all(match_selector)
    print(f"    Found {len(match_elements)} match card(s)")

    matches = []
    for el in match_elements:
        try:
            match_data = extract_match_data(el)
            if match_data:
                matches.append(match_data)
        except Exception as e:
            print(f"    Error parsing match card: {e}")

    return matches


def extract_match_data(el) -> dict | None:
    """
    Extract stats from a single v3-match-row element.

    FIXED: All selectors updated to match tracker.gg's current v3 DOM.
    Inspected from live HTML on 2026-04-05.

    Key selectors in the new DOM:
      - Win/loss:    el has class 'v3-match-row--win' or 'v3-match-row--loss'
      - Map name:    span.text-primary  (bold map name like "Split", "Breeze")
      - Score:       span.text-valorant-team-1 and span.text-valorant-team-2
      - Agent img:   img[alt] (first img in the row is always the agent)
      - Stat name:   span.stat-name span.truncate  (e.g. "K/D", "ACS", "HS%")
      - Stat value:  span.stat-value span.truncate  (the number)
      - K/D/A list:  div.stat-list span.value  (three spans: kills / deaths / assists)
      - Timestamp:   span[data-allow-mismatch]  (e.g. "2h ago")
    """
    data: dict = {}

    # ── Win / Loss ────────────────────────────────────────────────────────────
    try:
        class_attr = el.get_attribute("class") or ""
        if "v3-match-row--win" in class_attr:
            data["result"] = "Win"
        elif "v3-match-row--loss" in class_attr:
            data["result"] = "Loss"
        else:
            data["result"] = "Unknown"
    except Exception:
        data["result"] = "Unknown"

    # ── Map name ──────────────────────────────────────────────────────────────
    # The map is in a span with class "text-primary" containing bold text like "Split"
    try:
        map_el = el.query_selector("span.text-primary")
        if map_el:
            # Strip any nested chip text (e.g. "3rd") — get only direct text
            raw = map_el.inner_text(timeout=2000).strip()
            # The chip rank appears after a newline or space — take first token
            data["map"] = raw.split("\n")[0].strip()
    except Exception:
        pass

    # ── Score ─────────────────────────────────────────────────────────────────
    try:
        team1 = el.query_selector("span.text-valorant-team-1")
        team2 = el.query_selector("span.text-valorant-team-2")
        if team1 and team2:
            s1 = team1.inner_text(timeout=2000).strip()
            s2 = team2.inner_text(timeout=2000).strip()
            data["score"] = f"{s1}:{s2}"
    except Exception:
        pass

    # ── Agent ─────────────────────────────────────────────────────────────────
    try:
        agent_img = el.query_selector("img[alt]")
        if agent_img:
            data["agent"] = agent_img.get_attribute("alt") or ""
    except Exception:
        pass

    # ── Timestamp ─────────────────────────────────────────────────────────────
    try:
        time_el = el.query_selector("span[data-allow-mismatch]")
        if time_el:
            data["played_at"] = time_el.inner_text(timeout=2000).strip()
    except Exception:
        pass

    # ── Named stats (K/D, ACS, HS%, DDΔ) ────────────────────────────────────
    # Each stat block has a span.stat-name > span.truncate for the label
    # and a span.stat-value > span.truncate for the value.
    try:
        stat_name_els = el.query_selector_all("span.stat-name span.truncate")
        stat_value_els = el.query_selector_all("span.stat-value span.truncate")

        for name_el, value_el in zip(stat_name_els, stat_value_els):
            label = name_el.inner_text(timeout=1500).strip().lower()
            value_text = value_el.inner_text(timeout=1500).strip().replace(",", "")
            _parse_stat(label, value_text, data)
    except Exception:
        pass

    # ── K/D/A breakdown ───────────────────────────────────────────────────────
    # The K/D/A values are in a div.stat-list containing three span.value elements
    try:
        kda_list = el.query_selector("div.stat-list")
        if kda_list:
            spans = kda_list.query_selector_all("span.value")
            values = []
            for sp in spans:
                t = sp.inner_text(timeout=1500).strip()
                if t:
                    values.append(t)
            if len(values) >= 3:
                data["kills"]   = _safe_int(values[0])
                data["deaths"]  = _safe_int(values[1])
                data["assists"] = _safe_int(values[2])
    except Exception:
        pass

    # Require at least map + result to count as a valid card
    return data if len(data) >= 2 else None


def _parse_stat(label: str, value: str, data: dict):
    """Map a tracker.gg stat label to a data dict key."""
    try:
        if "k/d" == label or "kd" == label:
            data["KD"] = float(value)
        elif label == "acs" or "combat score" in label:
            data["ACS"] = float(value)
        elif "hs%" in label or "headshot" in label:
            data["HSPercent"] = float(value.replace("%", ""))
        elif "ddδ" in label or "damage delta" in label or label == "dd":
            data["damageDelta"] = value  # keep as string, can be negative
        elif "adr" in label or ("damage" in label and "delta" not in label and "ddδ" not in label):
            data["ADR"] = float(value)
    except (ValueError, TypeError):
        pass


def _safe_int(val: str) -> int:
    try:
        return int(val.strip())
    except (ValueError, TypeError):
        return 0


# ── Aggregation ───────────────────────────────────────────────────────────────

def aggregate_matches(matches: list[dict]) -> dict:
    """Compute per-player aggregate stats from a list of custom game match dicts."""
    if not matches:
        return {}

    wins   = sum(1 for m in matches if m.get("result") == "Win")
    losses = sum(1 for m in matches if m.get("result") == "Loss")
    total  = len(matches)

    def avg(key: str) -> float:
        vals = [m[key] for m in matches if key in m and m[key] is not None]
        return round(sum(vals) / len(vals), 2) if vals else 0.0

    return {
        "totalMatches": total,
        "wins":         wins,
        "losses":       losses,
        "winRate":      round(wins / total * 100, 1) if total else 0.0,
        "avgKD":        avg("KD"),
        "avgACS":       avg("ACS"),
        "avgHSPercent": avg("HSPercent"),
        "avgADR":       avg("ADR"),
        "avgKills":     avg("kills"),
        "avgDeaths":    avg("deaths"),
        "avgAssists":   avg("assists"),
    }


# ── MongoDB ───────────────────────────────────────────────────────────────────

def upsert_player_stats(db, player_name: str, riot_id: str,
                        matches: list[dict], aggregates: dict) -> None:
    doc = {
        "riot_id":    riot_id,
        "player_name": player_name,
        "scraped_at": datetime.now(timezone.utc),
        "matches":    matches,
        "aggregates": aggregates,
    }
    try:
        db[CUSTOM_STATS_COLL].update_one(
            {"riot_id": riot_id},
            {"$set": doc},
            upsert=True,
        )
        print(f"    Saved to MongoDB: {riot_id}")
    except PyMongoError as e:
        print(f"    MongoDB error for {riot_id}: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 72)
    print("CSU Valorant — Custom Games Scraper (tracker.gg)")
    print("=" * 72)

    # Load roster
    if not ROSTER_FILE.exists():
        print(f"ERROR: Roster file not found: {ROSTER_FILE}")
        return

    with open(ROSTER_FILE) as f:
        roster_data = json.load(f)

    # Support both {"players": [...]} and bare list formats
    players = roster_data.get("players", roster_data) if isinstance(roster_data, dict) else roster_data
    team_name = roster_data.get("teamName", "CSU Vikes Green") if isinstance(roster_data, dict) else "CSU Vikes Green"

    print(f"\nTeam: {team_name}")
    print(f"Players: {len(players)}\n")

    # MongoDB connection (optional — results also printed to console)
    db = None
    if MONGO_URI:
        try:
            client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
            db = client[MONGO_DB]
            db.command("ping")
            print("MongoDB connected.\n")
        except Exception as e:
            print(f"MongoDB connection failed (will still print results): {e}\n")

    all_results = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=HEADLESS)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        page = context.new_page()

        for idx, player in enumerate(players, 1):
            game_name = player.get("gameName") or player.get("game_name", "")
            tag_line  = player.get("tagLine")  or player.get("tag_line", "")
            name      = player.get("name", f"{game_name}#{tag_line}")
            role      = player.get("role", "Unknown")
            riot_id   = f"{game_name}#{tag_line}"

            if not game_name or not tag_line:
                print(f"[{idx}/{len(players)}] Skipping {name} — missing Riot ID")
                continue

            print(f"[{idx}/{len(players)}] {riot_id}  ({role})")

            matches   = scrape_custom_matches(page, game_name, tag_line)
            aggregates = aggregate_matches(matches)

            if aggregates:
                print(f"    {aggregates['totalMatches']} matches | "
                      f"W{aggregates['wins']}-L{aggregates['losses']} | "
                      f"KD {aggregates['avgKD']} | ACS {aggregates['avgACS']}")
            else:
                print("    No aggregate stats computed.")

            result_entry = {
                "name":       name,
                "riot_id":    riot_id,
                "role":       role,
                "matches":    matches,
                "aggregates": aggregates,
            }
            all_results.append(result_entry)

            if db is not None and matches:
                upsert_player_stats(db, name, riot_id, matches, aggregates)

            if idx < len(players):
                time.sleep(BETWEEN_PLAYERS_S)

        page.close()
        context.close()
        browser.close()

    # Always write a local JSON backup regardless of MongoDB
    out_file = SCRIPT_DIR / "custom_games_results.json"
    with open(out_file, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nResults saved to {out_file}")

    # Summary
    print("\n" + "=" * 72)
    print("SUMMARY")
    print("=" * 72)
    for r in all_results:
        agg = r.get("aggregates", {})
        if agg:
            print(f"  {r['riot_id']:30s}  "
                  f"{agg.get('totalMatches', 0):2d} matches  "
                  f"W{agg.get('wins', 0)}-L{agg.get('losses', 0)}  "
                  f"KD {agg.get('avgKD', 0.0):.2f}  "
                  f"ACS {agg.get('avgACS', 0.0):.0f}")
        else:
            print(f"  {r['riot_id']:30s}  no data")


if __name__ == "__main__":
    main()