"""Shared MongoDB connection singleton."""

import os
from pymongo import MongoClient
import certifi
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "")
MONGO_DB = os.getenv("MONGO_DB", "senior_design_esports")

_mongo_client = None


def get_db():
    global _mongo_client
    if not MONGO_URI:
        return None
    if _mongo_client is None:
        _mongo_client = MongoClient(MONGO_URI, tls=True, tlsCAFile=certifi.where())
    return _mongo_client[MONGO_DB]
