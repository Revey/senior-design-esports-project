# Phase 3d — Port `players_router` to Postgres (Path A)

**Migration:** Postgres v2
**Branch:** `postgres-migration-v2` (continues from Phase 3c commit `30df6c9`)
**Phase order:** Phase 3d of seven
**Status:** Draft, codex gate-A pending

## Phase Goal

Port `Backend/core/players_router.py` from Mongo to psycopg2 against the Phase 1 `players` table (with joins to `team_players` + `teams` for team resolution, and `player_match_stats` + `pms_<game>_details` + `matches` for the detail endpoint's recent-matches + frequency). Preserve the existing frontend wire contract per Path A.

The Mongo router had a split source (Valorant from `players` collection + LoL from `CLOL_player_stats` collection). The Phase 1 schema unifies both into a single `players` table discriminated by `game`. Phase 3d collapses the split — one query path, one normalize function.

## Frontend wire contract (preserved)

From `Frontend/app/players/page.tsx` and `[slug]/page.tsx`:

**`Player` (list):**
```ts
{ slug, displayName, riotId, role, game, team_name, team_slug, active }
```
Mix: camelCase `displayName`/`riotId`, snake_case `team_name`/`team_slug`, TitleCase `game` (`"Valorant"` / `"League of Legends"`).

**`PlayerProfile` (detail):**
```ts
{ ...Player, recent_matches: MatchStat[], frequency: FrequencyEntry[], frequency_field: "agent" | "champion" }
```

**`MatchStat`:**
```ts
{ matchId?, game?, mapName?, teamName?, agent?, champion?, role?, kills?, deaths?, assists?, acs?, cs?, win? }
```
All optional; camelCase throughout (`matchId`, `mapName`, `teamName`).

**`FrequencyEntry`:** `{ name, count }`.

## Technical Requirements

### File Manifest (2 paths committed)

| Action | Path | Purpose |
|---|---|---|
| **Rewrite** | `Backend/core/players_router.py` | psycopg2-based: list (game/team/role/sort/order/limit), detail (with recent_matches + frequency). |
| **Create** | `migrations/postgres-v2/phase-3d-SPEC.md` | This spec. |

### Endpoints

#### `GET /api/players`

Query params:
- `game` (optional): `"Valorant"` / `"League of Legends"` / `"All"` / omitted. Mapped via `_normalize_game_filter` (same convention as teams).
- `team` (optional): team slug. Filters via JOIN to `team_players` + `teams`.
- `role` (optional): role string (`"Duelist"`, `"Top"`, etc.) or `"All"` (no filter).
- `sort` (default `"displayName"`): one of `displayName | role | game`. Whitelist.
- `order` (default `"asc"`): `"asc"` | `"desc"`. Whitelist.
- `limit` (default 200, range 1–500).

SQL shape — two query paths, both enrich `team_name`/`team_slug`:

**Path A (no team filter): use a `DISTINCT ON` CTE to pick each player's earliest active team for display.**

```sql
WITH first_team AS (
    SELECT DISTINCT ON (tp.player_id)
           tp.player_id,
           t.name AS team_name,
           t.slug AS team_slug
    FROM team_players tp
    JOIN teams t ON t.id = tp.team_id
    WHERE tp.left_at IS NULL
    ORDER BY tp.player_id, tp.joined_at ASC
)
SELECT p.id, p.slug, p.display_name, p.name, p.riot_id, p.role, p.game, p.active,
       COALESCE(ft.team_name, '') AS team_name,
       COALESCE(ft.team_slug, '') AS team_slug
FROM players p
LEFT JOIN first_team ft ON ft.player_id = p.id
WHERE (%s::text IS NULL OR p.game = %s::text)
  AND (%s::text IS NULL OR p.role = %s::text)
ORDER BY <whitelisted> <ASC|DESC> NULLS LAST, p.display_name
LIMIT %s
```

**Path B (team filter present): JOIN directly through team_players + teams; show the requested team as the player's team_name/team_slug.**

```sql
SELECT p.id, p.slug, p.display_name, p.name, p.riot_id, p.role, p.game, p.active,
       t.name AS team_name,
       t.slug AS team_slug
FROM players p
JOIN team_players tp ON tp.player_id = p.id AND tp.left_at IS NULL
JOIN teams t ON t.id = tp.team_id
WHERE t.slug = %s
  AND (%s::text IS NULL OR p.game = %s::text)
  AND (%s::text IS NULL OR p.role = %s::text)
ORDER BY <whitelisted> <ASC|DESC> NULLS LAST, p.display_name
LIMIT %s
```

**Why two paths:** Path A's CTE picks one *display* team per player (earliest joined). If we tried to add `WHERE ft.team_slug = X` on top, players on multiple teams who happen to have a different earliest-joined team are wrongly filtered out (codex caught this on the previous draft). Path B avoids the problem by JOINing on the membership directly — players on the requested team always appear, and the display team is the requested one.

Both paths enrich `team_name`/`team_slug` so the frontend's Team column renders correctly in both cases.

Sort whitelist:
```python
_SORT_COLUMNS = {
    "displayName": "p.display_name",
    "role":        "p.role",
    "game":        "p.game",
}
_SORT_ORDERS = {"asc", "desc"}
```

Response: list of normalized player objects (see "Wire format" §below).

#### `GET /api/players/{slug}`

Lookup pattern: try `slug` exact first; fall back to derived slug from `display_name` (lowercased, spaces→hyphens) for legacy/admin-entered players that haven't been slug-normalized.

```sql
SELECT p.* 
FROM players p
WHERE p.slug = %s
   OR (p.slug IS NULL AND LOWER(REPLACE(p.display_name, ' ', '-')) = %s)
   OR LOWER(REPLACE(p.display_name, ' ', '-')) = %s
ORDER BY (p.slug = %s) DESC, p.id ASC  -- exact slug match wins
LIMIT 1
```

(Bind value: `(slug, slug, slug, slug)` — same value four times.)

If found, also fetch:
- Player's first active team (for `team_name`/`team_slug`):
  ```sql
  SELECT t.name, t.slug FROM teams t
  JOIN team_players tp ON tp.team_id = t.id
  WHERE tp.player_id = %s AND tp.left_at IS NULL
  ORDER BY tp.joined_at ASC LIMIT 1
  ```
- Recent matches (last 25, joined to per-game detail + matches for win calc):
  ```sql
  -- For game='valorant':
  SELECT pms.id AS pms_id, pms.match_id, pms.map_name, pms.team_name, pms.team_id,
         pms.game,
         v.kills, v.deaths, v.assists, v.agent, v.acs,
         m.team1_id, m.team1_score, m.team2_score
  FROM player_match_stats pms
  LEFT JOIN pms_valorant_details v ON v.pms_id = pms.id
  LEFT JOIN matches m ON m.id = pms.match_id
  WHERE pms.player_id = %s AND pms.game = 'valorant'
  ORDER BY pms.id DESC
  LIMIT 25
  
  -- For game='lol':
  SELECT pms.id AS pms_id, pms.match_id, pms.map_name, pms.team_name, pms.team_id,
         pms.game,
         l.kills, l.deaths, l.assists, l.champion, l.cs, l.lane,
         m.team1_id, m.team1_score, m.team2_score
  FROM player_match_stats pms
  LEFT JOIN pms_lol_details l ON l.pms_id = pms.id
  LEFT JOIN matches m ON m.id = pms.match_id
  WHERE pms.player_id = %s AND pms.game = 'lol'
  ORDER BY pms.id DESC
  LIMIT 25
  ```

Each row is shaped into a `MatchStat`:
- `matchId`: `str(match_id)`
- `game`: mapped via `_label_game()` (lowercase → TitleCase)
- `mapName`: `map_name`
- `teamName`: `team_name`
- `agent` (Val) or `champion` (LoL)
- `role`: from per-game-details `lane` for LoL, omitted for Val (Mongo had it on the doc; new schema doesn't carry per-match role for Val)
- `kills`, `deaths`, `assists`, `acs` (Val), `cs` (LoL): from details
- `win`: computed from `team1_id == player's team_id` and `team1_score > team2_score`

Frequency: Python `Counter` over `agent` (Val) or `champion` (LoL) from the 25 recent rows. Returns `[{ name, count }, ...]` sorted by `count` desc. `frequency_field` is `"agent"` or `"champion"` literal.

If no player found: 404 with `{"detail": "Player '{slug}' not found"}`.

### Removed behavior

- **Split CLOL_player_stats source** — one unified `players` table now. The `_normalize_clol` path is gone; `_normalize` handles both games via `game` column.
- **`_serialize`** ObjectId-handling — no BSON in Postgres world.
- **`teamIds` array resolution** — replaced by `team_players` junction table JOIN.
- **`_PMS = "player match stats"` Mongo collection name with literal spaces** — replaced by `player_match_stats` table.
- **Frequency field auto-detection from doc shape** — driven by `players.game` column instead.

### `_normalize` (Postgres version, simpler than Mongo)

```python
def _normalize(row: dict, team_name: str = "", team_slug: str = "") -> dict:
    name = row.get("display_name") or row.get("name") or "Unknown"
    slug = row.get("slug") or name.lower().replace(" ", "-")
    return {
        "slug":         slug,
        "displayName":  name,
        "riotId":       row.get("riot_id") or "",
        "role":         row.get("role") or "",
        "game":         _label_game(row.get("game", "")),
        "team_name":    team_name,
        "team_slug":    team_slug,
        "active":       row.get("active", True),
    }
```

(No `_id` field — Postgres doesn't need it. Frontend doesn't read it.)

### Out of Scope

- Pagination metadata (Mongo returned a plain list; preserve).
- POST/PATCH/DELETE — Phase 3f admin work.
- Aggregate career stats from `players.stats JSONB` — Mongo doc had it but the frontend doesn't currently render it; defer to a future feature phase.
- Updating the player slug retroactively when display_name changes — write-time concern handled by admin router (Phase 3f).

## Acceptance Criteria

- [ ] Diff allow-list: `Backend/core/players_router.py`, `migrations/postgres-v2/phase-3d-SPEC.md`. No other paths.
- [ ] No `pymongo`, `bson`, `certifi`, `core.db.get_db`, `_serialize`, `_normalize_clol`, `_PMS`, `_CLOL` references remain.
- [ ] All SQL parameterized; sort/order/limit whitelisted (400/422 on invalid).
- [ ] Skip count drops to **3** (admin, matches, valorant).
- [ ] `/api/players` returns `[]` when no seed data.
- [ ] After seeding 2 players (one Val, one LoL): `/api/players?game=Valorant` returns the 1 Val player; `/api/players?game=League of Legends` returns the 1 LoL player; `/api/players` returns both.
- [ ] After seeding a team_players relationship: `/api/players?team={team-slug}` returns players on that team with `team_name`/`team_slug` populated.
- [ ] `/api/players?role=Duelist` filters to players with that role.
- [ ] `/api/players/{slug}` returns full profile with `recent_matches[]`, `frequency[]`, `frequency_field` (`"agent"` for Val player; `"champion"` for LoL player).
- [ ] After seeding a Val match + pms + pms_valorant_details: that player's `recent_matches[0]` includes `agent`, `kills`, `deaths`, `assists`, `acs`, `win` computed correctly.
- [ ] `/api/players/{slug}` 404 on missing slug.
- [ ] Validation: `?sort=invalid` → 400, `?order=oops` → 400, `?limit=600` → 422.
- [ ] `/openapi.json` includes `/api/players/` and `/api/players/{slug}`.

## Verification Plan

```bash
docker compose down -v
docker compose up --build -d
until /usr/bin/curl -fs http://localhost:8000/api/health > /dev/null 2>&1; do sleep 1; done

# Seed: 1 Val player, 1 LoL player, 1 team, team_players, 1 match + pms + val details.
docker compose exec -T db psql -U esports -d esports <<'SQL'
INSERT INTO schools (name, slug) VALUES ('Northeastern', 'neu');
INSERT INTO organizations (name, abbreviation, slug, games) VALUES ('Test', 'TST', 'test', ARRAY['valorant','lol']);
INSERT INTO seasons (org_id, year, semester, label, active) SELECT id, 2027, 'fall', 'Fall 2027', true FROM organizations;
INSERT INTO teams (school_id, name, slug, game, school_name, region, rating, wins, losses)
  SELECT id, 'NEU Val', 'neu-val', 'valorant', name, 'na', 1200, 5, 2 FROM schools;
INSERT INTO players (name, slug, display_name, riot_id, role, game, active)
  VALUES ('Alex P', 'alexp', 'AlexP', 'AlexP#NA1', 'Duelist', 'valorant', true),
         ('Jordan L', 'jordanl', 'JordanL', 'JordanL#NA1', 'Top', 'lol', true);
INSERT INTO team_players (team_id, player_id, season_id, joined_at)
  SELECT t.id, p.id, s.id, NOW() FROM teams t, players p, seasons s
  WHERE t.slug='neu-val' AND p.display_name='AlexP' AND s.label='Fall 2027';
INSERT INTO teams (school_id, name, slug, game, school_name, rating, wins, losses)
  SELECT id, 'Opponent', 'opp', 'valorant', name, 1100, 0, 0 FROM schools;
INSERT INTO matches (team1_id, team2_id, team1_score, team2_score, format, match_date, game, source)
  SELECT t1.id, t2.id, 13, 9, 'bo1', NOW() - INTERVAL '1 day', 'valorant', 'admin'
  FROM teams t1, teams t2 WHERE t1.slug='neu-val' AND t2.slug='opp';
INSERT INTO player_match_stats (match_id, player_id, team_id, team_name, game, map_name)
  SELECT m.id, p.id, t.id, t.name, 'valorant', 'Bind'
  FROM matches m, players p, teams t
  WHERE p.display_name='AlexP' AND t.slug='neu-val';
INSERT INTO pms_valorant_details (pms_id, kills, deaths, assists, agent, acs)
  SELECT pms.id, 22, 14, 5, 'Jett', 245 FROM player_match_stats pms LIMIT 1;
SQL

# List checks.
/usr/bin/curl -s -L 'http://localhost:8000/api/players' | python3 -m json.tool
# Expect: 2 players, both with game mapped to TitleCase.

/usr/bin/curl -s -L 'http://localhost:8000/api/players?game=Valorant' | python3 -m json.tool
# Expect: 1 (Alex).

/usr/bin/curl -s -L 'http://localhost:8000/api/players?team=neu-val' | python3 -m json.tool
# Expect: 1 (Alex with team_name='NEU Val', team_slug='neu-val').

/usr/bin/curl -s -L 'http://localhost:8000/api/players?role=Duelist' | python3 -m json.tool
# Expect: 1 (Alex).

# Detail.
/usr/bin/curl -s 'http://localhost:8000/api/players/alexp' | python3 -m json.tool
# Expect:
#   - displayName: "AlexP", game: "Valorant", role: "Duelist"
#   - team_name: "NEU Val", team_slug: "neu-val"
#   - frequency_field: "agent"
#   - frequency: [{"name":"Jett","count":1}]
#   - recent_matches[0]: matchId, game="Valorant", mapName="Bind", teamName="NEU Val",
#                        agent="Jett", kills=22, deaths=14, assists=5, acs=245, win=true

# 404.
/usr/bin/curl -s -o /dev/null -w '/api/players/missing: %{http_code}\n' http://localhost:8000/api/players/missing

# Validation.
/usr/bin/curl -s -o /dev/null -w '?sort=invalid: %{http_code}\n' -L 'http://localhost:8000/api/players?sort=invalid'
/usr/bin/curl -s -o /dev/null -w '?order=oops:    %{http_code}\n' -L 'http://localhost:8000/api/players?order=oops'
/usr/bin/curl -s -o /dev/null -w '?limit=600:    %{http_code}\n' -L 'http://localhost:8000/api/players?limit=600'

# Skip count.
docker compose logs backend --tail=200 2>&1 | grep -E "router '.+_router' skipped" | tail -10 \
  | awk '{for(i=1;i<=NF;i++) if($i ~ /_router/) {gsub(/[\x27]/,"",$i); print $i}}' | sort -u
# Expect: 3 (admin_router, matches_router, valorant_router).
```

## Rollback Plan

`git revert <phase-3d-commit-sha>`.

## Risks & Open Questions

### Resolved: list endpoint enrichment

Initial draft deferred enrichment to the detail endpoint only. Codex flagged this as a frontend regression — `Frontend/app/players/page.tsx` defines `Player.team_name` as required and renders a Team column. Updated SPEC: the list query always enriches via a `DISTINCT ON` CTE. Single SQL path handles both filtered and unfiltered cases.

### Risk: slug fallback (display_name → slug) may collide

Two players with the same display name (rare but possible). The `LOWER(REPLACE(display_name, ' ', '-'))` produces the same slug. Disambiguation is `ORDER BY id ASC LIMIT 1` (deterministic earliest wins).

### Risk: recent_matches uses two SQL queries (one per game) — inefficient

The detail handler picks the per-game-details JOIN based on player.game. A single UNION ALL would be more elegant but harder to maintain. Two queries with shared shape is fine for v1.

### Risk: `win` calculation assumes 2-team binary outcome

Phase 1 schema's `pms.team_id` tells us which side the player was on, then we compare scores. Valid for both Val and LoL match data shapes. Tied/null scores → `win = None`.

## Decisions Made (Path A)

| # | Decision | Choice |
|---|---|---|
| 1 | Wire field naming | Match existing frontend exactly (camelCase displayName/riotId/matchId/teamName/mapName, snake_case team_name/team_slug/recent_matches/frequency_field, TitleCase game). |
| 2 | Mongo CLOL_player_stats split | **Removed**. One unified `players` table query. |
| 3 | `_id` field in response | **Removed**. Postgres doesn't need it; frontend doesn't read it. |
| 4 | Sort whitelist | `{displayName, role, game}` (matches Mongo router accepted values). |
| 5 | List endpoint team enrichment | **Always enrich** via a `DISTINCT ON (player_id)` CTE that picks each player's earliest active team. Single SQL path handles both filtered and unfiltered cases. (Reversed from initial draft after codex flagged that the frontend's Players table renders a Team column.) |
| 6 | Slug ambiguity (no UNIQUE on `players.slug`) | `ORDER BY id ASC LIMIT 1` deterministic tie-break. |
| 7 | Recent matches per-game JOIN | Two separate queries (one per game), picked at runtime by `player.game`. |
| 8 | Frequency field | Computed in Python from `recent_matches` agent/champion field. `frequency_field` literal `"agent"` (Val) or `"champion"` (LoL). |
| 9 | `win` calc | Compared `pms.team_id` to `matches.team1_id`; null on tie/missing scores. |
