# PROGRESS.md — Campus Rankers Hub

**Last Updated:** 2026-05-02 (evening — post-audit polish committed)
**Current Phase:** Postgres Migration v2 — **all code/config complete; awaiting production cutover** (Phase 6 manual provisioning)
**Branch:** `postgres-migration-v2` (19 commits ahead of `main`, all pushed; tip `99dd534`)

> **Agent Note:** You may autonomously edit this file. Append to ADRs and Graveyard as decisions accumulate. Keep this file as a *concise* state-of-the-world snapshot for AI context. The authoritative changelog lives in git.

---

## 🟢 Current Status (factual, as of 2026-05-02 evening)

The Mongo → Postgres migration is **code-complete on `postgres-migration-v2`**. `main` is still Mongo until the branch merges (post-cutover). Local docker compose stack runs end-to-end on Postgres with skip-count 0 (all routers ported). After the migration finished, a Playwright + codex + Claude-Sonnet site audit caught a handful of real bugs and stale CSU-era branding — all fixed, all pushed. The branch is ready for production deployment via the runbook at `migrations/postgres-v2/phase-6-RUNBOOK.md`.

**Latest 3 commits (post-migration polish):**
- `99dd534` — Brand sweep + remove legacy CSU/Vikings demo content (-1440/+115 lines)
- `0825e19` — Post-audit fixes: 7 of 8 review items
- `4ddf958` — SDD docs: reflect completed migration on branch

**Application code (on `postgres-migration-v2`):**
- [x] Frontend Next.js app (teams, players, matches, tournaments, leagues, valorant search, admin panel, about, privacy)
- [x] Backend FastAPI app on **PostgreSQL 18** via psycopg2 ThreadedConnectionPool (`core/db.py`)
- [x] All 6 public/admin routers ported: tournaments, teams, players, matches, admin, valorant. (`leagues_router` was deleted — replaced by org/season/conference hierarchy.)
- [x] Admin panel: login, manage schools/teams/players/orgs/seasons/conferences/memberships, manual match entry, edit/delete with W/L delta, dashboard stats, leagues-tree
- [x] RSO OAuth flow with consent gating: profiles default private, RSO sign-in = active consent, public APIs filter on consent at the data layer
- [x] Riot RSO scaffolding in `Backend/valorant/`; `rso_tokens` table-backed
- [x] Footer health pill polls `/api/health` every 60s (now pings Postgres)
- [x] Rate limiting (60/min per-IP default via slowapi)
- [x] Wire format standardized: canonical camelCase + lowercase game enum (`'valorant'` / `'lol'`); UI maps to TitleCase display labels via `Frontend/app/_shared/gameLabel.ts`
- [x] CVAL match ingestion script `Backend/IngestCVALMatches.py` (still Mongo-targeted; rewrite is post-launch backlog — admin manual entry covers v1)

**Schema (`Backend/schema.sql` — 15 tables, idempotent):**
- [x] `schools`, `organizations`, `seasons`, `conferences`, `teams`, `team_memberships`, `players`, `team_players` (junction), `player_consents`, `matches`, `player_match_stats` (thin core), `pms_valorant_details`, `pms_lol_details`, `tournaments`, `rso_tokens`
- [x] Critical DB-level invariants: sparse-unique `matches.riot_match_id`, partial unique on `seasons(org_id) WHERE active`, partial unique on `player_consents(player_id) WHERE revoked_at IS NULL`, `team1_id <> team2_id` CHECK on matches, `>= 0` CHECKs on all counter columns, `cardinality(games) > 0 AND games <@ ARRAY['valorant','lol']` on organizations
- [x] `set_updated_at()` trigger on every table with `updated_at`

**Infrastructure (`postgres-migration-v2`):**
- [x] `docker-compose.yml` runs the full stack (db + backend + frontend) end-to-end, verified at every phase
- [x] `Backend/Dockerfile` and `Frontend/Dockerfile` ready for DO deploy
- [x] `.do/app.yaml` updated for Phase 6: `databases:` block declares the managed Postgres cluster, `DATABASE_URL` auto-wired via `${db.DATABASE_URL}`, all secrets enumerated (ADMIN_PASSWORD/SECRET, RIOT_API_KEY, RSO_*, SESSION_SECRET)

**Migration index:** `migrations/postgres-v2/` contains per-phase SPECs + the README + the production cutover runbook.

**What is NOT yet done (Phase 6 manual provisioning — developer's plate):**
- [ ] Provision the DO App Platform app + managed Postgres cluster (`doctl apps create --spec .do/app.yaml`)
- [ ] Apply `Backend/schema.sql` against the managed cluster (one-shot via `psql`)
- [ ] Set production secrets in DO Console (ADMIN_PASSWORD, ADMIN_SECRET, RIOT_API_KEY, RSO_CLIENT_ID, RSO_CLIENT_SECRET, SESSION_SECRET)
- [ ] Update Riot RSO portal redirect URI to `${APP_URL}/api/valorant/auth/callback`
- [ ] Smoke test prod, then PR `postgres-migration-v2` → `main`

**Out-of-band / non-blocking:**
- [ ] Riot production API key (currently dev-tier — apply when ready for automated ingestion)
- [ ] Custom domain DNS (campusrankers.com → DO app)

---

## 🚧 Active Blockers & Known Bugs

- **Riot production API key** — dev-tier rate limits real ingestion. Required for automated matches; admin manual entry works fine without it.
- **DO Managed Postgres provisioning** — pending developer action; runbook ready.
- **`Backend/IngestCVALMatches.py`** still Mongo-coded. Move to `Backend/archive/` or rewrite for Postgres post-launch.
- **`Backend/migrate.py` and `Backend/migrate_leagues.py`** — Mongo-era backfill scripts; safe to delete or move to `Backend/archive/`.

---

## 🪦 The Graveyard (Things We Tried That Failed)

(Preserved verbatim from prior PROGRESS — these are real, hard-won lessons.)

1. **[2026-04-20] Frontend `DuplicateKeyError` catch-only as 409 fix:** Caught the symptom but missed the actual culprit (`matchId_1` non-sparse index). The reversed-team `$or` pre-check was a useful guard but not the root cause.
    - **The Fix:** `_fix_matchid_index()` drops and recreates `matchId_1` as `sparse=True` at module load (commit `8cec6a5`). Full investigation in `bug-409-match-duplicate.md`. **Carried forward in Postgres** as the partial unique index `uq_matches_riot_match_id ... WHERE riot_match_id IS NOT NULL`.

2. **[2026-04-23] `NEXT_PUBLIC_API_BASE_URL`:** Used in `Frontend/app/league/stats/page.tsx` and `Frontend/app/admin/adminClient.ts`, but `next.config.ts` only exposes `NEXT_PUBLIC_BACKEND_URL`. Variable resolved to `undefined` on DO, crashing the entire LoL stats page.
    - **The Fix:** Replaced both references with `NEXT_PUBLIC_BACKEND_URL` (with `http://localhost:8000` fallback). Removed the null-guard throw. **Never use `NEXT_PUBLIC_API_BASE_URL`.**

3. **[2026-04-17] PG18 `/var/lib/postgresql/data` mount path:** First `docker compose up` failed — postgres:18+ moved the recommended mount point to the parent dir to support `pg_upgrade --link`.
    - **The Fix:** Volume mount changed to `pgdata:/var/lib/postgresql`; ran `docker compose down -v` to wipe the half-init volume.

4. **[2026-04-17] `postgres:18-alpine`:** Used briefly for size. Musl libc has different collation/locale behavior than DO's Debian-based Managed Postgres → text-sort drift between local and prod.
    - **The Fix:** Reverted to `postgres:18` (Debian). ~200MB extra is worth predictable `ORDER BY`.

5. **[2026-04-15] Inline JSX fetcher in `match/page.tsx` Typeahead:** `fetchPlayersForTeam(teamId)` called inline produced a new function reference per render → useEffect fired on all 5 rows on any change → race conditions on the 5th-player typeahead.
    - **The Fix:** Stable `fetchPlayersRaw(teamId, q)` via `useCallback` + `useMemo`-derived per-team fetcher functions.

6. **[2026-05-02] First Postgres migration was effectively lost.** Branch `origin/postgres-migration` (April 15 base) contained an incomplete attempt; `origin/stash-postgres-wip` (May 1) recovered ~2k lines from a stash but never merged. A MacBook wipe deleted the local copy and the developer believed the remote branch was also gone. Lesson: **any in-flight migration must be pushed to remote daily, not held in a local stash.** The `postgres-migration-v2` branch was pushed after every phase to avoid repeating this.

7. **[2026-05-02] Phase 3d list endpoint CTE bug:** initial draft used a single `DISTINCT ON (player_id)` CTE for both filtered and unfiltered list cases. Codex caught: filtering on `?team=team-b` would wrongly omit a player whose globally-earliest team was `team-a`. **The Fix:** two SQL paths — Path A (no team filter) uses the CTE for display-team enrichment; Path B (team filter) JOINs through `team_players` directly so any active membership matches.

8. **[2026-05-02] Phase 3f.1 player teamIds[] without season_id:** the new `team_players` junction requires `season_id NOT NULL`, but the admin frontend's POST /players sends `teamIds[]` with no season. **The Fix:** router defaults to "earliest active season globally"; returns 400 if no active season exists. Admin must create org+active season before linking players.

9. **[2026-05-02] Path A wire-format trap:** Phase 3c v1 attempted to standardize to camelCase + lowercase enum during the router port. Codex caught that the existing frontend uses snake_case fields (`win_rate`, `league_slug`, `recent_matches`, etc.) and TitleCase game labels (`"Valorant"`). Standardizing during a router-by-router port would have left the branch in a broken state for ~5 commits. **The Fix:** Path A — preserve existing wire shape during Phase 3 (router-side game-enum mapping shims, snake_case alias keys); Phase 4 sweeps the standardization across all routers + frontend types in one go.

---

## 🛠 Helpful Commands & Snippets

**Full local stack (works on `postgres-migration-v2`):**
```bash
docker compose up --build
docker compose exec backend pip freeze | grep -E '(psycopg2|fastapi)'
docker compose logs -f backend
docker compose down       # stop, keep pgdata
docker compose down -v    # stop, wipe pgdata (re-runs schema.sql on next up)
```

**Frontend dev (host):**
```bash
cd Frontend && npm run dev   # http://localhost:3000
```

**Apply schema (idempotent — safe to re-run):**
```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f Backend/schema.sql
```

**Admin auth flow:**
```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/admin/login \
  -H 'Content-Type: application/json' \
  -d '{"password":"admin"}' | jq -r .token)
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/admin/me
```

**Codex review (used through every phase of the migration):**
```bash
codex review --uncommitted                         # review staged+unstaged diff
codex review --base main                           # review the whole branch
codex exec --sandbox read-only "<prompt>" < input  # focused outside-eyes review
```

**Inspect tables:**
```bash
docker compose exec db psql -U esports -d esports -c "\dt"
docker compose exec db psql -U esports -d esports -c "\d+ matches"
```

---

## 📝 Architectural Decisions (ADRs)

- **[2026-04-15] Brand rename:** "College Rankers" / "CSU Esports Hub" → **Campus Rankers** (campusrankers.com). Folder name `senior-design-esports-project` predates the rename.
- **[2026-04-16] Mongo → Postgres:** Bracket routing is fundamentally relational; needed ACID for state transitions and JOINs for live aggregates. No prod data to migrate. **Completed on `postgres-migration-v2` 2026-05-02; production cutover pending.**
- **[2026-04-16] Parameterized SQL with psycopg2 + RealDictCursor over an ORM:** Lightweight, transparent, no migration-tooling overhead. Trade-off: less safety. Mitigation: every query goes through `get_cursor` / `get_conn`. Multi-statement transactions use `get_conn() + conn.cursor()`; never nested `get_cursor` inside `get_conn`.
- **[2026-04-17] Debian Postgres image over alpine:** Glibc collation parity with DO Managed Postgres. Worth ~200MB.
- **[2026-04-18] Flat `conferences` table with `tier` column over nested `conference_groups`:** NACE's Premier/Plus → D1–10 was the ambiguous case. 20 docs vs 2+10+10, but a single uniform `Org → Season → Conference` picker everywhere. Free visual grouping via `<optgroup label={tier}>`.
- **[2026-05-02] Postgres migration uses gated, phased SDD.** Each phase has its own SPEC under `migrations/postgres-v2/`, gate-A approval before implementation, and gate-B approval (after `codex review`) before commit. The user delegated approval to `codex exec` for the latter half of the migration.
- **[2026-05-02] V1 scope: Val + LoL only.** Multi-game expansion (Smash, OW, RL, CoD, Fortnite, TFT, TF2) deferred until per-game data shape is researched.
- **[2026-05-02] RSO consent as the player visibility gate.** Profiles private by default. RSO sign-in = consent. Filter at the data layer (`core/consent.py` `CONSENTED_FILTER_SQL`), not the UI layer.
- **[2026-05-02] Path 2 polymorphic core for player_match_stats.** Thin core (`player_match_stats`) + per-game detail tables (`pms_valorant_details`, `pms_lol_details`). Future games add `pms_<game>_details` without touching the core.
- **[2026-05-02] Path A wire-format strategy for Phase 3.** Preserve the existing snake_case-heavy frontend contract during the router-by-router port; standardize to canonical camelCase + lowercase enum in one Phase 4 sweep. Avoided "broken UI for 5+ commits."
- **[2026-05-02] Option Z router skipping for Phase 2.** Two-signal `_try_router()` guard (`e.name in {pymongo, bson, certifi}` OR `core.db.get_db` cannot-import-name) lets the app boot cleanly with all Mongo-bound routers absent until each is ported in Phase 3.

---

## 🗺 Phase Roadmap (Postgres Migration v2)

All phases complete on branch (Phase 6 prep). Production provisioning pending.

- [x] **Phase 0** — Branch + doc reality reconciliation (`31b356d`)
- [x] **Phase 1** — `Backend/schema.sql`, 15 tables, idempotent (`122ce4e`)
- [x] **Phase 2** — psycopg2 pool + `main.py` rewrite, Option Z router skipping (`d1adfeb`)
- [x] **Phase 3a** — Delete `leagues_router` (no Postgres equivalent) (`89ca072`)
- [x] **Phase 3b** — Port `tournaments_router` + add `core/projection.py` (`55fca8d`)
- [x] **Phase 3c** — Port `teams_router` (Path A) (`30df6c9`)
- [x] **Phase 3d** — Port `players_router` (CLOL/Val collapse) (`7a7456a`)
- [x] **Phase 3e** — Port `matches_router` (per-game JOIN; per-map score gap documented) (`ad14e16`)
- [x] **Phase 3f.1** — Admin auth + simple CRUD (`9113f9d`)
- [x] **Phase 3f.2** — Admin match CRUD with W/L delta (`0466689`)
- [x] **Phase 3f.3** — Admin `/stats` (`4e1118b`)
- [x] **Phase 3g** — Port `valorant_router` + RSO token storage (`f4bac2b`)
- [x] **Phase 4** — Wire-format reconciliation (camelCase + lowercase enum) (`d29822d`)
- [x] **Phase 5** — Player accounts + RSO consent gate (`2d20929`)
- [x] **Phase 6 (prep)** — `.do/app.yaml` + runbook (`703b633`)
- [x] **Post-audit polish** — Playwright site audit + codex review + Sonnet sub-agent review; 7 fixes (real bugs + polish) at `0825e19`; full brand sweep + legacy CSU demo removal at `99dd534`. See "Post-audit polish" §below.
- [ ] **Phase 6 (production)** — `doctl apps create --spec .do/app.yaml`, schema apply, secrets, Riot redirect URI, smoke test, PR to main, cutover. **See `migrations/postgres-v2/phase-6-RUNBOOK.md`.**

---

## 🔍 Post-audit polish (2026-05-02 evening)

After the migration code landed, ran a full Playwright site walk + had codex (ChatGPT) and a Claude Sonnet sub-agent independently review the result. Codex verdict: LAUNCH-AFTER-FIXES. Sonnet verdict: LAUNCH-AFTER-NITS. Both agreed the migration was fundamentally sound; both flagged specific issues. All flagged items addressed.

### Real bugs Sonnet caught (fixed in `0825e19`)

1. **`admin_router.create_player` hardcoded `game="valorant"`.** `PlayerCreate` had no `game` field; every LoL player created via admin was silently inserted as Val. Fix: added `game: Literal["valorant","lol"]` to the model + threaded through INSERT + admin/players form gained a Game `<select>`.
2. **`.do/app.yaml` pinned Postgres `version: "15"`** while local docker runs `postgres:18`. Violated CONSTITUTION's libc-parity rule. Bumped to `"17"` with a comment about overriding to whichever DO actually exposes at provisioning time.
3. **`ADMIN_SECRET` silent fallback chain.** Defaults to `ADMIN_PASSWORD` then `"dev-insecure-secret"` — fine for local but a footgun for prod. Added module-init warnings (ERROR if unset/equal-to-password/literal-fallback in non-DEBUG environments).

### Audit-flagged display + content gaps (fixed across `0825e19` + `99dd534`)

4. **Brand sweep + remove StratOS** (`99dd534`):
   - Page `<title>`: `CollegeRankers — CSU Esports Hub` → `Campus Rankers — Collegiate Esports Stats`. OpenGraph + Twitter card metadata updated.
   - Home hero `Cleveland State Esports · Season 2026` pill **deleted** (option A). Subtitle dropped "CSU's competitive" in favor of "collegiate". Logo alt: `CollegeEsportsTracker logo` → `Campus Rankers logo`.
   - `/about` page fully rewritten — was CSU-specific with a hardcoded VIKES_GREEN_ROSTER (5 fake players); now describes the national collegiate scope (CVAL, CLOL, NACE, NECC, ECAC) + RSO consent model + multi-game roadmap.
   - `/privacy` page: CSU + MongoDB Atlas + Netlify references replaced with the actual stack (Postgres on DO App Platform).
   - `/valorant/auth` subtitle reworded; "Connected Players" hardcoded VIKES roster section already deleted in `0825e19`.
   - StratOS navbar link removed (was a temporary external promo).
   - admin/match team-search placeholder: `CSU Vikes Green` → `NEU Valorant Red`.

5. **`/leagues` removed from navbar** — was 404'ing post-Phase-3a (the endpoint was deleted, hierarchy lives at `/api/admin/leagues-tree`). Direct URL still resolves to a graceful "Failed to load" state; the page is just no longer surfaced. A future enhancement could rewrite it as a public org/conference browser.

6. **`formatLabel()` helper** added to `Frontend/app/_shared/gameLabel.ts` — backend now returns canonical lowercase `'bo1'`/`'bo3'`/`'bo5'`; UI displays `BO1`/`BO3`/`BO5`. Applied at the 4 render sites that previously showed raw lowercase.

7. **CONSTITUTION.md §3 stale `players: teamIds[]` corrected.** Replaced with the `team_players` junction table + expanded the data-model summary with all the columns/constraints settled during the migration (rating, region, school_name, partial UNIQUE on player_consents, matches CHECKs, per-game pms_<game>_details tables).

8. **Legacy `/valorant` + `/valorant/stats` routes neutralized** (`99dd534`). The original CSU-era pages had ~1300 lines of hardcoded VIKES player demo data with no DB backing. Replaced both with thin redirects to `/teams` (where real Postgres-backed data lives). `valTeamSearchUtils.ts` deleted entirely.

### Audit artifacts kept locally (gitignored)

- `audit-NN-*.png` screenshots from the Playwright walk (12 pages × 1 home + 1 rebrand verify).
- `.playwright-mcp/` snapshots and console logs.
- `/tmp/site-audit-findings.md` — the consolidated audit doc that went to codex and the Sonnet sub-agent.

### Remaining post-launch work surfaced by the audit (not blockers)

- SEO/social metadata sweep: page-specific titles, descriptions, Open Graph cards.
- Mobile responsive pass on teams/players/matches/admin tables.
- Accessibility basics: keyboard nav, focus states, aria labels.
- Error states for API down, missing slugs, 5xx responses.
- Rate-limit `/api/admin/login` (separate from the global 60/min default).
- Empty-state copy review across all pages.
- Rewrite `/leagues` page as a public org/conference browser (or remove the route file).
- Eventually: rewrite `Backend/valorant/tracker_scraper.py` and `Backend/IngestCVALMatches.py` for Postgres (or remove if RSO-authenticated Riot API access replaces the need).

---

## Post-launch backlog (not migration scope)

- Per-map round scores on Valorant matches (Phase 1 schema gap; either redesign detail page or add per-map score columns in a follow-up)
- Tournament JSONB → normalized tables (Phase 1 punt)
- Multi-game expansion (Smash, OW, RL, CoD, Fortnite, TFT, TF2 — per-game research first; schema reserved space via `pms_<game>_details` pattern)
- Live-computed standings (replace any stale snapshot fields)
- Mobile-responsive tables
- Consistent design-token system
- Real-time WebSocket updates (admin score submission → live dashboard)
- Riot prod API key + automated ingestion at scale (rewrite `IngestCVALMatches.py` for Postgres)
- Move/delete `Backend/migrate.py` + `Backend/migrate_leagues.py` Mongo-era scripts
- DRY the `_GAME_*` mapping helpers (Phase 4 inlined them per-router; could fold into `core/projection.py`)
- Standardize player_match_stats `team_name` denormalization (currently snapshot-at-write, not back-filled)
- Admin frontend for `team_memberships` management (currently API-only)
