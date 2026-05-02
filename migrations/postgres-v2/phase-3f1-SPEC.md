# Phase 3f.1 — Port admin auth + simple-CRUD endpoints

**Migration:** Postgres v2
**Branch:** `postgres-migration-v2` (continues from Phase 3e commit `ad14e16`)
**Phase order:** Phase 3f.1 of seven (split into 3f.1, 3f.2, 3f.3 due to size)
**Status:** Draft, codex gate-A pending

## Phase Goal

Port the auth-protected non-match admin endpoints from Mongo to Postgres. Excludes `/api/admin/matches` CRUD (Phase 3f.2 — heavy multi-statement transactions) and `/api/admin/stats` (Phase 3f.3). Also drops the legacy `/api/admin/leagues` CRUD endpoints — addressed in 3f.3.

## Frontend wire contract preservation (Path A)

Path A still applies: preserve the camelCase wire shape the existing admin frontend expects. Inspect `Frontend/app/admin/{teams,players,leagues,...}/page.tsx` for exact field names; common pattern is `_id` (string), `teamName`, `mapWins`, `displayName`, `riotId`, `teamIds[]`, etc.

## Technical Requirements

### File Manifest (4 paths committed)

| Action | Path | Purpose |
|---|---|---|
| **Rewrite** | `Backend/core/admin_router.py` | First slice (~700 lines): auth + schools/teams/players/orgs/seasons/conferences/memberships/leagues-tree. Match CRUD + stats remain TODO/pass-through (added in 3f.2 / 3f.3). |
| **Modify** | `Backend/.env.example` | Add `ADMIN_PASSWORD` and `ADMIN_SECRET` documentation lines (currently missing per Phase 2 deferral). |
| **Modify** | `docker-compose.yml` | Add `ADMIN_PASSWORD` + `ADMIN_SECRET` to backend service `environment` block with dev defaults. |
| **Create** | `migrations/postgres-v2/phase-3f1-SPEC.md` | This spec. |

### Auth (unchanged from Mongo — pure Python)

- `POST /api/admin/login`: accepts `{password}`. Compares to `ADMIN_PASSWORD` env (constant-time). Returns `{token, expiresIn}`.
- `GET /api/admin/me` with `require_admin` dep: returns `{ok: true}`.
- HMAC token format: `f"admin:{exp}.{hex_sha256_signature}"`. TTL 12h. Verified by `_sign()` + `hmac.compare_digest`.
- `ADMIN_SECRET` defaults to `ADMIN_PASSWORD` if unset (preserves Mongo behavior); falls back to `"dev-insecure-secret"` if both unset.

### Common helpers

```python
def _slugify(s: str) -> str: ...   # unchanged (lower + non-alphanumeric → hyphen + strip)
def _int_id(s: str) -> int: ...    # replaces _oid (raise 400 on non-int)
def _get_active_season(cur) -> dict | None:
    """Return earliest active season globally, or None if none exist.
    Used as the default season for player→team links when frontend doesn't pass one."""
    ...
def _label_game(db_value): ...      # 'valorant' → 'Valorant', etc.
def _normalize_game_filter(label): ...  # input mapping (same as other Phase-3 routers)
```

### `Backend/.env.example` additions

```ini
# --- Admin auth (single-shared-password model) ---
# Set a real strong password in production. Empty disables /api/admin/login (returns 500).
ADMIN_PASSWORD=admin
# Token signing secret. Defaults to ADMIN_PASSWORD if unset; production MUST set both
# to different strong values.
ADMIN_SECRET=
```

### `docker-compose.yml` additions (backend service env block)

```yaml
ADMIN_PASSWORD: admin
ADMIN_SECRET: dev-insecure-secret
```

(Dev defaults; CONSTITUTION mandates "do NOT set in `.env` while using docker compose" — these compose values are the in-docker source of truth. Real prod values go in DO's secrets, not committed.)

### Endpoints (~25)

For each I list: SQL query shape, errors, response shape. Brevity over completeness — implementation reads these as a contract.

#### Schools
- `GET /api/admin/schools?q=&limit=20`: `SELECT * FROM schools WHERE name ILIKE '%' || %s || '%' ORDER BY name LIMIT %s`. q param is sanitized via parameterization (no regex on Mongo side; ILIKE on Postgres). Returns list with `_id` as `str(id)`.
- `POST /api/admin/schools` `{name}`: idempotent on slug. SQL: `INSERT ... ON CONFLICT (slug) DO UPDATE SET ... RETURNING *` (or SELECT-then-INSERT pattern; either fine). Returns the school doc with `_id` as `str(id)`.

#### Teams (admin)
- `GET /api/admin/teams?q=&schoolId=&game=&limit=50`: `SELECT * FROM teams WHERE (name ILIKE %s OR school_name ILIKE %s) AND (school_id = %s::bigint OR %s::bigint IS NULL) AND (game = %s OR %s IS NULL)`. Returns rows with `_id`, `teamName` (alias of `name`), `school` (alias of `school_name`), `mapWins`, `mapLosses`, etc., to match Mongo wire format.
- `POST /api/admin/teams` `{schoolId, name, game, tier?}`: validates schoolId exists; idempotent on (slug, game). Returns the team.

#### Players (admin)
- `GET /api/admin/players?q=&teamId=&freeAgent=&limit=&skip=&paginated=`: ILIKE on display_name OR riot_id. teamId filter via JOIN to `team_players`. freeAgent: WHERE NOT EXISTS active membership. Pagination: standard. Returns list (or `{items, total}` if `paginated=true`).
  - Wire shape per item: `_id`, `displayName`, `riotId`, `role`, `teamIds: [str(id), ...]` (resolved via team_players JOIN).
- `POST /api/admin/players` `{displayName, riotId?, role?, teamIds[]}`: INSERT player + INSERT team_players rows (one per teamId, all using the **earliest active season** as default). 400 if teamIds non-empty AND no active season exists.
- `PATCH /api/admin/players/{player_id}/link` `{teamId}`: validates player_id and teamId. Same active-season default logic. INSERT INTO team_players ON CONFLICT (team_id, player_id, season_id) WHERE left_at IS NULL DO NOTHING. Sets `players.active = true`. Returns the updated player.
- `PATCH /api/admin/players/{player_id}/unlink` `{teamId}`: UPDATE team_players SET left_at = NOW() WHERE player_id = %s AND team_id = %s AND left_at IS NULL. If player has zero remaining active memberships, sets `players.active = false`. Returns the updated player.

#### Organizations
- `GET /api/admin/orgs?q=&game=&limit=`: ILIKE on name OR abbreviation. game filter against array column: `%s = ANY(games)` or `%s IS NULL`. Returns list.
- `POST /api/admin/orgs` `{name, abbreviation, games[]}`: idempotent on slug. Slug = `_slugify(abbreviation.upper())`. Returns the org.
- `PATCH /api/admin/orgs/{org_id}` `{name?, abbreviation?, games?}`: dynamic UPDATE SET. If abbreviation changes, slug rebuilds.
- `DELETE /api/admin/orgs/{org_id}`: **manual cascade** in dep order (Phase 1 schema uses ON DELETE RESTRICT for org refs, so we cascade in app code):
  ```sql
  -- All inside one transaction:
  DELETE FROM team_memberships WHERE conference_id IN (SELECT id FROM conferences WHERE org_id = %s);
  DELETE FROM team_memberships WHERE season_id IN (SELECT id FROM seasons WHERE org_id = %s);
  DELETE FROM conferences WHERE org_id = %s;
  DELETE FROM seasons WHERE org_id = %s;
  DELETE FROM organizations WHERE id = %s;
  ```
  Use `with get_conn() as conn: conn.cursor() ... conn.commit()`.

#### Seasons
- `GET /api/admin/seasons?orgId=&active=&limit=`: filter as Mongo. ORDER BY year DESC, semester ASC.
- `POST /api/admin/seasons` `{orgId, year (e.g. "2025-2026"), semester ("Fall"|"Spring"|"Summer"), active=false}`: validates org. Year regex `^\d{4}-\d{4}$`. **Maps year+semester → schema's int year + lowercase semester:** semester='Fall' → year=first part as int + semester='fall'; 'Spring' → second part as int + 'spring'; 'Summer' → first part + 'summer'. Constructs label as `{org.abbreviation} {Semester} {ShownYear}` matching Mongo `_season_label`. If `active=true`: rely on the partial-unique index from Phase 1 schema to enforce uniqueness; pre-set existing actives to false in same transaction (matches Mongo behavior).
- `PATCH /api/admin/seasons/{season_id}`: dynamic update, with active-flag handling (deactivate siblings if becoming active).
- `DELETE /api/admin/seasons/{season_id}`: cascades memberships in same transaction.

#### Conferences
- `GET /api/admin/conferences?orgId=&q=&limit=`: filters as Mongo.
- `POST /api/admin/conferences` `{orgId, name, shortName?, tier?, kind?}`: idempotent on (org_id, slug). Slug = `_slugify(f"{tier or ''} {name}".strip())`.
- `PATCH /api/admin/conferences/{conf_id}`: dynamic update; rebuild slug if name/tier changes.
- `DELETE /api/admin/conferences/{conf_id}`: cascades memberships.

#### Team Memberships (M2M)
- `GET /api/admin/memberships?teamId=&conferenceId=&seasonId=&active=&limit=`: filter as Mongo. Returns rows enriched with `seasonLabel`, `conferenceName`, `conferenceTier`, `orgAbbreviation`, `teamName` via JOINs to teams/seasons/conferences/organizations.
- `POST /api/admin/memberships` `{teamId, conferenceId, seasonId, active=true}`: validates all three exist + conference.org_id == season.org_id. Idempotent on (team_id, conference_id, season_id).
- `PATCH /api/admin/memberships/{membership_id}` `{active}`: sets active flag.
- `DELETE /api/admin/memberships/{membership_id}`: simple DELETE.

#### Leagues Tree (compound)
- `GET /api/admin/leagues-tree`: returns `[{...org, seasons: [...], conferences: [...]}, ...]`. Implemented as 3 SQL queries (orgs + seasons + conferences) and assembled in Python (one round trip per query).

### Out of Scope

- `/api/admin/matches` CRUD → Phase 3f.2.
- `/api/admin/stats` → Phase 3f.3.
- `/api/admin/leagues` legacy endpoints → deleted in Phase 3f.3.
- Index management helpers (`_ensure_match_index`, `_fix_matchid_index`, `_ensure_hierarchy_indexes`) → all Mongo-specific. Removed entirely; Phase 1 schema.sql is the source of truth.

## Acceptance Criteria

- [ ] Diff allow-list: 4 paths exactly.
- [ ] No `pymongo`, `bson`, `certifi`, `core.db.get_db`, `_oid`, `ObjectId`, `InvalidId`, `DuplicateKeyError`, `_ensure_*_index`, `_fix_matchid_index` references.
- [ ] All SQL parameterized.
- [ ] Skip count drops to **1** (valorant only — admin_router is now ported).
- [ ] `POST /api/admin/login {password}` with the configured `ADMIN_PASSWORD` returns 200 + token; wrong password 401; missing password env (empty string) → 500.
- [ ] `GET /api/admin/me` without token → 401; with valid token → `{ok: true}`.
- [ ] Schools / teams / players / orgs / seasons / conferences / memberships / leagues-tree endpoints work end-to-end against seeded data.
- [ ] DELETE /api/admin/orgs/{id} successfully cascades through memberships → seasons + conferences → org.
- [ ] POST /api/admin/seasons with active=true correctly deactivates sibling seasons (no DB UNIQUE violation).
- [ ] All wire shapes match the Mongo Path-A contract (`_id` as string, `teamName`, `mapWins`, etc.).
- [ ] `docker-compose.yml` adds `ADMIN_PASSWORD` + `ADMIN_SECRET` to backend env block.
- [ ] `Backend/.env.example` documents the two new vars.

## Verification Plan

```bash
docker compose down -v
docker compose up --build -d
until /usr/bin/curl -fs http://localhost:8000/api/health > /dev/null 2>&1; do sleep 1; done

# Auth.
TOKEN=$(/usr/bin/curl -s -X POST http://localhost:8000/api/admin/login -H 'Content-Type: application/json' -d '{"password":"admin"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")
echo "TOKEN: ${TOKEN:0:30}..."
/usr/bin/curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/admin/me

# Wrong password.
/usr/bin/curl -s -o /dev/null -w 'wrong-pw: %{http_code}\n' -X POST http://localhost:8000/api/admin/login -H 'Content-Type: application/json' -d '{"password":"wrong"}'

# Schools CRUD.
/usr/bin/curl -s -X POST -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"Northeastern University"}' \
  http://localhost:8000/api/admin/schools | python3 -m json.tool
/usr/bin/curl -s -H "Authorization: Bearer $TOKEN" 'http://localhost:8000/api/admin/schools?q=North' | python3 -m json.tool

# Org / season / conference cascade.
ORG_RES=$(/usr/bin/curl -s -X POST -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"Test Org","abbreviation":"TST","games":["Valorant"]}' \
  http://localhost:8000/api/admin/orgs)
ORG_ID=$(echo $ORG_RES | python3 -c "import sys,json; print(json.load(sys.stdin)['_id'])")
/usr/bin/curl -s -X POST -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d "{\"orgId\":\"$ORG_ID\",\"year\":\"2025-2026\",\"semester\":\"Fall\",\"active\":true}" \
  http://localhost:8000/api/admin/seasons
/usr/bin/curl -s -X DELETE -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/admin/orgs/$ORG_ID
# Expect: {"ok": true}; subsequent GET /seasons returns no rows for that org.
```

## Rollback Plan

`git revert <phase-3f1-commit-sha>`.

## Risks & Open Questions

### Risk: Player team_players default season

Frontend's POST /admin/players sends teamIds[] with no seasonId. Phase 1 schema requires `team_players.season_id NOT NULL`. We default to "earliest active season globally" — if no active season exists, return 400. This may break admin player creation in fresh installs until a season exists. Documented; admin must create org+active season before linking players.

### Risk: ILIKE search vs Mongo `$regex`

Mongo regex was case-insensitive substring; ILIKE with `'%' || q || '%'` produces the same. Special characters in q are passed via parameterization so they're treated as literals.

### Risk: `_doc` Mongo→Postgres mapping is custom per-table

Different tables need different camelCase aliases (teams → teamName from name; map_wins → mapWins; team_memberships → teamName/seasonLabel/etc.). Each endpoint shapes its own response; no shared `_doc` helper. Alternative: extend `core/projection.py` with per-table aliases. **Defer**; per-endpoint manual shaping is clearer for this phase given the contract preservation.

### Risk: Seasons schema mismatch

Mongo: `year` is a string like `"2025-2026"`, `semester` is `"Fall"`/`"Spring"`/`"Summer"`. Postgres: `year INTEGER`, `semester TEXT CHECK IN ('fall','spring','summer')`. Router translates at the boundary: `"2025-2026" + "Fall"` → `year=2025, semester='fall'`. Response converts back: `year=2025, semester='fall'` → `"2025-2026", "Fall"`. The mapping is lossy in some directions (a Postgres season can't tell if it was "2025-2026" or "2025-2030" — we always synthesize `"2025-2026"` from `year`). This is acceptable because the Mongo `year` was always a 4-year-pair string; we choose the convention `f"{year}-{year+1}"`.

## Decisions Made (Path A)

| # | Decision | Choice |
|---|---|---|
| 1 | Wire shape | Mongo-compatible camelCase: _id, teamName/mapWins/teamIds[]/etc. |
| 2 | _oid → _int_id | All admin path params are numeric; 400 on non-int. |
| 3 | Player teamIds default season | Earliest active season globally; 400 if none. |
| 4 | Org/season/conference DELETE cascade | Manual app-side cascade in correct order (schema uses RESTRICT). |
| 5 | seasons.year mapping | "2025-2026" string ↔ INTEGER 2025 (response synthesizes string back as `f"{year}-{year+1}"`). |
| 6 | Index management helpers | Removed entirely; schema.sql owns indexes. |
| 7 | One-active-season-per-org enforcement | Rely on Phase 1's partial unique index + app-level pre-deactivation in same transaction. |
| 8 | _doc helper | Per-endpoint manual shaping; no shared mapper for this phase. |
