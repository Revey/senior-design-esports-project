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


# Return values for get_puuid_by_riot_id:
PUUID_RATE_LIMITED = "RATE_LIMITED"   # 429 — hit API limit, retry later
PUUID_NOT_FOUND    = "NOT_FOUND"      # 404 — account doesn't exist / name changed
PUUID_ERROR        = "ERROR"          # unexpected status code


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