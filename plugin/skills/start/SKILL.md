---
name: start
description: >
  This skill should be used when the user says "/start" or asks to
  "run a task," "execute the procedure," or "begin this period's work."
  Executes a task for the current period — scaffolds directories, loads
  context, runs the procedure, and updates status.yaml directly.
version: 2.0.0
---

# /start — Execute Task for Current Period

## Step 1 — Read Status and Route

Read `status.yaml` from the current task directory. Route based on the `status` field:

| Current status | Action |
|----------------|--------|
| `not_started` | Proceed to Step 2. |
| `in_progress` | Crash recovery. Check if `periods/<period>/` exists. If yes, skip to Step 5. If no, proceed to Step 3. |
| `review_ready` | Re-execution after rejection. Proceed to Step 2. |
| `blocked` | Go to Step 1a (blocked recovery). |
| `done` | Tell the user this task is already complete for this period. **Stop.** |
| `abandoned` | Tell the user this task was abandoned for this period. **Stop.** |

If the status is `done` or `abandoned`, do not modify any state and do not commit. Stop immediately.

### Step 1a — Blocked Recovery

Present the issues from `status.yaml` to the user:

```
This task is blocked:
  issues: [<issues from status.yaml>]

Options:
  1. Retry — proceed with a fresh attempt
  2. Abandon — mark this period as unrecoverable
```

Wait for the user's decision.

**If the user chooses Retry:** Proceed to Step 2.

**If the user chooses Abandon:** Write `status.yaml` directly:

```yaml
schema_version: 1
status: abandoned
period: "<period>"
issues:
  - "<reason from user>"
done_at: null
```

Then commit and stop:

```bash
git add -A && git commit -m "[start] <period>: abandoned"
```

Do not continue to Step 2.

## Step 2 — Determine Period

Ask the user what period to execute (e.g., "2026-04" for monthly, "2026-Q1" for quarterly).

Write `status.yaml` directly:

```yaml
schema_version: 1
status: in_progress
period: "<period>"
issues: []
done_at: null
```

## Step 3 — Install Dependencies

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/install-deps.py
```

If this fails, go to the Failure Path in Step 7.

## Step 4 — Scaffold Period Directory

Only if `periods/<period>/` does **not** already exist:

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/init-period.py <period>
```

If the directory already exists, skip this step (crash recovery case).

If `init-period.py` fails, go to the Failure Path in Step 7.

## Step 5 — Load Context

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/load-context.py --level task
```

Read the output. This provides `SKILL.md`, `learned.md`, and other context files from the folder hierarchy.

## Step 6 — Execute Procedure

Read the task's `SKILL.md` and `learned.md` from the loaded context.

- **SKILL.md** contains the procedure, data sources, and validation rules. Follow its `## Procedure` section.
- **learned.md** contains patterns, known issues, and expected ranges from prior periods.

Key rules during execution:

- Place all source files in `periods/<period>/data/`.
- Place all outputs in `periods/<period>/workpapers/`.
- Never write files outside the period directory.
- If you need source data from the user, ask them to provide it. Place received files in `data/`.

## Step 7 — Handle Outcome

### Success Path

If execution succeeds (output produced, validation passes, completion criteria met):

Write `status.yaml` directly:

```yaml
schema_version: 1
status: review_ready
period: "<period>"
issues: []
done_at: null
```

### Failure Path

If execution fails (data missing, script error, validation fails, unrecoverable issue):

Write `status.yaml` directly:

```yaml
schema_version: 1
status: blocked
period: "<period>"
issues:
  - "<description of what went wrong>"
done_at: null
```

## Step 8 — Git Commit

Regardless of success or failure, produce exactly one commit:

```bash
git add -A && git commit -m "[start] Execute <period>"
```

## Step 9 — Report to User

**On success:** Tell the user what was prepared, key numbers, and any items needing attention. End with: *"Period execution complete. Run /done to review."*

**On failure:** Tell the user what failed, why, and whether it is likely recoverable.

## Constraints

- **Fresh agent per execution.** This skill runs as a stateless agent. All context comes from the folder hierarchy (`SKILL.md`, `learned.md`, `AGENT.md`). There is no memory of prior conversations.
- **status.yaml is written directly.** The agent writes `status.yaml` by hand. There is no `set-status.py` script.
- **One commit per invocation.** Whether the outcome is `review_ready` or `blocked`, produce exactly one git commit. If the task is `done` or `abandoned` (terminal on entry), produce no commit.
- **No partial state on crash.** If `/start` crashes before its commit step, nothing is committed. The user can retry or reset via `git checkout .`.
