# CONSTITUTION.md — Campus Rankers Hub

## 0. Current Reality (read this first)

**The Mongo → Postgres migration is code-complete on `postgres-migration-v2`.** The branch is 16 commits ahead of `main`, all pushed (tip `703b633`). Local docker compose stack runs end-to-end on Postgres with all routers ported. **Production cutover is pending** developer-run provisioning steps in `migrations/postgres-v2/phase-6-RUNBOOK.md`.

What is true today (as of 2026-05-02) **on the migration branch**:

- `Backend/main.py` and `Backend/core/db.py` use **psycopg2 with a `ThreadedConnectionPool`**. No pymongo, no certifi at runtime.
- `Backend/requirements.txt` lists `psycopg2-binary==2.9.9`. `pymongo`/`certifi` removed.
- `Backend/.env.example` documents `DATABASE_URL` + pool sizing + admin auth + RSO secrets.
- `Backend/schema.sql` exists: 15 tables, idempotent, encodes the hard invariants (sparse-unique `riot_match_id`, partial unique on one-active-season-per-org and active-consent-per-player, `team1_id <> team2_id` CHECK, `>= 0` CHECKs on counters, etc.).
- Player profiles default private. RSO sign-in records active consent in `player_consents`; public APIs filter at the data layer (`core/consent.py`).
- All 6 ported routers live: tournaments, teams, players, matches, admin, valorant. The legacy `leagues_router` was deleted (no Postgres equivalent — replaced by org/season/conference hierarchy).

What is true on **`main`** (pre-merge): still Mongo. Don't push fixes there until cutover lands; develop on `postgres-migration-v2` or a child branch.

What is **NOT yet done** (Phase 6 production work):
- DigitalOcean Managed Postgres cluster — not provisioned. `doctl apps create --spec .do/app.yaml` will provision both the app and the cluster on first run.
- Production secrets in DO Console: `ADMIN_PASSWORD`, `ADMIN_SECRET`, `RIOT_API_KEY`, `RSO_CLIENT_ID`, `RSO_CLIENT_SECRET`, `SESSION_SECRET`.
- Riot RSO portal redirect URI updated to the deployed `${APP_URL}/api/valorant/auth/callback`.
- Schema applied against the managed cluster: `psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f Backend/schema.sql`.
- PR `postgres-migration-v2` → `main`.

The migration was broken into 16 atomic commits across 15 phases (Phase 0 through Phase 6 prep). Each phase has its own SPEC under `migrations/postgres-v2/`, gate-A approval before implementation, and gate-B approval (after `codex review`) before commit. The end-to-end migration index is at `migrations/postgres-v2/README.md`.

---

## 1. Project Mission & Context

A collegiate esports site covering **Valorant** and **League of Legends** for collegiate leagues (CVAL, CLOL, NECC, NACE, ECAC, etc). Domain: **campusrankers.com**. The site shows leagues, standings, teams, players, tournaments, and per-match stats. An admin panel supports manual match entry while we wait on a Riot production API key.

Brand: **Campus Rankers** (renamed 2026-04-15 from "College Rankers" / "CSU Esports Hub" — the folder name `senior-design-esports-project` predates the rename).

**V1 scope:** Valorant + League of Legends only. Other titles (Smash, Overwatch, Rocket League, Call of Duty, Fortnite, TFT, TF2) are explicitly **deferred** until per-game data shape is researched. Do not pre-generalize the schema for them.

**Frontend deploy (planned):** DigitalOcean.
**Backend deploy (planned):** DigitalOcean.
**Database (current):** MongoDB Atlas.
**Database (target):** DigitalOcean Managed PostgreSQL.

---

## 2. Tech Stack & Architecture

Strict — do not introduce alternatives.

**Frontend** (`Frontend/`)
- Next.js (App Router, TypeScript)
- Plain CSS modules / inline `style={{}}` today (design-token cleanup is in backlog)
- Standalone build for Docker

**Backend** (`Backend/`)
- FastAPI (Python 3.12)
- **Current:** `pymongo` against Mongo Atlas
- **Target:** `psycopg2-binary` with a `ThreadedConnectionPool` (`Backend/core/db.py`); parameterized SQL only — no ORM. Every read goes through `get_cursor` (RealDictCursor).
- `slowapi` for rate limiting (`60/minute` default per IP)

**Database (target)**
- PostgreSQL 18 (Debian-based image to match DO's libc — never alpine)
- Schema lives in `Backend/schema.sql`, idempotent (`CREATE TABLE IF NOT EXISTS`, wrapped in `BEGIN/COMMIT`)
- Tables (provisional, finalized in Phase 1): `schools`, `organizations`, `seasons`, `conferences`, `teams`, `team_memberships`, `players`, `player_consents` (new for RSO gating), `matches`, `player_match_stats`, `tournaments`, `rso_tokens`

**Local dev stack (target)**
- `docker-compose.yml` runs `db` (postgres:18 Debian) + `backend` (FastAPI). Frontend stays on host (`npm run dev`) for HMR speed.

**Riot integration**
- RSO OAuth scaffolding in `Backend/valorant/` — PUUID + token storage will live in `rso_tokens`.
- Match ingestion via `Backend/IngestCVALMatches.py` (verify state before relying on it; written for Mongo).

**Auth (target)**
- Public site: no auth required for browsing.
- **Player consent gate:** profiles default to private. Riot RSO sign-in is the player's act of consent; only consented players appear in public listings, search, rankings, and match player lists.
- Admin: HMAC-signed bearer token, 12h TTL, single shared `ADMIN_PASSWORD`. Token stored in `localStorage` (`admin_token`). Admin route is hidden — not linked from navbar.

---

## 3. Data Model — Target Invariants (post-migration)

```
schools             id, name, slug
organizations       id, name, abbreviation, slug, games[]            -- governs leagues (CVAL/NECC/NACE/ECAC)
seasons             id, orgId, year, semester, label, active         -- one active=true per org enforced server-side
conferences         id, orgId, name, shortName, slug, tier?, kind    -- flat with tier label (NACE Premier/Plus)
teams               id, schoolId, name, slug (unique per (slug,game)), tier, wins, losses, mapWins, mapLosses
team_memberships    teamId, conferenceId, seasonId, active           -- M2M; kept after teams leave for history
players             id, name, riot_puuid (UNIQUE), teamIds[], active, stats(JSONB)
player_consents     playerId, granted_at, revoked_at?                -- RSO grant gates public visibility (Phase 5)
matches             id, team1_id, team2_id, scores, format, date, conferenceId, seasonId, orgId,
                    riot_match_id (UNIQUE; sparse for admin matches),
                    matches_dup_guard UNIQUE (team1_id, team2_id, match_date, game)
player_match_stats  match_id, player_id, team_id, map_name (NOT NULL DEFAULT '' so unique works for LoL series rows)
                    pms_unique (match_id, player_id, map_name)
tournaments         id, ..., teams (JSONB), matches (JSONB)
rso_tokens          puuid PK, expires_at (tz-aware)
```

**Hard invariants (don't break these):**

- `players.riot_puuid` is the upsert target for ingestion — never assume name uniqueness.
- `matches.riot_match_id` is **partial-unique** on `WHERE riot_match_id IS NOT NULL` (admin matches have no Riot ID; the partial pattern is carried forward from the Mongo `sparse: true` 409-bug fix).
- Reversed-order rematches: explicit pre-check on `(team1,team2)` and `(team2,team1)` before insert in `admin_router.create_match`.
- Active-season uniqueness per org enforced both server-side (deactivate siblings before insert) AND at the DB level (partial unique index `uq_seasons_one_active_per_org`).
- W/L counters on `teams` are source of truth (incremented on match insert, reversed on edit/delete).
- `league_name` on `matches` is the rendered string for fallback display.
- **Public reads filter by player consent.** Use `core/consent.py` `CONSENTED_FILTER_SQL` (a static SQL fragment) — bake the filter into the data layer; admin endpoints intentionally bypass the gate.
- `team1_id <> team2_id` CHECK on matches; `>= 0` CHECK on every counter column; `cardinality(games) > 0 AND games <@ ARRAY['valorant','lol']` on organizations.

---

## 4. Coding Conventions

**Backend (Python / FastAPI):**

- Parameterized SQL only — never f-string interpolate user input. Treat SQL injection as a kill-the-PR-level offense. The only allowed f-string interpolation in SQL is whitelisted SQL fragments from `_SORT_COLUMNS` maps and the literal `"ASC"`/`"DESC"` direction strings.
- All single-statement reads/writes via `get_cursor(dict_rows=True)` (auto-commit on success, rollback on exception, putconn always).
- Multi-statement transactions via `get_conn()` + `conn.cursor(cursor_factory=RealDictCursor)` directly. Caller manages `conn.commit()` / `conn.rollback()`. **Never call `get_cursor()` inside `get_conn()`** — it requests a separate connection from the pool, breaks atomicity, can deadlock when the pool is small. Documented as the "MULTI-STATEMENT TRANSACTION PATTERN" in `core/db.py`.
- `_int_id()` helper for path params (raises 400 on non-integer).
- `psycopg2.errors.UniqueViolation` → HTTP 409 with explanatory message.
- Sort keys from query params go through a `_SORT_COLUMNS` whitelist (e.g. `teams_router._SORT_COLUMNS`).
- Rate-limit decorators per route only when tighter than the global 60/min default.
- No `pymongo` / `MongoClient` / `certifi` in app code. The two-signal `_try_router` guard in `main.py` is the legacy of Phase 2 Option Z; it's still in place, but every router has been ported, so the guard's branches are no-ops on `postgres-migration-v2`.

**Frontend (Next.js / TypeScript):**

- camelCase JSON wire format from the backend; UI layer maps lowercase game enum → TitleCase display via `Frontend/app/_shared/gameLabel.ts`.
- `adminFetch` wraps all admin frontend calls (Authorization header + 401 → redirect to login).
- Pre-paginated lists return `{items, total}`; legacy callers without `paginated=true` get a plain list — don't break that.
- `NEXT_PUBLIC_BACKEND_URL` only — never `NEXT_PUBLIC_API_BASE_URL` (the latter broke prod once because it isn't exposed by `next.config.ts`).
- Use `Typeahead.tsx` for search-with-create flows; remember the "create option only renders when items.length === 0" quirk.

**Env:**

- `Backend/.env.example` is canonical. Required: `DATABASE_URL` (with `?sslmode=require` for DO), `DB_POOL_MIN`/`DB_POOL_MAX`, `ADMIN_PASSWORD`, `ADMIN_SECRET`, `ALLOWED_ORIGINS`, `FRONTEND_ORIGIN`, `RATE_LIMIT_DEFAULT`, RSO vars (`RSO_CLIENT_ID`/`RSO_CLIENT_SECRET`/`RSO_REDIRECT_URI`/`SESSION_SECRET`), `RIOT_API_KEY`, `RIOT_REGION`, `RIOT_ACCOUNT_REGION`.
- **Do NOT set `DATABASE_URL` in `Backend/.env` while using docker compose** — compose env overrides shadow it and break the internal `db` hostname.

---

## 5. Hard Constraints (Do Not Violate)

| Rule | Requirement |
|---|---|
| **No raw SQL string interpolation** | Always parameterized. SQL injection is the failure mode. Whitelisted sort/order fragments are the only exception. |
| **No pymongo / Mongo code** | Removed in Phase 2. New code is Postgres-only. |
| **Partial uniqueness on `matches.riot_match_id`** | Index MUST be partial (`WHERE riot_match_id IS NOT NULL`). Carries forward the historical 409-bug fix. |
| **Don't shadow compose env in `.env`** | `DATABASE_URL` lives in `docker-compose.yml` for local; `${db.DATABASE_URL}` in `.do/app.yaml` for prod. |
| **Postgres image: Debian** | `postgres:18`, never `postgres:18-alpine`. Glibc collation parity with DO Managed Postgres. |
| **Player consent gate** | Public APIs that surface a player by name MUST filter via `core/consent.py` `CONSENTED_FILTER_SQL` (active `player_consents` row, no revocation). Bake into the data layer, not the UI. Admin endpoints intentionally bypass. |
| **One active season per org** | DB-level partial unique index + app-level pre-deactivation in same transaction. |
| **Multi-statement transactions** | `get_conn()` + `conn.cursor()` directly. Caller commits/rollbacks. Never nest `get_cursor()` inside `get_conn()`. |
| **camelCase wire format** | All public APIs return camelCase keys. UI display labels live in the frontend. |
| **Admin route is hidden** | Do not link `/admin` from any public nav. |
| **`NEXT_PUBLIC_BACKEND_URL` only** | Never reintroduce `NEXT_PUBLIC_API_BASE_URL`. |
| **Match delete is hard-delete** | If audit trail becomes a requirement, add `deleted_at` and filter; do not soft-delete by default. |

---

## 6. The SDD Agent Workflow

Before writing any code for a new feature, follow Plan → Implement → Verify:

1. **Read the Spec** — Read this `CONSTITUTION.md` and the relevant `FEATURE_SPEC.md` (or the migration phase SPEC under `migrations/postgres-v2/` for historical context). Confirm understanding before doing anything.
2. **Propose a Plan** — Detail every file you will create or modify. Run the plan through `codex exec` for an outside review. Wait for the developer's explicit approval (gate A).
3. **Implement** — Write code strictly per the approved plan.
4. **Verify** — Provide exact commands. Run `codex review --uncommitted` (or `--base main`) for ChatGPT-side review of the diff. Wait for the developer's explicit approval (gate B) before any commit.

**Critical rule:** If verification fails, do not patch the code directly. Identify why it failed. If the spec was ambiguous, update the spec first.

**The completed Postgres migration** is documented at `migrations/postgres-v2/README.md` — phase-by-phase commit map, architecture decisions, lessons learned. New features should NOT modify those phase SPECs (they're historical record); use `FEATURE_SPEC.md` per-feature going forward.

**Codex as proxy reviewer:** the user delegated gate-A and gate-B approvals to `codex exec` for the Phase 3+ migration work. Future routine work can use the same pattern — run the SPEC through `codex exec --sandbox read-only` before implementation; pipe the staged diff through `codex exec` for gate B. Trust codex on technical correctness; pull the developer in for genuinely architectural decisions (path A/B/C choices, scope changes, anything outside the SPEC's intent).
