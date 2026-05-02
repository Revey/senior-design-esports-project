# Phase 4 — Frontend wire-format reconciliation

**Migration:** Postgres v2
**Branch:** `postgres-migration-v2` (continues from Phase 3g commit `f4bac2b`)
**Phase order:** Phase 4 of seven
**Status:** Implementing (gate-A skipped — codex consistently confused gate-A vs gate-B for routers; relying on gate-B)

## Phase Goal

Drop the Path A wire-format shims that Phase 3 carried for backward compatibility. Standardize:
- **Game enum:** wire is now canonical lowercase (`"valorant"` / `"lol"`). Drop `_GAME_LABEL_TO_DB` / `_GAME_DB_TO_LABEL` maps from all routers.
- **Field naming:** wire is now canonical camelCase across all public APIs. Drop snake_case fields like `win_rate`, `league_slug`, `recent_matches`, `map_record`, `own_score`, `opp_score`, `team_name`, `team_slug`, `frequency_field`.
- **Frontend types** updated in lockstep. Display-time TitleCase mapping (`"Valorant"` / `"League of Legends"`) becomes a frontend-only UI concern, NOT an API concern.

After Phase 4, the contract is consistent and Phase 5/6 can proceed against a clean surface.

## Files Modified

### Backend (4 routers + 1 helper drop)

| Path | Change |
|---|---|
| `Backend/core/teams_router.py` | Drop `_GAME_LABEL_TO_DB`, `_GAME_DB_TO_LABEL`, `_normalize_game_filter`, `_label_game`. Game param accepts lowercase only. Response field rename: `win_rate → winRate`, `league_slug → leagueSlug`, `recent_matches → recentMatches`, `map_record → mapRecord`, `own_score → ownScore`, `opp_score → oppScore`. |
| `Backend/core/players_router.py` | Drop game maps + helpers. Game param lowercase only. Response field rename: `team_name → teamName`, `team_slug → teamSlug`, `recent_matches → recentMatches`, `frequency_field → frequencyField`. |
| `Backend/core/matches_router.py` | Drop game maps + helpers. Game param lowercase only. (Match wire was already mostly camelCase; just the game value.) |
| `Backend/core/admin_router.py` | Game param/response lowercase. Drop _GAME_* maps. Drop _SEMESTER_* maps too — admin `seasons.semester` accepts lowercase only too (`"fall"`, `"spring"`, `"summer"`). |

### Frontend (6 pages + admin)

| Path | Change |
|---|---|
| `Frontend/app/teams/page.tsx` | Type `Team`: snake_case → camelCase. SortField unchanged (already camel). Game enum: send/expect lowercase. Add UI helper `gameLabel(g: string): string`. |
| `Frontend/app/teams/[slug]/page.tsx` | Same field renames. |
| `Frontend/app/players/page.tsx` | Type `Player`: team_name → teamName, team_slug → teamSlug. Game lowercase. |
| `Frontend/app/players/[slug]/page.tsx` | Type `PlayerProfile`: same renames + recent_matches → recentMatches, frequency_field → frequencyField. |
| `Frontend/app/matches/page.tsx` | Game param lowercase; display via gameLabel(). |
| `Frontend/app/matches/[id]/page.tsx` | Game param lowercase; display via gameLabel(). |
| `Frontend/app/admin/match/page.tsx` (and other admin pages that send game) | Send lowercase `game` to admin POST. Display label at UI. |

A single shared helper at `Frontend/app/_shared/gameLabel.ts` (~5 lines):
```ts
export const GAME_LABELS: Record<string, string> = {
  valorant: "Valorant",
  lol: "League of Legends",
};
export function gameLabel(g: string): string {
  return GAME_LABELS[g] ?? g;
}
```

## Acceptance Criteria

- [ ] No `_GAME_LABEL_TO_DB` / `_GAME_DB_TO_LABEL` / `_label_game` / `_normalize_game_filter` references in `Backend/core/*.py`.
- [ ] No snake_case keys in JSON responses for the public read endpoints (matches, teams, players, tournaments).
- [ ] Frontend `?game=` query params send lowercase; backend accepts only lowercase.
- [ ] `/api/teams?game=valorant` returns 1 team in seed data; `/api/teams?game=Valorant` returns `[]` (case sensitive now).
- [ ] All public site pages render against seeded data without 500s or undefined-field issues.
- [ ] Admin pages still work (auth + CRUD).
- [ ] Codex gate-B: APPROVE or APPROVE-WITH-NITS.

## Verification Plan

```bash
docker compose down -v
docker compose up --build -d
until /usr/bin/curl -fs http://localhost:8000/api/health > /dev/null 2>&1; do sleep 1; done

# Seed data + admin auth from prior phases.

# Game enum is now lowercase.
/usr/bin/curl -s 'http://localhost:8000/api/teams?game=valorant' | python3 -m json.tool
# Expect: lowercase 'valorant' in .game field; camelCase keys.

# Old TitleCase request returns []:
/usr/bin/curl -s 'http://localhost:8000/api/teams?game=Valorant' | python3 -c "import sys,json; print(len(json.load(sys.stdin)), 'teams')"
# Expect: 0

# Frontend pages render (manual or via npm run build):
docker compose logs frontend --tail=20
```
