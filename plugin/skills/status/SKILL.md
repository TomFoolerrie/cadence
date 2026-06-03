---
name: status
description: >
  This skill should be used when the user says "/status" or asks
  "where do things stand," "what's the progress," or "show me the
  dashboard." Read-only dashboard that scans task status files within
  a class and presents a human-readable progress rollup.
---

# Status Dashboard

Present a read-only progress dashboard for the current class. Read files directly from the filesystem. Do not call any scripts. Do not write any files. Do not perform any git operations.

## Step 1 — Confirm Location

Check that `.class.yaml` exists in the current working directory.

If it does not exist, respond with:

> Run `/status` from a class directory (a folder containing `.class.yaml`).

Stop. Do not produce any other output.

## Step 2 — Read the Class Manifest

Read `.class.yaml` in the current directory. Parse the `manifest` list. Identify every task entry where `enabled: true`. Discard every entry where `enabled: false`. Disabled tasks do not appear in any subsequent step — they are invisible to the dashboard.

Extract and retain the following fields from each enabled manifest entry for later use:

- `name` — the task directory name
- `order` — controls display order
- `anchor` — the recurrence anchor (e.g., `first_monday`)
- `period_format` — the recurrence type (e.g., `monthly`, `weekly`, `adhoc`)

## Step 3 — Read Task Status Files

For each enabled task (in manifest order), read the file `<task-name>/status.yaml` from the current directory.

Extract these fields:

| Field | Purpose |
|-------|---------|
| `status` | Current state: `not_started`, `in_progress`, `review_ready`, `blocked`, `done`, `abandoned` |
| `period` | The period string displayed in the header and per-task lines |
| `issues[]` | Displayed inline when the task is `blocked` |
| `done_at` | Timestamp used to compute the next due date |

If the task directory does not exist, or if `status.yaml` is missing inside it, treat that task as `not_started` with no period.

## Step 4 — Derive the Class Status

Apply these rules using only the enabled tasks:

| Condition | Derived class status |
|-----------|---------------------|
| Every enabled task is `not_started` | `not_started` |
| Every enabled task is `done` or `abandoned` | `done` |
| Any other combination | `in_progress` |

Count the terminal tasks (`done` + `abandoned`) and the total enabled tasks. Express this as a fraction: `<terminal>/<total> done`.

## Step 5 — Compute Next Due Dates

For each enabled task that has a terminal status (`done` or `abandoned`) and a `done_at` timestamp:

1. Look up that task's `anchor` and `period_format` from the manifest entry extracted in Step 2.
2. If `period_format` is `adhoc`, skip this task. Adhoc tasks have no computable next occurrence.
3. Otherwise, compute the next due date from `done_at` + `anchor` + `period_format`. For example: if `done_at` falls in April, `period_format` is `monthly`, and `anchor` is `first_monday`, the next due date is the first Monday of May.

## Step 6 — Present the Dashboard

Format the output exactly as follows.

### Header line

```
<ClassName> — <Period> — <DerivedStatus> (<terminal>/<total> done)
```

- **ClassName**: Title-case the class directory name.
- **Period**: Read from the task `status.yaml` files. If all tasks share the same period, show it once in the header. If tasks have different periods, omit the period from the header and show it per task line instead.
- **DerivedStatus**: The value computed in Step 4.
- **Progress fraction**: Terminal count over total enabled count.

### Task lines

Print one line per enabled task, ordered by the `order` field from the manifest.

```
  <icon> <task-name>      <status>    [done_at date]    [next due: <anchor> (<date>)]
```

**Icon rules:**

| Icon | When to use |
|------|-------------|
| `✓` | Terminal states: `done`, `abandoned` |
| `✗` | `blocked` |
| `·` | Non-terminal active states: `not_started`, `in_progress`, `review_ready` |

**Per-status formatting:**

- **done / abandoned**: If `done_at` is present, show the short date (e.g., `Apr 7`). If a next due date was computed in Step 5, append `next due: <anchor> (<date>)`.
- **blocked**: Append `blocked: "<text>"` using the first entry from the `issues[]` array.
- **not_started / in_progress / review_ready**: Show the status name. No additional annotation.

### Examples

A class with mixed task states:

```
Monthly Financials — Apr 2025 — in_progress (1/3 done)
  ✓ reconcile-accounts      done         Apr 7    next due: first_monday (May 5)
  ✗ review-expenses         blocked: "Missing Q1 vendor invoices"
  · prepare-report          in_progress
```

A class where all tasks are complete:

```
Weekly Standup — Week 14 — done (2/2 done)
  ✓ collect-updates         done         Apr 7    next due: monday (Apr 14)
  ✓ send-summary            done         Apr 7    next due: monday (Apr 14)
```

An adhoc task that is done (no next due shown):

```
Onboarding — Q1 2025 — done (1/1 done)
  ✓ setup-laptop            done         Mar 15
```

## Edge Cases

Handle each of these explicitly:

- **No enabled tasks in manifest**: Show the class name followed by "No enabled tasks." and stop.
- **Task directory missing**: Treat as `not_started` with no period.
- **`status.yaml` missing for a task**: Treat as `not_started` with no period.
- **All tasks `not_started`**: Class status is `not_started`. Fraction shows `0/N done`.
- **All terminal but mix of `done` and `abandoned`**: Class status is `done`. Both count toward the terminal fraction.
- **Tasks have different periods**: Show period per task line rather than a single header period.
- **`adhoc` task that is `done`**: Show `done_at` date but no "next due" annotation.
- **`blocked` task with multiple issues**: Show only the first issue inline.
- **Disabled task in manifest**: Exclude entirely. Do not show it, do not count it.

## Constraints

- **Never persist class status.** The derived status exists only in the displayed output. Do not write any file. Do not update any YAML.
- **No scripts.** Read `.class.yaml` and task `status.yaml` files directly from the filesystem. Do not invoke `load-context.py`, `set-status.py`, or any other script.
- **No side effects.** No file writes, no git operations, no status transitions. This skill is safe to run at any time, in any state.
- **Disabled tasks are invisible.** Tasks with `enabled: false` in `.class.yaml` are excluded from the rollup, the count, and the display.
