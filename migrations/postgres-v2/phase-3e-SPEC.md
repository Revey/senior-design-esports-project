# Phase 3e — Port `matches_router` to Postgres (Path A)

**Migration:** Postgres v2
**Branch:** `postgres-migration-v2` (continues from Phase 3d commit `7a7456a`)
**Phase order:** Phase 3e of seven
**Status:** Draft, codex gate-A pending

## Phase Goal

Port `Backend/core/matches_router.py` from Mongo to psycopg2. Two endpoints:
- `GET /api/matches` — paginated list with game + team filters.
- `GET /api/matches/{match_id}` — single match with enriched player breakdown.

**Known scope gap (documented decision):** the Mongo Match detail returned per-map score breakdowns (`maps[].team1Score`, `maps[].team2Score`). The Phase 1 schema doesn't carry per-map scores — only match-level aggregate. So the Phase 3e detail returns `maps[]` with `mapName + team1Players + team2Players` arrays but **omits per-map scores** (frontend's `ValMap.team1Score`/`team2Score` will be undefined; the page's score cells will show "—" or NaN until Phase 4 either redesigns the detail page or a follow-up phase adds per-map score columns to the schema).

## Frontend wire contract (preserved per Path A)

`Match` type from `Frontend/app/matches/page.tsx` and `[id]/page.tsx`:

**Match (list):**
```ts
{ _id, game, team1Name?, team2Name?, team1Score?, team2Score?, winnerTeamId?,
  team1Id?, format?, date?, leagueName? }
```

**Match (detail) — superset:**
```ts
Match & { orgAbbreviation?, seasonLabel?, conferenceName?,
          maps?: ValMap[], players?: { team1: LolPlayer[], team2: LolPlayer[] } }
```

`ValMap`: `{ mapName, team1Score, team2Score, team1Players: ValPlayer[], team2Players: ValPlayer[] }`. Per-map scores are required by frontend type but **will be undefined in Phase 3e responses** (known gap).

`ValPlayer`: `{ playerId, playerName?, agent, kills, deaths, assists, acs, firstKills?, plants?, defuses? }`.

`LolPlayer`: `{ playerId, playerName?, champion, role, kills, deaths, assists, cs, gold, damage, vision?, wards? }`.

All field names are camelCase (no snake_case in this contract — easy port).

`MatchResp` (list):
```ts
{ items: Match[], total: number, page: number, limit: number }
```

## Technical Requirements

### File Manifest (2 paths committed)

| Action | Path | Purpose |
|---|---|---|
| **Rewrite** | `Backend/core/matches_router.py` | psycopg2-based: list + detail. |
| **Create** | `migrations/postgres-v2/phase-3e-SPEC.md` | This spec. |

### `_normalize_game_filter`, `_label_game`, `_GAME_*` maps

Same shape as the helpers in `players_router.py`/`teams_router.py`. Could DRY into `core/projection.py` later, but for Phase 3 simplicity, each router carries its own copy. **Phase 4 cleanup item.**

### Endpoints

#### `GET /api/matches`

Query params:
- `game` (optional): `"Valorant"` | `"League of Legends"` | `"All"` | omitted. Mapped via `_normalize_game_filter`.
- `team` (optional): numeric team id (string form). Validated as int; HTTP 400 on non-integer.
- `limit` (default 25, range 1–100).
- `page` (default 1, ≥1).

SQL (parameterized; whitelist not needed since no sort param):

```sql
WITH base AS (
    SELECT m.*, t1.name AS team1_name, t2.name AS team2_name
    FROM matches m
    LEFT JOIN teams t1 ON t1.id = m.team1_id
    LEFT JOIN teams t2 ON t2.id = m.team2_id
    WHERE (%s::text IS NULL OR m.game = %s::text)
      AND (%s::bigint IS NULL OR m.team1_id = %s::bigint OR m.team2_id = %s::bigint)
)
SELECT * FROM base ORDER BY match_date DESC LIMIT %s OFFSET %s
```

(Plus a separate `SELECT COUNT(*) FROM base`-style query for `total`. Implementation: use a CTE or two queries; preferring two queries for clarity.)

Response per match (list-shape):
```python
{
    "_id":          str(row["id"]),
    "game":         _label_game(row["game"]),
    "team1Name":    row["team1_name"] or "",
    "team2Name":    row["team2_name"] or "",
    "team1Score":   row["team1_score"],
    "team2Score":   row["team2_score"],
    "team1Id":      str(row["team1_id"]),
    "winnerTeamId": _winner_id(row),
    "format":       row["format"],
    "date":         row["match_date"].isoformat() if row["match_date"] else None,
    "leagueName":   row["league_name"] or "",
}
```

`_winner_id(row)`: returns `str(team1_id)` when `team1_score > team2_score`, `str(team2_id)` when reverse, `None` on tie/null.

#### `GET /api/matches/{match_id}`

`match_id` validated as int. 400 on non-integer; 404 if no row.

Fetches:
1. The match row + team1/team2 names (same shape as list).
2. **`orgAbbreviation`, `seasonLabel`, `conferenceName`**: LEFT JOIN to `organizations`, `seasons`, `conferences` on respective FKs. Empty string when null.
3. All `player_match_stats` rows for this match, JOINed to the per-game detail table AND to `players` for `display_name` enrichment.

Then assembles the nested `maps[]` (Val) or `players: { team1, team2 }` (LoL):

**For Val (game = 'valorant'):**
- Group pms rows by `map_name`. For each group:
  - `mapName`: the group key
  - `team1Score`/`team2Score`: **omitted** (known gap; not in schema)
  - `team1Players`: pms rows where `team_id == match.team1_id`, shaped as `ValPlayer`
  - `team2Players`: pms rows where `team_id == match.team2_id`, shaped as `ValPlayer`

**For LoL (game = 'lol'):**
- Single LoL series row per player (the schema's `pms.map_name = ''` convention). No per-map nesting.
- `players.team1`: pms rows where `team_id == match.team1_id`, shaped as `LolPlayer`
- `players.team2`: pms rows where `team_id == match.team2_id`, shaped as `LolPlayer`

`ValPlayer` shape:
```python
{
    "playerId":   str(player_id),
    "playerName": display_name,
    "agent":      agent,
    "kills":      kills, "deaths": deaths, "assists": assists,
    "acs":        acs,
    "firstKills": pms.details.get("firstKills") if present,  # JSONB extras
    "plants":     pms.details.get("plants") if present,
    "defuses":    pms.details.get("defuses") if present,
}
```

`LolPlayer` shape:
```python
{
    "playerId":   str(player_id),
    "playerName": display_name,
    "champion":   champion,
    "role":       lane,  # frontend calls it 'role'; schema column is 'lane'
    "kills":      kills, "deaths": deaths, "assists": assists,
    "cs":         cs, "gold": gold,
    "damage":     pms.details.get("damage") if present,
    "vision":     pms.details.get("vision") if present,
    "wards":      pms.details.get("wards") if present,
}
```

### SQL for detail

```sql
-- 1. Match + team names + org/season/conference labels.
SELECT m.*, t1.name AS team1_name, t2.name AS team2_name,
       o.abbreviation AS org_abbreviation,
       s.label AS season_label,
       c.name AS conference_name
FROM matches m
LEFT JOIN teams t1 ON t1.id = m.team1_id
LEFT JOIN teams t2 ON t2.id = m.team2_id
LEFT JOIN organizations o ON o.id = m.org_id
LEFT JOIN seasons s ON s.id = m.season_id
LEFT JOIN conferences c ON c.id = m.conference_id
WHERE m.id = %s

-- 2a. For Val pms rows.
SELECT pms.id AS pms_id, pms.player_id, pms.team_id, pms.map_name,
       p.display_name, p.name,
       v.kills, v.deaths, v.assists, v.agent, v.acs, v.details
FROM player_match_stats pms
JOIN players p ON p.id = pms.player_id
LEFT JOIN pms_valorant_details v ON v.pms_id = pms.id
WHERE pms.match_id = %s
ORDER BY pms.map_name, pms.id

-- 2b. For LoL pms rows.
SELECT pms.id AS pms_id, pms.player_id, pms.team_id,
       p.display_name, p.name,
       l.kills, l.deaths, l.assists, l.champion, l.cs, l.gold, l.lane, l.details
FROM player_match_stats pms
JOIN players p ON p.id = pms.player_id
LEFT JOIN pms_lol_details l ON l.pms_id = pms.id
WHERE pms.match_id = %s
ORDER BY pms.id
```

### Out of Scope

- Per-map scores in Val detail (schema gap; documented).
- POST/PATCH/DELETE — Phase 3f admin work.
- Generic search / sort beyond what's listed.
- Match-level player aggregates across maps (frontend computes from per-map data).
- DRYing the `_GAME_*` helpers into a shared module (Phase 4 cleanup).

## Acceptance Criteria

- [ ] Diff allow-list: `Backend/core/matches_router.py`, `migrations/postgres-v2/phase-3e-SPEC.md`.
- [ ] No `pymongo`, `bson`, `certifi`, `core.db.get_db`, `ObjectId`, `InvalidId` imports.
- [ ] All SQL parameterized.
- [ ] Skip count drops to **2** (admin, valorant).
- [ ] `/api/matches` returns `{items: [], total: 0, page: 1, limit: 25}` when no seed data.
- [ ] After seeding: list returns the seeded match with all required fields populated; `_id` is a numeric string; `team1Name`/`team2Name` resolved.
- [ ] `/api/matches?game=Valorant` filters correctly; `/api/matches?team={id}` filters correctly.
- [ ] `/api/matches?team=notanint` → HTTP 400.
- [ ] `/api/matches/notanint` → HTTP 400.
- [ ] `/api/matches/999999` → HTTP 404.
- [ ] `/api/matches/{id}` for a Val match returns `maps: [{ mapName, team1Players, team2Players }]` (no per-map scores). `team1Players[0]` has `playerId`, `playerName`, `agent`, `kills`, `deaths`, `assists`, `acs`.
- [ ] `/api/matches/{id}` for an LoL match returns `players: { team1: [...], team2: [...] }` with `champion`, `role` (from lane), kills/deaths/assists/cs/gold.
- [ ] Pagination: `limit=1&page=2` returns 1 item starting from offset 1.
- [ ] `/openapi.json` includes `/api/matches/` and `/api/matches/{match_id}`.

## Verification Plan

```bash
docker compose down -v
docker compose up --build -d
until /usr/bin/curl -fs http://localhost:8000/api/health > /dev/null 2>&1; do sleep 1; done

# Seed: 2 teams, 1 match, 1 Val player, 2 pms rows (one per team), 2 pms_valorant_details.
docker compose exec -T db psql -U esports -d esports -v ON_ERROR_STOP=1 <<'SQL'
INSERT INTO schools (name, slug) VALUES ('NEU', 'neu');
INSERT INTO organizations (name, abbreviation, slug, games) VALUES ('CVAL', 'CVAL', 'cval', ARRAY['valorant']);
INSERT INTO seasons (org_id, year, semester, label, active) SELECT id, 2027, 'fall', 'Fall 2027', true FROM organizations;
INSERT INTO conferences (org_id, name, slug, kind) SELECT id, 'D1', 'd1', 'D1' FROM organizations;
INSERT INTO teams (school_id, name, slug, game, school_name, rating, wins, losses)
  SELECT id, 'NEU Red',  'neu-red',  'valorant', name, 1200, 5, 2 FROM schools;
INSERT INTO teams (school_id, name, slug, game, school_name, rating, wins, losses)
  SELECT id, 'NEU Blue', 'neu-blue', 'valorant', name, 1100, 3, 4 FROM schools;
INSERT INTO matches (team1_id, team2_id, team1_score, team2_score, format, match_date, game, source,
                     org_id, season_id, conference_id, league_name)
  SELECT t1.id, t2.id, 13, 9, 'bo1', NOW() - INTERVAL '1 day', 'valorant', 'admin',
         o.id, s.id, c.id, 'CVAL D1'
  FROM teams t1, teams t2, organizations o, seasons s, conferences c
  WHERE t1.slug='neu-red' AND t2.slug='neu-blue';
INSERT INTO players (name, slug, display_name, riot_id, role, game, active) VALUES
  ('Alex P', 'alexp', 'AlexP', 'AlexP#NA1', 'Duelist', 'valorant', true),
  ('Bob X',  'bobx',  'BobX',  'BobX#NA1',  'Duelist', 'valorant', true);
INSERT INTO player_match_stats (match_id, player_id, team_id, team_name, game, map_name)
  SELECT m.id, p.id, t.id, t.name, 'valorant', 'Bind'
  FROM matches m, players p, teams t
  WHERE p.display_name='AlexP' AND t.slug='neu-red';
INSERT INTO player_match_stats (match_id, player_id, team_id, team_name, game, map_name)
  SELECT m.id, p.id, t.id, t.name, 'valorant', 'Bind'
  FROM matches m, players p, teams t
  WHERE p.display_name='BobX' AND t.slug='neu-blue';
INSERT INTO pms_valorant_details (pms_id, kills, deaths, assists, agent, acs, details)
  SELECT pms.id, 22, 14, 5, 'Jett', 245, '{"firstKills": 4, "plants": 2}'
  FROM player_match_stats pms JOIN players p ON p.id=pms.player_id WHERE p.display_name='AlexP';
INSERT INTO pms_valorant_details (pms_id, kills, deaths, assists, agent, acs, details)
  SELECT pms.id, 14, 16, 7, 'Sage', 180, '{}'
  FROM player_match_stats pms JOIN players p ON p.id=pms.player_id WHERE p.display_name='BobX';
SQL

# List.
/usr/bin/curl -s -L 'http://localhost:8000/api/matches' | python3 -m json.tool
# Expect: items=1, total=1, page=1, limit=25.

/usr/bin/curl -s -L 'http://localhost:8000/api/matches?game=Valorant' | python3 -c "import sys,json; print(json.load(sys.stdin)['total'])"
# Expect: 1.

# Detail.
MATCH_ID=$(docker compose exec -T db psql -U esports -d esports -t -A -c "SELECT id FROM matches LIMIT 1")
/usr/bin/curl -s "http://localhost:8000/api/matches/$MATCH_ID" | python3 -m json.tool
# Expect:
#   - _id, game="Valorant", team1Name="NEU Red", team2Name="NEU Blue",
#     team1Score=13, team2Score=9, team1Id, winnerTeamId, format, date,
#     leagueName="CVAL D1", orgAbbreviation="CVAL", seasonLabel="Fall 2027",
#     conferenceName="D1"
#   - maps: [{ mapName: "Bind",
#              team1Players: [{ playerId, playerName: "AlexP", agent: "Jett", kills: 22, ..., firstKills: 4, plants: 2 }],
#              team2Players: [{ playerId, playerName: "BobX",  agent: "Sage", kills: 14, ... }] }]

# Validation.
/usr/bin/curl -s -o /dev/null -w '/api/matches?team=notanint:  %{http_code}\n' -L 'http://localhost:8000/api/matches?team=notanint'
/usr/bin/curl -s -o /dev/null -w '/api/matches/notanint:        %{http_code}\n' http://localhost:8000/api/matches/notanint
/usr/bin/curl -s -o /dev/null -w '/api/matches/999999:          %{http_code}\n' http://localhost:8000/api/matches/999999

# Pagination.
/usr/bin/curl -s -L 'http://localhost:8000/api/matches?limit=1&page=1' | python3 -c "import sys,json; d=json.load(sys.stdin); print('items:', len(d['items']), 'total:', d['total'])"

# Skip count.
docker compose logs backend --tail=200 2>&1 | grep -E "router '.+_router' skipped" | tail -10 \
  | awk '{for(i=1;i<=NF;i++) if($i ~ /_router/) {gsub(/[\x27]/,"",$i); print $i}}' | sort -u
# Expect: 2 (admin_router, valorant_router).
```

## Rollback Plan

`git revert <phase-3e-commit-sha>`.

## Risks & Open Questions

### Known gap: per-map scores not in schema

Phase 1 schema deliberately stores only match-level `team1_score`/`team2_score`, not per-map. The Mongo Match detail had per-map scores (collected by admin entry). Phase 3e returns `maps[]` without `team1Score`/`team2Score`. Frontend's typed `ValMap` requires them; absent values render as undefined. Score-row UI shows "—" or empty. Phase 4 either redesigns the detail page or adds `pms_valorant_details.team_round_score` columns (with admin-entry redesign). Documented as out-of-scope for Phase 3e.

### Risk: large match detail responses

A bo3 with 10 players × 3 maps = 30 pms rows. Plus organizations/seasons/conferences JOIN. Single-query workload is small; no concern at v1 scale.

### Risk: team filter expects numeric ID; frontend may pass slug

Existing Mongo router accepted ObjectId hex string. Postgres router accepts numeric ID. Phase 4 frontend update may convert from team slug → team ID before filtering. For now, the matches list page in `Frontend/app/matches/page.tsx` doesn't currently use `team` filter (verified by grep). The contract is mostly for API completeness.

## Decisions Made (Path A)

| # | Decision | Choice |
|---|---|---|
| 1 | Wire field naming | Match existing frontend types (mostly camelCase). |
| 2 | `_id` field | Numeric string of `matches.id`. Frontend reads as opaque string. |
| 3 | `winnerTeamId` | Computed from team1_score / team2_score; null on tie or unfinished. |
| 4 | Per-map scores in Val detail | **Omitted**. Known schema gap. Phase 4 / future cleanup. |
| 5 | LoL detail shape | `players: {team1: [], team2: []}` matching frontend `LolPlayer` type. No `maps[]` (LoL is series-based; one row per player per series). |
| 6 | Player name enrichment | JOIN to players table; `display_name` falls back to `name`. |
| 7 | `team` filter | Numeric ID (string-form), validated as int. 400 on non-integer. |
| 8 | DRY `_GAME_*` helpers | **Defer to Phase 4**. Each router carries its own copy for now. |
