# PROGRESS.md — Campus Rankers Hub

**Last Updated:** 2026-05-02
**Current Phase:** Postgres Migration v2 — **Phase 0** (branch + doc reality reconciliation)
**Branch:** `postgres-migration-v2` (off `main` @ `dc1500c`)

> **Agent Note:** You may autonomously edit this file. Append to ADRs and Graveyard as decisions accumulate. Keep this file as a *concise* state-of-the-world snapshot for AI context. The authoritative changelog lives in git.

---

## 🟢 Current Status (factual, as of 2026-05-02)

What is real today:

**Application code (on `main`):**
- [x] Frontend Next.js app exists with routes for leagues, teams, players, matches, tournaments, valorant search, admin panel, about, privacy
- [x] Backend FastAPI app with routers for leagues, teams, players, matches, tournaments, admin
- [x] **MongoDB Atlas** as the data store (`pymongo`, `certifi`)
- [x] Admin panel: login, manage teams/players/leagues, manual match entry (Valorant per-map, LoL per-series), match edit/delete, dashboard stats — currently against Mongo
- [x] Riot RSO OAuth scaffolding in `Backend/valorant/`
- [x] CVAL match ingestion script `Backend/IngestCVALMatches.py` (Mongo-targeted; verify state before relying)
- [x] CLOL player roster scraping in `Backend/League/`
- [x] Footer health pill polls `/api/health` every 60s
- [x] Rate limiting (60/min per-IP default via slowapi)

**Infrastructure:**
- [x] `docker-compose.yml` exists at repo root, defines `db` (postgres:18 Debian) + `backend` (FastAPI) services — but the local stack has never been verified end-to-end against the current Mongo backend code
- [x] `Backend/Dockerfile` and `Frontend/Dockerfile` exist for DO deploy
- [x] `.do/app.yaml` exists for DO App Platform configuration

**What does NOT exist yet:**
- [ ] `Backend/schema.sql` (target Postgres schema — Phase 1)
- [ ] `psycopg2-binary` in `requirements.txt` (Phase 2)
- [ ] Postgres-flavored `Backend/core/db.py` with ThreadedConnectionPool (Phase 2)
- [ ] Postgres-flavored routers (Phase 3)
- [ ] DO Managed Postgres cluster (Phase 6)
- [ ] Riot production API key (out-of-band; not blocked by code)
- [ ] User accounts + RSO consent gating (Phase 5)
- [ ] Live deployment — site is currently not deployed publicly
- [ ] Mobile-responsive tables (post-launch backlog)
- [ ] Consistent design-token system (post-launch backlog)

---

## 🚧 Active Blockers & Known Bugs

- **Riot production API key** — currently dev-tier; throttles real ingestion. Non-blocking for development; required before launch.
- **DO Managed Postgres provisioning** — not yet done. Phase 6 task.
- **Doc drift (resolved by this Phase-0 PR):** repo-root SDD docs previously claimed migration was done. This PR rewrites them to factual state.
- **Mongo-era artifacts to triage later:** `Backend/migrate.py` and `Backend/migrate_leagues.py` are old Mongo backfill scripts. Move to `Backend/archive/` in a future cleanup phase.

---

## 🪦 The Graveyard (Things We Tried That Failed)

(Preserved verbatim from prior PROGRESS — these are real, hard-won lessons.)

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

6. **[2026-05-02] First Postgres migration was effectively lost.** Branch `origin/postgres-migration` (April 15 base) contained an incomplete attempt; `origin/stash-postgres-wip` (May 1) recovered ~2k lines from a stash but never merged. A MacBook wipe deleted the local copy and the developer believed the remote branch was also gone. Lesson: **any in-flight migration must be pushed to remote daily, not held in a local stash.** The remote branches are kept as reference until `postgres-migration-v2` lands.

---

## 🛠 Helpful Commands & Snippets

(Some of these are target-state — they will work once the relevant phase lands; called out where applicable.)

**Full local stack (target — works once Phase 2 lands):**
```bash
docker compose up --build
docker compose exec backend python seed_data.py        # demo data (when seed_data.py exists)
docker compose logs -f backend
docker compose down       # stop, keep pgdata
docker compose down -v    # stop, wipe pgdata (re-runs schema.sql on next up)
```

**Frontend dev (host):**
```bash
cd Frontend && npm run dev   # http://localhost:3000
```

**Apply schema (target — Phase 1+):**
```bash
psql "$DATABASE_URL" -f Backend/schema.sql
```

**Codex review (use after each phase implementation):**
```bash
codex review --uncommitted        # review staged/unstaged diff
codex review --base main          # review the whole branch diff
codex exec "<prompt>"             # ask ChatGPT a focused question with optional stdin
```

**Inspect tables (target — Phase 2+):**
```bash
docker compose exec db psql -U esports -d esports -c "\dt"
```

---

## 📝 Architectural Decisions (ADRs)

- **[2026-04-15] Brand rename:** "College Rankers" / "CSU Esports Hub" → **Campus Rankers** (campusrankers.com). Folder name `senior-design-esports-project` predates the rename.
- **[2026-04-16] Mongo → Postgres (in-progress, restart):** Bracket routing is fundamentally relational; needed ACID for state transitions and JOINs for live aggregates. No prod data to migrate (no live users). First attempt was lost (see Graveyard #6); restarting on `postgres-migration-v2` with phased SDD-gated PRs.
- **[2026-04-16] Parameterized SQL with psycopg2 + RealDictCursor over an ORM (target):** Lightweight, transparent, no migration-tooling overhead. Trade-off: less safety. Mitigation: every query goes through `get_cursor` / `get_conn`.
- **[2026-04-17] Debian Postgres image over alpine (target):** Glibc collation parity with DO Managed Postgres. Worth ~200MB.
- **[2026-04-18] Flat `conferences` table with `tier` column over nested `conference_groups` (target):** NACE's Premier/Plus → D1–10 was the ambiguous case. 20 docs vs 2+10+10, but a single uniform `Org → Season → Conference` picker everywhere. Free visual grouping via `<optgroup label={tier}>`.
- **[2026-05-02] Postgres migration uses gated, phased SDD.** Each phase has its own SPEC under `migrations/postgres-v2/`, gate-A approval before implementation, and gate-B approval (after `codex review`) before commit.
- **[2026-05-02] V1 scope: Val + LoL only.** Multi-game expansion (Smash, OW, RL, CoD, Fortnite, TFT, TF2) deferred until per-game data shape is researched.
- **[2026-05-02] RSO consent as the player visibility gate.** Profiles private by default. RSO sign-in = consent. Filter at the data layer.

---

## 🗺 Phase Roadmap (Postgres Migration v2)

- [ ] **Phase 0** — Branch `postgres-migration-v2` + doc reality reconciliation (in progress, this PR)
- [ ] **Phase 1** — Author `Backend/schema.sql` (target Postgres schema, idempotent)
- [ ] **Phase 2** — Convert `Backend/core/db.py` to psycopg2 ThreadedConnectionPool; update `requirements.txt`, `Backend/.env.example`, `main.py` startup
- [ ] **Phase 3** — Port routers in dependency order (leagues → teams → players → matches → tournaments → admin); each router its own commit, each verified with curl
- [ ] **Phase 4** — Frontend reconciliation: confirm camelCase wire contract preserved; remove any Mongo-shaped expectations (`_id` strings, etc.)
- [ ] **Phase 5** — Player accounts + RSO consent gate (`users` table, `player_consents` table, RSO callback flow, public endpoints filter on consent)
- [ ] **Phase 6** — Provision DO Managed Postgres, update `.do/app.yaml`, smoke test against prod URL, cutover

---

## Post-launch backlog (not migration scope)

- Live-computed standings (replace any stale snapshot fields)
- Mobile-responsive tables
- Consistent design-token system
- Real-time WebSocket updates (admin score submission → live dashboard)
- Riot prod API key + automated ingestion at scale
- Multi-game expansion (per-game research first)
