"""
StorePlayer.py
--------------
Reads necc_val_teams_puuids.json and upserts each team document into the
MongoDB VAL collection.

Mirrors the structure of League/StorePlayer.py.

Requirements: pip install pymongo python-dotenv certifi
Run from the Backend/ directory:
    python valorant/StorePlayer.py
"""

import json
import os
from pathlib import Path

import certifi
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import PyMongoError


def main():
    load_dotenv()

    mongo_uri             = os.getenv("MONGO_URI")
    mongo_db_name         = os.getenv("MONGO_DB", "senior_design_esports")
    mongo_collection_name = os.getenv("VAL_COLLECTION", "VAL")

    if not mongo_uri:
        raise ValueError("Missing MONGO_URI in .env")

    script_dir = Path(__file__).resolve().parent
    json_file  = script_dir / "necc_val_teams_puuids.json"

    if not json_file.exists():
        raise FileNotFoundError(
            f"Could not find {json_file}. Run BuildNecc_val_teams_puuids.py first."
        )

    with json_file.open("r", encoding="utf-8") as f:
        documents = json.load(f)

    if isinstance(documents, dict):
        documents = [documents]

    client = MongoClient(mongo_uri, tls=True, tlsCAFile=certifi.where())

    try:
        db         = client[mongo_db_name]
        collection = db[mongo_collection_name]

        collection.create_index("team_name", unique=True)

        inserted_count = 0
        replaced_count = 0

        for doc in documents:
            if not isinstance(doc, dict):
                print("Skipping non-object entry.")
                continue

            team_name = doc.get("team_name")
            if not team_name:
                print("Skipping document with no team_name:", doc)
                continue

            result = collection.replace_one(
                {"team_name": team_name},
                doc,
                upsert=True,
            )

            if result.matched_count > 0:
                replaced_count += 1
            else:
                inserted_count += 1

        print(f"Finished syncing data to MongoDB.")
        print(f"Inserted: {inserted_count}")
        print(f"Replaced: {replaced_count}")
        print(f"Database: {mongo_db_name}")
        print(f"Collection: {mongo_collection_name}")
        print(f"Source file: {json_file.name}")

    except PyMongoError as e:
        print("MongoDB error:", e)
    finally:
        client.close()


if __name__ == "__main__":
    main()
