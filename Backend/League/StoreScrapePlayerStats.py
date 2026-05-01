import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.db import get_cursor  # noqa: E402

from RiotAPI import (
    get_champion_masteries,
    MASTERY_RATE_LIMITED,
    MASTERY_NOT_FOUND,
    MASTERY_ERROR,
)

# ── Config ────────────────────────────────────────────────────────────────────

REQUEST_DELAY_SECONDS = 2.0
PAGE_GOTO_TIMEOUT_MS  = 20_000
DEFAULT_TIMEOUT_MS    = 10_000

# Path to the JSON file that holds all team/player data (with PUUIDs already resolved)
JSON_SOURCE_PATH = Path(__file__).resolve().parent / "clol_teams_puuids.json"


# ── Text helpers ──────────────────────────────────────────────────────────────

def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def parse_riot_id(riot_id: str) -> Optional[tuple[str, str]]:
    if not riot_id or "#" not in riot_id:
        return None
    game_name, tag_line = riot_id.split("#", 1)
    game_name = game_name.strip()
    tag_line  = tag_line.strip()
    if not game_name or not tag_line:
        return None
    return game_name, tag_line


def build_opgg_url(riot_id: str, region_slug: str = "na") -> Optional[str]:
    parsed = parse_riot_id(riot_id)
    if not parsed:
        return None
    game_name, tag_line = parsed
    encoded_name = game_name.replace(" ", "%20")
    return f"https://www.op.gg/lol/summoners/{region_slug}/{encoded_name}-{tag_line}"


# ── Extraction helpers ────────────────────────────────────────────────────────

def extract_number(text: str, pattern: str) -> Optional[int]:
    m = re.search(pattern, text, re.IGNORECASE)
    if not m:
        return None
    return int(m.group(1).replace(",", ""))


def extract_percent(text: str) -> Optional[int]:
    m = re.search(r"(\d+)\s*%", text)
    return int(m.group(1)) if m else None


def extract_wins_losses(text: str) -> tuple[Optional[int], Optional[int]]:
    wins = losses = None
    w = re.search(r"(\d+)\s*W", text, re.IGNORECASE)
    l = re.search(r"(\d+)\s*L", text, re.IGNORECASE)
    if w:
        wins = int(w.group(1))
    if l:
        losses = int(l.group(1))
    return wins, losses


def extract_rank_name(text: str) -> Optional[str]:
    m = re.search(
        r"\b(Iron|Bronze|Silver|Gold|Platinum|Emerald|Diamond|Master|Grandmaster|Challenger)"
        r"(?:\s+([IVX]{1,4}|\d))?\b",
        text,
        re.IGNORECASE,
    )
    if not m:
        if "unranked" in text.lower():
            return "Unranked"
        return None
    tier = m.group(1).title()
    div  = m.group(2)
    return f"{tier} {div.upper()}" if div else tier


def extract_height_percent(style_text: str) -> float:
    """Pull the numeric value out of a CSS 'height: X%' string."""
    if not style_text:
        return 0.0
    match = re.search(r"height:\s*([\d.]+)%", style_text, re.IGNORECASE)
    return float(match.group(1)) if match else 0.0


def safe_inner_text(locator) -> str:
    try:
        return clean_text(locator.inner_text(timeout=5000))
    except Exception:
        return ""


# ── OP.GG scrapers ────────────────────────────────────────────────────────────

def scrape_preferred_roles(page) -> tuple[list[dict], dict, Optional[str]]:
    """
    Scrapes the 'Preferred Role (Ranked)' section from OP.GG using the
    proven height-% approach.

    OP.GG renders role play-rate as inline style="width: 100%; height: X%"
    on the filled bar div (class bg-main-500) inside each <li>. The 5 <li>
    elements always appear in a fixed order: TOP, JUNGLE, MID, ADC, SUPPORT.

    Strategy:
      1. Wait for the role <ul> to be present in the DOM
         (selector: "ul.hidden.flex-row" — matches the DevTools class list).
      2. Grab every <li> inside that <ul>.
      3. For each <li>, find the inner div with bg-main-500 and read its
         height: X% inline style.
      4. Map position → role name using role_order.
    """
    role_order = ["TOP", "JUNGLE", "MID", "ADC", "SUPPORT"]
    role_percentages: dict[str, float] = {role: 0.0 for role in role_order}

    try:
        # Skip immediately if the player has no ranked games — OP.GG won't
        # render the role section at all for unranked/no-data profiles.
        body_text = page.locator("body").inner_text(timeout=3000)
        if "unranked" in body_text.lower() and "preferred role" not in body_text.lower():
            return [], role_percentages, None

        # Wait for the <ul> to be ATTACHED to the DOM (state="attached"), not
        # visible. The ul has Tailwind class "hidden" (display:none by default)
        # and only becomes visible at md+ breakpoints via "md:flex". Playwright's
        # default wait_for_selector checks visibility, so it times out even when
        # the element is present. "attached" just confirms it exists in the DOM.
        try:
            page.wait_for_selector("ul.hidden.flex-row", state="attached", timeout=10_000)
        except Exception:
            # Element never appeared — player likely has no ranked role data
            return [], role_percentages, None

        ul = page.query_selector("ul.hidden.flex-row")
        if ul is None:
            return [], role_percentages, None

        list_items = ul.query_selector_all("li.flex.flex-col.items-center")
        if not list_items:
            # Fallback: any direct <li> children
            list_items = ul.query_selector_all("li")

        if not list_items:
            return [], role_percentages, None

        for i, li in enumerate(list_items[:len(role_order)]):
            role = role_order[i]

            # Primary: the filled blue bar has class bg-main-500
            bar = li.query_selector("div.bg-main-500")

            # Fallback: any div with an inline height style
            if bar is None:
                bar = li.query_selector("div[style*='height']")

            if bar is None:
                continue

            style_value = bar.get_attribute("style") or ""
            role_percentages[role] = extract_height_percent(style_value)

    except Exception as exc:
        print(f"    [OPGG ROLES] scrape_preferred_roles error: {exc}")

    # Build sorted list; only include roles the player has actually played
    preferred_roles = [
        {"role": role, "percentage": pct}
        for role, pct in sorted(role_percentages.items(), key=lambda x: x[1], reverse=True)
        if pct > 0
    ]

    main_role = preferred_roles[0]["role"] if preferred_roles else None
    return preferred_roles, role_percentages, main_role


def _parse_solo_duo_rank(page) -> tuple[Optional[dict], Optional[dict]]:
    """
    Scrapes the Ranked Solo/Duo card from OP.GG.

    Locates the specific Solo/Duo section element and reads only that subtree
    to avoid picking up Flex or previous-season ranks.

    Returns: (current_rank_dict, highest_rank_dict)
    """
    solo_section_text = ""

    try:
        ranked_label = page.get_by_text("Ranked Solo/Duo", exact=True)
        if ranked_label.count() > 0:
            for ancestor_tag in ("section", "article", "div"):
                ancestor = ranked_label.locator(f"xpath=ancestor::{ancestor_tag}[1]").first
                if ancestor.count() > 0:
                    candidate = safe_inner_text(ancestor)
                    if "lp" in candidate.lower() or "unranked" in candidate.lower():
                        solo_section_text = candidate
                        break
    except Exception:
        pass

    if not solo_section_text:
        return None, None

    # ── Current rank ─────────────────────────────────────────────────────────
    tier_lp_matches = re.findall(
        r"(Iron|Bronze|Silver|Gold|Platinum|Emerald|Diamond|Master|Grandmaster|Challenger)"
        r"(?:\s+([IVX]{1,4}|\d))?\s+([\d,]+)\s*LP",
        solo_section_text,
        re.IGNORECASE,
    )

    current_rank: Optional[dict] = None
    highest_rank: Optional[dict] = None

    if tier_lp_matches:
        tier_name, div, lp = tier_lp_matches[0]
        tier_text = f"{tier_name.title()} {div.upper()}" if div else tier_name.title()
        wins, losses = extract_wins_losses(solo_section_text)
        win_rate = extract_percent(solo_section_text)
        current_rank = {
            "tier_text": tier_text,
            "lp":        int(lp.replace(",", "")),
            "wins":      wins,
            "losses":    losses,
            "win_rate":  win_rate,
        }

    # ── Highest rank ─────────────────────────────────────────────────────────
    if len(tier_lp_matches) >= 2:
        tier_name, div, lp = tier_lp_matches[1]
        highest_rank = {
            "tier_text": f"{tier_name.title()} {div.upper()}" if div else tier_name.title(),
            "lp":        int(lp.replace(",", "")),
        }
    elif not current_rank:
        if "unranked" in solo_section_text.lower():
            current_rank = {
                "tier_text": "Unranked",
                "lp":        None,
                "wins":      None,
                "losses":    None,
                "win_rate":  None,
            }

    return current_rank, highest_rank


# ── Main page scraper ─────────────────────────────────────────────────────────

def scrape_player_page(page, riot_id: str) -> dict[str, Any]:
    url = build_opgg_url(riot_id)
    if not url:
        return {
            "scrape_status": "invalid_riot_id",
            "source":        "opgg",
            "error":         f"Invalid riot_id: {riot_id}",
            "opgg_url":      None,
        }

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=PAGE_GOTO_TIMEOUT_MS)
        page.wait_for_timeout(2500)

        body      = page.locator("body")
        body_text = safe_inner_text(body)

        # Detect blocks / bot-check pages
        if any(
            term in body_text.lower()
            for term in ["403 error", "forbidden", "access denied", "verify you are human", "just a moment"]
        ):
            return {
                "scrape_status": "blocked",
                "source":        "opgg",
                "opgg_url":      url,
                "error":         "OP.GG returned a blocked/error page",
            }

        # ── Header / summoner name ────────────────────────────────────────────
        heading_text    = ""
        summoner_name   = None
        header_tag_line = None
        try:
            h1 = page.locator("h1").first
            if h1.count() > 0:
                heading_text = safe_inner_text(h1)
        except Exception:
            pass

        if heading_text:
            if "#" in heading_text:
                summoner_name, header_tag_line = [p.strip() for p in heading_text.split("#", 1)]
            else:
                summoner_name = heading_text

        ladder_rank = extract_number(body_text, r"Ladder Rank\s+(\d[\d,]*)")

        last_updated = None
        m_updated = re.search(r"Last updated:\s*([^\n]+)", body_text, re.IGNORECASE)
        if m_updated:
            last_updated = clean_text(m_updated.group(1))

        # ── Solo/Duo rank ─────────────────────────────────────────────────────
        current_rank, highest_rank = _parse_solo_duo_rank(page)

        # ── Preferred roles from OP.GG role bars ──────────────────────────────
        preferred_roles, role_pct_map, opgg_main_role = scrape_preferred_roles(page)
        print(f"    [OPGG ROLES] {[(r['role'], r['percentage']) for r in preferred_roles] or 'none found'}")

        # ── Determine scrape status ───────────────────────────────────────────
        scrape_status = "ok" if current_rank else "partial"

        return {
            "scrape_status":     scrape_status,
            "source":            "opgg",
            "opgg_url":          url,
            "summoner_name":     summoner_name,
            "tag_line":          header_tag_line,
            "ladder_rank":       ladder_rank,
            "last_updated_text": last_updated,
            "solo_duo_rank":     current_rank,
            "highest_rank":      highest_rank,
            "flex_rank":         None,
            "top_roles":         preferred_roles,
            "main_role":         opgg_main_role,
        }

    except PlaywrightTimeoutError:
        return {"scrape_status": "timeout", "source": "opgg", "opgg_url": url}
    except Exception as e:
        return {"scrape_status": "error", "source": "opgg", "opgg_url": url, "error": str(e)}


# ── Document builder ──────────────────────────────────────────────────────────

def build_player_stat_doc(
    team_doc:   dict[str, Any],
    player_doc: dict[str, Any],
    scraped:    dict[str, Any],
    masteries:  list[dict],
) -> dict[str, Any]:
    return {
        "team_name":            team_doc.get("team_name"),
        "school":               team_doc.get("school"),
        "display_name":         player_doc.get("display_name"),
        "team_role_from_clol":  player_doc.get("role"),
        "riot_id":              player_doc.get("riot_id"),
        "game_name":            player_doc.get("game_name"),
        "tag_line":             player_doc.get("tag_line"),
        "puuid":                player_doc.get("puuid"),
        "updated_at_utc":       datetime.now(timezone.utc).isoformat(),
        **scraped,
        "top_5_masteries": masteries,
    }


# ── Entry point ───────────────────────────────────────────────────────────────

def upsert_player_stats_pg(puuid: str, riot_id: str, payload: dict) -> str:
    """Merge `payload` into players.stats (JSONB) for the given puuid/riot_id.

    Returns: "updated", "not_found", or "error".
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
                (json.dumps(payload, default=str), puuid, riot_id),
            )
            return "updated" if cur.fetchone() else "not_found"
    except Exception as exc:
        print(f"    [DB ERROR] {exc}")
        return "error"


def main():
    load_dotenv()

    if not os.getenv("DATABASE_URL"):
        raise SystemExit("Missing DATABASE_URL in environment")

    # ── Load player data from JSON ────────────────────────────────────────────
    if not JSON_SOURCE_PATH.exists():
        raise FileNotFoundError(f"JSON source not found: {JSON_SOURCE_PATH}")

    with JSON_SOURCE_PATH.open(encoding="utf-8") as f:
        teams: list[dict] = json.load(f)

    print(f"Loaded {len(teams)} teams from {JSON_SOURCE_PATH.name}")

    # ── Collect all valid players ─────────────────────────────────────────────
    valid_players: list[tuple[dict, dict]] = []   # (team_doc, player_doc)
    skipped = 0
    for team in teams:
        for player in team.get("players", []):
            riot_id = player.get("riot_id")
            puuid   = player.get("puuid")
            name    = player.get("display_name", "Unknown")
            if not riot_id or "#" not in riot_id:
                skipped += 1
                print(f"  Skipping {name}: invalid Riot ID")
                continue
            if not puuid:
                skipped += 1
                print(f"  Skipping {name}: no PUUID")
                continue
            valid_players.append((team, player))

    print(f"Valid players: {len(valid_players)}  |  Skipped: {skipped}\n")

    updated = 0
    missing = 0
    failed = 0

    # ── Scrape all players ────────────────────────────────────────────────────
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 1100},
        )
        context.set_default_timeout(DEFAULT_TIMEOUT_MS)
        page = context.new_page()

        for team, player in valid_players:
            riot_id      = player.get("riot_id")
            display_name = player.get("display_name", "Unknown Player")
            puuid        = player.get("puuid")

            print(f"  Scraping {display_name} ({riot_id}) ...")

            # ── 1. OP.GG scrape (rank + role bars) ───────────────────────────
            try:
                scraped = scrape_player_page(page, riot_id)
            except Exception as e:
                print(f"    [OPGG ERROR] {e}")
                scraped = {"scrape_status": "error", "source": "opgg", "error": str(e),
                           "top_roles": [], "main_role": None}

            print(f"    Roles: {[r['role'] for r in scraped.get('top_roles', [])] or 'none'}")

            # ── 2. Mastery from Riot API ──────────────────────────────────────
            masteries: list[dict] = []
            mastery_result = get_champion_masteries(puuid, count=5)

            if isinstance(mastery_result, list):
                masteries = mastery_result
                print(f"    Masteries: {[m['champion'] for m in masteries]}")
            elif mastery_result == MASTERY_RATE_LIMITED:
                print("    [MASTERY] Rate limited — waiting 10 s before retry")
                time.sleep(10)
                retry = get_champion_masteries(puuid, count=5)
                if isinstance(retry, list):
                    masteries = retry
            elif mastery_result == MASTERY_NOT_FOUND:
                print("    [MASTERY] Not found (no mastery data for this player)")
            else:
                print(f"    [MASTERY] Unexpected result: {mastery_result}")

            # ── 3. Merge scraped payload into players.stats ───────────────────
            payload = {
                **scraped,
                "top_5_masteries": masteries,
                "team_name":       team.get("team_name"),
                "school":          team.get("school"),
                "updated_at_utc":  datetime.now(timezone.utc).isoformat(),
            }

            result = upsert_player_stats_pg(puuid, riot_id, payload)
            if result == "updated":
                updated += 1
                print(f"    Saved → scrape_status={scraped.get('scrape_status')}")
            elif result == "not_found":
                missing += 1
                print("    No matching player row — run StorePlayer.py first.")
            else:
                failed += 1

            time.sleep(REQUEST_DELAY_SECONDS)

        browser.close()

    print("\n── Done ──────────────────────────────────")
    print(f"Updated:  {updated}")
    print(f"Missing:  {missing}")
    print(f"Failed:   {failed}")
    print(f"Skipped:  {skipped}")


if __name__ == "__main__":
    main()