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

SCRIPT_DIR   = Path(__file__).resolve().parent
ROSTER_FILE  = SCRIPT_DIR / "rosters" / "CSUValGreen.json"

MONGO_URI            = os.getenv("MONGO_URI", "")
MONGO_DB             = os.getenv("MONGO_DB", "senior_design_esports")
CUSTOM_STATS_COLL    = "VAL_custom_stats"

HEADLESS          = True    # Set False to watch the browser (useful for debugging)
PAGE_TIMEOUT_MS   = 20_000
WAIT_TIMEOUT_MS   = 15_000
BETWEEN_PLAYERS_S = 3       # pause between players to avoid rate limiting

TRACKER_BASE = "https://tracker.gg/valorant/profile/riot"


# ── URL builder ───────────────────────────────────────────────────────────────

def build_custom_url(game_name: str, tag_line: str) -> str:
    import urllib.parse
    riot_id = f"{game_name}#{tag_line}"
    encoded = urllib.parse.quote(riot_id, safe="")
    return f"{TRACKER_BASE}/{encoded}/matches?playlist=custom"


# ── Playwright scraper ────────────────────────────────────────────────────────

def scrape_custom_matches(page, game_name: str, tag_line: str) -> list[dict]:
    """
    Navigate to a player's custom matches page and extract match data.
    Returns a list of match dicts.
    """
    url = build_custom_url(game_name, tag_line)
    print(f"    Loading: {url}")

    try:
        page.goto(url, timeout=PAGE_TIMEOUT_MS, wait_until="domcontentloaded")
    except PlaywrightTimeoutError:
        print("    Page load timed out.")
        return []

    # Wait for match cards to appear
    match_selector = "div.match, article.match, .matches__match, [class*='Match__']"
    try:
        page.wait_for_selector(match_selector, timeout=WAIT_TIMEOUT_MS)
    except PlaywrightTimeoutError:
        # Check if tracker.gg shows a "no matches" or "private profile" message
        body_text = page.inner_text("body")[:500]
        if "private" in body_text.lower():
            print("    Profile is private — no data available.")
        elif "no matches" in body_text.lower() or "no results" in body_text.lower():
            print("    No custom game matches found.")
        else:
            print("    Match cards did not load in time.")
            print(f"    Page snippet: {body_text[:200]}")
        return []

    # Scroll down to load more matches (tracker.gg uses lazy loading)
    for _ in range(3):
        page.evaluate("window.scrollBy(0, window.innerHeight)")
        time.sleep(1)

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
    Extract stats from a single match card element.
    Returns a dict or None if the card can't be parsed.
    """
    data: dict = {}

    # Result (Win / Loss / Draw)
    for sel in [".result", ".match__result", "[class*='Result']", ".won", ".lost"]:
        el2 = el.query_selector(sel)
        if el2:
            data["result"] = el2.inner_text(timeout=2000).strip()
            break

    # Map name
    for sel in [".map", ".match__map", "[class*='Map']", "[data-map]"]:
        el2 = el.query_selector(sel)
        if el2:
            data["map"] = el2.inner_text(timeout=2000).strip()
            break

    # Agent
    for sel in ["img[alt*='agent' i]", "img[alt*='Agent' i]", ".agent img", "[class*='Agent'] img"]:
        el2 = el.query_selector(sel)
        if el2:
            data["agent"] = el2.get_attribute("alt") or ""
            break

    # Score (rounds like "13-7")
    for sel in [".score", ".match__score", "[class*='Score']"]:
        el2 = el.query_selector(sel)
        if el2:
            data["score"] = el2.inner_text(timeout=2000).strip()
            break

    # Date / time played
    for sel in ["time", ".date", "[class*='Date']", "[datetime]"]:
        el2 = el.query_selector(sel)
        if el2:
            data["played_at"] = el2.get_attribute("datetime") or el2.inner_text(timeout=2000).strip()
            break

    # Stat blocks — tracker.gg renders these as labeled stat pairs
    stat_blocks = el.query_selector_all("div.stat, [class*='Stat'], .match-stat")
    for block in stat_blocks:
        try:
            label_el = block.query_selector("span.name, .stat__name, [class*='Label'], [class*='Name']")
            value_el = block.query_selector("span.value, .stat__value, [class*='Value']")
            if not label_el or not value_el:
                continue
            label = label_el.inner_text(timeout=2000).strip().lower()
            value = value_el.inner_text(timeout=2000).strip().replace(",", "")
            _parse_stat(label, value, data)
        except Exception:
            pass

    # Alternative: inline stat text (some tracker.gg layouts use spans directly)
    if not any(k in data for k in ("kills", "deaths", "ACS")):
        all_spans = el.query_selector_all("span")
        _try_parse_kda_spans(all_spans, data)

    return data if len(data) > 1 else None


def _parse_stat(label: str, value: str, data: dict):
    try:
        if "k/d" in label or "kd" in label:
            data["KD"] = float(value)
        elif label in ("kills", "k"):
            data["kills"] = int(value)
        elif label in ("deaths", "d"):
            data["deaths"] = int(value)
        elif label in ("assists", "a"):
            data["assists"] = int(value)
        elif "acs" in label or "combat score" in label:
            data["ACS"] = float(value)
        elif "headshot" in label:
            data["HSPercent"] = float(value.replace("%", ""))
        elif "damage" in label and "delta" not in label:
            data["ADR"] = float(value)
        elif "damage delta" in label or label == "dd":
            data["damageDelta"] = value
    except (ValueError, TypeError):
        pass


def _try_parse_kda_spans(spans, data: dict):
    """Fallback: try to find K/D/A values from raw span text in the card."""
    texts = []
    for sp in spans:
        try:
            t = sp.inner_text(timeout=1000).strip()
            if t and t.replace("/", "").replace(".", "").isdigit():
                texts.append(t)
        except Exception:
            pass
    # Common pattern: "kills / deaths / assists" appears as three consecutive integers
    if len(texts) >= 3:
        try:
            data.setdefault("kills",   int(texts[0]))
            data.setdefault("deaths",  int(texts[1]))
            data.setdefault("assists", int(texts[2]))
        except ValueError:
            pass


# ── Aggregation ───────────────────────────────────────────────────────────────

def aggregate_matches(matches: list[dict]) -> dict:
    """Compute per-player aggregate stats from a list of custom game match dicts."""
    if not matches:
        return {}

    total_matches = len(matches)
    wins = sum(1 for m in matches if "win" in m.get("result", "").lower())

    kills   = sum(m.get("kills",   0) for m in matches)
    deaths  = sum(m.get("deaths",  0) for m in matches)
    assists = sum(m.get("assists", 0) for m in matches)

    acs_vals = [m["ACS"]       for m in matches if "ACS"       in m]
    hs_vals  = [m["HSPercent"] for m in matches if "HSPercent" in m]
    adr_vals = [m["ADR"]       for m in matches if "ADR"       in m]

    return {
        "matches_played":  total_matches,
        "wins":            wins,
        "losses":          total_matches - wins,
        "win_rate":        round(wins / total_matches * 100, 1) if total_matches else 0,
        "total_kills":     kills,
        "total_deaths":    deaths,
        "total_assists":   assists,
        "KD":              round(kills / max(deaths, 1), 2),
        "avg_ACS":         round(sum(acs_vals) / len(acs_vals), 1) if acs_vals else None,
        "avg_HSPercent":   round(sum(hs_vals)  / len(hs_vals),  1) if hs_vals  else None,
        "avg_ADR":         round(sum(adr_vals) / len(adr_vals), 1) if adr_vals else None,
    }


# ── MongoDB ───────────────────────────────────────────────────────────────────

def get_mongo_collection():
    if not MONGO_URI:
        raise ValueError("Missing MONGO_URI in .env")
    client = MongoClient(MONGO_URI, tls=True, tlsCAFile=certifi.where())
    db     = client[MONGO_DB]
    coll   = db[CUSTOM_STATS_COLL]
    coll.create_index("riot_id", unique=True)
    return client, coll


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 72)
    print("CSU Valorant — Custom Games Scraper (tracker.gg)")
    print("=" * 72)

    if not ROSTER_FILE.exists():
        print(f"ERROR: Roster file not found: {ROSTER_FILE}")
        return

    with ROSTER_FILE.open(encoding="utf-8") as f:
        roster = json.load(f)

    players  = roster.get("players", [])
    team_name = roster.get("teamName", "CSU Vikes Green")

    print(f"\nTeam: {team_name}")
    print(f"Players: {len(players)}")

    if not players:
        print("No players in roster.")
        return

    # Set up MongoDB
    mongo_client, collection = None, None
    use_mongo = bool(MONGO_URI)
    if use_mongo:
        try:
            mongo_client, collection = get_mongo_collection()
            print(f"MongoDB: {MONGO_DB}.{CUSTOM_STATS_COLL}")
        except Exception as e:
            print(f"MongoDB connection failed: {e} — results will only be printed.")
            use_mongo = False

    all_results = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=HEADLESS,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        page = context.new_page()

        for i, player in enumerate(players, 1):
            game_name = player.get("gameName", "")
            tag_line  = player.get("tagLine",  "")
            role      = player.get("role", "")
            riot_id   = f"{game_name}#{tag_line}"

            if not game_name or not tag_line:
                print(f"\n[{i}/{len(players)}] Skipping — missing gameName or tagLine: {player}")
                continue

            print(f"\n[{i}/{len(players)}] {riot_id}  ({role})")

            matches   = scrape_custom_matches(page, game_name, tag_line)
            aggregate = aggregate_matches(matches)

            result_doc = {
                "riot_id":       riot_id,
                "game_name":     game_name,
                "tag_line":      tag_line,
                "team_name":     team_name,
                "role":          role,
                "custom_matches": matches,
                "aggregate":     aggregate,
                "scrape_status": "OK" if matches else "NO_DATA",
                "updated_at_utc": datetime.now(timezone.utc).isoformat(),
            }

            all_results.append(result_doc)

            if aggregate:
                print(f"    Matches: {aggregate['matches_played']}  "
                      f"Win%: {aggregate['win_rate']}%  "
                      f"KD: {aggregate['KD']}  "
                      f"ACS: {aggregate.get('avg_ACS', 'N/A')}")
            else:
                print("    No aggregate stats computed.")

            if use_mongo and collection is not None:
                try:
                    collection.replace_one({"riot_id": riot_id}, result_doc, upsert=True)
                    print("    Saved to MongoDB.")
                except PyMongoError as e:
                    print(f"    MongoDB error: {e}")

            if i < len(players):
                time.sleep(BETWEEN_PLAYERS_S)

        browser.close()

    # Print summary
    print(f"\n{'='*72}")
    print("SUMMARY")
    print(f"{'='*72}")
    for r in all_results:
        agg = r.get("aggregate", {})
        print(f"  {r['riot_id']:<35} "
              f"{agg.get('matches_played', 0):>3} matches  "
              f"KD: {agg.get('KD', 'N/A')}")

    # Also save raw results to a local JSON for inspection
    out_file = SCRIPT_DIR / "csu_custom_games.json"
    with out_file.open("w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nRaw results saved to {out_file.name}")

    if mongo_client:
        mongo_client.close()


if __name__ == "__main__":
    main()
