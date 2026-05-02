# Phase 0 — Branch + Doc Reality Reconciliation

**Migration:** Postgres v2 (Mongo → DigitalOcean Managed Postgres)
**Branch:** `postgres-migration-v2`
**Phase order:** Phase 0 of seven phases total (Phases 0–6). See `/migrations/postgres-v2/README.md` once Phase 1 is filed.
**Status:** Draft, awaiting approval

## Approval Flow (two gates)

1. **Spec approval (gate A)** — Developer (Daniel) reviews this SPEC + the `codex exec` critique. On approval, implementation begins.
2. **Pre-commit approval (gate B)** — After implementation, developer reviews the actual edited SDD docs. On approval, the commit lands. No commit before gate B.

Local-only changes to `CLAUDE.md` (gitignored) are intentional but **not part of the committed diff** and are **not acceptance-gated** by the criteria below.

---

## Phase Goal

Prepare the workspace for the migration: create the working branch, commit the SDD docs that currently sit untracked, and reconcile those docs so they describe the **actual** state of the codebase (Mongo on `main`, migration in flight on `postgres-migration-v2`) instead of an aspirational Postgres world that does not yet exist.

No code changes. No dependency changes. No infrastructure changes.

## User Story

> As **the developer (and any future AI session)**, I want **the SDD docs to describe what the code actually does**, so that **I do not waste time following rules for code paths that do not exist or skip checks that the real (Mongo) code still requires.**

## Technical Requirements

### Repository / Branch

- Create branch `postgres-migration-v2` off the current tip of `main` (`dc1500c`).
- All work in this phase happens on that branch. `main` is not touched.

### Documentation Changes

The currently-untracked SDD docs are committed onto `postgres-migration-v2` after being edited to describe reality. Specifically:

| File | Action | Purpose |
|---|---|---|
| `CONSTITUTION.md` | edit + commit | Split into "Current Reality (Mongo)" and "Target Architecture (Postgres) — to be built in this branch". Hard rules that apply NOW vs. hard rules that apply AFTER the migration are separated. |
| `PROGRESS.md` | edit + commit | Replace the false "PostgreSQL migration complete" claims with the real status: Mongo on prod-bound `main`, migration restart on this branch, no live users, no Riot prod key, no DO Postgres provisioned. Phase Roadmap rewritten as Phases 0–6 of this migration. The "Graveyard" historical section is preserved verbatim — it is real, hard-won institutional knowledge. |
| `SDD.md` | commit as-is | Methodology doc. Already accurate — no edits. |
| `FEATURE_SPEC.md` | commit as-is | File on disk is already the empty per-feature template — no edits needed. |
| `IMPLEMENTATION_PLAN.md` | commit as-is | File on disk is already the empty per-feature template — no edits needed. |

`CLAUDE.md` is gitignored — stays local-only. It still gets edited to match the corrected CONSTITUTION/PROGRESS so my future sessions are anchored to reality, but the change is invisible to git and is **not part of the acceptance criteria below**.

### Migration Phase Docs

- Create `migrations/postgres-v2/` directory.
- This file (`phase-0-SPEC.md`) is the first artifact in it.
- Future phases (`phase-1-SPEC.md`, `phase-2-SPEC.md`, …) will live alongside.
- Each phase SPEC will be drafted before its phase begins, reviewed via `codex exec`, approved by the developer, then implemented.

### .gitignore

Add the following two entries to `/.gitignore` so the Riot reference docs stay local but never get committed:

```
# Riot API reference docs (kept locally for AI context, not committed)
/Riot Developer Portal.md
/riot_content_api_wiki 1.md
```

The `/` prefix anchors them to the repo root so we do not accidentally ignore similarly-named files elsewhere.

### Out of Scope (explicitly NOT in Phase 0)

- Any change to `Backend/`, `Frontend/`, `docker-compose.yml`, `Backend/Dockerfile`, `Frontend/Dockerfile`, or `Backend/.env.example`.
- Any change to `requirements.txt` or `package.json`.
- Adding `psycopg2-binary` or removing `pymongo`.
- Writing `Backend/schema.sql`.
- Touching the `core/*_router.py` files.
- Deleting remote branches (`postgres-migration`, `stash-postgres-wip`, `sdd-docs`) — they stay as reference until the new migration merges.
- Provisioning DigitalOcean Managed Postgres.
- Any RSO / auth / consent work.

## API Contract

N/A — no code changes.

## Acceptance Criteria

- [ ] `git rev-parse --abbrev-ref HEAD` returns `postgres-migration-v2`.
- [ ] `git log --oneline main..HEAD` lists 1–2 commits, all documentation-only.
- [ ] `git diff --name-only main..HEAD` lists **only** files in this exact set (no others):
  - `CONSTITUTION.md`
  - `PROGRESS.md`
  - `SDD.md`
  - `FEATURE_SPEC.md`
  - `IMPLEMENTATION_PLAN.md`
  - `migrations/postgres-v2/phase-0-SPEC.md`
  - `.gitignore`
- [ ] `git check-ignore -v "Riot Developer Portal.md" "riot_content_api_wiki 1.md"` returns both files as ignored, citing `.gitignore` lines from this branch.
- [ ] Both Riot doc files still exist on the local filesystem (gitignore does not delete them).
- [ ] `CONSTITUTION.md` opens with a "Current Reality" section that explicitly says "production-bound `main` is Mongo; this branch is migrating to Postgres" — no claim that the migration is done.
- [ ] `PROGRESS.md` reflects the seven-phase roadmap (Phase 0 in progress, Phases 1–6 pending) and lists the actually-true blockers (no DO Postgres, dev-tier Riot key, no auth/consent system yet). The Graveyard section is retained verbatim.
- [ ] `migrations/postgres-v2/phase-0-SPEC.md` exists and matches the spec-approved version (gate A).
- [ ] **Manual sensitive-info pass:** developer scans the SDD doc edits for secrets, API keys, internal IPs, or private operational notes before commit. Documented as a "reviewed by Daniel — clean" line in the commit message.
- [ ] **Advisory only (not a hard gate):** `codex review --base main` produces no critical/security findings. A non-clean codex review prompts a discussion, not an auto-block.
- [ ] **Pre-commit (gate B):** developer (Daniel) explicitly approves the actual edited docs before the commit lands.

## Verification Plan

```bash
# Branch state
git rev-parse --abbrev-ref HEAD                  # → postgres-migration-v2
git log --oneline main..HEAD                     # 1–2 commits, doc-only

# Diff scope check (exact path allow-list, not glob)
git diff --name-only main..HEAD | sort > /tmp/phase0-actual.txt
cat <<'EOF' | sort > /tmp/phase0-expected.txt
.gitignore
CONSTITUTION.md
FEATURE_SPEC.md
IMPLEMENTATION_PLAN.md
PROGRESS.md
SDD.md
migrations/postgres-v2/phase-0-SPEC.md
EOF
diff /tmp/phase0-expected.txt /tmp/phase0-actual.txt && echo "diff scope OK"

# Verify gitignore actually ignores the Riot docs (not just that they are untracked elsewhere)
git check-ignore -v "Riot Developer Portal.md" "riot_content_api_wiki 1.md"

# Verify the local files still exist (gitignore must not delete)
ls -1 "Riot Developer Portal.md" "riot_content_api_wiki 1.md"

# Manual: scan staged docs for secrets / PII / internal-only text before commit
git diff --staged | less

# Advisory ChatGPT review (not a hard gate — informational only)
codex review --base main --title "Phase 0 — doc reconciliation" \
  "Review only. Verify: (1) the new CONSTITUTION/PROGRESS accurately describe the current Mongo-on-main reality versus the planned Postgres target; (2) no claim is made that the migration is already done; (3) no code/dependency files are touched; (4) gitignore additions are correct and scoped to repo root; (5) phase-0-SPEC.md matches what was actually committed."
```

## Rollback Plan

```bash
# Confirm no in-flight uncommitted work that would be lost (CLAUDE.md is gitignored
# and survives branch deletion; everything else should be staged/committed or
# explicitly discarded):
git status --short
git stash list

# When the working tree is acceptable, discard the branch:
git checkout main
git branch -D postgres-migration-v2
```

No remote push happens in Phase 0 (work stays local until developer approves a push). No data, schema, or runtime state is modified. The `CLAUDE.md` local edits remain on the filesystem after branch deletion (it's gitignored) — re-edit by hand if you want the old aspirational version back.

## Risks & Open Questions

- **Risk: developer disagreement with "Current Reality" framing.** If the rewritten CONSTITUTION/PROGRESS misinterprets project intent, downstream phases inherit the misframing. Mitigation: developer reviews the rewrite *before* commit (gate B), plus `codex exec` second-eyes review.
- **Risk: SDD-doc drift returns.** Once Postgres ships, both files need re-updating to flip "current reality" sections. Captured as an explicit Phase 6 task.
- **Risk: committing previously-untracked SDD docs may carry stale content beyond the named edit sections** — old aspirational claims, internal notes, or accidentally-pasted secrets. Mitigation: explicit manual sensitive-info scan in the acceptance criteria, plus codex advisory review.
- **Open: should the existing `migrate_leagues.py` and `migrate.py` files (Mongo-era backfill scripts) move to `Backend/archive/`?** Recommend deferring to a future cleanup phase — not in Phase 0 scope.
- **Open: where does `riot.txt` belong?** It's a one-line file at repo root, looks like a Riot domain-verification file. Leave it tracked, do not gitignore.
