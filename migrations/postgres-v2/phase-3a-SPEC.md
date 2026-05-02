# Phase 3a — Delete `leagues_router`

**Migration:** Postgres v2 (Mongo → DigitalOcean Managed Postgres)
**Branch:** `postgres-migration-v2` (continues from Phase 2 commit `d1adfeb`)
**Phase order:** Phase 3a of seven Phase-3 sub-phases (3a leagues, 3b tournaments, 3c teams, 3d players, 3e matches, 3f admin, 3g valorant)
**Status:** Draft, awaiting codex gate-A

## Approval Flow (codex-as-proxy)

The developer (Daniel) delegated gate-A and gate-B approvals to `codex exec` for the remaining migration phases. This SPEC is reviewed by codex; on APPROVE / APPROVE-WITH-NITS (nits addressed), implementation proceeds. Same for gate-B on the staged diff. The developer is notified of progress between phases and pulled in only for: codex BLOCK verdicts, architectural deltas not anticipated by this SPEC, or anything outside the original scope.

## Phase Goal

Delete `Backend/core/leagues_router.py` and the `_try_router("core.leagues_router", ...)` line in `Backend/main.py`. The `leagues` collection has no Postgres equivalent — Phase 1's schema replaced the flat-leagues model with the `organizations` + `seasons` + `conferences` + `team_memberships` hierarchy (per `CONSTITUTION.md` §3 and ADR 2026-04-18). Continuing to expose `/api/leagues` from the migrated backend would be a doc-drift attractor: the route would either need to query data that doesn't exist (always 500/empty) or fabricate "league-like" rows from the new tables, which contradicts the migration's stated intent.

The frontend `/leagues` page currently fetches `/api/leagues` (verified at `Frontend/app/leagues/page.tsx:40`). It will 404 on this branch after Phase 3a lands. That is **acceptable** — the migration branch is not user-facing and the frontend will be rewritten against the new hierarchy in Phase 4.

## User Story

> As **the developer**, I want **the migrated backend to stop exposing `/api/leagues`**, so that **the API surface accurately reflects the new org/conference hierarchy and we don't carry a Mongo-era endpoint forward as a maintenance shim.**

## Technical Requirements

### File Manifest (3 paths)

| Action | Path | Purpose |
|---|---|---|
| **Delete** | `Backend/core/leagues_router.py` | Two-endpoint Mongo-bound router; replaced by org/conference hierarchy. |
| **Modify** | `Backend/main.py` | Remove the `leagues_router = _try_router("core.leagues_router", ...)` line and the `if leagues_router is not None: app.include_router(leagues_router, prefix="/api/leagues")` block. Update header docstring to say "6 routers" instead of "7" (the only remaining counts are skipped-but-still-present routers, not the deleted one). |
| **Create** | `migrations/postgres-v2/phase-3a-SPEC.md` | This spec. |

### Out of Scope

- Frontend changes (Phase 4 — `/leagues` page rewrite or removal).
- Building new `/api/organizations`, `/api/conferences` endpoints (a future phase, post-Phase-3 — the new hierarchy already has admin endpoints planned in `admin_router.py` for create/edit; public listing endpoints can be designed when needed).
- Touching `core/models.py`'s `LeagueResponse` model (it's unused after `leagues_router.py` is deleted, but pruning it is a separate cleanup; not blocking).

## API Contract

After Phase 3a:
- `GET /api/leagues` → 404
- `GET /api/leagues/<slug>` → 404

(These were the only two endpoints. No other routes use the `leagues_router` import.)

## Acceptance Criteria

- [ ] `git diff --name-only HEAD~1..HEAD` for the Phase 3a commit lists exactly: `Backend/core/leagues_router.py` (deleted), `Backend/main.py` (modified), `migrations/postgres-v2/phase-3a-SPEC.md` (created).
- [ ] `Backend/core/leagues_router.py` does not exist after the commit.
- [ ] `grep -n leagues_router Backend/main.py` returns zero hits.
- [ ] `docker compose down -v && docker compose up --build -d` boots clean.
- [ ] Option Z log breakdown after Phase 3a: total skipped routers = **6** (down from 7). Specifically: valorant=pymongo; tournaments+teams=core.db.get_db; players+admin+matches=bson. **leagues skip line is gone** (the router doesn't exist to attempt importing).
- [ ] `curl -i http://localhost:8000/api/leagues` returns HTTP 404.
- [ ] `curl -s http://localhost:8000/openapi.json | jq -r '.paths | keys | .[]'` still returns exactly `/`, `/health`, `/api/health`.
- [ ] No real `import` of `core.leagues_router` anywhere in Backend Python: `grep -rn 'leagues_router\|core\.leagues_router' Backend/ --include='*.py'` returns zero hits.
- [ ] Codex gate-B advisory: APPROVE or APPROVE-WITH-NITS (nits addressed before commit).

## Verification Plan

```bash
# 1. Apply changes (delete file + edit main.py + add spec).
# 2. Boot.
docker compose down -v
docker compose up --build -d
until /usr/bin/curl -fs http://localhost:8000/api/health > /dev/null 2>&1; do sleep 1; done

# 3. Confirm Option Z has 6 skips, none for leagues.
docker compose logs backend --since 30s 2>&1 | grep -E "router '.+_router' skipped" | sort -u
# Expect: 6 lines (valorant, tournaments, teams, players, admin, matches). No 'leagues_router' line.

# 4. Confirm /api/leagues is 404.
/usr/bin/curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8000/api/leagues
# Expect: 404

# 5. /openapi.json route table unchanged.
/usr/bin/curl -s http://localhost:8000/openapi.json | python3 -c "import sys,json; print('\n'.join(sorted(json.load(sys.stdin)['paths'].keys())))"
# Expect: /, /api/health, /health

# 6. No stale references.
grep -rn 'leagues_router\|core\.leagues_router' Backend/ --include='*.py'
# Expect: zero hits.
```

## Rollback Plan

```bash
git revert <phase-3a-commit-sha>
```

Trivial revert: brings back `leagues_router.py` and the `main.py` registration line. Schema and data layer are untouched.

## Risks & Open Questions

### Risk: frontend /leagues page breaks

Known and accepted. The migration branch is not user-facing. Phase 4 rewrites the frontend against the new hierarchy. If a reviewer wants to test the broken state for completeness, `curl -i http://localhost:3000/leagues` after the next `docker compose up` will show the page rendering with an error (since `/api/leagues` 404s). Acceptable.

### Risk: `core/models.py` LeagueResponse becomes orphaned

The Pydantic `LeagueResponse` model in `core/models.py` is imported only by `leagues_router.py`. After deletion, the model becomes unused but harmless. **Not pruning in Phase 3a** — keeps the diff minimal. A future cleanup phase can remove it (or the unused-import warning will surface in lint).

### Open: should `/api/leagues` redirect to `/api/conferences` once that exists?

Out of scope for Phase 3a. Phase 4 (or a later UX-focused phase) can decide whether to redirect or just remove the link from the navbar.

## Decisions Made (locked)

| # | Decision | Choice |
|---|---|---|
| 1 | Port vs delete | **Delete.** The Mongo `leagues` collection has no Postgres equivalent. Building a shim would be doc-drift. |
| 2 | Frontend handling | Defer to Phase 4. The branch is not user-facing during migration. |
| 3 | Scope of cleanup | Minimal — only `leagues_router.py` deletion + `main.py` edit + this SPEC. `core/models.py` LeagueResponse pruning deferred. |
