# CONSTITUTION.md — Campus Rankers Hub

## 0. Current Reality (read this first)

**Production-bound `main` is on MongoDB Atlas.** The Mongo→Postgres migration is **in progress on the `postgres-migration-v2` branch**, not done. Every "Postgres" reference in this document describes the **target architecture** we are building toward, not facts about the current code.

What is actually true today (as of 2026-05-02):

- `Backend/main.py` and `Backend/core/db.py` are MongoDB code (`pymongo`, `MongoClient`, `certifi`).
- `Backend/requirements.txt` lists `pymongo==4.8.0` and `certifi==2024.8.30`, and **does not** include `psycopg2-binary`.
- `Backend/.env.example` configures `MONGO_URI` / `MONGO_DB`, **not** `DATABASE_URL`.
- No `Backend/schema.sql` exists.
- No DigitalOcean Managed Postgres cluster has been provisioned.
- No live users; no Riot production API key (still on dev tier).
- No user accounts / RSO consent gating yet — public site has no auth, admin uses a single shared `ADMIN_PASSWORD`.

**Caveat: some Postgres-flavored *infrastructure artifacts* already exist on `main` even though the *application* has not migrated.** Specifically: `docker-compose.yml` defines a `postgres:18` service, `Backend/Dockerfile` and `Frontend/Dockerfile` exist, and `.do/app.yaml` is wired for a DO deploy. None of these are exercised by the current Mongo backend code — they are pre-built scaffolding waiting for the app code to catch up.

Two sets of hard rules apply: rules that apply **NOW** (to current Mongo code) and rules that apply **AFTER MIGRATION** (the contract for the Postgres world we are building). They are separated in §5 below.

The migration is broken into seven phases (0–6), each with its own SPEC under `migrations/postgres-v2/phase-N-SPEC.md`, gate-A approval before implementation, and gate-B approval (after `codex review`) before commit.

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

**Hard invariants (post-migration "don't break these"):**

- `players.riot_puuid` is the upsert target for ingestion — never assume name uniqueness.
- `matches.riot_match_id` is **sparse-unique** (admin matches have no Riot ID; non-sparse caused the original 409 bug).
- Reversed-order rematches: explicit pre-check on `(team1,team2)` and `(team2,team1)` before insert.
- Active-season uniqueness per org enforced server-side in both create and PATCH.
- W/L counters on `teams` are source of truth.
- `leagueName` on match docs is the rendered string for fallback compatibility with legacy matches.
- **Public reads filter by player consent.** A player without an active `player_consents` grant is not surfaced by name in public APIs. Bake the filter into the data layer; do not rely on the UI.

---

## 4. Coding Conventions

### Apply NOW (current Mongo code)

- camelCase JSON wire format — do not break across the migration; the frontend depends on it.
- Admin auth: HMAC-signed bearer token, 12h TTL.
- `adminFetch` wraps all admin frontend calls (Authorization header + 401 → redirect to login).
- Pre-paginated lists return `{items, total}`; legacy callers without `paginated=true` get a plain list — don't break that.
- `NEXT_PUBLIC_BACKEND_URL` only — never `NEXT_PUBLIC_API_BASE_URL` (the latter broke prod once because it isn't exposed by `next.config.ts`).
- Use `Typeahead.tsx` for search-with-create flows; remember the "create option only renders when items.length === 0" quirk.

### Apply AFTER MIGRATION (Postgres code)

- Parameterized SQL only — never f-string interpolate user input. Treat SQL injection as a kill-the-PR-level offense.
- All reads via `get_cursor(dict_rows=True)`; multi-table writes via `get_conn()` context manager with explicit commit.
- `_int_id()` helper for path params; `_project()` helper for snake_case → camelCase mapping.
- `psycopg2.errors.UniqueViolation` → HTTP 409 with explanatory message.
- Sort keys from query params must go through a `_SORT_COLUMNS` whitelist (per the `teams_router.py` pattern we will port).
- Rate-limit decorators per route only when tighter than the global 60/min default.
- Keep `pymongo` / `MongoClient` / `certifi` out — the migration removes them; do not reintroduce.

### Env (target)

- `Backend/.env.example` is canonical post-migration. Required: `DATABASE_URL` (with `?sslmode=require` for DO), `ADMIN_PASSWORD`, `ADMIN_SECRET`, `ALLOWED_ORIGINS`, `FRONTEND_ORIGIN`, `RATE_LIMIT_DEFAULT`, RSO vars.
- **Do NOT set `DATABASE_URL` in `Backend/.env` while using docker compose** — compose env overrides shadow it and break the internal `db` hostname.

---

## 5. Hard Constraints (Do Not Violate)

### Apply NOW

| Rule | Requirement |
|---|---|
| **camelCase wire format** | Never reshape JSON keys to snake_case; the frontend depends on camelCase across the migration. |
| **Admin route is hidden** | Do not link `/admin` from any public nav. |
| **`NEXT_PUBLIC_BACKEND_URL` only** | Never reintroduce `NEXT_PUBLIC_API_BASE_URL`. |
| **Match delete is hard-delete** | If audit trail becomes a requirement, add `deleted_at` and filter; do not soft-delete by default. |

### Apply AFTER MIGRATION

| Rule | Requirement |
|---|---|
| **No raw SQL string interpolation** | Always parameterized. SQL injection is the failure mode. |
| **No pymongo / Mongo code** | Migration removes it. New Postgres-era code is Postgres-only. |
| **Sparse uniqueness on `matches.riot_match_id`** | Index MUST be sparse — admin matches have no Riot ID. Non-sparse caused the production 409 bug originally. |
| **Don't shadow compose env in `.env`** | `DATABASE_URL` lives in `docker-compose.yml` for local. |
| **Postgres image: Debian** | `postgres:18`, never `postgres:18-alpine`. Glibc collation behavior matches DO Managed Postgres. |
| **Player consent gate** | Public APIs that surface a player by name MUST filter on `player_consents` (active grant, no revocation). Bake into the data layer, not the UI. |
| **One active season per org** | Server-side enforced — do not manually deactivate siblings. |

---

## 6. The SDD Agent Workflow

Before writing any code for a new feature, follow Plan → Implement → Verify:

1. **Read the Spec** — Read this `CONSTITUTION.md` and the relevant `FEATURE_SPEC.md` (or the migration phase SPEC under `migrations/postgres-v2/`). Confirm understanding before doing anything.
2. **Propose a Plan** — Detail every file you will create or modify. Run the plan through `codex exec` for an outside review. Wait for the developer's explicit approval (gate A).
3. **Implement** — Write code strictly per the approved plan.
4. **Verify** — Provide exact commands. Run `codex review --uncommitted` (or `--base main`) for ChatGPT-side review of the diff. Wait for the developer's explicit approval (gate B) before any commit.

**Critical rule:** If verification fails, do not patch the code directly. Identify why it failed. If the spec was ambiguous, update the spec first.

**Migration phases** are tracked in `migrations/postgres-v2/phase-N-SPEC.md`, each with its own gate-A and gate-B approval cycle.
