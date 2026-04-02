import os
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load .env from Backend/.env
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

RIOT_API_KEY = os.getenv("RIOT_API_KEY")
if not RIOT_API_KEY:
    raise ValueError(f"RIOT_API_KEY not found in {ENV_PATH}")

DEFAULT_HEADERS = {
    "X-Riot-Token": RIOT_API_KEY,
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://developer.riotgames.com",
}


def riot_get(url: str, params=None):
    """
    Generic helper for Riot GET requests.
    Returns the response object so each function can decide how to handle status codes.
    """
    return requests.get(url, headers=DEFAULT_HEADERS, params=params, timeout=20)


# ── PUUID lookup ──────────────────────────────────────────────────────────────

PUUID_RATE_LIMITED = "RATE_LIMITED"
PUUID_NOT_FOUND    = "NOT_FOUND"
PUUID_ERROR        = "ERROR"


def get_puuid_by_riot_id(game_name: str, tag_line: str):
    """
    Returns the player's PUUID using Riot ID (gameName#tagLine).

    Return values:
        str (puuid)          — success
        PUUID_NOT_FOUND      — 404, account not found or name changed
        PUUID_RATE_LIMITED   — 429, hit rate limit (retry later)
        PUUID_ERROR          — unexpected HTTP error
        None                 — network/request exception
    """
    encoded_name = requests.utils.quote(game_name, safe="")
    encoded_tag  = requests.utils.quote(tag_line,  safe="")

    url = (
        "https://americas.api.riotgames.com"
        f"/riot/account/v1/accounts/by-riot-id/{encoded_name}/{encoded_tag}"
    )

    try:
        resp = riot_get(url)
    except Exception as e:
        print(f"  [EXCEPTION] {game_name}#{tag_line}: {e}")
        return None

    if resp.status_code == 200:
        return resp.json().get("puuid")
    if resp.status_code == 404:
        return PUUID_NOT_FOUND
    if resp.status_code == 429:
        print(f"  [RATE LIMITED] {game_name}#{tag_line}")
        return PUUID_RATE_LIMITED

    print(f"  [HTTP {resp.status_code}] {game_name}#{tag_line}")
    return PUUID_ERROR


# ── Champion mastery ──────────────────────────────────────────────────────────

MASTERY_RATE_LIMITED = "RATE_LIMITED"
MASTERY_NOT_FOUND    = "NOT_FOUND"
MASTERY_ERROR        = "ERROR"

# Module-level cache so Data Dragon is only fetched once per process run.
_CHAMPION_ID_MAP: dict[str, str] = {}


def _load_champion_id_map() -> dict[str, str]:
    """
    Fetches the latest champion data from Data Dragon and returns a mapping of
    champion key (numeric string) → champion name.  Falls back to {} on failure.
    """
    global _CHAMPION_ID_MAP
    if _CHAMPION_ID_MAP:
        return _CHAMPION_ID_MAP

    try:
        versions_resp = requests.get(
            "https://ddragon.leagueoflegends.com/api/versions.json", timeout=10
        )
        versions_resp.raise_for_status()
        latest_version = versions_resp.json()[0]

        champ_resp = requests.get(
            f"https://ddragon.leagueoflegends.com/cdn/{latest_version}/data/en_US/champion.json",
            timeout=10,
        )
        champ_resp.raise_for_status()
        champ_data = champ_resp.json().get("data", {})

        # champ_data format: { "Aatrox": { "key": "266", ... }, ... }
        _CHAMPION_ID_MAP = {info["key"]: name for name, info in champ_data.items()}
        print(f"  [Data Dragon] Loaded {len(_CHAMPION_ID_MAP)} champion entries (patch {latest_version})")
    except Exception as e:
        print(f"  [WARNING] Could not load champion ID map from Data Dragon: {e}")
        _CHAMPION_ID_MAP = {}

    return _CHAMPION_ID_MAP


def get_champion_masteries(puuid: str, count: int = 5):
    """
    Returns the top `count` champion masteries for a player by PUUID,
    using the NA1 regional endpoint.

    Endpoint: GET /lol/champion-mastery/v4/champion-masteries/by-puuid/{encryptedPUUID}/top

    Each entry in the returned list is a dict:
        {
            "champion":        str,   # champion name from Data Dragon
            "champion_id":     int,   # raw Riot champion ID
            "mastery_level":   int,   # mastery level (1–10)
            "mastery_points":  int,   # total mastery points
        }

    Return values:
        list[dict]           — success (may be empty if player has no mastery data)
        MASTERY_NOT_FOUND    — 404
        MASTERY_RATE_LIMITED — 429 (retry after backing off)
        MASTERY_ERROR        — unexpected HTTP status
        None                 — network / request exception
    """
    encoded_puuid = requests.utils.quote(puuid, safe="")
    url = (
        "https://na1.api.riotgames.com"
        f"/lol/champion-mastery/v4/champion-masteries/by-puuid/{encoded_puuid}/top"
    )

    try:
        resp = riot_get(url, params={"count": count})
    except Exception as e:
        print(f"  [EXCEPTION] mastery for puuid {puuid[:12]}…: {e}")
        return None

    if resp.status_code == 200:
        champ_map = _load_champion_id_map()
        results = []
        for entry in resp.json():
            champ_id   = entry.get("championId", 0)
            champ_name = champ_map.get(str(champ_id), f"Champion_{champ_id}")
            results.append({
                "champion":       champ_name,
                "champion_id":    champ_id,
                "mastery_level":  entry.get("championLevel", 0),
                "mastery_points": entry.get("championPoints", 0),
            })
        return results

    if resp.status_code == 404:
        return MASTERY_NOT_FOUND

    if resp.status_code == 429:
        print(f"  [RATE LIMITED] mastery for puuid {puuid[:12]}…")
        return MASTERY_RATE_LIMITED

    print(f"  [HTTP {resp.status_code}] mastery for puuid {puuid[:12]}…")
    return MASTERY_ERROR