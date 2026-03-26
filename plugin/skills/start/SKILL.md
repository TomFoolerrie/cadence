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

## Step 1 — Set In Progress

Determine the period string. The period is the **period being closed**, not the current calendar period (e.g., if today is April, the period for a monthly task is `2026-03`).

**If `status.yaml` already has a non-empty `period` field** (normal case — set by `check-periods.py` on reset, or crash recovery / rejected draft):

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/set-status.py in_progress
```

**If `period` is empty AND `period_format` is `adhoc`:**

Ask the user for the period string. Then run:

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/set-status.py in_progress --period "<period>"
```

**If `period` is empty AND `period_format` is not `adhoc`:**

Compute the period being closed from the current date:

- `monthly` — use the previous month (e.g., if today is 2026-04-07, period is `2026-03`)
- `quarterly` — use the previous quarter (e.g., if today is 2026-04-07, period is `2026-Q1`)
- `weekly` — use the previous week

Then run:

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/set-status.py in_progress --period "<period>"
```

This step is idempotent. If the task is already `in_progress` (crash recovery) or transitioning from `review_ready` (rejected draft), `set-status.py` succeeds without error.

## Step 2 — Install Dependencies

Run:

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/install-deps.py
```

This installs `requirements.txt` files top-down (root, class, task).

If `install-deps.py` exits with code 2, run:

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/set-status.py blocked "<error details from install-deps.py>"
```

Then commit and stop:

```bash
git add .
git commit -m "[start] <task-name> <period>: blocked — dependency install failed"
```

## Step 3 — Setup Period

Check whether the period directory `periods/<period>/` already exists.

**If it does not exist**, scaffold it (substituting the period string):

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/init-period.py <period>
```

This creates `periods/<period>/` with `data/`, `workpapers/`, and `review-notes/` subdirectories.

**If it already exists** (crash recovery, re-execution after rejection), skip this step.

## Step 4 — Load Context

Run:

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/load-context.py --level task
```

This loads the full context chain: root `AGENT.md`, class `AGENT.md`, task `SKILL.md`, `learned.md`, and `status.yaml`. Use the output for execution in the next step.

If `load-context.py` exits with code 1, run:

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/set-status.py blocked "<error details from load-context.py>"
```

Then commit and stop:

```bash
git add .
git commit -m "[start] <task-name> <period>: blocked — context load failed"
```

## Step 5 — Execute

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

## Step 6 — Handle Outcome

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

Then proceed to Step 7.

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

Do not proceed to Step 7.

## Step 7 — Git Commit (Success Path)

Commit all work for the period:

```bash
git add .
git commit -m "[start] <task-name> <period>: draft ready for review"
```

The user reviews the draft and then runs `/done` in this same conversation.

## Edge Cases

- **Period directory already exists:** Skip `init-period.py`. Resume execution with existing data.
- **`in_progress` from a crashed session:** `set-status.py in_progress` is a no-op. Resume execution from where context loads.
- **`review_ready` and human rejects:** `set-status.py in_progress` clears issues. Re-execute from Step 5.
- **`done` or `abandoned`:** Inform the user the task is already terminal for this period. Stop without modifying state.
- **Source data not yet available:** Ask the user to provide it. If they cannot, set `blocked` with details.
- **Tool fails mid-execution:** Report the error and set `blocked` with details.
- **`adhoc` period format:** Ask the user for the period string instead of computing it.

## Constraints

- **Fresh agent per execution.** The agent is stateless — everything it needs is in the folder. It reads SKILL.md and learned.md fresh every time.
- **One commit per invocation.** Whether the outcome is `review_ready` or `blocked`, produce exactly one git commit. If the task is `done` or `abandoned`, produce no commit.
- **No partial state on crash.** If `/start` crashes before its commit step, nothing is committed. The user can retry or reset via `git checkout .`.
- **`/done` runs in this conversation.** After setting `review_ready`, the human reviews and calls `/done` in the same session. `/done` does not load context independently.
