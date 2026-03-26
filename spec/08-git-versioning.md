# Git Versioning

The hierarchy is initialized as a git repository during scaffolding. The agent commits every structural change automatically — adding tasks, updating procedures, capturing learnings. This gives the hierarchy full version history with zero effort from the user.

## 9.1 Initialization

During scaffolding, the agent runs:

```
git init
git add .context-root AGENT.md .claude/ .gitignore requirements.txt
git add treasury/ reporting/ ...
git commit -m "Initial scaffold by accounting plugin"
```

## 9.2 .gitignore

```
# Source data files (too large for git, provided by user/external systems)
**/periods/*/data/

# Workpapers (generated outputs — archived via Drive when period completes)
**/periods/*/workpapers/

# Cache and OS
.context-cache/
.DS_Store
```

The structural files — `.context-root`, `.class.yaml`, `AGENT.md`, `status.yaml` (task level), `SKILL.md`, `learned.md`, `tools/` — **are tracked**. Period review notes (feedback that feeds into learned.md) **are tracked**. Source data inputs in `periods/*/data/` **are not tracked** (they come from external systems and may be large). Workpapers in `periods/*/workpapers/` **are not tracked** — they are generated outputs that can be reproduced by re-running the task, and may include large binary files (`.xlsx`, `.pdf`). `archive-period.py` uploads workpapers and data to Google Drive when a period is completed (called by `/done` after commit).

This means the git history captures the *orchestration structure, state, procedures, learnings, and review feedback* — everything needed to reproduce work, without the bulk of generated outputs.

## 9.3 Automatic Commits

**Skills own commits.** Each skill (`/onboard`, `/start`, `/done`) includes a git commit as its final step. Scripts (`set-status.py`, `init-period.py`, `load-context.py`, `archive-period.py`, etc.) have no git side effects — they modify files, and the calling skill commits the aggregate changes when it completes. This is what makes commits **atomic per skill invocation** — each `/onboard`, `/start`, and `/done` produces exactly one commit, whether the outcome is success or error.

`/done` also calls `archive-period.py` to upload workpapers and data to Google Drive after committing.

Two distinct failure modes:

- **Blocked (committed).** The skill ran to completion but the outcome was blocked — e.g., an API returned 401, a validation check failed, a data source was missing. This is a valid, recorded status. The skill sets `status: blocked` in `status.yaml` via `set-status.py` and commits. The commit message includes the reason (see examples below). Blocked states are part of the audit trail.
- **Partial failure (not committed).** The skill crashed or was interrupted mid-execution — e.g., Claude's session dropped, a script threw an unhandled exception, the user aborted. The skill never reached its commit step, so nothing is committed. The working tree may contain intermediate state; the human can inspect and either retry or reset via `git checkout .`.

**Branch strategy (MVP):** Everything on `main`. Single user, local only — no branching needed. Future multi-user state may introduce per-class or per-period branches.

**Commit message format:** `[skill] task-name period: summary`

```
/onboard completes:
  git commit -m "[onboard] monthly-bank-fees: SKILL.md, tools, dry run validated"

/start completes:
  git commit -m "[start] monthly-bank-fees 2026-03: draft ready for review"

/start fails:
  git commit -m "[start] monthly-bank-fees 2026-03: blocked — Chase API 401"

/done completes:
  git commit -m "[done] monthly-bank-fees 2026-03: updated learned.md"

User adds a connection:
  git commit -m "Add Gmail invoice source to reporting class"
```

## 9.4 What This Enables

- **Undo.** "Undo that last change" → `git revert HEAD`
- **History.** "What did we change last week?" → `git log --since="1 week ago"`
- **Diff.** "How has this SKILL.md evolved?" → `git log -p -- treasury/monthly-bank-fees/SKILL.md`
- **Audit trail.** Every execution, every review, every learning is a commit. Full traceability.

## 9.5 Developer Access

Developers can interact with the git repo directly:

```bash
cd ~/Documents/Accounting
git log --oneline
git diff HEAD~1
```

The agent treats the git repo as its own — it doesn't expect manual commits. But if a developer hand-edits files, the agent picks up their changes on next session.
