# PROGRESS.md — Campus Rankers Hub

**Last Updated:** 2026-04-30
**Current Phase:** Phase 3 — Live data correctness (computed standings, profile pages live)

> **Agent Note:** You have permission to autonomously edit this file. Append to ADRs and Graveyard as decisions accumulate. The authoritative shipping history lives in `changelog.md` — keep this file as a *concise* state-of-the-world snapshot for AI context.

---

## 🟢 Current Status

_What is working right now?_

- [x] PostgreSQL migration complete (branch `postgres-migration` — schema.sql idempotent, all routers rewritten, MongoDB removed)
- [x] Local dev stack via Docker Compose (backend + db; frontend on host)
- [x] Frontend deployed on DigitalOcean (migrated from Netlify 2026-04-23)
- [x] Backend deployed on DigitalOcean
- [x] Admin panel: login, schools/teams/players CRUD, manual match entry (Valorant per-map, LoL per-series), match edit/delete, dashboard stats
- [x] Public site: leagues, tournaments, teams (rankings + per-team profile), players (rankings + per-player profile), matches list + detail page, About, Privacy
- [x] Riot RSO OAuth flow, PUUID tracking, `rso_tokens` upsert
- [x] CVAL match ingestion via `IngestCVALMatches.py`
- [x] Three-level league hierarchy: `organizations / seasons / conferences / team_memberships` (replaced flat `leagues`)
- [x] Footer health pill polls `/api/health` every 60s
- [x] Rate limiting (60/min per-IP default via slowapi)
- [x] `matches.riot_match_id` sparse-unique index (the 409 bug fix)
- [ ] **Live-computed standings** (`leagues[].standings` is still the stale snapshot — see `FEATURE_SPEC.md` for current work)
- [ ] Mobile-responsive tables (backlog)
- [ ] Consistent design token system (scattered inline `style={{}}` — backlog)

---

## 🚧 Active Blockers & Known Bugs

_What is currently broken?_

- **Open work (not a bug):** `leagues[].standings` denormalized snapshot is the active feature in `FEATURE_SPEC.md`. Not blocking anything — just stale.
- **Doc drift:** `CLAUDE.md` (project) still says "CollegeRankers / CSU Esports Hub" in some places after the 2026-04-15 brand rename to **Campus Rankers**. Worth a sweep on the repo CLAUDE if the new name is final.
- **Legacy endpoints:** `GET/POST /api/admin/leagues` + `LeagueCreate` model still exist in `admin_router.py`, no longer called by the frontend, read/write the dropped `leagues` collection. Safe to delete once migration is fully verified in prod.
- **Untracked files on `postgres-migration` branch:** `Backend/Dockerfile`, `Backend/.dockerignore`, `Backend/schema.sql`, `Backend/IngestCVALMatches.py`, `docker-compose.yml` were never committed (per 2026-04-18 sync note). Confirm they're committed before Phase-1 prod cutover.
- **`Backend/.env` legacy entries:** Still has unused `MONGO_URI` / `MONGO_DB`. Harmless, but worth cleaning.

---

## 🪦 The Graveyard (Things We Tried That Failed)

1. **[2026-04-20] Frontend `DuplicateKeyError` catch-only as 409 fix:** Caught the symptom but missed the actual culprit (`matchId_1` non-sparse index). The reversed-team `$or` pre-check was a useful guard but not the root cause.
    - **The Fix:** `_fix_matchid_index()` drops and recreates `matchId_1` as `sparse=True` at module load (commit `8cec6a5`). Full investigation in `bug-409-match-duplicate.md`.

2. **[2026-04-23] `NEXT_PUBLIC_API_BASE_URL`:** Used in `Frontend/app/league/stats/page.tsx` and `Frontend/app/admin/adminClient.ts`, but `next.config.ts` only exposes `NEXT_PUBLIC_BACKEND_URL`. Variable resolved to `undefined` on DO, crashing the entire LoL stats page.
    - **The Fix:** Replaced both references with `NEXT_PUBLIC_BACKEND_URL` (with `http://localhost:8000` fallback). Removed the null-guard throw. **Never use `NEXT_PUBLIC_API_BASE_URL`.**

3. **[2026-04-17] PG18 `/var/lib/postgresql/data` mount path:** First `docker compose up` failed — postgres:18+ moved the recommended mount point to the parent dir to support `pg_upgrade --link`.
    - **The Fix:** Volume mount changed to `pgdata:/var/lib/postgresql`; ran `docker compose down -v` to wipe the half-init volume.

4. **[2026-04-17] `postgres:18-alpine`:** Used briefly for size. Musl libc has different collation/locale behavior than DO's Debian-based Managed Postgres → text-sort drift between local and prod.
    - **The Fix:** Reverted to `postgres:18` (Debian). ~200MB extra is worth predictable `ORDER BY`.

5. **[2026-04-15] Inline JSX fetcher in `match/page.tsx` Typeahead:** `fetchPlayersForTeam(teamId)` called inline produced a new function reference per render → useEffect fired on all 5 rows on any change → race conditions on the 5th-player typeahead.
    - **The Fix:** Stable `fetchPlayersRaw(teamId, q)` via `useCallback` + `useMemo`-derived per-team fetcher functions.

---

## 🛠 Helpful Commands & Snippets

**Full local stack:**
```bash
docker compose up --build
docker compose exec backend python seed_data.py        # demo data
docker compose exec backend python seed_data.py --reset  # wipe + reseed
docker compose logs -f backend
docker compose down       # stop, keep pgdata
docker compose down -v    # stop, wipe pgdata (re-runs schema.sql on next up)
```

**Apply schema (idempotent):**
```bash
psql "$DATABASE_URL" -f Backend/schema.sql
```

**Frontend dev (host, not in compose):**
```bash
cd Frontend && npm run dev   # http://localhost:3000
```

**Health check:**
```bash
curl http://localhost:8000/api/health    # → {"status":"ok","db":"connected"}
```

**Inspect tables:**
```bash
docker compose exec db psql -U esports -d esports -c "\dt"
```

**Run match ingestion:**
```bash
docker compose exec backend python IngestCVALMatches.py --dry-run
docker compose exec backend python IngestCVALMatches.py
```

**Migrate leagues (one-time, idempotent):**
```bash
docker compose exec backend python migrate_leagues.py --dry-run
docker compose exec backend python migrate_leagues.py
```

---

## 📝 Architectural Decisions (ADRs)

- **[2026-04-16] Mongo → Postgres:** Bracket routing is fundamentally relational; needed ACID for state transitions and JOINs for live aggregates. No prod data to migrate (fresh target). Removed all `pymongo`/`certifi` paths.
- **[2026-04-16] Parameterized SQL with psycopg2 + RealDictCursor over an ORM:** Lightweight, transparent, no migration-tooling overhead. Trade-off: less safety. Mitigation: every query goes through `get_cursor` / `get_conn`.
- **[2026-04-17] Debian Postgres image over alpine:** Glibc collation parity with DO Managed Postgres. Worth ~200MB.
- **[2026-04-18] Flat `conferences` table with `tier` column over nested `conference_groups`:** NACE's Premier/Plus → D1–10 was the ambiguous case. 20 docs vs 2+10+10, but a single uniform `Org → Season → Conference` picker everywhere. Free visual grouping via `<optgroup label={tier}>`.
- **[2026-04-23] DigitalOcean for frontend:** Netlify free credits ran out. DO chosen for cost predictability matching the backend host.
- **[Match index sparseness]** Sparse-unique on `matches.riot_match_id` is mandatory — admin matches have no Riot ID, and a non-sparse index treats every `null` as duplicate.

---

## 🗺 Phase Roadmap

- [x] **Phase 0** — MVP UI + Mongo backend + admin panel
- [x] **Phase 1** — Mongo → Postgres migration; Docker Compose dev stack
- [x] **Phase 2** — League hierarchy overhaul (orgs/seasons/conferences); profile pages; match detail; UX polish batch
- [ ] **Phase 3** — Live-computed standings (current); design-token unification; mobile-responsive tables
- [ ] **Phase 4** — Real-time WebSocket updates (admin score submission → live dashboard); Riot prod API key + automated ingestion at scale
- [ ] **Phase 5** — Multi-tenant TO accounts (move beyond single-shared-password admin auth)
