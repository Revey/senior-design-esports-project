"""One-off migration: backfill admin-era fields on legacy teams.

Adds missing `slug`, `schoolId`, `wins`, `losses`, `mapWins`, `mapLosses` to
`teams` docs that were created before the Admin-Page branch landed. Also
ensures a `schools` doc exists for each legacy `school` string so the
frontend typeahead works consistently.

Usage:
    cd Backend && python3 migrate.py [--dry-run]
"""

from __future__ import annotations

import argparse
import os
import re
from datetime import datetime, timezone

import certifi
from dotenv import load_dotenv
from pymongo import MongoClient


def slugify(s: str) -> str:
    s = (s or "").lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    load_dotenv()
    uri = os.getenv("MONGO_URI")
    if not uri:
        raise SystemExit("MONGO_URI not set")
    db_name = os.getenv("MONGO_DB", "senior_design_esports")

    client = MongoClient(uri, tls=True, tlsCAFile=certifi.where())
    db = client[db_name]

    teams = db["teams"]
    schools = db["schools"]

    # 1. Ensure a school doc exists for each legacy school string.
    distinct_schools = teams.distinct("school")
    created_schools = 0
    school_by_name: dict[str, object] = {}
    for name in distinct_schools:
        if not name:
            continue
        slug = slugify(name)
        doc = schools.find_one({"slug": slug})
        if doc:
            school_by_name[name] = doc["_id"]
            continue
        if args.dry_run:
            print(f"[dry-run] would create school: {name}")
            continue
        res = schools.insert_one({
            "name": name,
            "slug": slug,
            "createdAt": datetime.now(timezone.utc).isoformat(),
        })
        school_by_name[name] = res.inserted_id
        created_schools += 1

    # 2. Backfill each team.
    backfilled = 0
    cursor = teams.find({})
    for t in cursor:
        updates: dict[str, object] = {}
        name = t.get("teamName") or t.get("name") or ""
        if not t.get("slug"):
            updates["slug"] = slugify(name)
        if not t.get("schoolId") and t.get("school") in school_by_name:
            updates["schoolId"] = school_by_name[t["school"]]
        for field in ("wins", "losses", "mapWins", "mapLosses"):
            if field not in t:
                updates[field] = 0
        if not updates:
            continue
        if args.dry_run:
            print(f"[dry-run] {name or t.get('_id')}: {list(updates.keys())}")
        else:
            teams.update_one({"_id": t["_id"]}, {"$set": updates})
        backfilled += 1

    mode = "(dry-run)" if args.dry_run else ""
    print(f"Schools created: {created_schools} {mode}".strip())
    print(f"Teams backfilled: {backfilled} {mode}".strip())


if __name__ == "__main__":
    main()
