# Phase 6 — DO Managed Postgres + Production Cutover (RUNBOOK)

**Migration:** Postgres v2
**Branch:** `postgres-migration-v2` (continues from Phase 5 commit `2d20929`)
**Phase order:** Phase 6 of seven (final)
**Status:** Prep done; manual provisioning steps below require developer (Daniel) execution.

This phase has two halves:
1. **Code/config (committed in this phase):** updated `.do/app.yaml` with the managed-Postgres binding + all required secrets. Documented in this runbook.
2. **Manual provisioning (developer executes):** create the DO App Platform app + push the branch + set secrets + run `schema.sql`. See "Steps" below.

The migration branch is fully verified locally via docker compose. Phase 6 takes that to production.

---

## Pre-flight checks

- [ ] `git log --oneline main..postgres-migration-v2` shows the full 16-commit migration (Phases 0–6 prep). All pushed.
- [ ] `docker compose down -v && docker compose up --build -d` boots clean locally; skip count = 0.
- [ ] `npm run build` in `Frontend/` succeeds.
- [ ] Riot RSO production app is registered with the redirect URI matching `${APP_URL}/api/valorant/auth/callback` (will be filled in once the DO app URL is known — RSO supports updating the redirect URI without recreating the app).

## Steps (developer execution)

### 1. Provision the DO App Platform app

```bash
# Install doctl if you haven't:
brew install doctl
doctl auth init   # paste your DO API token

# Validate the spec:
doctl apps spec validate .do/app.yaml

# Create the app (this also provisions the managed Postgres cluster):
doctl apps create --spec .do/app.yaml --wait
```

The first deploy will:
- Provision a `db-s-dev-database` (or similar) Postgres 15 cluster (~$15/mo on dev tier; $60/mo+ on production tier).
- Build and deploy the backend + frontend services.
- Auto-wire `DATABASE_URL` into the backend service (no manual secret entry needed for that one).
- Backend will fail to fully boot until step 2 — that's expected.

### 2. Apply the schema

The auto-wired `DATABASE_URL` points to the cluster but the schema isn't loaded yet. Apply it once:

```bash
APP_ID=$(doctl apps list --format ID,Spec.Name --no-header | grep campus-rankers | awk '{print $1}')

# Get the DATABASE_URL from DO. (Has '?sslmode=require' — DO Managed PG enforces SSL.)
DB_URL=$(doctl databases connection $(doctl apps list-deployment-spec --format DBs $APP_ID | …) ...)
# Or simpler: pull from the Console UI: App → Components → db → Connection Details → Connection String.

psql "$DB_URL" -v ON_ERROR_STOP=1 -f Backend/schema.sql
psql "$DB_URL" -c '\dt'   # verify 15 tables
```

(The exact `doctl` invocation to fetch the connection string varies by `doctl` version. The DO Console UI is the most reliable path: App → Database → Connection Details → "Connection string" → "Public network".)

### 3. Set the remaining secrets

In the DO Console, under your app → Settings → Components → backend → Environment Variables, set:

- `ADMIN_PASSWORD` — strong random string for production.
- `ADMIN_SECRET` — DIFFERENT strong random for HMAC token signing. Use `openssl rand -hex 32`.
- `RIOT_API_KEY` — your prod-tier Riot API key. (Currently dev-tier per project memory; apply for prod when ready.)
- `RSO_CLIENT_ID` — from Riot's RSO developer portal.
- `RSO_CLIENT_SECRET` — same.
- `SESSION_SECRET` — `openssl rand -hex 32`.

Save and trigger a redeploy.

### 4. Update the RSO redirect URI

Riot's RSO config requires the exact callback URL to be allow-listed. After the app is deployed, the public URL is `https://<APP_NAME>-<HASH>.ondigitalocean.app`. Add `${APP_URL}/api/valorant/auth/callback` to the RSO app's allowed redirect URIs.

If you have a custom domain (e.g. `campusrankers.com`), point it at the DO app first, then use that in the RSO redirect URI for cleaner sign-in URLs.

### 5. Smoke tests against production

```bash
APP_URL=https://your-app.ondigitalocean.app

# Health
curl -fs $APP_URL/api/health | jq
# Expect: {"status":"ok","db":"connected"}

# OpenAPI surface (full set of routes registered):
curl -fs $APP_URL/openapi.json | jq -r '.paths | keys | .[]' | wc -l
# Expect: 25+ paths.

# Admin login with the DO secret:
curl -fs -X POST $APP_URL/api/admin/login \
  -H 'Content-Type: application/json' \
  -d "{\"password\":\"$ADMIN_PASSWORD\"}" | jq -r '.token'

# Public list (empty until seeded):
curl -fs $APP_URL/api/teams
curl -fs $APP_URL/api/players

# Frontend renders:
curl -I $APP_URL/   # 200 OK
```

### 6. Cutover

When all smoke tests pass:

1. Open a PR from `postgres-migration-v2` to `main` on GitHub.
2. Self-review the diff (Phases 0–6 are atomic individually but the merge to main is the canonical "this is now Postgres" moment).
3. Squash-merge or merge-commit (your preference). Squash loses per-phase history; merge-commit preserves it.
4. Delete the `postgres-migration-v2` branch.
5. Update DO app to point at `main`.
6. (Optional) Bump the DO Postgres cluster from `dev` to production tier when ready for HA + backups.

### 7. Post-cutover housekeeping

- Update `CONSTITUTION.md` "Current Reality" → reflect Postgres as live (Phase 0's reality reconciliation gets reversed: "production is on Postgres now").
- Update `PROGRESS.md` Phase Roadmap: all phases checked off.
- Remove the `Backend/migrate.py` and `Backend/migrate_leagues.py` Mongo-era backfill scripts (or move to `Backend/archive/`).
- Remove the `riot_content_api_wiki 1.md` and `Riot Developer Portal.md` from .gitignore-only status if they should now be committed (or leave as-is if you want to keep them local-only).

---

## Rollback (if cutover fails)

DO App Platform makes rollback safe:

```bash
doctl apps create-deployment $APP_ID --commit-sha=<previous-good-sha>
```

This redeploys the previous build. The Postgres cluster keeps its data; if you need to wipe and re-apply:

```bash
psql "$DB_URL" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
psql "$DB_URL" -v ON_ERROR_STOP=1 -f Backend/schema.sql
```

(Don't do this in production once you have real users. For the pre-launch state described in CONSTITUTION §0, it's safe.)

## Costs (rough estimate)

- DO App Platform basic apps: ~$5/mo each (backend + frontend) = $10/mo.
- DO Managed Postgres dev tier: ~$15/mo.
- **Total: ~$25–30/mo** to launch. Production-tier Postgres + larger app instances would push to $80–120/mo.

The dev-tier Postgres has no HA and limited backups — fine for pre-launch / soft launch. Bump to production when active users justify the cost.
