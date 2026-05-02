# Postgres Migration v2

End-to-end migration from MongoDB Atlas to DigitalOcean Managed PostgreSQL.

## Phases

| Phase | What | Commit |
|---|---|---|
| **0** | Branch + doc reality reconciliation (CONSTITUTION/PROGRESS now describe actual state) | `31b356d` |
| **1** | Author `Backend/schema.sql` — 15 tables, idempotent, sparse-unique indexes, partial unique on one-active-season + active-consent | `122ce4e` |
| **2** | psycopg2 ThreadedConnectionPool in `core/db.py`, swap `requirements.txt`, rewrite `main.py` (Option Z router skipping until ports complete) | `d1adfeb` |
| **3a** | Delete `leagues_router` (no Postgres equivalent — replaced by org/season/conference hierarchy) | `89ca072` |
| **3b** | Port `tournaments_router` + add shared `to_camel()` projection helper | `55fca8d` |
| **3c** | Port `teams_router` (Path A — preserve Mongo wire shape; Phase 4 standardizes) | `30df6c9` |
| **3d** | Port `players_router` (unifies Mongo's split CLOL/Val sources) | `7a7456a` |
| **3e** | Port `matches_router` (list + detail with per-game JOIN; per-map score gap documented) | `ad14e16` |
| **3f.1** | Admin auth + simple CRUD (schools, teams, players, orgs, seasons, conferences, memberships, leagues-tree) | `9113f9d` |
| **3f.2** | Admin match CRUD with W/L delta logic (multi-statement transactions via `get_conn`) | `0466689` |
| **3f.3** | Admin `/stats` dashboard endpoint | `4e1118b` |
| **3g** | Port `valorant_router` + RSO token storage to Postgres | `f4bac2b` |
| **4** | Wire-format reconciliation: drop Path A shims, canonical camelCase + lowercase enum on the wire, frontend types + display labels updated | `d29822d` |
| **5** | Player accounts + RSO consent gate at the data layer | `2d20929` |
| **6** | DO Managed Postgres + cutover (this phase — see [phase-6-RUNBOOK.md](./phase-6-RUNBOOK.md)) | (deploy time) |

## Architecture decisions worth knowing

- **Schema is the contract:** `Backend/schema.sql` is idempotent (re-runnable, but NOT convergent — drift requires a forward-migration script). 15 tables; the 12 from CONSTITUTION §3 plus `team_players` (junction replacing Mongo `players.teamIds[]`), `pms_valorant_details`, and `pms_lol_details` (Path 2 polymorphic core for future games).
- **No ORM.** psycopg2 + parameterized SQL only. Multi-statement transactions use `get_conn() + conn.cursor()`; reads use `get_cursor()`. Never nest the two.
- **camelCase wire format** (Phase 4 standardized). Lowercase game enum (`'valorant'` / `'lol'`); UI maps to TitleCase display labels via `Frontend/app/_shared/gameLabel.ts`.
- **Player consent gate** (Phase 5). Profiles default private. RSO sign-in records consent; revocation is self-service. Admin endpoints bypass the gate.
- **Path A frontend strategy** (Phases 3c–3g): preserve existing wire format during router-by-router porting, standardize in one Phase 4 sweep. Avoided "broken UI for 6 commits."
- **Option Z** (Phase 2): swap `pymongo`/`bson`/`certifi` from requirements; `_try_router()` recognizes legacy-Mongo ImportError signals and skips registration with INFO log. Phase 3 ports each router and removes its `_try_router` line.

## Codex as gate-A/gate-B reviewer

The user delegated review approvals to `codex exec` for the migration. Each phase ran the SPEC through `codex exec --sandbox read-only` for gate A (review the plan) and the staged diff for gate B (review the implementation). Codex caught real issues (slug ambiguity, CTE filtering bug, snake_case wire mismatches, BO1 vs bo1 form values) and mostly-correctly approved otherwise. Process consistently confused gate-A "review the spec" with "verify implementation done" — a known limitation; gate-B was more reliable.

## Things deferred for post-launch

- Per-map score columns on Val matches (Phase 1 schema gap; Phase 3e detail returns `maps[]` without `team1Score`/`team2Score`).
- Tournament JSONB → normalized tables (Phase 1 punt).
- Multi-game roadmap (Smash, OW, RL, CoD, Fortnite, TFT, TF2) — schema reserved space via game discriminator + per-game `pms_<game>_details` pattern; not implemented.
- Standardize `_GAME_*` helpers across remaining routers into `core/projection.py` (Phase 4 inlined per-router).
- Admin frontend for membership management (currently API-only).
- Real-time WebSocket updates for live match scoring.
