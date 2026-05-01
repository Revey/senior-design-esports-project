"""Upsert NECC Valorant team rosters into the PostgreSQL `players` table.

Reads `necc_val_teams_puuids.json` (produced by BuildNecc_val_teams_puuids.py),
iterates each team's player list, and upserts one row per player into `players`
keyed on riot_puuid via INSERT ... ON CONFLICT DO UPDATE.

Requires DATABASE_URL to be set in the environment.

Run from the Backend/ directory:
    python archive/StorePlayer.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.db import get_cursor  # noqa: E402


GAME = "Valorant"


def _iter_players(teams: Iterable[dict]) -> Iterable[tuple[dict, dict]]:
    for team in teams:
        for player in team.get("players", []) or []:
            yield team, player


def _slugify(s: str) -> str:
    import re

    s = (s or "").lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-") or None


def main() -> None:
    load_dotenv()

    if not os.getenv("DATABASE_URL"):
        raise SystemExit("Missing DATABASE_URL in environment")

    json_file = Path(__file__).resolve().parent / "necc_val_teams_puuids.json"
    if not json_file.exists():
        raise FileNotFoundError(
            f"Could not find {json_file}. Run BuildNecc_val_teams_puuids.py first."
        )

    with json_file.open("r", encoding="utf-8") as f:
        data = json.load(f)
    teams = data if isinstance(data, list) else [data]

    inserted = 0
    updated = 0
    skipped = 0

    with get_cursor(commit=True) as cur:
        for team, player in _iter_players(teams):
            puuid = (player.get("puuid") or "").strip() or None
            display_name = (player.get("display_name") or player.get("game_name") or "").strip()
            if not display_name:
                skipped += 1
                continue

            riot_id = (player.get("riot_id") or "").strip() or None
            game_name = (player.get("game_name") or "").strip() or None
            tag_line = (player.get("tag_line") or "").strip() or None
            role = (player.get("role") or "").strip() or None
            slug = _slugify(f"{display_name}-{team.get('team_name', '')}")

            if puuid:
                cur.execute(
                    """
                    INSERT INTO players (
                        slug, display_name, riot_id, riot_puuid,
                        game_name, tag_line, role, game, last_updated
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (riot_puuid) DO UPDATE SET
                        display_name = EXCLUDED.display_name,
                        riot_id = EXCLUDED.riot_id,
                        game_name = EXCLUDED.game_name,
                        tag_line = EXCLUDED.tag_line,
                        role = COALESCE(EXCLUDED.role, players.role),
                        game = EXCLUDED.game,
                        last_updated = NOW()
                    RETURNING (xmax = 0) AS inserted
                    """,
                    (slug, display_name, riot_id, puuid, game_name, tag_line, role, GAME),
                )
                was_inserted = cur.fetchone()["inserted"]
            else:
                cur.execute(
                    """
                    INSERT INTO players (
                        slug, display_name, riot_id, game_name, tag_line, role, game, last_updated
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (slug) DO UPDATE SET
                        display_name = EXCLUDED.display_name,
                        riot_id = EXCLUDED.riot_id,
                        game_name = EXCLUDED.game_name,
                        tag_line = EXCLUDED.tag_line,
                        role = COALESCE(EXCLUDED.role, players.role),
                        game = EXCLUDED.game,
                        last_updated = NOW()
                    RETURNING (xmax = 0) AS inserted
                    """,
                    (slug, display_name, riot_id, game_name, tag_line, role, GAME),
                )
                was_inserted = cur.fetchone()["inserted"]

            if was_inserted:
                inserted += 1
            else:
                updated += 1

    print(f"Done syncing NECC Valorant rosters → players")
    print(f"Inserted: {inserted}")
    print(f"Updated:  {updated}")
    print(f"Skipped:  {skipped}")
    print(f"Source:   {json_file.name}")


if __name__ == "__main__":
    main()
