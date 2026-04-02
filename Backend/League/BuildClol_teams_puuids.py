"""
TESTscrape_clolpuuids.py
---------------------
Scrapes all teams + players from the 2024/25 CLOL Championship and resolves
each player's LoL Riot ID to a PUUID via the Riot API.

Each player's 'puuid_status' field will be one of:
    "found"        — PUUID successfully resolved
    "not_found"    — 404 from Riot API (name changed or account doesn't exist)
    "rate_limited" — 429, was skipped; re-run the script to retry these
    "no_riot_id"   — player has no LoL Riot ID on their profile
    "error"        — unexpected API error
    "pending"      — not yet attempted (shouldn't appear in final output)

On each run the script:
  1. Fetches fresh tournament data from the ggtech API
  2. Loads the existing clol_teams_puuids.json if it exists
  3. Skips players already marked "found" or "not_found" (no need to retry)
  4. Retries players marked "rate_limited" or "error"
  5. Overwrites clol_teams_puuids.json with the updated results

Place this file in the same directory as RiotAPI.py.
Requirements:  pip install requests python-dotenv
Run:           python scrape_clol.py

Running for the first time: it may reach limit, just re run this script to get those 
players puuids that we missed
"""

import json
import re
import time
import requests
from pathlib import Path

from RiotAPI import (
    get_puuid_by_riot_id,
    PUUID_NOT_FOUND,
    PUUID_RATE_LIMITED,
    PUUID_ERROR,
)

# ── Config ────────────────────────────────────────────────────────────────────
LOL_GAME_ID = "XS3bzSuFXwkHcDL2P"

API_URL = (
    "https://api-ggtech.leagueoflegends.com/api/v001"
    "/showcase/university-united-states-and-canada"
    "/tournament-endpoint/2025-clol-championship"
)

OUT_FILE = Path(__file__).parent / "clol_teams_puuids.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin":          "https://universityesportsna.riotgames.com",
    "Referer":         "https://universityesportsna.riotgames.com/",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def parse_riot_id(raw: str):
    m = re.match(r"^(.+?)\s*#\s*(\S+)$", raw.strip())
    return (m.group(1).strip(), m.group(2).strip()) if m else None


def fetch_tournament() -> dict:
    print(f"  GET {API_URL}")
    r = requests.get(API_URL, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.json()


# ── Parsing ───────────────────────────────────────────────────────────────────

def extract_teams(data: dict) -> list[dict]:
    teams = []
    for m in data["returnData"]["members"]:
        team_name   = m.get("name", "Unknown Team")
        institution = m.get("institution") or {}
        school      = institution.get("name", "") if isinstance(institution, dict) else ""
        role_map    = {mem["userId"]: mem.get("rolGame") for mem in m.get("members", []) if mem.get("userId")}

        players = []
        for user in m.get("users", []):
            display_name = user.get("displayName") or user.get("username") or ""
            role         = role_map.get(user.get("_id", ""))

            lol_nick = None
            for gn in (user.get("profile") or {}).get("gameNicks", []):
                if gn.get("id") == LOL_GAME_ID:
                    lol_nick = gn.get("nick", "").strip()
                    break
            if not lol_nick and "#" in display_name:
                lol_nick = display_name.strip()

            rid = parse_riot_id(lol_nick) if lol_nick else None

            players.append({
                "team_name":    team_name,
                "school":       school,
                "display_name": display_name,
                "role":         role,
                "riot_id":      lol_nick,
                "game_name":    rid[0] if rid else None,
                "tag_line":     rid[1] if rid else None,
                "puuid":        None,
                "puuid_status": "no_riot_id" if not rid else "pending",
            })

        teams.append({"team_name": team_name, "school": school, "players": players})
    return teams


def merge_with_existing(fresh_teams: list[dict], existing_teams: list[dict]) -> list[dict]:
    """
    For players already resolved (found / not_found), carry over their
    puuid + puuid_status from the existing file so we don't re-hit the API.
    Key: (team_name, riot_id)
    """
    existing_map: dict[tuple, dict] = {}
    for t in existing_teams:
        for p in t["players"]:
            key = (p.get("team_name") or t.get("team_name", ""), p.get("riot_id", ""))
            existing_map[key] = p

    for t in fresh_teams:
        for p in t["players"]:
            key = (p["team_name"], p.get("riot_id", ""))
            prev = existing_map.get(key)
            if prev and prev.get("puuid_status") in ("found", "not_found"):
                p["puuid"]        = prev["puuid"]
                p["puuid_status"] = prev["puuid_status"]

    return fresh_teams


# ── PUUID resolution ──────────────────────────────────────────────────────────

def enrich_with_puuids(teams: list[dict]) -> list[dict]:
    """
    Attempt PUUID lookup for every player whose status is 'pending'.
    Stops ALL lookups immediately on first rate-limit hit and marks all
    remaining pending players as 'rate_limited'.
    """
    pending = [(t, p) for t in teams for p in t["players"] if p["puuid_status"] == "pending"]
    total   = len(pending)

    if total == 0:
        print("  Nothing to look up — all players already resolved.")
        return teams

    print(f"  {total} player(s) to look up …\n")
    rate_limited = False

    for i, (team, player) in enumerate(pending, 1):
        gn = player["game_name"]
        tl = player["tag_line"]
        print(f"  [{i:>3}/{total}] {gn}#{tl}", end=" … ", flush=True)

        if rate_limited:
            player["puuid_status"] = "rate_limited"
            player["puuid"]        = None
            print("skipped (rate limited)")
            continue

        result = get_puuid_by_riot_id(gn, tl)

        if result == PUUID_RATE_LIMITED:
            player["puuid_status"] = "rate_limited"
            player["puuid"]        = None
            rate_limited           = True
            print("RATE LIMITED — marking remaining as rate_limited")

        elif result == PUUID_NOT_FOUND:
            player["puuid_status"] = "not_found"
            player["puuid"]        = None
            print("NOT FOUND (name changed or account gone)")

        elif result == PUUID_ERROR or result is None:
            player["puuid_status"] = "error"
            player["puuid"]        = None
            print("ERROR")

        else:
            player["puuid_status"] = "found"
            player["puuid"]        = result
            print(result)

        time.sleep(0.4)

    return teams


# ── Output ────────────────────────────────────────────────────────────────────

def print_summary(teams: list[dict]):
    from collections import Counter
    status_counts = Counter(p["puuid_status"] for t in teams for p in t["players"])
    total = sum(status_counts.values())

    print(f"\n{'='*72}")
    print("RESULTS")
    print(f"{'='*72}")

    for team in teams:
        players = team["players"]
        found   = sum(1 for p in players if p["puuid_status"] == "found")
        print(f"\n  ┌─ {team['team_name']}")
        if team["school"]:
            print(f"  │   {team['school']}")
        print(f"  │")
        for p in players:
            icons = {
                "found":       "✓",
                "not_found":   "✗",
                "rate_limited":"⏳",
                "no_riot_id":  "—",
                "error":       "!",
                "pending":     "?",
            }
            icon  = icons.get(p["puuid_status"], "?")
            role  = f"{p['role']:<9}" if p["role"] else "         "
            rid   = p["riot_id"] or f"({p['display_name']})"
            value = p["puuid"] or p["puuid_status"].upper()
            print(f"  │  [{icon}] [{role}]  {rid:<35}  {value}")
        print(f"  └{'─'*70}")

    print(f"\n  Teams:          {len(teams)}")
    print(f"  Total players:  {total}")
    print(f"  ✓  Found:       {status_counts['found']}")
    print(f"  ✗  Not found:   {status_counts['not_found']}  (name changed / account gone)")
    print(f"  ⏳ Rate limited: {status_counts['rate_limited']}  (re-run to retry)")
    print(f"  —  No Riot ID:  {status_counts['no_riot_id']}")
    if status_counts["error"]:
        print(f"  !  Errors:      {status_counts['error']}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 72)
    print("2025 CLOL Championship Scraper")
    print("=" * 72)

    # Step 1: fetch fresh tournament data
    print("\n[STEP 1] Fetching tournament data …")
    try:
        data = fetch_tournament()
    except Exception as e:
        print(f"  API call failed: {e}")
        return

    # Step 2: parse fresh teams
    print("\n[STEP 2] Parsing teams and players …")
    teams = extract_teams(data)
    total = sum(len(t["players"]) for t in teams)
    print(f"  {len(teams)} teams  |  {total} players")

    # Step 3: carry over already-resolved PUUIDs from existing output file
    if OUT_FILE.exists():
        print(f"\n[STEP 3] Loading existing results from {OUT_FILE.name} …")
        with open(OUT_FILE) as f:
            existing = json.load(f)
        teams = merge_with_existing(teams, existing)
        skipped  = sum(1 for t in teams for p in t["players"] if p["puuid_status"] in ("found", "not_found"))
        pending  = sum(1 for t in teams for p in t["players"] if p["puuid_status"] == "pending")
        print(f"  {skipped} already resolved (skipping)  |  {pending} to look up")
    else:
        print("\n[STEP 3] No existing file — looking up all players.")

    # Step 4: resolve PUUIDs for pending players
    print("\n[STEP 4] Resolving PUUIDs via Riot API …")
    teams = enrich_with_puuids(teams)

    # Step 5: print summary
    print_summary(teams)

    # Step 6: overwrite output file
    with open(OUT_FILE, "w") as f:
        json.dump(teams, f, indent=2)
    print(f"\n  Saved to {OUT_FILE}")


if __name__ == "__main__":
    main()