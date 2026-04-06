"""Configuration loaded from environment variables."""

import os
from dotenv import load_dotenv

load_dotenv()

# Riot Games API
RIOT_API_KEY = os.getenv("RIOT_API_KEY", "")
RIOT_REGION = os.getenv("RIOT_REGION", "na1")          # na1, eu, ap, kr
RIOT_ACCOUNT_REGION = os.getenv("RIOT_ACCOUNT_REGION", "americas")  # americas, europe, asia, sea

# Base URLs
RIOT_ACCOUNT_BASE = f"https://{RIOT_ACCOUNT_REGION}.api.riotgames.com"
RIOT_VAL_BASE = f"https://{RIOT_REGION}.api.riotgames.com"

# Tracker.gg scraping
TRACKER_BASE_URL = "https://tracker.gg/valorant/profile/riot"
SCRAPE_DELAY = float(os.getenv("SCRAPE_DELAY", "2.0"))   # seconds between requests

# Server
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# Cache (simple in-memory TTL in seconds)
CACHE_TTL = int(os.getenv("CACHE_TTL", "300"))           # 5 minutes

# MongoDB
MONGO_URI = os.getenv("MONGO_URI", "")
MONGO_DB  = os.getenv("MONGO_DB", "senior_design_esports")
