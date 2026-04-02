"""
pip install pymongo python-dotenv certifi

"""
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import PyMongoError
import certifi


def load_json_file(file_path: Path):
    with file_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def normalize_to_list(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [data]
    raise ValueError("JSON must contain either a list of objects or a single object.")


def main():
    load_dotenv()

    mongo_uri = os.getenv("MONGO_URI")
    mongo_db_name = os.getenv("MONGO_DB", "senior_design_esports")
    mongo_collection_name = os.getenv("MONGO_COLLECTION", "CLOL")

    if not mongo_uri:
        raise ValueError("Missing MONGO_URI in .env")

    script_dir = Path(__file__).resolve().parent
    json_file = script_dir / "clol_teams_puuids.json"

    if not json_file.exists():
        raise FileNotFoundError(f"Could not find file: {json_file}")

    data = load_json_file(json_file)
    documents = normalize_to_list(data)

    client = MongoClient(
        mongo_uri,
        tls=True,
        tlsCAFile=certifi.where()
    )

    try:
        db = client[mongo_db_name]
        collection = db[mongo_collection_name]

        # Optional but strongly recommended:
        # ensures team_name stays unique in this collection
        collection.create_index("team_name", unique=True)

        inserted_count = 0
        replaced_count = 0

        for doc in documents:
            if not isinstance(doc, dict):
                print("Skipping non-object entry in JSON.")
                continue

            team_name = doc.get("team_name")
            if not team_name:
                print("Skipping document with no team_name:", doc)
                continue

            result = collection.replace_one(
                {"team_name": team_name},
                doc,
                upsert=True
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