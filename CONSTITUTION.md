# CONSTITUTION.md —  Campus Rankers Hub

## 1. Project Mission & Context

A collegiate esports site covering **Valorant** and **League of Legends** competition for collegiate leagues (CVAL, CLOL, NECC, NACE, ECAC, etc). The site shows leagues, standings, teams, players, tournaments, and per-match stats. An admin panel supports manual match entry while we wait on a Riot prod API key.

Brand: **Campus Rankers** (renamed 2026-04-15 from "College Rankers" / "CSU Esports Hub" — keep folder name and CLAUDE.md repo name aligned over time).

**Frontend deploy:** DigitalOcean (migrated from Netlify 2026-04-23 after free credits ran out)
**Backend deploy:** DigitalOcean
**Database:** DigitalOcean Managed PostgreSQL (migrated from MongoDB Atlas on branch `postgres-migration`, 2026-04-16)
IMPORTANT NOTE PRODUCTION IS CURRENTLY ON MONGODB BUT CURRENT DEVELOPMENT SHOULD BE PLANED FOR POSTGRESQL

---

## 2. Tech Stack & Architecture

Strict — do not introduce alternatives.

**Frontend** (`Frontend/`)
- Next.js (App Router, TypeScript)
- Plain CSS modules / inline `style={{}}` today (design-token cleanup is in backlog)
- Standalone build for Docker

**Backend** (`Backend/`)
- FastAPI (Python 3.12)
- `psycopg2-binary` with a `ThreadedConnectionPool` (`Backend/core/db.py`)
- Parameterized SQL only — **no ORM**. Every read goes through `get_cursor` (RealDictCursor).
- `slowapi` for rate limiting (`60/minute` default per IP)

**Database**
- PostgreSQL 18 (Debian-based image to match DO's libc — never alpine)
- Schema lives in `Backend/schema.sql`, idempotent (`CREATE TABLE IF NOT EXISTS`, wrapped in `BEGIN/COMMIT`)
- 9 tables: `schools`, `leagues` (legacy), `teams`, `players`, `team_players`, `matches`, `player_match_stats`, `tournaments`, `rso_tokens`
- New hierarchy collections (post-2026-04-18): `organizations`, `seasons`, `conferences`, `team_memberships` — replacing flat `leagues`

**Local dev stack**
- `docker-compose.yml` runs `db` (postgres:18 Debian) + `backend` (FastAPI). Frontend stays on host (`npm run dev`) for HMR speed.

**Riot integration**
- RSO OAuth (`Backend/valorant/`) — PUUID + token storage in `rso_tokens`
- Match ingestion via `Backend/IngestCVALMatches.py`

**Auth**
- Public site: no auth
- Admin: HMAC-signed bearer token, 12h TTL, single shared `ADMIN_PASSWORD`. Token stored in `localStorage` (`admin_token`). Admin route is hidden — not linked from navbar.

---

## 3. Data Model — Key Invariants

```
schools             id, name, slug
organizations       id, name, abbreviation, slug, games[]            -- governs leagues (CVAL/NECC/NACE/ECAC)
seasons             id, orgId, year, semester, label, active         -- one active=true per org enforced server-side
conferences         id, orgId, name, shortName, slug, tier?, kind    -- flat with tier label (NACE Premier/Plus)
teams               id, schoolId, name, slug (unique per (slug,game)), tier, wins, losses, mapWins, mapLosses
team_memberships    teamId, conferenceId, seasonId, active           -- M2M; kept after teams leave for history
players             id, name, riot_puuid (UNIQUE), teamIds[], active, stats(JSONB)
matches             id, team1_id, team2_id, scores, format, date, conferenceId, seasonId, orgId,
                    riot_match_id (UNIQUE; sparse for admin matches),
                    matches_dup_guard UNIQUE (team1_id, team2_id, match_date, game)
player_match_stats  match_id, player_id, team_id, map_name (NOT NULL DEFAULT '' so unique works for LoL series rows)
                    pms_unique (match_id, player_id, map_name)
tournaments         id, ..., teams (JSONB), matches (JSONB)
rso_tokens          puuid PK, expires_at (tz-aware)
```

**Hard invariants (the "don't break these" list):**
- `players.riot_puuid` is the upsert target for ingestion — never assume name uniqueness.
- `matches.riot_match_id` is **sparse-unique** (admin matches have no Riot ID; non-sparse caused the famous 409 bug, fixed by `_fix_matchid_index()` recreating the index sparse at module load — see `bug-409-match-duplicate.md`).
- Reversed-order rematches: explicit `$or` pre-check `(team1,team2)` and `(team2,team1)` in `admin_router.py` before insert.
- Active-season uniqueness per org enforced server-side in both create and PATCH.
- W/L counters on `teams` are source of truth; `leagues[].standings` is a stale snapshot — recompute live where it matters.
- `leagueName` on match docs is the rendered string for fallback compatibility with legacy matches.

---

## 4. Coding Conventions

**Backend**
- Parameterized SQL only — never f-string interpolate user input.
- All reads via `get_cursor(dict_rows=True)`; multi-table writes via `get_conn()` context manager with explicit commit.
- camelCase JSON wire format preserved (frontend contracts unchanged across the Mongo→Postgres migration).
- `_int_id()` helper for path params; `_project()` helper for snake_case → camelCase mapping.
- `psycopg2.errors.UniqueViolation` → HTTP 409 with explanatory message.
- Sort keys from query params must go through a `_SORT_COLUMNS` whitelist (per `teams_router.py` pattern).
- Rate-limit decorators per route only when tighter than the global 60/min default.
- Keep `pymongo` / `MongoClient` / `certifi` out — the migration removed them; don't reintroduce.

**Frontend**
- TypeScript strict
- `adminFetch` wraps all admin calls (Authorization header + 401 → return-path save → redirect to login)
- Use `NEXT_PUBLIC_BACKEND_URL` (with `http://localhost:8000` fallback). **Never use `NEXT_PUBLIC_API_BASE_URL`** — it's not exposed in `next.config.ts` and broke prod once (2026-04-23 league/stats crash).
- Use `Typeahead.tsx` for search-with-create flows; remember the "create option only renders when items.length === 0" quirk.
- Pre-paginated lists return `{items, total}`; legacy callers without `paginated=true` get a plain list — don't break that.

**Env**
- `Backend/.env.example` is canonical. Required: `DATABASE_URL` (with `?sslmode=require` for DO), `ADMIN_PASSWORD`, `ADMIN_SECRET`, `ALLOWED_ORIGINS`, `FRONTEND_ORIGIN`, `RATE_LIMIT_DEFAULT`, RSO vars.
- **Do NOT set `DATABASE_URL` in `Backend/.env` while using docker compose** — compose env overrides shadow it and break the internal `db` hostname.

---

## 5. Hard Constraints (Do Not Violate)

| Rule | Requirement |
|---|---|
| **No raw SQL string interpolation** | Always parameterized. SQL injection is the failure mode. |
| **No pymongo / Mongo code** | The migration removed it. New code is Postgres-only. |
| **Sparse uniqueness on `matches.riot_match_id`** | If you recreate the index, it MUST be sparse. Non-sparse caused the production 409 bug. |
| **Don't shadow compose env in `.env`** | `DATABASE_URL` lives in `docker-compose.yml` for local; `Backend/.env` would silently override. |
| **`NEXT_PUBLIC_BACKEND_URL` only** | Never reintroduce `NEXT_PUBLIC_API_BASE_URL` references. |
| **Postgres image: Debian** | `postgres:18`, never `postgres:18-alpine`. Glibc collation behavior matches DO Managed Postgres. |
| **Admin route hidden** | Don't link `/admin` from any public nav. |
| **Match delete is hard-delete** | If audit trail becomes a requirement later, add `deleted_at` and filter; do not soft-delete by default. |

---

## 6. The SDD Agent Workflow

Before writing any code for a new feature, follow Plan → Implement → Verify:

1. **Read the Spec** — Read `FEATURE_SPEC.md`. Confirm understanding before doing anything.
2. **Propose a Plan** — Detail every file (frontend route, backend router, schema migration) you will create or modify. Wait for explicit approval.
3. **Implement** — Write code strictly per the approved plan.
4. **Verify** — Provide exact commands: `docker compose up`, `curl` against the new endpoint, `npm run dev` exercise of the UI.

**Critical rule:** If verification fails, do not patch the code directly. Identify why it failed. If the spec was ambiguous, update the spec first.
