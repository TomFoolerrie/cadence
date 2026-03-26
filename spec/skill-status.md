# Skill: `/status`

## Frontmatter

```yaml
---
name: status
description: >
  Human orchestrator's dashboard. Reads task-level status.yaml
  files within a class and computes a human-readable rollup
  of class progress on the fly. Read-only — no side effects.
version: 1.0.0
---
```

## Purpose

Show the human orchestrator where a class stands. `/status` is a **read-only dashboard** — it scans every task in the class, reads each task's `status.yaml`, and presents a single summary. The class-level status is never persisted; it is always derived on the fly from the individual task states.

---

## Constraints

- **Read-only.** `/status` does not modify any file, does not call any script, and does not create git commits. It is purely a reader.
- **Class directory only.** `/status` must be run from a directory containing `.class.yaml`. If run from the root or a task directory, inform the user and stop.
- **No script calls.** `/status` does not call `load-context.py`, `set-status.py`, or any other script. It reads `.class.yaml` and task `status.yaml` files directly from the filesystem.

---

## Procedure

### Step 1 — Confirm Location

Verify the current directory contains `.class.yaml`. If it does not, tell the user: *"Run `/status` from a class directory (a folder containing `.class.yaml`)."* Stop.

### Step 2 — Read the Class Manifest

Read `.class.yaml` and extract the `manifest` list. Identify which tasks are **enabled** (`enabled: true`). Disabled tasks (`enabled: false`) are excluded from all subsequent steps — they do not appear in the output and do not count toward the rollup.

### Step 3 — Read Task Status Files

For each enabled task in the manifest, read `<task>/status.yaml`. Extract:

| Field | Used for |
|-------|----------|
| `status` | Current task state (`not_started`, `in_progress`, `review_ready`, `blocked`, `done`, `abandoned`) |
| `period` | The period string shown in the header and per-task lines |
| `issues[]` | Displayed inline for `blocked` tasks |
| `done_at` | Timestamp used to compute "next due" for terminal tasks |

If a task directory or its `status.yaml` is missing, treat that task as `not_started` with no period.

### Step 4 — Derive Class Status

Apply the derivation rules to **enabled tasks only**:

| Condition | Derived class status |
|-----------|---------------------|
| All enabled tasks are `not_started` | `not_started` |
| All enabled tasks are `done` or `abandoned` | `done` |
| Any other combination | `in_progress` |

Count terminal tasks (`done` + `abandoned`) vs. total enabled tasks for the progress fraction (e.g., "2/3 done").

### Step 5 — Compute Next Due Dates

For each enabled task that is `done` or `abandoned` and has a `done_at` timestamp:

1. Read the task's `anchor` and `period_format` from the manifest entry in `.class.yaml`.
2. If `period_format` is `adhoc`, do **not** show a "next due" date — adhoc tasks cannot auto-compute their next occurrence.
3. Otherwise, compute the next due date from `done_at` + `anchor` + `period_format`. For example, if `done_at` is in April, `period_format` is `monthly`, and `anchor` is `first_monday`, the next due date is the first Monday of May.

### Step 6 — Present the Dashboard

Format the output as a human-readable summary:

```
<ClassName> — <Period> — <DerivedStatus> (<terminal>/<total> done)
  <icon> <task-name>    <status>  [done_at date]  [next due: <anchor> (<date>)]
  <icon> <task-name>    <status>  [blocked: "<issue>"]
  ...
```

**Formatting rules:**

- **Header line:** Class name (title case from the directory name), period, derived status, and progress fraction.
- **Period in header:** Read from the task `status.yaml` files. If tasks have different periods (possible with mixed `period_format` values), show the most common period or list them individually per task.
- **Icons:** Use `✓` for terminal states (`done`, `abandoned`), `✗` for `blocked`, `·` for non-terminal active states (`not_started`, `in_progress`, `review_ready`).
- **Done/abandoned tasks:** If `done_at` is present, show the short date (e.g., "Apr 7"). If the task has a computable next due date, append `next due: <anchor> (<date>)`.
- **Blocked tasks:** Append `blocked: "<first issue from issues[]>"`.
- **Task order:** Follow the `order` field from the manifest.
- **Disabled tasks:** Do not show them at all.

---

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| Not in a class directory | Inform the user, stop. No output. |
| No enabled tasks in manifest | Show the class name with "No enabled tasks." |
| Task directory missing | Treat as `not_started` with no period. |
| `status.yaml` missing for a task | Treat as `not_started` with no period. |
| All tasks `not_started` | Class status is `not_started`, fraction shows "0/N done". |
| Mix of `done` and `abandoned` (all terminal) | Class status is `done`. Both count toward the terminal fraction. |
| Tasks have different periods | Show period per task line rather than a single header period. |
| `adhoc` task that is `done` | Show `done_at` date but no "next due" line. |
| `blocked` task with multiple issues | Show only the first issue inline. |
| Disabled task exists in manifest | Excluded entirely — not shown, not counted. |

---

## Key Constraints

- **Never persist class status.** The derived status exists only in the terminal output. No file is written, no YAML is updated.
- **No scripts.** `/status` reads `.class.yaml` and task `status.yaml` files directly. It does not invoke any Python script.
- **No side effects.** No file writes, no git operations, no status transitions. `/status` is safe to run at any time, in any state.
- **Disabled tasks are invisible.** Tasks with `enabled: false` in `.class.yaml` are excluded from the rollup, the count, and the display.

---

## Script Composition

| Script | When called | Purpose |
|--------|------------|---------|
| *(none)* | — | `/status` calls no scripts. It reads files directly from the filesystem. |
