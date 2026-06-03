# Script Contracts

Per-script interface specifications for implementers. Each contract defines: arguments, preconditions, stdout, file writes, exit codes, and idempotency.

For general failure behavior (exit codes, side-effect guarantees), see Section 6.7 in `04-scaffolding.md`.

---

## `init-engagement.py`

**Purpose:** Scaffolds a new engagement directory with git initialization.

**Arguments:**

| Argument | Position | Required | Values |
|----------|----------|----------|--------|
| `path` | 1 | Yes | Filesystem path for the new engagement directory |
| `--name` | Named | No | Engagement name (default: title-cased basename of path) |

**Preconditions:**

| Condition | Check | On failure |
|-----------|-------|------------|
| Target path does not exist | `Path(path).resolve()` does not exist | Exit 1: `"Path already exists: <resolved-path>"` |
| Parent directory is writable | Filesystem check (implicit via `mkdir`) | Exit 2: `"Filesystem error: ..."` |

**File writes:**

```
<path>/
├── .context-root       ← engagement: <name>, schema_version: 1
├── AGENTS.md            ← template with # <name>, ## Entity Details
├── .claude/
│   ├── tools/          ← empty directory
│   └── settings.json   ← write scope: allow Read and Write(./*)
├── .gitignore          ← ignores **/periods/*/data/, **/periods/*/workpapers/,
│                         .context-cache/, .DS_Store
└── requirements.txt    ← empty file
```

`<name>` is derived from the path basename by converting hyphens and underscores to spaces, then title-casing. Overridden by `--name` if provided.

**Git behavior:** After writing files, runs:
```
git init
git add .
git commit -m "[init] <name>: engagement created"
```

If `git` is not available or any git command fails, exits 2.

**Stdout:** None on success. Error message on failure (to stderr).

**Idempotent:** No — exits 1 if path already exists.

**Exit codes:**

| Code | Condition |
|------|-----------|
| 0 | Engagement directory created with initial git commit |
| 1 | Path already exists, or invalid arguments |
| 2 | Filesystem error, git not available, or git command failed |

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
── root/AGENTS.md ──
<contents of root AGENTS.md>

── class/AGENTS.md ──
<contents of class AGENTS.md>

── SKILL.md ──
<contents of SKILL.md>

── learned.md ──
<contents of learned.md>

── status.yaml ──
<contents of status.yaml>

── reference.md ──
<contents of reference.md (write restrictions, script docs)>

── tools ──
task:   treasury/monthly-bank-fees/tools/
class:  treasury/tools/
global: .claude/tools/
```

The `── tools ──` section is only printed at `--level task`. It lists tool directories in resolution order (task > class > global). Directories that don't exist are omitted.

**With `--orchestrator` flag** (only valid with `--level class`):

Appends `.class.yaml` contents after class AGENTS.md:

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

## `edit-class-yaml.py`

**Purpose:** Agent/skill gateway for `.class.yaml` mutations. Validates inputs before writing.

**Arguments:**

Subcommand-based interface:

| Subcommand | Positional Args | Named Args |
|------------|----------------|------------|
| `set-description` | `<description>` (required) | — |
| `add-task` | `<task>` (required) | `--order <N>` (required), `--enabled`/`--no-enabled` (default: true), `--period-format <fmt>` (default: `monthly`), `--anchor <anchor>` (default: `first_monday`) |
| `update-task` | `<task>` (required) | `--order <N>`, `--enabled`/`--no-enabled`, `--period-format <fmt>`, `--anchor <anchor>` (at least one required) |
| `remove-task` | `<task>` (required) | — |

**Valid enums:**

- `period-format`: `monthly`, `weekly`, `quarterly`, `adhoc`
- `anchor`: `first_monday`, `first_tuesday`, `first_wednesday`, `first_thursday`, `first_friday`, `first_saturday`, `first_sunday`, `last_monday`, `last_tuesday`, `last_wednesday`, `last_thursday`, `last_friday`, `last_saturday`, `last_sunday`, `monday`, `tuesday`, `wednesday`, `thursday`, `friday`, `saturday`, `sunday`

**Preconditions:**

| Condition | Check | On failure |
|-----------|-------|------------|
| cwd contains `.class.yaml` | File exists | Exit 1: `"No .class.yaml in current directory"` |
| `.class.yaml` is valid YAML with `manifest` list | Parse and check | Exit 2: `"Corrupt .class.yaml"` / `"Corrupt .class.yaml: missing manifest"` |
| `add-task`: task not already in manifest | Scan manifest | Exit 1: `"Task '<task>' already in manifest"` |
| `add-task`: task directory exists with `SKILL.md` | Directory and file check | Exit 1: `"Task directory '<task>' does not exist"` / `"Task directory '<task>' has no SKILL.md"` |
| `add-task`/`update-task`: `--order` must be positive | Value check | Exit 1: `"--order must be a positive integer"` |
| `add-task`/`update-task`: enum values must be valid | Value check | Exit 1: `"Invalid period-format: '<value>'"` / `"Invalid anchor: '<value>'"` |
| `update-task`/`remove-task`: task must be in manifest | Scan manifest | Exit 1: `"Task '<task>' not in manifest"` |
| `update-task`: at least one field to update | Argument check | Exit 1: `"No fields provided to update"` |

**File writes:** `.class.yaml` in cwd.

| Subcommand | Fields modified |
|------------|-----------------|
| `set-description` | `description` |
| `add-task` | Appends new entry to `manifest[]` with `task`, `order`, `enabled`, `period_format`, `anchor` |
| `update-task` | Updates specified fields on existing manifest entry |
| `remove-task` | Removes entry from `manifest[]` |

**Stdout:** None on success. Error message on failure (to stderr).

**Idempotent:** No — `add-task` rejects duplicates; `update-task` and `remove-task` require the task to exist.

**Exit codes:**

| Code | Condition |
|------|-----------|
| 0 | Mutation applied |
| 1 | Validation error (missing `.class.yaml`, task not found, invalid enum, duplicate task) |
| 2 | Corrupt `.class.yaml`, filesystem error |

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
├── AGENTS.md            ← template with ## What This Class Covers, ## Key Concepts
├── .claude/
│   └── settings.json   ← write scope: allow Write(./**), deny Write(../**) and Write(./.class.yaml)
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
├── reference.md        ← auto-generated quick-reference for plugin scripts and write restrictions
├── status.yaml         ← schema_version: 1, period: "", status: not_started,
│                         issues: [], done_at: null
├── .claude/
│   └── settings.json   ← write scope: allow Write(./**), deny Write(../**) and Write(./status.yaml)
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

## `init-venv.py`

**Purpose:** Creates a Python virtual environment at the engagement root. Idempotent — exits 0 if the venv already exists.

**Arguments:** None.

**Preconditions:**

| Condition | Check | On failure |
|-----------|-------|------------|
| `.context-root` exists in an ancestor directory | Walk up from cwd | Exit 1: `"No .context-root found in any ancestor directory"` |

**Behavior:**

1. Walk up from cwd to engagement root (via `.context-root`).
2. Check if `<root>/venv/bin/python` exists — if yes, exit 0 (idempotent).
3. Create venv: `python -m venv <root>/venv`.

Unix-only paths (`venv/bin/`). Windows would use `venv/Scripts/`.

**File writes:** Creates `<root>/venv/` directory with a standard Python virtual environment.

**Stdout:** None on success. Error message on failure (to stderr).

**Idempotent:** Yes — exits 0 if venv already exists.

**Exit codes:**

| Code | Condition |
|------|-----------|
| 0 | Venv created or already exists |
| 1 | No `.context-root` found |
| 2 | Venv creation failed |

---

## `install-deps.py`

**Purpose:** Installs Python dependencies from `requirements.txt` files into the engagement venv, top-down through the hierarchy.

**Arguments:** None.

**Preconditions:**

| Condition | Check | On failure |
|-----------|-------|------------|
| `.context-root` exists in an ancestor directory | Walk up from cwd | Exit 1: `"No .context-root found in any ancestor directory"` |
| Engagement venv exists | `<root>/venv/bin/pip` exists | Exit 2: `"No venv found at <root>/venv/ — run init-venv.py first"` |

**Behavior:**

1. Walk up from cwd to engagement root (via `.context-root`).
2. Resolve venv pip at `<root>/venv/bin/pip`. If not found, exit 2.
3. Determine the current level (root, class, or task) based on cwd position. Level detection: if cwd contains `SKILL.md` → task level; if cwd contains `.class.yaml` → class level; if cwd contains `.context-root` → root level.
4. Install `requirements.txt` files top-down using the venv pip, skipping any that don't exist:
   - Root: `<root>/venv/bin/pip install -r <root>/requirements.txt`
   - Class (if at class or task level): `<root>/venv/bin/pip install -r <class>/requirements.txt`
   - Task (if at task level): `<root>/venv/bin/pip install -r <task>/requirements.txt`

Dependencies install into the engagement venv, not system Python.

**File writes:** None (pip installs packages into the venv, not to the hierarchy).

**Stdout:** pip output (installation progress, already-satisfied messages).

**Idempotent:** Yes — pip handles already-installed packages.

**Exit codes:**

| Code | Condition |
|------|-----------|
| 0 | All requirements installed (or already satisfied) |
| 1 | No `.context-root` found |
| 2 | No venv found, or pip install failed (network error, package not found, version conflict) |

---

## `start-setup.py`

**Purpose:** Atomic setup phase for the `/start` skill. Wraps Steps 1–4 (set status, install deps, scaffold period, load context) into a single script call so the agent handles one exit code instead of four.

**Arguments:**

| Argument | Position | Required | Values |
|----------|----------|----------|--------|
| `--period` | Named | No | Period string — passed to `set-status.py` if `status.yaml` period is empty |

**Preconditions:**

| Condition | Check | On failure |
|-----------|-------|------------|
| cwd contains `status.yaml` | File exists | Exit 1: `"No status.yaml in current directory"` |
| `status.yaml` is valid YAML | Parse | Exit 1: `"Corrupt status.yaml"` |
| Period resolvable | Non-empty `period` in `status.yaml`, or `--period` provided | Exit 1: `"No period available — pass --period or ensure status.yaml has a period set"` |

**Behavior:**

Runs five scripts in sequence from the current (task) directory:

1. **`set-status.py in_progress [--period <period>]`** — Transitions to `in_progress`. Only passes `--period` when current status is `not_started` and the period field is empty. For `in_progress` (crash recovery) and `review_ready` (rejected draft), omits `--period`.
1.5. **`init-venv.py`** — Creates the engagement venv if it doesn't exist (idempotent).
2. **`install-deps.py`** — Installs `requirements.txt` files top-down into the engagement venv.
3. **`init-period.py <period>`** — Scaffolds the period directory. Skipped if `periods/<period>/` already exists (crash recovery, re-execution).
4. **`load-context.py --level task`** — Loads the full context chain.

**Period resolution priority:**

1. Non-empty `period` field in `status.yaml` (set by `check-periods.py` on reset, or from prior invocation)
2. `--period` argument (agent-computed or user-provided for `adhoc` tasks)
3. If both empty: exit 1. The wrapper is non-interactive — the agent must resolve the period before calling.

**On failure (steps 2–4):** Calls `set-status.py blocked "<error message>"` before exiting. If `set-status.py blocked` itself fails, prints a warning to stderr but still exits 2.

**On failure (step 1):** Exits with `set-status.py`'s return code directly. Does not attempt to set blocked — if the status transition failed, the task remains in its original state, which is recoverable.

**Stdout:** `load-context.py` output on success (the context payload for the agent). No output on failure.

**File writes:** `status.yaml` (via `set-status.py`), `periods/<period>/` (via `init-period.py`).

**Idempotent:** Yes — `set-status.py in_progress` is a no-op when already `in_progress`; `init-period.py` is skipped if the directory exists; `install-deps.py` handles already-installed packages; `load-context.py` is a pure read.

**Exit codes:**

| Code | Condition |
|------|-----------|
| 0 | Setup complete, context printed to stdout |
| 1 | Precondition error (no `status.yaml`, no period, invalid status transition) |
| 2 | Script failure (status set to blocked) |

---

## `onboard-setup.py`

**Purpose:** Setup phase for the `/onboard` skill (task-level). Wraps load-context and init-task into a single script call so the agent handles one exit code instead of two.

**Arguments:**

| Argument | Position | Required | Values |
|----------|----------|----------|--------|
| `task-name` | 1 | Yes | Kebab-case task name |

**Preconditions:**

| Condition | Check | On failure |
|-----------|-------|------------|
| cwd contains `.class.yaml` | File exists | Exit 1: `"Not in a class directory (no .class.yaml)"` |

**Behavior:**

Runs two scripts in sequence from the current (class) directory:

1. **`load-context.py --level class`** — Loads root AGENTS.md and class AGENTS.md.
2. **`init-task.py <task-name>`** — Scaffolds the task directory.

If `load-context.py` fails, `init-task.py` is not run (no partial state).

**File writes:** Task directory structure (via `init-task.py`): `<task-name>/SKILL.md`, `learned.md`, `reference.md`, `status.yaml`, `tools/`, `periods/`, `requirements.txt`, `.claude/settings.json`.

**Stdout:** `load-context.py` output on success (the context payload for the agent). No output on failure.

**Idempotent:** No — `init-task.py` exits with error if the task directory exists.

**Exit codes:**

| Code | Condition |
|------|-----------|
| 0 | Setup complete, context printed to stdout |
| 1 | Precondition error (no `.class.yaml`, task already exists, no args) |
| 2 | System error (load-context failure) |

---

## `onboard-register.py`

**Purpose:** Registration phase for the `/onboard` skill. Wraps init-venv, install-deps, and edit-class-yaml (add-task + optional set-description) into a single script call.

**Arguments:**

| Argument | Position | Required | Values |
|----------|----------|----------|--------|
| `task-name` | 1 | Yes | Kebab-case task name |
| `--order` | Named | Yes | Positive integer — execution order |
| `--period-format` | Named | No | `monthly`, `weekly`, `quarterly`, `adhoc` (default: `monthly`) |
| `--anchor` | Named | No | Anchor value (default: `first_monday`) |
| `--description` | Named | No | Class description text (optional) |

**Preconditions:**

| Condition | Check | On failure |
|-----------|-------|------------|
| cwd contains `.class.yaml` | File exists | Exit 1: `"Not in a class directory (no .class.yaml)"` |
| `<task-name>/` directory exists | Directory check | Exit 1: `"Task directory '<task-name>' does not exist"` |
| `<task-name>/SKILL.md` exists | File check | Exit 1: `"Task directory '<task-name>' has no SKILL.md"` |

**Behavior:**

Runs scripts in sequence from the current (class) directory:

1. **`init-venv.py`** — Creates the engagement venv if it doesn't exist (idempotent).
2. **`install-deps.py`** — Installs requirements.txt files top-down. Runs with `cwd` set to the task directory so it detects task level.
3. **`edit-class-yaml.py add-task <task-name> --order N --period-format fmt --anchor anchor`** — Adds the task to the manifest.
4. **`edit-class-yaml.py set-description "<description>"`** — Only if `--description` is provided. **Non-fatal on failure** — prints a warning to stderr but still exits 0.

**File writes:** `.class.yaml` (via `edit-class-yaml.py`). Venv directory (via `init-venv.py`). Package installations (via `install-deps.py`).

**Stdout:** None on success. Error/warning messages on stderr.

**Idempotent:** No — `edit-class-yaml.py add-task` rejects duplicates.

**Exit codes:**

| Code | Condition |
|------|-----------|
| 0 | Task registered (description failure is non-fatal) |
| 1 | Precondition error (no `.class.yaml`, task dir missing, no SKILL.md, invalid manifest args) |
| 2 | System error (venv, install, or manifest failure) |

---

## `check-periods.py`

**Purpose:** Scheduled infrastructure script. Walks the hierarchy and resets terminal tasks whose next anchor date has arrived. Runs as a cron job — no agent session.

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `--as-of <YYYY-MM-DD>` | No | Override today's date. Used by the test suite to simulate future dates without waiting for real time to pass. |

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
    Compute next_per = next_period_string(current_period) (handle year rollover):
      monthly:   YYYY-MM incremented (2026-03 → 2026-04, 2026-12 → 2027-01)
      weekly:    YYYY-WNN incremented (2026-W12 → 2026-W13, 2026-W52 → 2027-W01)
      quarterly: YYYY-QN incremented (2026-Q1 → 2026-Q2, 2026-Q4 → 2027-Q1)
      Note: ISO week numbering — some years have W53. Implementers must use
      proper date arithmetic, not string manipulation.
    Compute anchor_date (one-ahead logic):
      monthly  + first_<weekday>  → first <weekday> of the NEXT period's month
      monthly  + last_<weekday>   → last <weekday> of the NEXT period's month
      quarterly + first_<weekday> → first <weekday> of first month of NEXT quarter
      quarterly + last_<weekday>  → last <weekday> of final month of NEXT quarter
      weekly   + <weekday>        → that weekday of the next ISO week
      adhoc                       → skip (cannot auto-compute)
    Late-completion guard:
      If anchor_date <= done_at (task finished after the anchor already passed):
        Advance next_per by one more period
        Recompute anchor_date for the new next_per
    If today >= anchor_date:
      Write status.yaml:
        period: <next_per>
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
