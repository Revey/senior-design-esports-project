"""Deprecated — left in place so existing instructions/scripts don't break.

The original `migrate.py` backfilled admin-era fields (slug, schoolId,
wins/losses counters, and a `schools` collection) onto legacy MongoDB `teams`
documents created before the Admin-Page branch landed.

With the Postgres migration, those fields are part of the schema from the
start (see `schema.sql`) — new columns are NOT NULL with defaults, and both
`seed_data.py` and the admin router populate them on every insert. No legacy
data exists to backfill.

If a future Postgres-era migration is needed, add it as a dedicated script
under `Backend/migrations/` rather than reusing this file.

Running this script is a no-op.
"""

from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Ignored; kept for CLI compatibility.")
    parser.parse_args()

    print(
        "migrate.py is a no-op under the Postgres schema. "
        "See the module docstring for details."
    )


if __name__ == "__main__":
    main()
