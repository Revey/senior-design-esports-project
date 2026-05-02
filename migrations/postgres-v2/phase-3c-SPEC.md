# Phase 3c — Port `teams_router` to Postgres (Path A: preserve existing contract)

**Migration:** Postgres v2
**Branch:** `postgres-migration-v2` (continues from Phase 3b commit `55fca8d`)
**Phase order:** Phase 3c of seven
**Status:** Draft v2 (Path A re-spec after gate-A BLOCK), codex gate-A pending

## Phase Goal

Port `Backend/core/teams_router.py` from Mongo to psycopg2 against the Phase 1 `teams` table. **Preserve the existing wire contract that the current frontend expects** — even though it's a mixed-case mess (mostly snake_case with sprinkles of camelCase) — so the frontend at `Frontend/app/teams/{page,[slug]/page}.tsx` keeps rendering correctly during the migration.

This is "Path A" per the gate-A discussion: don't standardize to camelCase yet. **Phase 4 is the wire-format standardization phase** — that's where the frontend types get updated to canonical camelCase + lowercase-enum, AND the Phase 3 routers get a `to_camel()` cleanup PR.

## Strategic Context (Path A)

Codex flagged on Phase 3c v1 that the proposed `to_camel()` shape would break the frontend (which uses `win_rate`, `league_slug`, `recent_matches`, `map_record`, `own_score`, `opp_score` and reads `t.game === "Valorant"`). The user (Daniel) chose Path A: preserve the existing contract during Phase 3 ports, do the standardization sweep in Phase 4. This SPEC reflects that.

The `to_camel()` helper from Phase 3b is **NOT used** in Phase 3c. It stays in the codebase for future use; Phase 3c manually shapes responses.

## Technical Requirements

### File Manifest (2 paths committed)

| Action | Path | Purpose |
|---|---|---|
| **Rewrite** | `Backend/core/teams_router.py` | psycopg2-based: list (with sort/game filter/limit), get-by-slug detail. Wire shape preserves the existing Mongo contract exactly — see "Wire Contract" §below. |
| **Create** | `migrations/postgres-v2/phase-3c-SPEC.md` | This spec (replaces v1). |

`Backend/main.py` and `Backend/core/projection.py` not modified. `_try_router("core.teams_router", ...)` already exists; `to_camel()` not used.

### `game` enum case mapping at the router boundary

The frontend sends and expects:
- Display labels: `"Valorant"` and `"League of Legends"`
- Filter param: `?game=Valorant` or `?game=League of Legends` (or omitted / "All")

The Phase 1 schema stores: `'valorant'` and `'lol'` (lowercase, enforced by CHECK constraint).

Router does the case mapping:

```python
_GAME_LABEL_TO_DB = {
    "Valorant": "valorant",
    "League of Legends": "lol",
}
_GAME_DB_TO_LABEL = {v: k for k, v in _GAME_LABEL_TO_DB.items()}

def _normalize_game_filter(label: str | None) -> str | None:
    """Convert frontend 'Valorant'/'League of Legends' to DB lowercase enum.
    Unknown values are lowercased and passed through to SQL so they filter to
    zero rows (matches the Mongo router's behavior where an unknown filter
    string returned nothing rather than ignoring the filter)."""
    if label is None or label == "All":
        return None
    if label in _GAME_LABEL_TO_DB:
        return _GAME_LABEL_TO_DB[label]
    return label.lower()  # unknown → lowercased; matches no rows under CHECK constraint
```

Output: every `game` field in responses goes through `_GAME_DB_TO_LABEL`. So the router writes `'valorant'` to/reads from the DB but reports `'Valorant'` on the wire.

This mapping is a Phase 4 cleanup target — when Phase 4 standardizes the frontend to use canonical lowercase, the mapping shims drop out.

### Endpoints

#### `GET /api/teams`

Query params:
- `game` (optional): `"Valorant"`, `"League of Legends"`, `"All"`, or omitted. Maps to DB enum via `_normalize_game_filter`. `None` / `"All"` → no filter; known labels → mapped to lowercase enum; unknown labels → lowercased and passed through to SQL, which returns zero rows under the `teams.game` CHECK constraint (preserves Mongo's "filter on this string, get nothing if it doesn't match" behavior).
- `sort` (default `"rating"`): one of `rating | win_rate | record.wins` (matches frontend's `SortField` type exactly). Whitelist; rejects others (including `name`) with 400.
- `order` (default `"desc"`): `"asc"` or `"desc"`. Whitelist.
- `limit` (default 50, range 1–100, FastAPI validates).

Sort whitelist (matches the frontend's `SortField = "rating" | "win_rate" | "record.wins"` exactly — no extra values):
```python
_SORT_COLUMNS = {
    "rating":      "rating",
    "record.wins": "wins",
    "win_rate":    ("CASE WHEN (wins + losses) > 0 "
                    "THEN (wins::float / (wins + losses)) ELSE 0 END"),
}
```
(`record.wins` is the frontend's value — preserved verbatim.)

Response shape (matches Mongo router exactly — note the snake_case):

```json
[
  {
    "slug": "neu-val-red",
    "name": "NEU Valorant Red",
    "school": "Northeastern",
    "game": "Valorant",
    "record": {"wins": 5, "losses": 2},
    "win_rate": 71.4,
    "rating": 1200.0,
    "region": "na",
    "league_slug": ""
  }
]
```

- `school` ← `teams.school_name` (denormalized snapshot).
- `game` ← mapped via `_GAME_DB_TO_LABEL` (so `"valorant"` → `"Valorant"`).
- `record` ← nested object (Python construction, not from DB).
- `win_rate` ← computed in Python: `round((wins / (wins+losses)) * 100, 1)`, 0.0 when no games.
- `rating` ← `teams.rating` column. **Float when present, `null` when DB column is NULL.** Frontend's `Team.rating: number` type doesn't allow null, so this is a known frontend-side issue Phase 4 fixes (or seed data ensures rating is always set; the Mongo router computed a fallback).
- `region` ← `teams.region` or empty string.
- `league_slug` ← always empty string. The Mongo concept is gone (replaced by org/conference hierarchy). Frontend currently shows it on the slug detail page when truthy; empty string hides it. Phase 4 removes this field from the contract.

#### `GET /api/teams/{slug}`

Returns the same fields as the list element above, plus:

- `roster`: array of `{ name, role, riotId, active }` (note: `riotId` is camelCase — frontend uses `p.riotId`).
- `recent_matches`: array of last 15 matches: `{ matchId, date, game, format, opponent, own_score, opp_score, win }`. **Note the case mix: `matchId` is camelCase (frontend uses `m.matchId`? actually frontend treats it as opaque — but Mongo router returned `matchId` so we preserve), but `own_score`/`opp_score` are snake_case (frontend reads `m.own_score`).**
- `map_record`: `{ wins, losses }` from `teams.map_wins` / `teams.map_losses`.

Match `win` semantics: computed from `team1_score > team2_score` from the perspective of the team being viewed. `null` when scores are tied or null.

Match `game` field: mapped via `_GAME_DB_TO_LABEL` like the team's own `game` field.

404 with `{"detail": "Team 'X' not found"}` when slug doesn't exist.

### Implementation: `Backend/core/teams_router.py`

```python
"""API routes for teams (Postgres-backed; Phase 3c of postgres-migration-v2).

Wire contract: snake_case for win_rate/league_slug/recent_matches/map_record/
own_score/opp_score (matching the existing frontend); camelCase for matchId,
riotId. game enum mapped at router boundary (DB stores 'valorant'/'lol';
frontend uses 'Valorant'/'League of Legends'). The mixed-case shape is
intentional Phase-3 backward compat — Phase 4 standardizes everything to
camelCase + lowercase enum and drops the case-mapping shims.
"""

from typing import Optional, Any
from fastapi import APIRouter, HTTPException, Query
from core.db import get_cursor

router = APIRouter()

_GAME_LABEL_TO_DB = {"Valorant": "valorant", "League of Legends": "lol"}
_GAME_DB_TO_LABEL = {v: k for k, v in _GAME_LABEL_TO_DB.items()}

_SORT_COLUMNS = {
    "rating":      "rating",
    "record.wins": "wins",
    "win_rate":    ("CASE WHEN (wins + losses) > 0 "
                    "THEN (wins::float / (wins + losses)) ELSE 0 END"),
}
_SORT_ORDERS = {"asc", "desc"}


def _normalize_game_filter(label: Optional[str]) -> Optional[str]:
    """See spec §game enum mapping. Unknown labels are lowercased and pass
    through to the SQL filter (CHECK constraint will return zero rows)."""
    if label is None or label == "All":
        return None
    if label in _GAME_LABEL_TO_DB:
        return _GAME_LABEL_TO_DB[label]
    return label.lower()


def _label_game(db_value: str) -> str:
    return _GAME_DB_TO_LABEL.get(db_value, db_value)


def _team_row_to_response(row: dict) -> dict:
    wins = int(row.get("wins") or 0)
    losses = int(row.get("losses") or 0)
    total = wins + losses
    win_rate = round((wins / total) * 100, 1) if total > 0 else 0.0
    rating = row.get("rating")
    return {
        "slug": row.get("slug", ""),
        "name": row.get("name", ""),
        "school": row.get("school_name") or "",
        "game": _label_game(row.get("game", "")),
        "record": {"wins": wins, "losses": losses},
        "win_rate": win_rate,
        "rating": float(rating) if rating is not None else None,
        "region": row.get("region") or "",
        "league_slug": "",
    }


@router.get("/")
def list_teams(
    game: Optional[str] = Query(None),
    sort: str = Query("rating"),
    order: str = Query("desc"),
    limit: int = Query(50, ge=1, le=100),
):
    if sort not in _SORT_COLUMNS:
        raise HTTPException(400, f"Invalid sort: {sort!r}")
    if order not in _SORT_ORDERS:
        raise HTTPException(400, f"Invalid order: {order!r}")

    direction = "DESC" if order == "desc" else "ASC"
    sort_expr = _SORT_COLUMNS[sort]
    db_game = _normalize_game_filter(game)

    sql = (
        f"SELECT * FROM teams "
        f"WHERE (%s::text IS NULL OR game = %s::text) "
        f"ORDER BY {sort_expr} {direction} NULLS LAST, name "
        f"LIMIT %s"
    )
    with get_cursor() as cur:
        cur.execute(sql, (db_game, db_game, limit))
        rows = cur.fetchall()
    return [_team_row_to_response(r) for r in rows]


@router.get("/{slug}")
def get_team(slug: str):
    with get_cursor() as cur:
        # NOTE: teams.slug is UNIQUE only within (slug, game). The frontend
        # detail URL carries no game qualifier, so on the rare collision
        # (slug shared across Valorant + LoL teams) we deterministically
        # return the earlier team (by id ASC). This matches the Mongo
        # router's `find_one` behavior — neither was strictly unambiguous.
        # Phase 4 will switch to game-qualified URLs and remove this
        # caveat; a database-level fix would be a global UNIQUE(slug)
        # which conflicts with the Phase 1 schema's per-game uniqueness.
        cur.execute(
            "SELECT * FROM teams WHERE slug = %s ORDER BY id ASC LIMIT 1",
            (slug,),
        )
        team = cur.fetchone()
        if team is None:
            raise HTTPException(404, f"Team '{slug}' not found")

        cur.execute(
            "SELECT p.display_name, p.role, p.riot_id, p.active "
            "FROM players p "
            "JOIN team_players tp ON tp.player_id = p.id "
            "WHERE tp.team_id = %s AND tp.left_at IS NULL "
            "ORDER BY p.display_name",
            (team["id"],),
        )
        roster_rows = cur.fetchall()

        cur.execute(
            "SELECT m.id, m.match_date, m.game, m.format, "
            "       m.team1_id, m.team2_id, m.team1_score, m.team2_score, "
            "       t1.name AS team1_name, t2.name AS team2_name "
            "FROM matches m "
            "LEFT JOIN teams t1 ON t1.id = m.team1_id "
            "LEFT JOIN teams t2 ON t2.id = m.team2_id "
            "WHERE m.team1_id = %s OR m.team2_id = %s "
            "ORDER BY m.match_date DESC "
            "LIMIT 15",
            (team["id"], team["id"]),
        )
        match_rows = cur.fetchall()

    response = _team_row_to_response(team)
    response["roster"] = [
        {
            "name": r["display_name"],
            "role": r["role"],
            "riotId": r["riot_id"],
            "active": r["active"],
        }
        for r in roster_rows
    ]
    response["recent_matches"] = [
        _match_row_to_recent(m, team["id"]) for m in match_rows
    ]
    response["map_record"] = {
        "wins": int(team.get("map_wins") or 0),
        "losses": int(team.get("map_losses") or 0),
    }
    return response


def _match_row_to_recent(m: dict, own_team_id: int) -> dict:
    is_team1 = m["team1_id"] == own_team_id
    opp_name = m["team2_name"] if is_team1 else m["team1_name"]
    own_score = m["team1_score"] if is_team1 else m["team2_score"]
    opp_score = m["team2_score"] if is_team1 else m["team1_score"]
    if own_score is None or opp_score is None or own_score == opp_score:
        win = None
    else:
        win = own_score > opp_score
    return {
        "matchId": str(m["id"]),
        "date": m["match_date"].isoformat() if m.get("match_date") else None,
        "game": _label_game(m.get("game", "")),
        "format": m.get("format"),
        "opponent": opp_name or "",
        "own_score": own_score,
        "opp_score": opp_score,
        "win": win,
    }
```

### Removed behavior

- **`ranked_teams` / `ranked_players` Mongo seed collections** — Phase 1 schema has no equivalent. Removed entirely.
- **Heuristic rating computation** — Phase 1's `teams.rating` column is the source of truth.

### Out of Scope

- Pagination metadata (preserve plain-list contract).
- Schools-table JOIN (use `teams.school_name` denormalized).
- POST/PATCH/DELETE — Phase 3f admin work.
- Wire-format standardization to canonical camelCase — **Phase 4** (this is the explicit deferred cleanup).

## Acceptance Criteria

- [ ] Diff allow-list: `Backend/core/teams_router.py` (modified), `migrations/postgres-v2/phase-3c-SPEC.md` (added).
- [ ] No `pymongo`, `bson`, `certifi`, or `core.db.get_db` imports in `teams_router.py`.
- [ ] All SQL parameterized; sort/order whitelist enforced (400 on unknown values).
- [ ] Skip count drops to 4 (valorant, players, admin, matches).
- [ ] `/api/teams` returns 200 with `[]` when no seed data.
- [ ] After seeding two teams + a match: `/api/teams?game=Valorant` returns both teams (game field = `"Valorant"`).
- [ ] `/api/teams?sort=invalid` → 400; `/api/teams?sort=name` → 400 (name is NOT in the whitelist); `/api/teams?order=oops` → 400; `/api/teams?limit=200` → 422.
- [ ] `/api/teams/{slug}` returns the team with `record`, `map_record`, `win_rate`, `recent_matches[].own_score`/`opp_score`, `roster[].riotId` — exact field names per spec above.
- [ ] `/api/teams?game=Valorant` filter sends `'valorant'` to SQL (verified by checking returned data); `/api/teams?game=Foo` returns `[]` (zero rows — unknown labels are lowercased and pass through; CHECK constraint on `teams.game` ensures no row matches an unknown enum value).

## Verification Plan

```bash
docker compose down -v
docker compose up --build -d
until /usr/bin/curl -fs http://localhost:8000/api/health > /dev/null 2>&1; do sleep 1; done

# Empty list.
/usr/bin/curl -s -L http://localhost:8000/api/teams | python3 -m json.tool
# Expect: []

# Seed two teams + one match.
docker compose exec -T db psql -U esports -d esports <<'SQL'
INSERT INTO schools (name, slug) VALUES ('Northeastern', 'neu') ON CONFLICT DO NOTHING;
INSERT INTO teams (school_id, name, slug, game, school_name, region, rating, wins, losses, map_wins, map_losses)
  SELECT id, 'NEU Val Red', 'neu-val-red', 'valorant', name, 'na', 1200, 5, 2, 12, 6 FROM schools WHERE slug='neu' ON CONFLICT DO NOTHING;
INSERT INTO teams (school_id, name, slug, game, school_name, region, rating, wins, losses, map_wins, map_losses)
  SELECT id, 'NEU Val Blue', 'neu-val-blue', 'valorant', name, 'na', 1100, 3, 4, 8, 9 FROM schools WHERE slug='neu' ON CONFLICT DO NOTHING;
INSERT INTO matches (team1_id, team2_id, team1_score, team2_score, format, match_date, game, source)
  SELECT t1.id, t2.id, 13, 9, 'bo1', NOW() - INTERVAL '2 days', 'valorant', 'admin'
  FROM teams t1, teams t2 WHERE t1.slug='neu-val-red' AND t2.slug='neu-val-blue';
INSERT INTO players (name, display_name, role, riot_id, game, active)
  VALUES ('Alex P', 'AlexP', 'Duelist', 'AlexP#NA1', 'valorant', true);
INSERT INTO seasons (org_id, year, semester, label, active)
  SELECT 1, 2027, 'fall', 'Fall 2027', true FROM organizations LIMIT 1;
SQL

docker compose exec -T db psql -U esports -d esports -c "
INSERT INTO organizations (name, abbreviation, slug, games)
  VALUES ('Test Org', 'TST', 'test-org', ARRAY['valorant']) ON CONFLICT DO NOTHING;
INSERT INTO seasons (org_id, year, semester, label, active)
  SELECT id, 2027, 'fall', 'Fall 2027', true FROM organizations WHERE slug='test-org' ON CONFLICT DO NOTHING;
INSERT INTO team_players (team_id, player_id, season_id, joined_at)
  SELECT t.id, p.id, s.id, NOW() FROM teams t, players p, seasons s
  WHERE t.slug='neu-val-red' AND p.display_name='AlexP' AND s.label='Fall 2027';"

# Game filter (frontend sends 'Valorant', router maps to 'valorant').
/usr/bin/curl -s -L "http://localhost:8000/api/teams?game=Valorant" | python3 -m json.tool
# Expect: 2 teams; .[0].game == "Valorant" (mapped back); sorted by rating desc.

# Detail with roster + recent matches.
/usr/bin/curl -s "http://localhost:8000/api/teams/neu-val-red" | python3 -m json.tool
# Expect:
#   - roster: [{ name: "AlexP", role: "Duelist", riotId: "AlexP#NA1", active: true }]
#   - recent_matches: [{ matchId, date, game: "Valorant", format: "bo1",
#                        opponent: "NEU Val Blue", own_score: 13, opp_score: 9, win: true }]
#   - map_record: { wins: 12, losses: 6 }
#   - win_rate: 71.4
#   - league_slug: ""
#   - rating: 1200.0

# Validation errors.
/usr/bin/curl -s -o /dev/null -w '  /api/teams?sort=invalid: %{http_code}\n' -L 'http://localhost:8000/api/teams?sort=invalid'
/usr/bin/curl -s -o /dev/null -w '  /api/teams?order=oops:    %{http_code}\n' -L 'http://localhost:8000/api/teams?order=oops'
/usr/bin/curl -s -o /dev/null -w '  /api/teams?limit=200:     %{http_code}\n' -L 'http://localhost:8000/api/teams?limit=200'
/usr/bin/curl -s -o /dev/null -w '  /api/teams/missing:       %{http_code}\n' http://localhost:8000/api/teams/missing
# Expect: 400, 400, 422, 404.

# Skip count.
docker compose logs backend --tail=200 2>&1 | grep -E "router '.+_router' skipped" | tail -10 \
  | awk '{for(i=1;i<=NF;i++) if($i ~ /_router/) {gsub(/[\x27]/,"",$i); print $i}}' | sort -u
# Expect: 4 lines (admin_router, matches_router, players_router, valorant_router).
```

## Rollback Plan

`git revert <phase-3c-commit-sha>`.

## Risks & Open Questions

### Risk: rating null breaks frontend type

`teams.rating` is nullable; the existing frontend `Team.rating: number` type doesn't allow null. If a real null lands in seed data, the frontend page may render `NaN` or crash on sort. Phase 4 fixes the type. For Phase 3c we set rating in seed data so this doesn't fire in our tests.

### Risk: game label mapping is brittle

Two case-conversion dictionaries; if the frontend ever sends a third game value (e.g. once we add games), they'd silently filter to nothing. Phase 4 standardizes the wire to canonical lowercase enum and drops both maps.

### Risk: legacy field `league_slug` always empty

Frontend's slug detail page guards `team.league_slug && (...)` so empty string hides it gracefully. List page doesn't reference league_slug. No render bug.

### Risk: this Phase locks in mixed-case wire format that Phase 4 must clean up

Documented as the explicit Phase 4 task. Phase 3 routers will all use `_label_game()` and snake_case fields; Phase 4 sweeps the standardization.

## Decisions Made (Path A)

| # | Decision | Choice |
|---|---|---|
| 1 | Wire field naming during Phase 3 | **Match existing frontend exactly** (snake_case for win_rate/league_slug/recent_matches/map_record/own_score/opp_score; camelCase for matchId/riotId). Phase 4 standardizes. |
| 2 | game enum case | **Map at router boundary** ('Valorant'↔'valorant'). Phase 4 drops the maps + updates frontend. |
| 3 | Sort whitelist | `{rating, record.wins, win_rate}` — exactly the values in the frontend's `SortField` type. `name` is NOT included. |
| 8 | Slug detail disambiguation | `WHERE slug = %s ORDER BY id ASC LIMIT 1` — deterministic earliest-team-by-id wins on cross-game slug collision. Documents matches Mongo's implicit `find_one` behavior. Phase 4 may switch to game-qualified URLs. |
| 9 | Unknown game filter values | Lowercased and passed to SQL → zero rows (matches Mongo's permissive-but-filtering behavior; not "no filter applied"). |
| 4 | Mongo seed collection fallback | **Removed** (no Postgres equivalent). |
| 5 | Rating | Use `teams.rating` column directly; null when unset (frontend type may need updating in Phase 4). |
| 6 | `to_camel()` usage | **Not used** in Phase 3c. Helper stays for future routers that DO need standardization (or for Phase 4). |
| 7 | `league_slug` field | Always empty string. Frontend's slug page hides it via truthy check; list page doesn't reference. |
