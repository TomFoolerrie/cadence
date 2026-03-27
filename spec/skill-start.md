# Skill: `/start`

## Frontmatter

```yaml
---
name: start
description: >
  Executes a task for the current period. Loads context,
  runs the procedure, produces a draft, and sets review_ready.
  Also handles recovery from blocked and rejected states.
version: 1.0.0
---
```

## Purpose

Execute a task for the current period. `/start` is the execution skill — used for **every period after the first**. The first period is executed inline by `/onboard` during knowledge transfer.

`/start` also handles recovery:
- **Blocked** → human decides to retry (→ `not_started`) or abandon (→ `abandoned`)
- **Review rejected** → re-executes (→ `in_progress` from `review_ready`)
- **Crashed session** → re-enters `in_progress` idempotently

---

## Procedure

### Step 0 — Read Status and Route

Read `status.yaml` directly and route based on current state:

| Current status | Action | Next step |
|---------------|--------|-----------|
| `not_started` | Normal execution | → Step 1 |
| `in_progress` | Crash recovery — re-enter idempotently | → Step 1 |
| `review_ready` | Human rejected the draft — re-execute | → Step 1 |
| `blocked` | Recovery decision needed | → Step 0a |
| `done` | Already complete for this period | → Tell user, stop |
| `abandoned` | Already abandoned for this period | → Tell user, stop |

#### Step 0a — Blocked Recovery

The task is blocked. Present the issues from `status.yaml`:

```
This task is blocked:
  issues: ["Chase API returned 401 — token expired"]

Options:
  1. Retry — resets to not_started for a fresh attempt
  2. Abandon — marks this period as unrecoverable
```

Wait for the user's decision:

- **Retry:**
  ```bash
  set-status.py not_started
  ```
  Then proceed to Step 1.

- **Abandon:**
  ```bash
  set-status.py abandoned "reason from user"
  ```
  Commit and stop:
  ```bash
  git add status.yaml
  git commit -m "[start] <task-name> <period>: abandoned — <reason>"
  ```

### Step 1 — Setup

Determine the period string. This is the **period being closed**, not the current calendar period (e.g., if it's April, the period is `2026-03` for March close).

- If `status.yaml` already has a non-empty `period` (normal case — set by `check-periods.py` on reset, or crash recovery / rejected draft): no `--period` needed.
- If period is empty AND `period_format` is `adhoc`: ask the user for the period string.
- If period is empty AND `period_format` is not `adhoc`: compute the period being closed from the current date — for `monthly`, use the previous month (e.g., if today is 2026-04-07, period is `2026-03`); for `quarterly`, use the previous quarter; for `weekly`, use the previous week.

> **Note:** The `period` field is normally set by `check-periods.py` on reset. The agent only computes the period itself for `adhoc` tasks or when the period is unexpectedly empty.

Then run the setup wrapper:

```bash
start-setup.py [--period "<period>"]
```

This runs four scripts atomically: `set-status.py in_progress`, `install-deps.py`, `init-period.py`, and `load-context.py --level task`. On success, it prints the loaded context to stdout. On failure at any step, it sets the task to `blocked` and exits.

- **Exit 0:** Setup complete. Context is printed to stdout. Proceed to Step 2.
- **Exit 1:** Precondition error (invalid transition, no period). Report to user, stop.
- **Exit 2:** Script failure. Task is already set to `blocked`. Commit and stop:
  ```bash
  git add .
  git commit -m "[start] <task-name> <period>: blocked — setup failed"
  ```

### Step 2 — Execute

Read `SKILL.md` and `learned.md` from the loaded context.

- **SKILL.md** tells you what to do — procedure, data sources, validation rules
- **learned.md** tells you what to expect — patterns, known issues, expected ranges from prior periods

Follow the `## Procedure` section of SKILL.md. Key rules:

- All source files go in `periods/{period}/data/`
- All outputs go in `periods/{period}/workpapers/`
- Never write files outside the period directory
- Reference tools by path using the resolution order: task `tools/` → class `tools/` → global `.claude/tools/`
- Check the `## Completion Criteria` section — your output must satisfy these before you can set `review_ready`

If you need source data from the user, ask them to provide it via Cowork file attachment. Place it in `data/`.

### Step 3 — Handle Outcome

**If execution succeeds** (output produced, validation passes, completion criteria met):

```bash
set-status.py review_ready
```

Report to the user:
- What was prepared
- Key numbers (totals, line counts, significant amounts)
- How the results compare to learned.md patterns (within expected range? anomalies?)
- Any items that need attention
- *"Ready for your review. Run `/done` when you've reviewed the output."*

**If execution fails** (data missing, API error, validation fails, unrecoverable issue):

```bash
set-status.py blocked "description of what failed"
```

Report to the user:
- What failed and why
- What you tried
- Whether this is likely recoverable (retry after fixing the issue) or not

Then commit:

```bash
git add .
git commit -m "[start] <task-name> <period>: blocked — <reason>"
```

### Step 4 — Commit (success path)

```bash
git add .
git commit -m "[start] <task-name> <period>: draft ready for review"
```

The user reviews the draft and then runs `/done` in **this same conversation**.

---

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| Period directory already exists | `start-setup.py` skips `init-period.py` — resume execution with existing data |
| `in_progress` from crashed session | `start-setup.py` is idempotent; resume execution |
| `review_ready` and human rejects | `start-setup.py` transitions to `in_progress`; re-execute from Step 2 |
| `done` or `abandoned` | Inform the user the task is already terminal for this period; stop |
| Source data not yet available | Ask the user to provide it; if they can't, set `blocked` |
| Tool fails mid-execution | Report the error, set `blocked` with details |
| `adhoc` period format | Ask user for the period string, pass to `start-setup.py --period` |

---

## Key Constraints

- **Fresh agent per execution.** The agent is stateless — everything it needs is in the folder. It reads SKILL.md and learned.md fresh every time.
- **`/done` runs in this conversation.** After `/start` sets `review_ready`, the human reviews and calls `/done` in the same session. `/done` does not load context independently.
- **One commit per invocation that modifies state.** Whether the outcome is `review_ready` or `blocked`, `/start` produces exactly one git commit. If the task is already `done` or `abandoned`, no state is modified and no commit is produced.
- **No partial state on crash.** If `/start` crashes before reaching its commit step, nothing is committed. The user can retry or reset via `git checkout .`.

---

## Script Composition

| Script | When called | Purpose |
|--------|------------|---------|
| `set-status.py <status>` | Steps 0a, 3 | Transition task status (blocked recovery, outcome) |
| `start-setup.py [--period]` | Step 1 | Atomic setup phase (wraps `set-status.py`, `install-deps.py`, `init-period.py`, `load-context.py`) |
