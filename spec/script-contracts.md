# Script Contracts

Per-script interface specifications for implementers. Each contract defines: arguments, preconditions, stdout, file writes, exit codes, and idempotency.

For general failure behavior (exit codes, side-effect guarantees), see Section 6.7 in `05-scaffolding.md`.

---

## `load-context.py`

**Purpose:** Pure context assembly. Reads hierarchy files, prints them to stdout. No side effects.

**Arguments:**

| Argument | Required | Values | Default |
|----------|----------|--------|---------|
| `--level` | Yes | `root`, `class`, `task` | — |
| `--orchestrator` | No | Flag (no value) | Off |

**Preconditions:**

| Condition | Check | On failure |
|-----------|-------|------------|
| `.context-root` exists in an ancestor directory | Walk up from cwd | Exit 1: `"No .context-root found in any ancestor directory"` |
| `.context-root` is valid YAML with `engagement` key | Parse YAML | Exit 1: `"Invalid .context-root: missing engagement key"` |
| If `--level class`: cwd is inside a class directory | Parent has `.class.yaml` or cwd has `.class.yaml` | Exit 1: `"Not in a class directory"` |
| If `--level task`: cwd is inside a task directory | cwd has `SKILL.md` | Exit 1: `"Not in a task directory (no SKILL.md found)"` |
| If `--orchestrator` with `--level` other than `class` | Flag check | Exit 1: `"--orchestrator is only valid with --level class"` |

**Stdout:**

Prints each file with section headers. Order is always top-down (root first, task last).

```
── root/AGENT.md ──
<contents of root AGENT.md>

── class/AGENT.md ──
<contents of class AGENT.md>

── SKILL.md ──
<contents of SKILL.md>

── learned.md ──
<contents of learned.md>

── status.yaml ──
<contents of status.yaml>

── tools ──
task:   treasury/monthly-bank-fees/tools/
class:  treasury/tools/
global: .claude/tools/
```

The `── tools ──` section is only printed at `--level task`. It lists tool directories in resolution order (task > class > global). Directories that don't exist are omitted.

**With `--orchestrator` flag** (only valid with `--level class`):

Appends `.class.yaml` contents after class AGENT.md:

```
── .class.yaml ──
<contents of .class.yaml>
```

**Recovery hint** (only at `--level task` when status is `blocked`):

Appends after status.yaml output:

```
⚠ Recovery: This task is blocked. Review issues[] and decide — retry (resets to not_started) or investigate further.
```

**File writes:** None. Pure read.

**Idempotent:** Yes — stateless read.

**Exit codes:**

| Code | Condition |
|------|-----------|
| 0 | Context printed to stdout |
| 1 | Precondition failed (no `.context-root`, wrong directory level, invalid YAML) |

---

## `set-status.py`

**Purpose:** Agent/skill gateway for task-level `status.yaml`. Validates that the requested transition is legal before writing.

**Arguments:**

| Argument | Position | Required | Values |
|----------|----------|----------|--------|
| `status` | 1 | Yes | `not_started`, `in_progress`, `review_ready`, `blocked`, `done`, `abandoned` |
| `reason` | 2 | No | String — recorded in `issues[]` for `blocked` and `abandoned` |
| `--period` | Named | No | Period string — written to `period` field. Only valid on `not_started → in_progress` transition. |

**Preconditions:**

| Condition | Check | On failure |
|-----------|-------|------------|
| cwd contains `status.yaml` | File exists | Exit 1: `"No status.yaml in current directory"` |
| `status.yaml` is valid YAML | Parse | Exit 2: `"Corrupt status.yaml"` |
| Transition is legal | Check current → requested against transition table | Exit 1: `"Invalid transition: <current> → <requested>"` |
| `reason` provided for `blocked` and `abandoned` | Argument check | Exit 1: `"Reason required for blocked/abandoned status"` |
| If `--period` provided, transition must be `not_started → in_progress` | Transition + flag check | Exit 1: `"--period is only valid on not_started → in_progress"` |

**Valid transitions:**

```
not_started  → in_progress
in_progress  → in_progress    (no-op)
in_progress  → review_ready
in_progress  → blocked
review_ready → in_progress
review_ready → done
blocked      → not_started
blocked      → abandoned
```

All other transitions exit 1.

**File writes:** `status.yaml` in cwd.

| Transition | Fields modified |
|-----------|-----------------|
| → `in_progress` (from `not_started`) | `status: in_progress`. If `--period` provided: `period: "<period>"` |
| → `in_progress` (from `in_progress`) | No-op — file unchanged |
| → `in_progress` (from `review_ready`) | `status: in_progress`, `issues: []` |
| → `review_ready` | `status: review_ready`, `issues: []` |
| → `blocked` | `status: blocked`, `issues: ["<reason>"]` |
| → `done` | `status: done`, `issues: []`, `done_at: "<ISO 8601 timestamp>"` |
| → `abandoned` | `status: abandoned`, `issues: ["<reason>"]`, `done_at: "<ISO 8601 timestamp>"` |
| → `not_started` (from `blocked`) | `status: not_started`, `issues: []`, `done_at: null` |

`schema_version` is never modified by `set-status.py`. The `period` field is only written when `--period` is provided on a `not_started → in_progress` transition.

**Stdout:** None on success. Error message on failure.

**Idempotent:** Only for `in_progress → in_progress` (defined no-op). All other duplicate transitions are rejected (exit 1).

**Exit codes:**

| Code | Condition |
|------|-----------|
| 0 | Transition applied (or no-op for idempotent case) |
| 1 | Invalid transition, missing reason, missing status.yaml |
| 2 | Filesystem error (couldn't write file) |

---

## `init-class.py`

**Purpose:** Scaffolds a new class directory.

**Arguments:**

| Argument | Position | Required | Values |
|----------|----------|----------|--------|
| `name` | 1 | Yes | Kebab-case string (e.g., `treasury`, `order-to-cash`) |

**Preconditions:**

| Condition | Check | On failure |
|-----------|-------|------------|
| cwd contains `.context-root` | File exists | Exit 1: `"Not at engagement root (no .context-root)"` |
| Target directory does not exist | `<name>/` not present | Exit 1: `"Directory <name>/ already exists"` |

**File writes:**

```
<name>/
├── .class.yaml         ← schema_version: 1, name: <Name>, description: "", manifest: []
├── AGENT.md            ← template with ## What This Class Covers, ## Key Concepts
├── tools/              ← empty directory
└── requirements.txt    ← empty file
```

`<Name>` is the display name derived from the kebab-case argument (e.g., `order-to-cash` → `Order To Cash`).

**Stdout:** None on success. Error message on failure.

**Idempotent:** No — exits with error if directory exists.

**Exit codes:**

| Code | Condition |
|------|-----------|
| 0 | Class directory created |
| 1 | Not at engagement root, or directory already exists |
| 2 | Filesystem error |

---

## `init-task.py`

**Purpose:** Scaffolds a new task folder within a class.

**Arguments:**

| Argument | Position | Required | Values |
|----------|----------|----------|--------|
| `name` | 1 | Yes | Kebab-case string (e.g., `monthly-bank-fees`) |

**Preconditions:**

| Condition | Check | On failure |
|-----------|-------|------------|
| cwd contains `.class.yaml` | File exists | Exit 1: `"Not in a class directory (no .class.yaml)"` |
| Target directory does not exist | `<name>/` not present | Exit 1: `"Directory <name>/ already exists"` |

**File writes:**

```
<name>/
├── SKILL.md            ← template (frontmatter + Purpose, Data Sources, Procedure,
│                         Validation, Completion Criteria, Contacts sections).
│                         SKILL.md frontmatter `name` field and heading `# <name>`
│                         are interpolated from the argument.
├── learned.md          ← template (Review History table, Patterns, What Didn't Work,
│                         Open Questions sections)
├── status.yaml         ← schema_version: 1, period: "", status: not_started,
│                         issues: [], done_at: null
├── tools/              ← empty directory
├── periods/            ← empty directory
└── requirements.txt    ← empty file
```

**Stdout:** None on success. Error message on failure.

**Idempotent:** No — exits with error if directory exists.

**Exit codes:**

| Code | Condition |
|------|-----------|
| 0 | Task folder created |
| 1 | Not in a class directory, or directory already exists |
| 2 | Filesystem error |

---

## `init-period.py`

> **Note:** The `period` field in `status.yaml` is written by `set-status.py` (via `--period` on `not_started → in_progress`) or by `check-periods.py` on period reset — not by `init-period.py`.

**Purpose:** Scaffolds a period directory within a task.

**Arguments:**

| Argument | Position | Required | Values |
|----------|----------|----------|--------|
| `period` | 1 | Yes | Period string matching the task's `period_format` |

**Period string formats:**

| `period_format` | Pattern | Regex | Example |
|-----------------|---------|-------|---------|
| `monthly` | `YYYY-MM` | `^[0-9]{4}-(0[1-9]\|1[0-2])$` | `2026-03` |
| `weekly` | `YYYY-WNN` | `^[0-9]{4}-W(0[1-9]\|[1-4][0-9]\|5[0-3])$` | `2026-W12` |
| `quarterly` | `YYYY-QN` | `^[0-9]{4}-Q[1-4]$` | `2026-Q1` |
| `adhoc` | Any string | *(no validation)* | `year-end-true-up` |

**Preconditions:**

| Condition | Check | On failure |
|-----------|-------|------------|
| cwd contains `SKILL.md` | File exists | Exit 1: `"Not in a task directory (no SKILL.md)"` |
| `status.yaml` status is `in_progress` | Read and check | Exit 1: `"Status must be in_progress (current: <status>)"` |
| Period string matches `period_format` | Read `period_format` from parent `.class.yaml` manifest (default: `monthly`) | Exit 1: `"Period '<period>' does not match format <format>"` |
| Period directory does not exist | `periods/<period>/` not present | Exit 1: `"Period directory periods/<period>/ already exists"` |

**File writes:**

```
periods/<period>/
├── data/              ← empty directory (inputs)
├── workpapers/        ← empty directory (outputs)
└── review-notes/      ← empty directory (feedback)
```

Does **not** modify `status.yaml`. Status transitions are handled by skills via `set-status.py`.

**Stdout:** None on success. Error message on failure.

**Idempotent:** No — exits with error if period directory exists.

**Exit codes:**

| Code | Condition |
|------|-----------|
| 0 | Period directory created |
| 1 | Not in a task directory, wrong status, invalid period string, directory exists |
| 2 | Filesystem error |

---

## `install-deps.py`

**Purpose:** Installs Python dependencies from `requirements.txt` files, top-down through the hierarchy.

**Arguments:** None.

**Preconditions:**

| Condition | Check | On failure |
|-----------|-------|------------|
| `.context-root` exists in an ancestor directory | Walk up from cwd | Exit 1: `"No .context-root found in any ancestor directory"` |

**Behavior:**

1. Walk up from cwd to engagement root (via `.context-root`).
2. Determine the current level (root, class, or task) based on cwd position. Level detection: if cwd contains `SKILL.md` → task level; if cwd contains `.class.yaml` → class level; if cwd contains `.context-root` → root level.
3. Install `requirements.txt` files top-down, skipping any that don't exist:
   - Root: `pip install -r <root>/requirements.txt`
   - Class (if at class or task level): `pip install -r <class>/requirements.txt`
   - Task (if at task level): `pip install -r <task>/requirements.txt`

Runs on Cowork VM using system Python. Dependencies install globally within the VM.

**File writes:** None (pip installs packages to system Python, not to the hierarchy).

**Stdout:** pip output (installation progress, already-satisfied messages).

**Idempotent:** Yes — pip handles already-installed packages.

**Exit codes:**

| Code | Condition |
|------|-----------|
| 0 | All requirements installed (or already satisfied) |
| 1 | No `.context-root` found |
| 2 | pip install failed (network error, package not found, version conflict) |

---

## `check-periods.py`

**Purpose:** Scheduled infrastructure script. Walks the hierarchy and resets terminal tasks whose next anchor date has arrived. Runs as a cron job — no agent session.

**Arguments:** None.

**Preconditions:**

| Condition | Check | On failure |
|-----------|-------|------------|
| cwd contains `.context-root` | File exists | Exit 1: `"Not at engagement root (no .context-root)"` |

**Algorithm:**

```
For each class in engagement root (identified by immediate subdirectories containing `.class.yaml` — directories without `.class.yaml` such as `.git/`, `.claude/` are skipped):
  Read .class.yaml manifest
  For each enabled task:
    Read task/status.yaml
    Skip if status is not terminal (done or abandoned)
    Read done_at from status.yaml
    Read anchor and period_format from .class.yaml manifest
    Compute next_anchor_date:
      monthly  + first_monday  → first Monday of the month after current period
      monthly  + first_tuesday → first Tuesday of the month after current period
      ...
      weekly   + monday        → next Monday after done_at
      quarterly + first_monday → first Monday of the quarter after current period
      adhoc                    → skip (cannot auto-compute)
    If today >= next_anchor_date:
      Compute next_period_string (handle year rollover):
        monthly:   YYYY-MM incremented (2026-03 → 2026-04, 2026-12 → 2027-01)
        weekly:    YYYY-WNN incremented (2026-W12 → 2026-W13, 2026-W52 → 2027-W01)
        quarterly: YYYY-QN incremented (2026-Q1 → 2026-Q2, 2026-Q4 → 2027-Q1)
      Note: ISO week numbering — some years have W53. Implementers must use
      proper date arithmetic, not string manipulation.
      Write status.yaml:
        period: <next_period_string>
        status: not_started
        issues: []
        done_at: null
        (schema_version unchanged)
```

**File writes:** `status.yaml` for each reset task. Writes directly — does **not** go through `set-status.py` (operates outside agent sessions).

**Git:** If any tasks were reset, commits:
```
git add <class-dir>/
git commit -m "[check] <class-name>: reset N tasks for new period"
```
One commit per class that had resets. No commit if nothing changed.

**Stdout:** Summary of actions taken (for cron log):
```
treasury: reset monthly-bank-fees (2026-03 → 2026-04), reset zba-entries (2026-03 → 2026-04)
treasury: skipped bank-reconciliation (next anchor: 2026-05-07)
reporting: no resets needed
```

**Idempotent:** Yes — skips tasks already at `not_started`, skips tasks whose anchor hasn't arrived.

**Exit codes:**

| Code | Condition |
|------|-----------|
| 0 | Completed (resets applied or nothing to do) |
| 1 | Not at engagement root |
| 2 | Filesystem or YAML parse error |

---

## `archive-period.py`

**Purpose:** Uploads a completed period's work to Google Drive.

**Arguments:** None.

**Preconditions:**

| Condition | Check | On failure |
|-----------|-------|------------|
| cwd contains `status.yaml` | File exists | Exit 1: `"No status.yaml in current directory"` |
| Status is `done` | Read `status.yaml` | Exit 1: `"Status must be done (current: <status>)"` |
| `.context-root` exists in ancestor | Walk up | Exit 1: `"No .context-root found"` |
| Google Drive access configured | Check for credentials | Exit 2: `"Google Drive not configured"` |

**Behavior:**

1. Read `status.yaml` to get the current period.
2. Read `.context-root` to get the engagement name.
3. Determine class name and task name from the directory path.
4. Check if the target Drive folder already exists: `<Engagement>/<Class>/<Task>/<Period>/`
   - If exists: skip (idempotent), exit 0.
   - If not: create folder structure and upload.
5. Upload `periods/<period>/workpapers/` and `periods/<period>/data/` to Drive. Uploads all files recursively. Empty directories are not created on Drive.

**File writes:** None locally. Creates folders and uploads files on Google Drive.

**Stdout:** Upload progress or skip message:
```
Uploaded to Drive: Acme Corp/treasury/monthly-bank-fees/2026-03/ (4 files)
```
or:
```
Skipped: Acme Corp/treasury/monthly-bank-fees/2026-03/ already exists on Drive
```

**Idempotent:** Yes — checks for existing Drive folder before uploading.

**Exit codes:**

| Code | Condition |
|------|-----------|
| 0 | Upload complete or already uploaded |
| 1 | Wrong status, missing `.context-root` |
| 2 | Google Drive not configured, upload failed (network error, auth failure) |

**Failure behavior:** Archive failure is **non-blocking**. The calling skill (`/done`) reports the error to the user but does not change task status. The task remains `done`.
