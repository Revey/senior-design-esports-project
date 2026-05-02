# Phase 1 — Backend/schema.sql (target Postgres schema, idempotent)

**Migration:** Postgres v2 (Mongo → DigitalOcean Managed Postgres)
**Branch:** `postgres-migration-v2` (continues from Phase 0 commit `31b356d`)
**Phase order:** Phase 1 of seven phases total (Phases 0–6)
**Status:** Locked — awaiting gate-A approval (all open implementation questions resolved with developer-confirmed defaults; see "Decisions made" §below).

## Approval Flow (two gates)

1. **Spec approval (gate A)** — Developer reviews this SPEC + the `codex exec` critique. On approval, implementation begins.
2. **Pre-commit approval (gate B)** — After implementation, developer reviews the actual `Backend/schema.sql` (and the verification output proving it applies cleanly twice in a row). On approval, the commit lands.

---

## Phase Goal

Author a single re-runnable `Backend/schema.sql` file that defines the entire target Postgres schema (tables, indexes, FK constraints, default values) for Campus Rankers Hub. The schema must:

1. Apply cleanly against an empty `postgres:18` Debian database.
2. Apply cleanly *again* against the same database without errors (re-run safety).
3. Cover every entity Phase 3 routers will need to read or write — no "missing column" surprises later.
4. Encode every "hard invariant" from `CONSTITUTION.md` §3 that can be enforced at the DB level (sparse-unique `matches.riot_match_id`, unique `players.riot_puuid`, FK cascade behavior, etc.).
5. Document — in SQL comments or in this SPEC — invariants that **cannot** be enforced at the DB level (e.g. RSO consent gate read filtering) so a future router author knows where the responsibility lives.

**Idempotency caveat:** "Re-runnable without error" is *not* "convergent." `CREATE TABLE IF NOT EXISTS` does **not** repair an existing table whose shape has drifted. If you change a column type or constraint after Phase 1 lands, that is a separate forward-migration script (Phase 1.x or its own phase), not an edit to `schema.sql` that magically retro-applies. The SQL file's job is "from empty → target shape" and "no error if already at target shape." Anything else is out of its scope.

No `core/db.py` changes, no `requirements.txt` changes, no router changes, no application-side code. Just the SQL.

## User Story

> As **the developer (and Phase 2/3/5 implementations)**, I want **a single committed Postgres schema file that is the contractual source of truth for what columns, types, and constraints exist**, so that **router code can be written against it without guessing, and so that local-dev / staging / prod are guaranteed to converge to the same shape.**

## Technical Requirements

### File

- Path: `Backend/schema.sql`
- Encoding: UTF-8, LF line endings.
- Wrapped in a single `BEGIN; … COMMIT;` for atomicity (whole-or-nothing apply).
- Every `CREATE TABLE` uses `IF NOT EXISTS`. Every `CREATE INDEX` and `CREATE UNIQUE INDEX` uses `IF NOT EXISTS`. This makes the file safe to run repeatedly against an unchanged target.
- Header comment block at the top documenting: filename, purpose, date, and the re-runnability/non-convergent caveat from Phase Goal §5.
- No data inserts. No seed rows. (Seeding is its own future task — `seed_data.py` will live separately.)
- **No `DROP` statements except for trigger management.** Postgres has no `CREATE TRIGGER IF NOT EXISTS`, so the only acceptable `DROP` pattern is `DROP TRIGGER IF EXISTS <name> ON <table>; CREATE TRIGGER <name> …`, scoped tightly to a named trigger inside the `BEGIN/COMMIT` block. No `DROP TABLE`, no `DROP INDEX`, no `DROP COLUMN`, no `DROP CONSTRAINT`.
- All idempotency-affecting choices documented in SQL comments at the relevant statements.

### Tables (15 total)

CONSTITUTION.md §3 lists 12 entities. Two architectural deltas bring the count to 15:

1. **Junction table for player↔team↔season** — `players.teamIds[]` (a Mongo array) becomes `team_players` for FK integrity and per-relationship attributes (`joined_at`, `left_at`, `season_id`).
2. **Per-game detail tables for `player_match_stats`** (Path 2 architecture, decided at gate A — see Decisions Made #9). The shared `player_match_stats` core is thinned to truly cross-game columns. Game-specific stats (K/D/A, agent, champion, ACS, CS, gold, etc.) live in 1:1-related per-game tables: `pms_valorant_details` and `pms_lol_details`. Future games (Rocket League, TFT, Smash, etc.) get their own `pms_<game>_details` tables in their own future phase, with no rework to the core.

The 15 tables, in dependency order:

| # | Table | New (vs §3)? |
|---|---|---|
| 1 | `schools` | listed |
| 2 | `organizations` | listed |
| 3 | `seasons` | listed |
| 4 | `conferences` | listed |
| 5 | `teams` | listed |
| 6 | `team_memberships` | listed |
| 7 | `players` | listed |
| 8 | `team_players` | **new junction** (replaces `players.teamIds[]`) |
| 9 | `player_consents` | listed |
| 10 | `matches` | listed |
| 11 | `player_match_stats` | listed (now a thin core — see Decision #9) |
| 12 | `pms_valorant_details` | **new per-game detail** (1:1 with `player_match_stats`) |
| 13 | `pms_lol_details` | **new per-game detail** (1:1 with `player_match_stats`) |
| 14 | `tournaments` | listed |
| 15 | `rso_tokens` | listed |

Listed in dependency order so FK targets exist when referenced.

#### `schools`
- `id BIGSERIAL PRIMARY KEY`
- `name TEXT NOT NULL`
- `slug TEXT NOT NULL UNIQUE` (the UNIQUE constraint already creates a backing index — no separate `idx_schools_slug`)
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

#### `organizations` (governs leagues — CVAL/NECC/NACE/ECAC)
- `id BIGSERIAL PRIMARY KEY`
- `name TEXT NOT NULL`
- `abbreviation TEXT NOT NULL`
- `slug TEXT NOT NULL UNIQUE`
- `games TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[]`
  - `CHECK (cardinality(games) > 0)` — an organization governs at least one game.
  - `CHECK (games <@ ARRAY['valorant', 'lol']::TEXT[])` — only V1 supported games. When we expand the multi-game roadmap, this CHECK gets edited (its own phase).
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

#### `seasons`
- `id BIGSERIAL PRIMARY KEY`
- `org_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT`
- `year INTEGER NOT NULL CHECK (year >= 2000 AND year <= 2100)` — sanity bound; seasons before 2000 or after 2100 are almost certainly bad data
- `semester TEXT NOT NULL CHECK (semester IN ('fall', 'spring', 'summer'))` — winter not included; collegiate calendars don't use it for these leagues
- `label TEXT NOT NULL` — human-readable, e.g. "Fall 2026"
- `active BOOLEAN NOT NULL DEFAULT FALSE`
- `created_at`, `updated_at` as above.
- Index: `idx_seasons_org_active` on `(org_id, active)` for the "active season for this org" query.
- **DB-level enforcement of "one active season per org" via partial unique index:**
  ```sql
  CREATE UNIQUE INDEX IF NOT EXISTS uq_seasons_one_active_per_org
    ON seasons(org_id) WHERE active;
  ```
  This is **stronger** than the "server-side enforced" guarantee CONSTITUTION mentions and removes the race-condition class. Phase 3 still validates at app level for friendly error messages, but the DB is the final guard.

#### `conferences` (flat with `tier` label — see ADR 2026-04-18)
- `id BIGSERIAL PRIMARY KEY`
- `org_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT`
- `name TEXT NOT NULL`
- `short_name TEXT`
- `slug TEXT NOT NULL`
- `tier TEXT` — nullable; e.g. `'Premier'`, `'Plus'` for NACE
- `kind TEXT` — e.g. `'D1'`, `'D2'`, `'open'`. Freeform `TEXT`, **no CHECK constraint** (canonical list is not yet known; we'll add the CHECK in a future phase once the values stabilize). SQL comment will note this decision.
- `created_at`, `updated_at`
- UNIQUE INDEX: `uq_conferences_slug_org` on `(org_id, slug)` (slug only unique within an org).

#### `teams`
- `id BIGSERIAL PRIMARY KEY`
- `school_id BIGINT NOT NULL REFERENCES schools(id) ON DELETE RESTRICT`
- `name TEXT NOT NULL`
- `slug TEXT NOT NULL`
- `game TEXT NOT NULL CHECK (game IN ('valorant', 'lol'))`
- `tier TEXT` — nullable
- `school_name TEXT` — denormalized snapshot of `schools.name` at write time. Speeds up team-list queries that don't need the full school join. **Not back-filled** if `schools.name` is later renamed; documented in SQL comment.
- `region TEXT` — nullable; e.g. `'na'`, `'eu'`. Used by valorant search/stats pages.
- `rating NUMERIC` — nullable; ELO-style score maintained by application.
- `wins INTEGER NOT NULL DEFAULT 0 CHECK (wins >= 0)`
- `losses INTEGER NOT NULL DEFAULT 0 CHECK (losses >= 0)`
- `map_wins INTEGER NOT NULL DEFAULT 0 CHECK (map_wins >= 0)`
- `map_losses INTEGER NOT NULL DEFAULT 0 CHECK (map_losses >= 0)`
- `created_at`, `updated_at`
- UNIQUE INDEX: `uq_teams_slug_game` on `(slug, game)` — slug only unique within a game.
- (Note: `teams.league_slug` was observed on the WIP branch but is intentionally **dropped** here — it's a hangover from the old flat-leagues model; the modern hierarchy uses `team_memberships` → `conferences` → `organizations`.)

#### `team_memberships` (M2M: team↔conference per season; kept after teams leave for history)
- `id BIGSERIAL PRIMARY KEY`
- `team_id BIGINT NOT NULL REFERENCES teams(id) ON DELETE CASCADE`
- `conference_id BIGINT NOT NULL REFERENCES conferences(id) ON DELETE RESTRICT`
- `season_id BIGINT NOT NULL REFERENCES seasons(id) ON DELETE RESTRICT`
- `active BOOLEAN NOT NULL DEFAULT TRUE`
- `created_at`, `updated_at`
- UNIQUE INDEX: `uq_team_memberships` on `(team_id, conference_id, season_id)`.
- Index: `idx_team_memberships_active` on `(season_id, conference_id) WHERE active`.

#### `players`
- `id BIGSERIAL PRIMARY KEY`
- `name TEXT NOT NULL`
- `slug TEXT` — nullable for now, populated by Phase 5 RSO flow
- `riot_puuid TEXT UNIQUE` — nullable. Note: Postgres `UNIQUE` permits multiple NULLs, so admin-entered players without a PUUID coexist freely. The UNIQUE constraint only fires once a real PUUID is set.
- `riot_id TEXT` — game-name#tag-line; nullable
- `display_name TEXT` — nullable; preferred public-facing name
- `role TEXT` — nullable; "Duelist", "Top", etc.
- `game TEXT NOT NULL CHECK (game IN ('valorant', 'lol'))`
- `active BOOLEAN NOT NULL DEFAULT TRUE`
- `rating NUMERIC` — nullable; per-player ELO-style score maintained by application.
- `stats JSONB NOT NULL DEFAULT '{}'::jsonb` — career aggregate stats
- `created_at`, `updated_at`
- (No separate `idx_players_riot_puuid`; the UNIQUE constraint already provides the lookup index.)

#### `team_players` (M2M: player↔team↔season)
- `id BIGSERIAL PRIMARY KEY`
- `team_id BIGINT NOT NULL REFERENCES teams(id) ON DELETE CASCADE`
- `player_id BIGINT NOT NULL REFERENCES players(id) ON DELETE CASCADE`
- `season_id BIGINT NOT NULL REFERENCES seasons(id) ON DELETE RESTRICT` — rosters are season-scoped (a player can leave team A in Fall, join team B in Spring)
- `joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `left_at TIMESTAMPTZ` — nullable; non-null = left the team mid-season
- UNIQUE INDEX: `uq_team_players_active` on `(team_id, player_id, season_id) WHERE left_at IS NULL` — same player cannot be on the same team in the same season twice without leaving first.
- **Per-game-per-season uniqueness is intentionally NOT enforced here** (Decision #7 below — deferred). A player can simultaneously roster on two teams in the same season for the same game; if a real conflict surfaces, we add `UNIQUE (player_id, season_id, game) WHERE left_at IS NULL` in a one-line follow-up phase.

#### `player_consents` (Phase 5 RSO consent gate; table exists from Phase 1 so FKs are stable from the start)
- `id BIGSERIAL PRIMARY KEY`
- `player_id BIGINT NOT NULL REFERENCES players(id) ON DELETE CASCADE`
- `granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `revoked_at TIMESTAMPTZ` — nullable; non-null = consent withdrawn
- `riot_puuid TEXT NOT NULL` — denormalized from `players.riot_puuid` at grant time, immutable for audit
- `created_at`, `updated_at`
- **Partial unique index** `uq_player_consents_active` on `(player_id) WHERE revoked_at IS NULL`. This permits multiple grant→revoke→re-grant rows over time (one active row at any moment) so we keep a full audit trail of the consent lifecycle. SQL comment will explain the audit-history rationale.
- Index: `idx_player_consents_player` on `(player_id, granted_at DESC)` for "show me this player's consent history" queries.

#### `matches`
- `id BIGSERIAL PRIMARY KEY`
- `team1_id BIGINT NOT NULL REFERENCES teams(id) ON DELETE RESTRICT`
- `team2_id BIGINT NOT NULL REFERENCES teams(id) ON DELETE RESTRICT`
- `CHECK (team1_id <> team2_id)` — a team cannot play itself
- `team1_score INTEGER NOT NULL DEFAULT 0 CHECK (team1_score >= 0)`
- `team2_score INTEGER NOT NULL DEFAULT 0 CHECK (team2_score >= 0)`
- `format TEXT NOT NULL CHECK (format IN ('bo1', 'bo3', 'bo5'))`
- `match_date TIMESTAMPTZ NOT NULL`
- `game TEXT NOT NULL CHECK (game IN ('valorant', 'lol'))`
- `org_id BIGINT REFERENCES organizations(id) ON DELETE RESTRICT` — nullable for legacy matches
- `season_id BIGINT REFERENCES seasons(id) ON DELETE RESTRICT` — nullable
- `conference_id BIGINT REFERENCES conferences(id) ON DELETE RESTRICT` — nullable
- `riot_match_id TEXT` — nullable; admin matches have no Riot ID
- `source TEXT NOT NULL DEFAULT 'admin' CHECK (source IN ('admin', 'riot'))`
- `league_name TEXT` — denormalized rendered league name for legacy fallback display
- `created_at`, `updated_at`
- **CRITICAL: sparse-unique index on `riot_match_id`:**
  ```sql
  CREATE UNIQUE INDEX IF NOT EXISTS uq_matches_riot_match_id
    ON matches(riot_match_id) WHERE riot_match_id IS NOT NULL;
  ```
  Non-sparse caused the original 409 bug — see Graveyard #1.
- **`matches_dup_guard` (per CONSTITUTION §3 mandate):**
  ```sql
  CREATE UNIQUE INDEX IF NOT EXISTS uq_matches_dup_guard
    ON matches(team1_id, team2_id, match_date, game);
  ```
  **Known limitations** (documented in SQL comment, not fixed at the DB level — CONSTITUTION assigns the responsibility elsewhere):
  - Same-order only: it does NOT catch reversed-team rematches (`(A, B, date)` vs `(B, A, date)`). Per CONSTITUTION §3, the explicit `(team1,team2) OR (team2,team1)` pre-check happens at the application layer in Phase 3.
  - Timestamp-strict: two legitimate matches on the same calendar day at different scheduled times will pass; two duplicate inserts at the exact same timestamp will collide.
  - Riot-source duplicates also caught more strongly by `uq_matches_riot_match_id`.
- Index: `idx_matches_match_date` on `(match_date DESC)` for the recent-matches query.
- Index: `idx_matches_team1` on `(team1_id, match_date DESC)`.
- Index: `idx_matches_team2` on `(team2_id, match_date DESC)`.

#### `player_match_stats` (thin core — game-agnostic)

The thin polymorphic core. Truly cross-game columns only. Per-game stats live in `pms_<game>_details` tables (1:1 with this row, FK'd by `pms_id`).

- `id BIGSERIAL PRIMARY KEY`
- `match_id BIGINT NOT NULL REFERENCES matches(id) ON DELETE CASCADE`
- `player_id BIGINT NOT NULL REFERENCES players(id) ON DELETE RESTRICT`
- `team_id BIGINT NOT NULL REFERENCES teams(id) ON DELETE RESTRICT`
- `team_name TEXT` — denormalized snapshot of `teams.name` at write time, for match-detail rendering without a join. **Not back-filled** if the team is later renamed; documented in SQL comment.
- `game TEXT NOT NULL CHECK (game IN ('valorant', 'lol'))` — denormalized from `matches.game` for query convenience and for app-level routing to the correct `pms_<game>_details` table.
- `map_name TEXT NOT NULL DEFAULT ''` — empty string is intentional for series rows (one row per series; e.g. LoL bo3 currently models the whole series as one row).
- `created_at`, `updated_at`
- UNIQUE INDEX: `uq_pms` on `(match_id, player_id, map_name)`.
- Index: `idx_pms_player` on `(player_id, match_id)` for player profile queries.
- SQL comment: "K/D/A and agent/champion live in per-game detail tables (`pms_valorant_details`, `pms_lol_details`). Reading a player's per-match stats requires a JOIN to the appropriate detail table based on `game`. Cross-game queries (e.g. 'all of player X's matches across all games') run against the core alone."

**App-level invariant (not DB-enforced):** for every row in `player_match_stats`, the app must insert exactly one corresponding row into `pms_<game>_details` matching the core's `game` value. Phase 3 admin/ingestion code is responsible. Documented in SQL comment.

#### `pms_valorant_details` (1:1 with `player_match_stats` for Valorant rows only)
- `id BIGSERIAL PRIMARY KEY`
- `pms_id BIGINT NOT NULL UNIQUE REFERENCES player_match_stats(id) ON DELETE CASCADE` — the unique constraint enforces the 1:1 relationship; cascade deletes the detail row when the core row is deleted
- `kills INTEGER NOT NULL DEFAULT 0 CHECK (kills >= 0)`
- `deaths INTEGER NOT NULL DEFAULT 0 CHECK (deaths >= 0)`
- `assists INTEGER NOT NULL DEFAULT 0 CHECK (assists >= 0)`
- `agent TEXT NOT NULL` — required (every Val match has an agent picked)
- `acs INTEGER CHECK (acs >= 0)` — Average Combat Score; nullable so admin entry without ACS is allowed
- `side TEXT CHECK (side IS NULL OR side IN ('attacker', 'defender'))` — nullable for series rows where side doesn't apply
- `details JSONB NOT NULL DEFAULT '{}'::jsonb` — non-essential extras (ADR, HS%, first kills, first deaths, plant/defuse counts, etc.)
- `created_at`, `updated_at`

#### `pms_lol_details` (1:1 with `player_match_stats` for LoL rows only)
- `id BIGSERIAL PRIMARY KEY`
- `pms_id BIGINT NOT NULL UNIQUE REFERENCES player_match_stats(id) ON DELETE CASCADE`
- `kills INTEGER NOT NULL DEFAULT 0 CHECK (kills >= 0)`
- `deaths INTEGER NOT NULL DEFAULT 0 CHECK (deaths >= 0)`
- `assists INTEGER NOT NULL DEFAULT 0 CHECK (assists >= 0)`
- `champion TEXT NOT NULL` — required
- `cs INTEGER CHECK (cs >= 0)` — creep score; nullable for admin entry without CS
- `gold INTEGER CHECK (gold >= 0)` — total gold earned; nullable
- `lane TEXT` — nullable; "Top", "Jungle", "Mid", "ADC", "Support"
- `details JSONB NOT NULL DEFAULT '{}'::jsonb` — non-essential extras (KP%, vision score, damage shares, ward stats, KDA ratio, etc.)
- `created_at`, `updated_at`

#### `tournaments`
- `id BIGSERIAL PRIMARY KEY`
- `name TEXT NOT NULL`
- `slug TEXT NOT NULL UNIQUE`
- `game TEXT NOT NULL CHECK (game IN ('valorant', 'lol'))`
- `start_date DATE`
- `end_date DATE`
- `teams JSONB NOT NULL DEFAULT '[]'::jsonb` — denormalized list (per CONSTITUTION §3)
- `matches JSONB NOT NULL DEFAULT '[]'::jsonb` — denormalized list
- `created_at`, `updated_at`

#### `rso_tokens`
- `puuid TEXT PRIMARY KEY`
- `access_token TEXT NOT NULL`
- `refresh_token TEXT`
- `expires_at TIMESTAMPTZ NOT NULL`
- `created_at`, `updated_at`
- **No FK to `players.riot_puuid`.** The RSO callback receives a PUUID before any `players` row may exist (the player record is created/looked-up *from* the token). A hard FK would make the very first sign-in flow circular. The relationship is logical-only; Phase 3/5 routers will look up the player by `riot_puuid` after the token is stored. Documented in SQL comment.

### Triggers / Functions

- An `updated_at` auto-touch trigger on every table that has `updated_at`. Implemented as a single `set_updated_at()` PL/pgSQL function plus per-table `BEFORE UPDATE` triggers.
- Function uses `CREATE OR REPLACE FUNCTION set_updated_at() …` (idempotent natively).
- Triggers use the `DROP TRIGGER IF EXISTS <name> ON <table>; CREATE TRIGGER <name> …` pattern. This is the *only* place `DROP` appears in the file; tightly scoped to named triggers. Each trigger is a 2-line block. SQL comment at the top of the trigger section explains why this pattern is necessary (no `CREATE TRIGGER IF NOT EXISTS` in Postgres) and reaffirms it is the only `DROP`-class allowance.

### Out of Scope (explicitly NOT in Phase 1)

- `Backend/core/db.py` changes — Phase 2.
- `requirements.txt` (no `psycopg2-binary` add) — Phase 2.
- `Backend/.env.example` (no `DATABASE_URL`) — Phase 2.
- Any router work — Phase 3.
- Any `seed_data.py` or sample data — separate task; not part of this migration's critical path.
- Any `users` table for human accounts (not players) — Phase 5.
- DigitalOcean Managed Postgres provisioning — Phase 6.
- Schema migrations tooling (Alembic, dbmate, etc.) — explicitly **not** in scope; CONSTITUTION mandates raw `schema.sql` as the source of truth.
- Removing the deprecated `Backend/migrate.py` / `Backend/migrate_leagues.py` Mongo backfill scripts — future cleanup.

## API Contract

N/A — no application code touched.

## Acceptance Criteria

- [ ] `Backend/schema.sql` exists and is the **only** application-area file changed by this PR. The diff allow-list is exactly `Backend/schema.sql` and `migrations/postgres-v2/phase-1-SPEC.md`.
- [ ] `git diff --name-only HEAD~1..HEAD` (after commit) lists only those two paths.
- [ ] **Re-run safety (not full convergence — see Phase Goal §5 caveat):**
  ```bash
  docker compose up -d db
  docker compose exec -T db psql -U esports -d esports -v ON_ERROR_STOP=1 -f /docker-entrypoint-initdb.d/01-schema.sql
  docker compose exec -T db psql -U esports -d esports -v ON_ERROR_STOP=1 -f /docker-entrypoint-initdb.d/01-schema.sql   # second run
  ```
  Both runs exit 0 with no errors. Note: trigger recreation (`DROP TRIGGER IF EXISTS … ; CREATE TRIGGER …`) mutates `pg_trigger` rows on every run by design, so "no rows touched" is not the test — "no errors with `ON_ERROR_STOP=1`" is.
- [ ] **Table count:** `\dt` returns exactly the **15** tables enumerated above (the 12 from CONSTITUTION §3 plus `team_players` junction plus `pms_valorant_details` and `pms_lol_details` per-game detail tables).
- [ ] **Sparse-unique on `matches.riot_match_id`:** `\d+ matches` includes the index `uq_matches_riot_match_id` with predicate `WHERE (riot_match_id IS NOT NULL)`.
- [ ] **One-active-season-per-org partial unique:** `\d+ seasons` includes the index `uq_seasons_one_active_per_org` with predicate `WHERE active`.
- [ ] **Triggers exist and call `set_updated_at()`:** the `information_schema.triggers` query in Verification Plan step 5 (which now selects `action_statement` too) returns one `BEFORE UPDATE` row per table with an `updated_at` column, and every `action_statement` references `set_updated_at()`. Use the `information_schema.triggers` query, **not** `\dy` (which is for event triggers, not table triggers).
- [ ] **FK / CHECK behaviors visible:** `\d+` outputs for `matches`, `team_memberships`, `player_match_stats`, `pms_valorant_details`, `pms_lol_details`, and `team_players` show the cascade/restrict FK actions and CHECK constraints from this SPEC. The two `pms_*_details` tables must each show `UNIQUE (pms_id)` and `ON DELETE CASCADE` on the FK to `player_match_stats`. Visual review against the SPEC body, not a runtime fire test (firing CHECKs requires seed data Phase 1 doesn't ship).
- [ ] No `pymongo`, no `MongoClient`, no `certifi` references touched (file is SQL-only — trivially satisfied, but explicit).
- [ ] **Manual sensitive-info pass:** schema.sql contains no real PUUIDs, no example tokens, no production hostnames. Documented in commit message.
- [ ] **Advisory:** `codex exec` review of the staged diff returns no critical findings.
- [ ] **Pre-commit (gate B):** developer reviews schema.sql, the `\d+` table outputs, and the second-run apply log before the commit lands.

## Verification Plan

All `psql` invocations use `-v ON_ERROR_STOP=1` so the very first SQL error halts the script; we don't depend on `grep` heuristics.

```bash
# 1. Spin up only the postgres service (no backend yet — Phase 2 builds that).
#    Wipe any prior pgdata so the entrypoint re-applies schema.sql cleanly.
docker compose down -v
docker compose up -d db
docker compose exec -T db pg_isready -U esports -d esports

# 2. Confirm fresh apply succeeded (the docker-entrypoint-initdb.d mount runs
#    schema.sql automatically on first volume init).
docker compose exec -T db psql -U esports -d esports -v ON_ERROR_STOP=1 -c '\dt'
# Expect: 15 tables.

# 3. Idempotency: re-apply schema.sql against the now-populated schema.
#    With ON_ERROR_STOP=1, any error fails the command directly.
docker compose exec -T db psql -U esports -d esports -v ON_ERROR_STOP=1 \
  -f /docker-entrypoint-initdb.d/01-schema.sql \
  && echo "idempotency OK"

# 4. Inspect the two critical partial-unique indexes.
docker compose exec -T db psql -U esports -d esports -v ON_ERROR_STOP=1 \
  -c '\d+ matches' \
  -c '\d+ seasons'
# Look for "WHERE riot_match_id IS NOT NULL" on uq_matches_riot_match_id
# and "WHERE active" on uq_seasons_one_active_per_org.

# 5. Confirm triggers exist AND call set_updated_at() by querying
#    information_schema.triggers directly. (\dy is for event triggers, wrong here.)
docker compose exec -T db psql -U esports -d esports -v ON_ERROR_STOP=1 -c "
  SELECT event_object_table AS table_name,
         trigger_name,
         action_statement
  FROM information_schema.triggers
  WHERE trigger_schema = 'public'
    AND action_timing = 'BEFORE'
    AND event_manipulation = 'UPDATE'
  ORDER BY table_name, trigger_name;
"
# Expect: one row per table with an updated_at column. action_statement
# should reference set_updated_at() so we prove the trigger calls the right
# function, not just that some trigger exists.

# 6. Inspect FK behavior and CHECK constraints on the most critical tables.
docker compose exec -T db psql -U esports -d esports -v ON_ERROR_STOP=1 \
  -c '\d+ matches' \
  -c '\d+ team_memberships' \
  -c '\d+ player_match_stats' \
  -c '\d+ pms_valorant_details' \
  -c '\d+ pms_lol_details' \
  -c '\d+ team_players'
# Confirm: pms_valorant_details and pms_lol_details each have UNIQUE(pms_id)
# (the 1:1 enforcement) and ON DELETE CASCADE on the FK to player_match_stats.

# 7. (Removed.) A runtime CHECK-constraint fire-test would require seeded teams
#    (FK satisfaction comes before the CHECK), and Phase 1 ships no seed data.
#    The CHECK definitions are reviewed via the `\d+ <table>` output in step 6;
#    runtime exercise happens in Phase 3 router tests.

# 8. Outside review.
{ echo "=== STAGED DIFF FOR PHASE 1 ==="; git diff --cached; } | \
  codex exec --sandbox read-only "Review this Postgres schema for: missing FK constraints, missing indexes, type mismatches with the documented invariants in CONSTITUTION.md §3, idempotency hazards, missing CHECK constraints. Output critical issues first, then nits. End with verdict: APPROVE | APPROVE-WITH-NITS | BLOCK."
```

## Rollback Plan

The safe default is `git revert`, which preserves history. The "reset to Phase 0" path is a developer-owned local escape hatch only valid before any push.

```bash
# Local Postgres state — wipe so the (now-removed) schema.sql isn't auto-applied:
docker compose down -v

# Preferred: revert the Phase 1 commit (preserves history; works pre- or post-push):
git revert <phase-1-commit-sha>

# Local-only escape hatch (pre-push only — destructive to local commits):
#   git reset --hard 31b356d   # back to Phase 0 commit
# Use only if you are absolutely sure the commit hasn't been pushed and there
# are no other unpushed commits you want to keep. Coordinate with yourself.
```

No data outside the local docker volume is modified. There is no remote Postgres to roll back. No remote push assumed in Phase 1 (developer chooses push timing).

## Decisions Made (locked at gate-A)

The following decisions are baked into the schema body above; no implementation-blocking open questions remain. These were confirmed by the developer ("all defaults") before gate-A approval.

| # | Decision | Choice | Where it shows up |
|---|---|---|---|
| 1 | WIP-observed columns | **Keep** `teams.school_name`, `teams.region`, `teams.rating`, `players.rating`, `player_match_stats.team_name`, `player_match_stats.game` (denormalized snapshots; not back-filled). **Drop** `teams.league_slug` (stale flat-leagues hangover). | `teams`, `players`, `player_match_stats` table bodies |
| 2 | `organizations.games` CHECK | `cardinality(games) > 0 AND games <@ ARRAY['valorant', 'lol']::TEXT[]` | `organizations` table body |
| 3 | `conferences.kind` constraint | Freeform `TEXT`, **no CHECK**; SQL comment notes "canonical list not yet defined" | `conferences` table body |
| 4 | `seasons.semester` values | `CHECK (semester IN ('fall', 'spring', 'summer'))` — no `'winter'` | `seasons` table body |
| 5 | Tournaments shape | JSONB blobs (`teams`, `matches`) per CONSTITUTION §3; revisit post-launch | `tournaments` table body |
| 6 | `player_match_stats.team_name` denormalization | Keep as snapshot; documented "not back-filled if team is later renamed" | `player_match_stats` table body |
| 7 | `team_players` per-game-per-season uniqueness | **Deferred (Option C)**: only `(team_id, player_id, season_id)` unique for now; per-game-per-season uniqueness added later if a real conflict surfaces | `team_players` table body |
| 8 | ENUM vs CHECK for `game` | CHECK (easier to extend in the multi-game roadmap) | `teams`, `players`, `matches`, `player_match_stats`, `tournaments` |
| 9 | `player_match_stats` shape | **Path 2 — thin polymorphic core + 1:1 per-game detail tables.** Core stays cross-game; K/D/A, agent/champion, ACS/CS/gold live in `pms_valorant_details` and `pms_lol_details`. Future games (RL/Smash/TFT/etc.) add `pms_<game>_details` tables without touching the core. | `player_match_stats`, `pms_valorant_details`, `pms_lol_details` |

## Risks (informational only — no decisions remaining)

### Risk: schema decisions are expensive to reverse later

Once Phase 3 routers are written against this schema, changing types or constraint shapes means rewriting routers. Mitigation: every implementation-affecting decision was made at gate-A above. No "we'll figure it out as we go."

### Risk: `TIMESTAMPTZ` vs `TIMESTAMP`

DO Managed Postgres defaults to `UTC`; using `TIMESTAMPTZ` everywhere prevents the "stored a naive timestamp in local time and lost the offset" class of bug. SPEC uses `TIMESTAMPTZ` exclusively.

### Risk: matches_dup_guard is same-order only

DB-level uniqueness on `(team1_id, team2_id, match_date, game)` does not catch reversed-team duplicates. CONSTITUTION §3 mandates this and assigns the reversed-team pre-check to the application layer (Phase 3). Documented in SQL comment on the matches table.

### Note: `Backend/schema.sql` auto-applies via the existing compose mount

`docker-compose.yml` already mounts `./Backend/schema.sql:/docker-entrypoint-initdb.d/01-schema.sql:ro`. Phase 1 just creates the file; no compose changes needed.

### Note: `riot.txt` is out of scope

That's a static file in the frontend public dir / DO config. Not relevant to schema.
