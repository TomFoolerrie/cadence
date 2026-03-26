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

Execute a task for the current period. `/start` is the recurring execution skill — used from the **second period onward** (the first period is handled by `/onboard`).

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

### Step 1 — Set In Progress

Determine the period string. This is the **period being closed**, not the current calendar period (e.g., if it's April, the period is `2026-03` for March close).

- If `status.yaml` already has a non-empty `period` (normal case — set by `check-periods.py` on reset, or crash recovery / rejected draft):
  ```bash
  set-status.py in_progress
  ```
- If period is empty AND `period_format` is `adhoc`: ask the user for the period string, then:
  ```bash
  set-status.py in_progress --period "<period>"
  ```
- If period is empty AND `period_format` is not `adhoc`: compute the period being closed from the current date — for `monthly`, use the previous month (e.g., if today is 2026-04-07, period is `2026-03`); for `quarterly`, use the previous quarter; for `weekly`, use the previous week. Then:
  ```bash
  set-status.py in_progress --period "<period>"
  ```

> **Note:** The `period` field is normally set by `check-periods.py` on reset. `/start` only passes `--period` for the first non-onboarded execution or for `adhoc` tasks.

This is idempotent — if already `in_progress` (crash recovery) or transitioning from `review_ready` (rejected draft), it succeeds without error.

### Step 2 — Install Dependencies

```bash
install-deps.py
```

Installs `requirements.txt` files top-down (root → class → task). If `install-deps.py` fails (exit 2), set `blocked` with the error details, commit, and stop.

### Step 3 — Setup Period

If the period directory doesn't already exist, scaffold it:

```bash
init-period.py <period>
```

Creates `periods/{period}/` with `data/`, `workpapers/`, and `review-notes/`.

If the period directory already exists (crash recovery, re-execution after rejection), skip scaffolding.

### Step 4 — Load Context

```bash
load-context.py --level task
```

This loads the full context chain: root `AGENT.md` → class `AGENT.md` → `SKILL.md` + `learned.md` + `status.yaml`. The agent receives this output and uses it for execution.

If `load-context.py` fails (exit 1), set `blocked` with the error details, commit, and stop.

> **Wrapper note:** Steps 1–4 (set status, install deps, init period, load context) form the **setup phase**. In implementation, a lightweight Python wrapper runs these scripts in sequence before handing context to the agent for execution.

### Step 5 — Execute

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

### Step 6 — Handle Outcome

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

### Step 7 — Commit (success path)

```bash
git add .
git commit -m "[start] <task-name> <period>: draft ready for review"
```

The user reviews the draft and then runs `/done` in **this same conversation**.

---

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| Period directory already exists | Skip `init-period.py` — resume execution with existing data |
| `in_progress` from crashed session | `set-status.py in_progress` is a no-op; resume execution |
| `review_ready` and human rejects | `set-status.py in_progress` clears issues; re-execute from Step 5 |
| `done` or `abandoned` | Inform the user the task is already terminal for this period; stop |
| Source data not yet available | Ask the user to provide it; if they can't, set `blocked` |
| Tool fails mid-execution | Report the error, set `blocked` with details |
| `adhoc` period format | Ask user for the period string instead of computing it |

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
| `set-status.py <status>` | Steps 0a, 1, 6 | Transition task status |
| `install-deps.py` | Step 2 | Install Python dependencies top-down |
| `init-period.py <period>` | Step 3 | Scaffold period directory (if needed) |
| `load-context.py --level task` | Step 4 | Load root + class + task context |
