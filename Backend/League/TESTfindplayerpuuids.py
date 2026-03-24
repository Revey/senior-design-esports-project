"""
TESTfindplayerpuuids.py
--------------
Scrapes every team and player from the 2025 CLOL Championship page on
universityesportsna.riotgames.com, then resolves each player's Riot ID to a
PUUID using the existing get_puuid_by_riot_id() helper in RiotAPI.py.

Requirements:
    pip install playwright python-dotenv requests
    playwright install chromium
"""

import json
import re
import time
import requests
 
from RiotAPI import get_puuid_by_riot_id
 
# ── Config ────────────────────────────────────────────────────────────────────
# League of Legends game ID used in this showcase (filters gameNicks)
LOL_GAME_ID = "XS3bzSuFXwkHcDL2P"
 
API_URL = (
    "https://api-ggtech.leagueoflegends.com/api/v001"
    "/showcase/university-united-states-and-canada"
    "/tournament-endpoint/2025-clol-championship"
)
 
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
    """Return (game_name, tag_line) from 'Name#TAG', else None."""
    m = re.match(r"^(.+?)\s*#\s*(\S+)$", raw.strip())
    return (m.group(1).strip(), m.group(2).strip()) if m else None
 
 
def fetch_tournament() -> dict:
    print(f"  GET {API_URL}")
    r = requests.get(API_URL, headers=HEADERS, timeout=20)
    r.raise_for_status()
    data = r.json()
    with open("raw_tournament.json", "w") as f:
        json.dump(data, f, indent=2)
    print("  Cached to raw_tournament.json")
    return data
 
 
# ── Parsing ───────────────────────────────────────────────────────────────────
 
def extract_teams(data: dict) -> list[dict]:
    """
    Parse returnData.members into clean team dicts.
 
    JSON shape (per team):
        name         -> team name
        institution  -> {name: "University Name"}
        members[]    -> [{userId, rolGame, ...}]   (role info)
        users[]      -> [{_id, displayName, profile.gameNicks[]}]  (player profiles)
    """
    teams = []
 
    for m in data["returnData"]["members"]:
        team_name   = m.get("name", "Unknown Team")
        institution = m.get("institution") or {}
        school      = institution.get("name", "") if isinstance(institution, dict) else ""
 
        # Build userId -> rolGame lookup from the members array
        role_map = {mem["userId"]: mem.get("rolGame") for mem in m.get("members", []) if mem.get("userId")}
 
        players = []
        for user in m.get("users", []):
            user_id      = user.get("_id", "")
            display_name = user.get("displayName") or user.get("username") or ""
            role         = role_map.get(user_id)
 
            # Find the LoL Riot ID in gameNicks (filter by LOL_GAME_ID)
            lol_nick = None
            for gn in (user.get("profile") or {}).get("gameNicks", []):
                if gn.get("id") == LOL_GAME_ID:
                    lol_nick = gn.get("nick", "").strip()
                    break
 
            # Fallback: use displayName if it contains '#' and looks like a Riot ID
            if not lol_nick and "#" in display_name:
                lol_nick = display_name.strip()
 
            rid = parse_riot_id(lol_nick) if lol_nick else None
 
            players.append({
                "display_name": display_name,
                "role":         role,
                "riot_id":      lol_nick,
                "game_name":    rid[0] if rid else None,
                "tag_line":     rid[1] if rid else None,
                "puuid":        None,
            })
 
        teams.append({
            "team_name": team_name,
            "school":    school,
            "players":   players,
        })
 
    return teams
 
 
# ── PUUID resolution ──────────────────────────────────────────────────────────
 
def enrich_with_puuids(teams: list[dict]) -> list[dict]:
    total = sum(len(t["players"]) for t in teams)
    done  = 0
 
    for team in teams:
        for player in team["players"]:
            done += 1
            gn = player["game_name"]
            tl = player["tag_line"]
 
            if gn and tl:
                print(f"  [{done:>3}/{total}] {gn}#{tl}", end=" … ", flush=True)
                puuid = get_puuid_by_riot_id(gn, tl)
                player["puuid"] = puuid
                print(puuid if puuid else "NOT FOUND")
                time.sleep(0.4)   # stay under Riot rate limit
            else:
                player["puuid"] = None
                print(f"  [{done:>3}/{total}] SKIP — no LoL nick for '{player['display_name']}'")
 
    return teams
 
 
# ── Output ────────────────────────────────────────────────────────────────────
 
def print_summary(teams: list[dict]):
    total_players = sum(len(t["players"]) for t in teams)
    found_puuids  = sum(1 for t in teams for p in t["players"] if p["puuid"])
 
    print(f"\n{'='*72}")
    print("RESULTS")
    print(f"{'='*72}")
 
    for team in teams:
        players  = team["players"]
        resolved = [p for p in players if p["puuid"]]
        print(f"\n  ┌─ {team['team_name']}")
        if team["school"]:
            print(f"  │   {team['school']}")
        print(f"  │   {len(resolved)}/{len(players)} PUUIDs resolved")
        print(f"  │")
        for p in players:
            ok    = "✓" if p["puuid"] else "✗"
            role  = f"{p['role']:<9}" if p["role"] else "         "
            rid   = p["riot_id"] or f"({p['display_name']})"
            puuid = p["puuid"] or "NOT FOUND"
            print(f"  │  [{ok}] [{role}]  {rid:<35}  {puuid}")
        print(f"  └{'─'*70}")
 
    print(f"\n  Teams:          {len(teams)}")
    print(f"  Total players:  {total_players}")
    print(f"  PUUIDs found:   {found_puuids}")
    print(f"  Missing:        {total_players - found_puuids}")
 
 
# ── Main ──────────────────────────────────────────────────────────────────────
 
def main():
    print("=" * 72)
    print("2025 CLOL Championship Scraper")
    print("=" * 72)
 
    # Step 1: fetch (or load from cache)
    print("\n[STEP 1] Fetching tournament data …")
    try:
        data = fetch_tournament()
    except Exception as e:
        print(f"  API call failed: {e}")
        print("  Trying cached raw_tournament.json …")
        try:
            with open("raw_tournament.json") as f:
                data = json.load(f)
            print("  Loaded from cache.")
        except FileNotFoundError:
            print("  ERROR: No cache found. Check your network connection.")
            return
 
    # Step 2: parse
    print("\n[STEP 2] Parsing teams and players …")
    teams = extract_teams(data)
    total = sum(len(t["players"]) for t in teams)
    parseable = sum(1 for t in teams for p in t["players"] if p["game_name"])
    print(f"  {len(teams)} teams  |  {total} players  |  {parseable} with LoL Riot IDs")
 
    # Step 3: PUUIDs
    print("\n[STEP 3] Resolving PUUIDs via Riot API …")
    teams = enrich_with_puuids(teams)
 
    # Step 4: print + save
    print_summary(teams)
 
    out = "clol_teams_puuids.json"
    with open(out, "w") as f:
        json.dump(teams, f, indent=2)
    print(f"\n  Saved to {out}")
 
 
if __name__ == "__main__":
    main()