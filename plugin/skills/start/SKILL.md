---
name: start
description: >
  This skill should be used when the user says "/start" or asks to
  "run a task," "execute the procedure," or "begin this period's work."
  Executes a task for the current period — loads context, runs the
  procedure, produces a draft, and sets review_ready. Also handles
  recovery from blocked and rejected states.
version: 1.0.0
---

# /start — Execute Task for Current Period

## Step 0 — Read Status and Route

Read `status.yaml` from the current task directory. Route based on the `status` field:

| Current status | Action |
|---------------|--------|
| `not_started` | Proceed to Step 1 (normal execution). |
| `in_progress` | Crash recovery — proceed to Step 1 idempotently. |
| `review_ready` | Human rejected the draft — proceed to Step 1 to re-execute. |
| `blocked` | Go to Step 0a (blocked recovery). |
| `done` | Tell the user this task is already complete for the current period. Stop. |
| `abandoned` | Tell the user this task was abandoned for the current period. Stop. |

If the status is `done` or `abandoned`, do not modify any state and do not commit. Stop immediately.

### Step 0a — Blocked Recovery

Present the issues from `status.yaml` to the user in this format:

```
This task is blocked:
  issues: [<issues from status.yaml>]

Options:
  1. Retry — resets to not_started for a fresh attempt
  2. Abandon — marks this period as unrecoverable
```

Wait for the user's decision.

**If the user chooses Retry:**

Run:

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/set-status.py not_started
```

Then proceed to Step 1.

**If the user chooses Abandon:**

Run (substituting the user's reason):

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/set-status.py abandoned "<reason from user>"
```

Then commit and stop:

```bash
git add status.yaml
git commit -m "[start] <task-name> <period>: abandoned — <reason>"
```

Do not continue to Step 1.

## Step 1 — Setup

Determine the period string. The period is a label for the work being done in this cycle.

- If `status.yaml` already has a non-empty `period` field (normal case — set by `check-periods.py` on reset, or crash recovery / rejected draft): no `--period` needed.
- If `period` is empty AND `period_format` is `adhoc`: ask the user for the period string.
- If `period` is empty AND `period_format` is not `adhoc`: ask the user for the period string (e.g., `2026-03` for monthly, `2026-Q1` for quarterly, `2026-W12` for weekly).

Then run the setup wrapper:

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/start-setup.py [--period "<period>"]
```

This runs four scripts atomically: sets status to `in_progress`, installs dependencies, scaffolds the period directory (if needed), and loads the full context chain. On success, context is printed to stdout.

- **Exit 0:** Setup complete. Proceed to Step 2.
- **Exit 1:** Precondition error (invalid transition, no period). Report to user, stop.
- **Exit 2:** Script failure. Task is already set to `blocked`. Commit and stop:
  ```bash
  git add .
  git commit -m "[start] <task-name> <period>: blocked — setup failed"
  ```

## Step 2 — Execute

Before running task tools, ensure the engagement venv is active. The venv is at `<root>/venv/` where `<root>` is the engagement root containing `.context-root`. Activate it with `source <root>/venv/bin/activate`.

Read `SKILL.md` and `learned.md` from the loaded context.

- **SKILL.md** contains the procedure, data sources, and validation rules. Follow its `## Procedure` section.
- **learned.md** contains patterns, known issues, and expected ranges from prior periods. Use these to validate your work and anticipate problems.

Key rules during execution:

- Place all source files in `periods/<period>/data/`.
- Place all outputs in `periods/<period>/workpapers/`.
- Never write files outside the period directory.
- Reference tools by path using the resolution order: task `tools/`, then class `tools/`, then global `.claude/tools/`.
- Check the `## Completion Criteria` section of `SKILL.md`. Your output must satisfy every criterion before you can set `review_ready`.

If you need source data from the user, ask them to provide it via Cowork file attachment. Place received files in `data/`.

## Step 3 — Handle Outcome

### Success Path

If execution succeeds (output produced, validation passes, all completion criteria met):

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/set-status.py review_ready
```

Report to the user:

- What was prepared.
- Key numbers (totals, line counts, significant amounts).
- How the results compare to `learned.md` patterns (within expected range? anomalies?).
- Any items that need attention.
- End with: *"Ready for your review. Run `/done` when you've reviewed the output."*

Then proceed to Step 4.

### Failure Path

If execution fails (data missing, API error, validation fails, unrecoverable issue):

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/set-status.py blocked "<description of what failed>"
```

Report to the user:

- What failed and why.
- What you tried.
- Whether this is likely recoverable (retry after fixing the issue) or not.

Then commit and stop:

```bash
git add .
git commit -m "[start] <task-name> <period>: blocked — <reason>"
```

Do not proceed to Step 4.

## Step 4 — Git Commit (Success Path)

Commit all work for the period:

```bash
git add .
git commit -m "[start] <task-name> <period>: draft ready for review"
```

The user reviews the draft and then runs `/done` in this same conversation.

## Edge Cases

- **Period directory already exists:** `start-setup.py` skips `init-period.py`. Resume execution with existing data.
- **`in_progress` from a crashed session:** `start-setup.py` is idempotent. Resume execution.
- **`review_ready` and human rejects:** `start-setup.py` transitions to `in_progress`. Re-execute from Step 2.
- **`done` or `abandoned`:** Inform the user the task is already terminal for this period. Stop without modifying state.
- **Source data not yet available:** Ask the user to provide it. If they cannot, set `blocked` with details.
- **Tool fails mid-execution:** Report the error and set `blocked` with details.
- **`adhoc` period format:** Ask the user for the period string, pass to `start-setup.py --period`.

## Constraints

- **Fresh agent per execution.** The agent is stateless — everything it needs is in the folder. It reads SKILL.md and learned.md fresh every time.
- **One commit per invocation.** Whether the outcome is `review_ready` or `blocked`, produce exactly one git commit. If the task is `done` or `abandoned`, produce no commit.
- **No partial state on crash.** If `/start` crashes before its commit step, nothing is committed. The user can retry or reset via `git checkout .`.
- **`/done` runs in this conversation.** After setting `review_ready`, the human reviews and calls `/done` in the same session. `/done` does not load context independently.
