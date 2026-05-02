# Phase 3b — Port `tournaments_router` to Postgres

**Migration:** Postgres v2
**Branch:** `postgres-migration-v2` (continues from Phase 3a commit `89ca072`)
**Phase order:** Phase 3b of seven Phase-3 sub-phases
**Status:** Draft, codex gate-A pending

## Phase Goal

Port `Backend/core/tournaments_router.py` from Mongo to psycopg2 against the Phase 1 `tournaments` table. Preserve the API contract (`GET /api/tournaments` list, `GET /api/tournaments/{slug}` detail) with the camelCase wire format the frontend expects. Establish a shared snake_case→camelCase projection helper (`core/projection.py`) that subsequent router-port phases (3c–3g) will reuse — refactoring out duplication after the fact would be wasteful.

## Technical Requirements

### File Manifest (3 paths committed)

| Action | Path | Purpose |
|---|---|---|
| **Create** | `Backend/core/projection.py` | Shared `to_camel(row)` helper for snake_case→camelCase top-level dict-key conversion. ~25 lines. |
| **Rewrite** | `Backend/core/tournaments_router.py` | psycopg2-based: list (with optional `game` filter) + get-by-slug. Uses `get_cursor()` from `core/db.py`, returns camelCase via `to_camel()`. |
| **Create** | `migrations/postgres-v2/phase-3b-SPEC.md` | This spec. |

**Backend/main.py is intentionally NOT modified.** The existing `tournaments_router = _try_router("core.tournaments_router", "tournaments_router")` line and the `if tournaments_router is not None: app.include_router(...)` guard already exist from Phase 2. Once the rewritten `tournaments_router.py` no longer imports legacy Mongo deps, `_try_router()` returns the real router (not None), and registration activates automatically. No diff in main.py = phase-3b commit.

### `core/projection.py` shape

```python
"""Snake_case → camelCase wire-format helpers for Postgres routers.

The DB returns RealDictCursor rows with snake_case keys (matches `schema.sql`).
The frontend wire format is camelCase (CONSTITUTION §4 — "camelCase wire format
preserved across the migration"). `to_camel()` is the bridge.
"""

def _camelize(snake: str) -> str:
    if "_" not in snake:
        return snake
    head, *tail = snake.split("_")
    return head + "".join(p[:1].upper() + p[1:] for p in tail)


def to_camel(row: dict | None) -> dict | None:
    """Convert top-level snake_case keys to camelCase. Returns None if input
    is None (RealDictCursor.fetchone() returns None for no-match queries).

    Does NOT recurse into nested dicts/lists. JSONB columns already store
    application-controlled JSON; their contents pass through unchanged.
    """
    if row is None:
        return None
    return {_camelize(k): v for k, v in row.items()}
```

### `core/tournaments_router.py` shape

Two endpoints:

```python
@router.get("/")
def list_tournaments(game: Optional[str] = Query(None)):
    """List tournaments. Optional game filter ('valorant'|'lol').
    Returns [] when none."""

@router.get("/{slug}")
def get_tournament(slug: str):
    """Get one tournament by slug. 404 if not found."""
```

**SQL (parameterized):**
```python
with get_cursor() as cur:
    if game is not None:
        cur.execute("SELECT * FROM tournaments WHERE game = %s ORDER BY start_date DESC NULLS LAST, name", (game,))
    else:
        cur.execute("SELECT * FROM tournaments ORDER BY start_date DESC NULLS LAST, name")
    return [to_camel(r) for r in cur.fetchall()]
```

```python
with get_cursor() as cur:
    cur.execute("SELECT * FROM tournaments WHERE slug = %s", (slug,))
    row = cur.fetchone()
    if row is None:
        raise HTTPException(404, f"Tournament '{slug}' not found")
    return to_camel(row)
```

### Removed behavior

The Mongo router accepted a `status` query parameter and filtered `db["tournaments"].find({"status": status})`. The Phase 1 `tournaments` table has **no `status` column** (the schema treats tournament state as derivable from `start_date`/`end_date`, or didn't model it at all). Phase 3b drops the `status` query parameter. If a future feature wants explicit status, that's a schema-migration phase + frontend update; not in 3b scope. Documented in SQL comment.

### Out of Scope

- Tournament write endpoints (no POST/PATCH/DELETE in 3b — those live in `admin_router` and will be ported in Phase 3f).
- Adding a `status` column to the schema.
- Pagination (the Mongo version returned all tournaments unfiltered; with no live data the volume is tiny and pagination is a Phase 4 / post-launch concern).
- Tournament detail enrichment (joining `teams` JSONB IDs to live `teams` rows for richer display) — Phase 4 frontend can decide if this is needed.
- Touching `core/models.py` Pydantic models — the new router returns plain dicts via FastAPI's default JSON encoder.

## API Contract

### `GET /api/tournaments`

Query params: `game` (optional, `'valorant'` or `'lol'`).

Response 200:
```json
[
  {
    "id": 1,
    "name": "Spring Open 2027",
    "slug": "spring-open-2027",
    "game": "valorant",
    "startDate": "2027-03-15",
    "endDate": "2027-04-30",
    "teams": [...],
    "matches": [...],
    "createdAt": "...",
    "updatedAt": "..."
  }
]
```

Empty array when no tournaments exist or filter excludes all.

### `GET /api/tournaments/{slug}`

Response 200: same shape as a single list element above.
Response 404: `{"detail": "Tournament 'X' not found"}` when slug doesn't exist.

## Acceptance Criteria

- [ ] `git diff --name-only HEAD~1..HEAD` for Phase 3b's commit lists exactly: `Backend/core/projection.py` (added), `Backend/core/tournaments_router.py` (modified), `migrations/postgres-v2/phase-3b-SPEC.md` (added). `Backend/main.py` is **not** modified (the existing `_try_router` line auto-activates).
- [ ] `Backend/core/tournaments_router.py` does not import `pymongo`, `bson`, `certifi`, or `core.db.get_db`. It does import `from core.db import get_cursor` and `from core.projection import to_camel`.
- [ ] `docker compose down -v && docker compose up --build -d` boots clean.
- [ ] Option Z log breakdown: total skipped routers = **5** (down from 6). `tournaments_router` no longer appears in skip list.
- [ ] `/api/tournaments` returns HTTP 200 with `[]` (no seed data).
- [ ] `/api/tournaments?game=valorant` returns HTTP 200 with `[]`.
- [ ] `/api/tournaments?game=invalid` returns HTTP 200 with `[]` (no validation; param is just used in WHERE clause — invalid values match nothing).
- [ ] `/api/tournaments/missing` returns HTTP 404 with `{"detail":"Tournament 'missing' not found"}`.
- [ ] `/openapi.json` paths now include `/api/tournaments/` and `/api/tournaments/{slug}` in addition to `/`, `/health`, `/api/health`.
- [ ] `to_camel()` edge cases (developer can spot-check via `python -c`):
  - `to_camel(None)` → `None`
  - `to_camel({"name": "x"})` → `{"name": "x"}` (no underscore, unchanged)
  - `to_camel({"start_date": "x", "team_name": "Y"})` → `{"startDate": "x", "teamName": "Y"}`
  - `to_camel({"a__b": 1})` → `{"aB": 1}` (consecutive underscores collapse — empty parts contribute nothing)
  - `to_camel({"_id": 1})` → `{"Id": 1}` (leading underscore: empty head + 'id' as tail; output is title-cased 'Id')
  - `to_camel({"end_": 1})` → `{"end": 1}` (trailing underscore: 'end' head + empty tail; output drops the trailing nothing)
- [ ] No `f"...{user_input}..."` SQL strings; only `cur.execute(sql, params)` parameterized form.

## Verification Plan

```bash
docker compose down -v
docker compose up --build -d
until /usr/bin/curl -fs http://localhost:8000/api/health > /dev/null 2>&1; do sleep 1; done

# Skip count drops to 5.
docker compose logs backend --since 30s 2>&1 | grep -E "router '.+_router' skipped" | sort -u | wc -l
# Expect: 5.

# /api/tournaments — empty list, 200.
/usr/bin/curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8000/api/tournaments
# Expect: 200.
/usr/bin/curl -s http://localhost:8000/api/tournaments
# Expect: []

# Filter by game.
/usr/bin/curl -s 'http://localhost:8000/api/tournaments?game=valorant'
# Expect: []

# 404 on missing slug.
/usr/bin/curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8000/api/tournaments/missing-slug
# Expect: 404.

# OpenAPI route table.
/usr/bin/curl -s http://localhost:8000/openapi.json | python3 -c "import sys,json; print('\n'.join(sorted(json.load(sys.stdin)['paths'].keys())))"
# Expect: /, /api/health, /api/tournaments/, /api/tournaments/{slug}, /health

# Insert one tournament directly to confirm round-trip works (smoke).
docker compose exec -T db psql -U esports -d esports -c "INSERT INTO tournaments (name, slug, game, start_date, end_date, teams, matches) VALUES ('Test Cup', 'test-cup', 'valorant', '2027-03-01', '2027-03-15', '[]', '[]');"
/usr/bin/curl -s http://localhost:8000/api/tournaments | python3 -m json.tool
# Expect: one row with camelCase keys (startDate, endDate, createdAt, updatedAt).
/usr/bin/curl -s http://localhost:8000/api/tournaments/test-cup | python3 -m json.tool
# Expect: same row, single object (not array).
```

## Rollback Plan

```bash
git revert <phase-3b-commit-sha>
```

Brings back the previous Mongo-based tournaments_router.py (which was already failing the Option Z guard). The `core/projection.py` helper is also reverted, but Phase 3c-3g would have to re-create it — so a Phase 3b rollback effectively means re-doing the whole infra step.

## Risks & Open Questions

### Risk: dropping `status` query param breaks the frontend's tournament-status filter

The Mongo `tournaments` collection had a `status` field used by the `/tournaments` page's filter UI. The Phase 1 schema doesn't carry that field forward. Frontend will lose the filter; Phase 4 either re-adds the column (separate schema migration) or computes status from dates client-side. Documented in SPEC.

### Risk: ordering choice (`start_date DESC NULLS LAST, name`)

Default sort. If the frontend assumed a different order (e.g. alphabetical), Phase 4 testing will reveal it. Ordering is trivially changeable.

### Risk: this is the first router-port; the projection helper's contract gets reused 6 more times

If `to_camel()` has a subtle bug (e.g. doesn't handle 1-letter words, doesn't handle leading underscore), it propagates. Codex gate-B should review the helper carefully.

## Decisions Made (locked)

| # | Decision | Choice |
|---|---|---|
| 1 | Add shared projection helper now? | **Yes** — extracting on first reuse is wasteful; helper is small (~25 lines). |
| 2 | Drop `status` query param? | **Yes** — schema has no column; adding one is its own phase. |
| 3 | Pagination? | **Defer** — small data volume, post-launch concern. |
| 4 | Tournament-detail enrichment (resolve teams JSONB IDs to live team rows)? | **Defer** — Phase 4 frontend decides if this is needed. |
| 5 | Wire format | **camelCase** via `to_camel()` per CONSTITUTION §4 — non-negotiable. |
