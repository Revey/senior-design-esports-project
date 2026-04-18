"""Migrate from flat `leagues` collection to org/season/conference hierarchy.

Drops the legacy `leagues` collection (it's safe to overwrite per user), clears
`leagueId` on existing match docs (preserving `leagueName` for display), and
seeds fresh `organizations` docs for CVAL, NECC, NACE, and ECAC. Seasons and
conferences are left empty — the admin will create them via /admin/leagues.

Usage:
    cd Backend && python3 migrate_leagues.py [--dry-run]
"""

from __future__ import annotations

import argparse
import os
import re
from datetime import datetime, timezone

import certifi
from dotenv import load_dotenv
from pymongo import MongoClient


SEED_ORGS = [
    {
        "name": "Collegiate Valorant",
        "abbreviation": "CVAL",
        "games": ["Valorant"],
    },
    {
        "name": "National Esports Collegiate Conference",
        "abbreviation": "NECC",
        "games": ["Valorant", "League of Legends"],
    },
    {
        "name": "National Association of Collegiate Esports",
        "abbreviation": "NACE",
        "games": ["Valorant", "League of Legends"],
    },
    {
        "name": "Eastern College Athletic Conference",
        "abbreviation": "ECAC",
        "games": ["Valorant", "League of Legends"],
    },
]


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

    print(f"Target DB: {db_name}  (dry-run={args.dry_run})")

    legacy_leagues = list(db["leagues"].find({}))
    print(f"Legacy leagues found: {len(legacy_leagues)}")
    for L in legacy_leagues:
        print(f"  - {L.get('abbreviation') or L.get('name')} ({L.get('game')})")

    matches_with_leagueid = db["matches"].count_documents({"leagueId": {"$ne": None}})
    print(f"Matches with leagueId set: {matches_with_leagueid}")

    now = datetime.now(timezone.utc).isoformat()

    if args.dry_run:
        print("\n[dry-run] Would:")
        print("  - Drop `leagues` collection")
        print(f"  - Clear leagueId on {matches_with_leagueid} match docs (leagueName preserved)")
        for o in SEED_ORGS:
            print(f"  - Upsert organizations/{o['abbreviation']} -> {o['name']} {o['games']}")
        return

    # Drop legacy collection
    db["leagues"].drop()
    print("Dropped `leagues` collection.")

    # Clear leagueId on matches but keep leagueName for display
    res = db["matches"].update_many(
        {"leagueId": {"$ne": None}},
        {"$set": {"leagueId": None}},
    )
    print(f"Cleared leagueId on {res.modified_count} matches.")

    # Seed organizations (upsert by slug)
    db["organizations"].create_index("slug", unique=True, background=True)
    for o in SEED_ORGS:
        slug = slugify(o["abbreviation"])
        db["organizations"].update_one(
            {"slug": slug},
            {
                "$setOnInsert": {
                    "name": o["name"],
                    "abbreviation": o["abbreviation"],
                    "slug": slug,
                    "games": o["games"],
                    "createdAt": now,
                }
            },
            upsert=True,
        )
        print(f"Upserted org: {o['abbreviation']}")

    # Ensure hierarchy indexes exist
    db["seasons"].create_index(
        [("orgId", 1), ("year", 1), ("semester", 1)],
        unique=True, name="uniq_season", background=True,
    )
    db["conferences"].create_index(
        [("orgId", 1), ("slug", 1)],
        unique=True, name="uniq_conf_slug", background=True,
    )
    db["team_memberships"].create_index(
        [("teamId", 1), ("conferenceId", 1), ("seasonId", 1)],
        unique=True, name="uniq_membership", background=True,
    )
    print("Indexes ensured.")

    print("Migration complete.")


if __name__ == "__main__":
    main()
