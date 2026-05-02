# FEATURE_SPEC.md — Campus Rankers Hub

> **Per-feature blueprint.** Replace the contents below for each new feature before implementation begins. For features tightly scoped to a folder, you may instead place a `SPEC.md` next to the code (e.g. `Frontend/app/<feature>/SPEC.md`) and leave this file pointing to it.
>
> **Assumption:** the default acceptance criteria below (parameterized SQL, `Backend/schema.sql`, etc.) presume the Postgres migration is complete. While the migration is in progress, use the per-phase SPEC under `migrations/postgres-v2/phase-N-SPEC.md` instead — those have their own phase-appropriate acceptance criteria. Don't apply the Postgres criteria below to a Mongo-era feature.

---

## Feature Goal

_One sentence describing what this feature achieves and the user-visible outcome._

## User Story

> As a **[user type]**, I want to **[action]** so that **[value]**.

## Technical Requirements

### Frontend
- **Route(s):**
- **Components / state:**
- **Data fetching:** (must use `NEXT_PUBLIC_BACKEND_URL`; no `NEXT_PUBLIC_API_BASE_URL`)
- **Auth / visibility:** (note if hidden like `/admin`)

### Backend
- **Router / endpoints:**
- **Schema changes:** (table, columns, indexes — update `Backend/schema.sql`, parameterized only)
- **Migration steps:** (idempotent SQL or one-shot script)
- **Business rules / invariants:** (e.g. one active season per org; hard-delete matches)

## API Contract

### Request
```http
METHOD /path
Content-Type: application/json

{
  "fieldInCamelCase": "..."
}
```

### Response
```json
{
  "fieldInCamelCase": "..."
}
```

### Errors
| Status | When | Body |
|---|---|---|
| 400 | invalid input | `{ "detail": "..." }` |
| 404 | not found | `{ "detail": "..." }` |

## Acceptance Criteria

- [ ]
- [ ]
- [ ] No raw SQL string interpolation introduced.
- [ ] camelCase preserved on the wire.
- [ ] `docker compose up --build` succeeds; endpoint exercised via `curl`.
- [ ] Frontend verified in `npm run dev` against local backend.

## Out of Scope

_List explicitly to prevent scope creep._

## Open Questions

_Resolve before implementation; do not let the AI guess._
