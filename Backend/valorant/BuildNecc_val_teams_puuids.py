"""
BuildNecc_val_teams_puuids.py
-----------------------------
Fetches all NECC Valorant teams + player rosters from the LeagueOS API,
resolves each player's Valorant Riot ID to a PUUID via the Riot API,
and saves the results to necc_val_teams_puuids.json.

Mirrors the structure of League/BuildClol_teams_puuids.py.

Each player's 'puuid_status' will be one of:
    "found"        — PUUID resolved successfully
    "not_found"    — 404 from Riot API (account doesn't exist or name changed)
    "rate_limited" — 429 hit; re-run the script to retry these
    "no_riot_id"   — player has no Valorant Riot ID on their profile
    "error"        — unexpected error
    "pending"      — not yet attempted (shouldn't appear in final output)

On each run the script:
  1. Fetches fresh school/team data from the LeagueOS API
  2. Loads the existing necc_val_teams_puuids.json if it exists
  3. Skips players already marked "found" or "not_found"
  4. Retries "rate_limited" or "error" players
  5. Saves updated results to necc_val_teams_puuids.json

Run from the Backend/ directory:
    python valorant/BuildNecc_val_teams_puuids.py

NOTE: The LeagueOS session cookie (los.sid) in LEAGUEOS_COOKIES may expire.
Update it from your browser's DevTools (necc.leagueos.gg) if you get 401/403.

NOTE: On first run, the script prints the raw API response for one school so
you can verify the player field names. Adjust PLAYER_NICK_FIELDS below if needed.
"""

import json
import os
import re
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

# ── Paths ─────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
OUT_FILE   = SCRIPT_DIR / "necc_val_teams_puuids.json"

# ── Riot API ──────────────────────────────────────────────────────────────────

RIOT_API_KEY        = os.getenv("RIOT_API_KEY", "")
RIOT_ACCOUNT_REGION = os.getenv("RIOT_ACCOUNT_REGION", "americas")
RIOT_ACCOUNT_BASE   = f"https://{RIOT_ACCOUNT_REGION}.api.riotgames.com"

# ── LeagueOS API ──────────────────────────────────────────────────────────────

LEAGUE_ID = "b1q6j3ea75j6zgk1s4i79dlw7"

LEAGUEOS_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "origin": "https://necc.leagueos.gg",
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
    ),
    "x-leagueos-aid": "los-league",
    "x-leagueos-did": "1652185412",
    "x-leagueos-lid": LEAGUE_ID,
    "x-leagueos-rid": "-1408404481",
}

LEAGUEOS_COOKIES = {
    # Update this cookie if you get 401/403 — grab it from browser DevTools
    "los.sid": "90ovz2guzpl8889ir34dx7swo",
}

# Field names to try when looking for a player's Valorant Riot ID in the API response.
# The script will try each in order and stop at the first non-empty value.
PLAYER_NICK_FIELDS = [
    "stdActNick",       # standard activity nick (most common in LeagueOS)
    "valorantRiotId",
    "riotId",
    "gameNick",
]

PUUID_DELAY = 0.4   # seconds between Riot API calls


# ── LeagueOS helpers ──────────────────────────────────────────────────────────

def fetch_schools() -> list[dict]:
    """
    Fetch all NECC school groups from the LeagueOS API.
    Returns a list of dicts each with at least '_id' and 'name'.
    """
    url    = "https://api.leagueos.gg/league/groups"
    params = {"type": "school"}

    print(f"  GET {url}")
    try:
        resp = requests.get(
            url,
            headers=LEAGUEOS_HEADERS,
            cookies=LEAGUEOS_COOKIES,
            params=params,
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()

        # Try several common response shapes
        schools = (
            data.get("data", {}).get("groups")
            or data.get("data", {}).get("items")
            or data.get("groups")
            or data.get("items")
            or []
        )

        if not schools and isinstance(data, list):
            schools = data

        if not schools:
            print("  WARNING: Could not find schools list in response.")
            print("  Response keys:", list(data.keys()) if isinstance(data, dict) else type(data))

        return schools

    except requests.exceptions.HTTPError as e:
        print(f"  HTTP {e.response.status_code} fetching school list — cookies may be expired.")
        return []
    except Exception as e:
        print(f"  Failed to fetch school list: {e}")
        return []


def get_school_extended(school_id: str) -> dict:
    url = f"https://api.leagueos.gg/league/groups/{school_id}/extended?hidden=0"
    resp = requests.get(
        url,
        headers=LEAGUEOS_HEADERS,
        cookies=LEAGUEOS_COOKIES,
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def build_logo_url(icon_id: str | None) -> str | None:
    if not icon_id:
        return None
    return f"https://images.leagueos.gg/{icon_id}"


# ── Player extraction ─────────────────────────────────────────────────────────

def parse_riot_id(raw: str) -> tuple[str, str] | None:
    m = re.match(r"^(.+?)\s*#\s*(\S+)$", raw.strip())
    return (m.group(1).strip(), m.group(2).strip()) if m else None


def extract_player_riot_id(member: dict) -> str | None:
    """Try known field names to find a Valorant Riot ID (GameName#Tag)."""
    for field in PLAYER_NICK_FIELDS:
        val = member.get(field, "")
        if val and "#" in str(val):
            return str(val).strip()

    # Last resort: display name / username if it looks like a Riot ID
    for fname in ("displayName", "username", "name"):
        val = member.get(fname, "")
        if val and "#" in str(val):
            return str(val).strip()

    return None


def extract_teams(extended_json: dict, school_name: str, logo_url: str | None,
                  debug_raw: bool = False) -> list[dict]:
    """
    Pull Valorant teams + players out of a school's extended API response.

    Set debug_raw=True to print the raw JSON — useful for verifying field names.
    """
    if debug_raw:
        print("\n  [DEBUG] Raw extended response:")
        print(json.dumps(extended_json, indent=2)[:3000])
        print("  ... (truncated)")

    data  = extended_json.get("data", {})
    teams = data.get("teams", [])

    result = []
    for team in teams:
        if team.get("stdAct") != "valorant":
            continue

        team_name = (team.get("name") or "").strip() or school_name

        # Players may be nested under several keys
        raw_members = (
            team.get("members")
            or team.get("players")
            or team.get("users")
            or []
        )

        players = []
        for member in raw_members:
            display_name = (
                member.get("displayName")
                or member.get("username")
                or member.get("name")
                or ""
            ).strip()

            role = (
                member.get("rolGame")
                or member.get("role")
                or member.get("position")
                or None
            )

            riot_id = extract_player_riot_id(member)
            rid     = parse_riot_id(riot_id) if riot_id else None

            players.append({
                "team_name":    team_name,
                "school":       school_name,
                "display_name": display_name,
                "role":         role,
                "riot_id":      riot_id,
                "game_name":    rid[0] if rid else None,
                "tag_line":     rid[1] if rid else None,
                "puuid":        None,
                "puuid_status": "no_riot_id" if not rid else "pending",
            })

        result.append({
            "team_name": team_name,
            "school":    school_name,
            "logo_url":  logo_url,
            "players":   players,
        })

    return result


# ── Merge ─────────────────────────────────────────────────────────────────────

def merge_with_existing(fresh_teams: list[dict], existing_teams: list[dict]) -> list[dict]:
    """
    Carry over already-resolved PUUIDs so we don't re-hit the Riot API.
    Key: (team_name, riot_id)
    """
    existing_map: dict[tuple, dict] = {}
    for t in existing_teams:
        for p in t["players"]:
            key = (p.get("team_name") or t.get("team_name", ""), p.get("riot_id", ""))
            existing_map[key] = p

    for t in fresh_teams:
        for p in t["players"]:
            key  = (p["team_name"], p.get("riot_id", ""))
            prev = existing_map.get(key)
            if prev and prev.get("puuid_status") in ("found", "not_found"):
                p["puuid"]        = prev["puuid"]
                p["puuid_status"] = prev["puuid_status"]

    return fresh_teams


# ── Riot API PUUID resolution ─────────────────────────────────────────────────

def resolve_puuid(game_name: str, tag_line: str) -> tuple[str | None, str]:
    """
    Returns (puuid, status).
    status is one of: "found", "not_found", "rate_limited", "error"
    """
    if not RIOT_API_KEY:
        return None, "error"

    url = f"{RIOT_ACCOUNT_BASE}/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
    try:
        resp = requests.get(
            url,
            headers={"X-Riot-Token": RIOT_API_KEY},
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json().get("puuid"), "found"
        if resp.status_code == 404:
            return None, "not_found"
        if resp.status_code == 429:
            return None, "rate_limited"
        return None, "error"
    except Exception:
        return None, "error"


def enrich_with_puuids(teams: list[dict]) -> list[dict]:
    """
    Attempt PUUID lookup for every player whose status is 'pending'.
    Stops ALL lookups immediately on first rate-limit and marks remaining as 'rate_limited'.
    """
    pending = [(t, p) for t in teams for p in t["players"] if p["puuid_status"] == "pending"]
    total   = len(pending)

    if total == 0:
        print("  Nothing to look up — all players already resolved.")
        return teams

    print(f"  {total} player(s) to look up …\n")
    rate_limited = False

    for i, (_, player) in enumerate(pending, 1):
        gn = player["game_name"]
        tl = player["tag_line"]
        print(f"  [{i:>3}/{total}] {gn}#{tl}", end=" … ", flush=True)

        if rate_limited:
            player["puuid_status"] = "rate_limited"
            player["puuid"]        = None
            print("skipped (rate limited)")
            continue

        puuid, status = resolve_puuid(gn, tl)
        player["puuid"]        = puuid
        player["puuid_status"] = status

        if status == "found":
            print(puuid)
        elif status == "rate_limited":
            rate_limited = True
            print("RATE LIMITED — marking remaining as rate_limited")
        elif status == "not_found":
            print("NOT FOUND")
        else:
            print("ERROR")

        time.sleep(PUUID_DELAY)

    return teams


# ── Summary ───────────────────────────────────────────────────────────────────

def print_summary(teams: list[dict]):
    from collections import Counter
    status_counts = Counter(p["puuid_status"] for t in teams for p in t["players"])
    total = sum(status_counts.values())

    print(f"\n{'='*72}")
    print("RESULTS")
    print(f"{'='*72}")

    icons = {
        "found":       "✓",
        "not_found":   "✗",
        "rate_limited": "⏳",
        "no_riot_id":  "—",
        "error":       "!",
        "pending":     "?",
    }

    for team in teams:
        players = team["players"]
        print(f"\n  ┌─ {team['team_name']}  ({team['school']})")
        for p in players:
            icon  = icons.get(p["puuid_status"], "?")
            role  = f"{p['role']:<10}" if p["role"] else "          "
            rid   = p["riot_id"] or f"({p['display_name']})"
            value = p["puuid"] or p["puuid_status"].upper()
            print(f"  │  [{icon}] [{role}]  {rid:<35}  {value}")
        print(f"  └{'─'*70}")

    print(f"\n  Teams:          {len(teams)}")
    print(f"  Total players:  {total}")
    print(f"  ✓  Found:       {status_counts['found']}")
    print(f"  ✗  Not found:   {status_counts['not_found']}")
    print(f"  ⏳ Rate limited: {status_counts['rate_limited']}  (re-run to retry)")
    print(f"  —  No Riot ID:  {status_counts['no_riot_id']}")
    if status_counts["error"]:
        print(f"  !  Errors:      {status_counts['error']}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 72)
    print("NECC Valorant Teams + PUUID Builder")
    print("=" * 72)

    if not RIOT_API_KEY:
        print("ERROR: RIOT_API_KEY not set in .env")
        return

    # Step 1: Fetch school list
    print("\n[STEP 1] Fetching NECC school list from LeagueOS API …")
    schools = fetch_schools()

    if not schools:
        print("  No schools returned. Check cookies/endpoint. Exiting.")
        print("  Tip: update 'los.sid' in LEAGUEOS_COOKIES from browser DevTools.")
        return

    print(f"  {len(schools)} school(s) found.")

    # Step 2: For each school, fetch extended data and extract Valorant teams
    print("\n[STEP 2] Fetching team/player data for each school …")
    all_teams: list[dict] = []
    debug_printed = False   # Print raw JSON for the first school to verify field names

    for i, school in enumerate(schools, 1):
        school_id   = school.get("_id") or school.get("id") or school.get("groupId", "")
        school_name = school.get("name") or school.get("schoolName") or f"School {i}"

        if not school_id:
            print(f"  [{i}/{len(schools)}] Skipping — no ID: {school_name}")
            continue

        try:
            extended = get_school_extended(school_id)
            logo_url = build_logo_url(extended.get("data", {}).get("avatar"))

            # Print raw JSON for the first school so you can verify player field names
            teams = extract_teams(extended, school_name, logo_url, debug_raw=not debug_printed)
            debug_printed = True

            if teams:
                all_teams.extend(teams)
                player_count = sum(len(t["players"]) for t in teams)
                print(f"  [{i}/{len(schools)}] {school_name} — {len(teams)} team(s), {player_count} player(s)")
            else:
                pass  # No Valorant teams at this school — skip silently

        except requests.exceptions.HTTPError as e:
            print(f"  [{i}/{len(schools)}] HTTP {e.response.status_code}: {school_name}")
        except Exception as e:
            print(f"  [{i}/{len(schools)}] Error: {school_name} — {e}")

        time.sleep(0.5)

    print(f"\n  Total Valorant teams found: {len(all_teams)}")

    if not all_teams:
        print("  No Valorant teams found. Check PLAYER_NICK_FIELDS or API structure.")
        return

    # Step 3: Carry over already-resolved PUUIDs from existing output file
    if OUT_FILE.exists():
        print(f"\n[STEP 3] Loading existing results from {OUT_FILE.name} …")
        with open(OUT_FILE) as f:
            existing = json.load(f)
        all_teams = merge_with_existing(all_teams, existing)
        skipped = sum(1 for t in all_teams for p in t["players"] if p["puuid_status"] in ("found", "not_found"))
        pending = sum(1 for t in all_teams for p in t["players"] if p["puuid_status"] == "pending")
        print(f"  {skipped} already resolved (skipping)  |  {pending} to look up")
    else:
        print("\n[STEP 3] No existing file — looking up all players.")

    # Step 4: Resolve PUUIDs for pending players
    print("\n[STEP 4] Resolving PUUIDs via Riot API …")
    all_teams = enrich_with_puuids(all_teams)

    # Step 5: Summary + save
    print_summary(all_teams)

    with open(OUT_FILE, "w") as f:
        json.dump(all_teams, f, indent=2)
    print(f"\n  Saved to {OUT_FILE}")


if __name__ == "__main__":
    main()
