# Scaffolding

The hierarchy is created once and then managed through conversation. The plugin provides the initial structure.

## 6.1 What the Plugin Ships

```
accounting-plugin/
├── .claude-plugin/
│   └── plugin.json
├── engagement-template/            ← copied to user's folder
│   ├── .context-root               ← root marker (YAML: engagement name + schema_version)
│   ├── AGENT.md                    ← root context template (user fills in)
│   ├── .claude/
│   │   └── tools/                  ← global shared tools
│   ├── .gitignore
│   └── requirements.txt
├── scripts/
│   ├── load-context.py             ← pure context assembly (no side effects)
│   ├── install-deps.py             ← installs requirements.txt top-down
│   ├── set-status.py               ← agent/skill gateway for status.yaml (validates transitions)
│   ├── init-class.py               ← scaffolds a new class directory
│   ├── init-task.py                ← scaffolds a new task folder
│   ├── init-period.py              ← scaffolds a period within a task
│   ├── check-periods.py            ← scheduled: resets tasks whose next anchor has arrived
│   └── archive-period.py           ← uploads period to Google Drive on /done
└── skills/
    ├── onboard/SKILL.md            ← knowledge transfer
    ├── start/SKILL.md              ← period execution
    ├── done/SKILL.md               ← post-review learning
    └── status/SKILL.md             ← class progress dashboard
```

### `${CLAUDE_PLUGIN_ROOT}`

Cowork sets `${CLAUDE_PLUGIN_ROOT}` to the absolute path of the plugin's installation directory at runtime. All script invocations in skill files use this prefix (e.g., `python ${CLAUDE_PLUGIN_ROOT}/scripts/set-status.py`). The variable is replaced on each plugin update.

## 6.2 Setup Flow

```
User:    Installs plugin, opens a folder in Cowork
Agent:   Copies engagement-template/ into the folder
Agent:   Writes .context-root YAML (engagement name + schema_version)
Agent:   git init, initial commit
Agent:   "Fill in AGENT.md with your entity details and
          I'll take it from there."

User:    Fills in AGENT.md (entity name, fiscal year, etc.)
Agent:   git commit -m "Configure engagement context"

User:    "I want to set up treasury work"
Agent:   Runs /onboard from root level → creates class
Agent:   Runs init-class.py treasury
Agent:   Interviews user → writes AGENT.md (minimal: what this class is, key concepts)
Agent:   git commit -m "Onboard class: treasury"

User:    "I want to teach you how we do monthly bank fees"
Agent:   Runs /onboard from treasury/ → creates task
Agent:   Runs init-task.py monthly-bank-fees
Agent:   Interviews user → writes SKILL.md, learned.md, tools
Agent:   Executes first period dry run → sets review_ready
Agent:   Adds task to treasury/.class.yaml manifest
Agent:   git commit -m "[onboard] monthly-bank-fees: SKILL.md, tools, dry run ready for review"
User:    Reviews dry run output
User:    /done → captures learnings, sets done, archives to Drive
Agent:   git commit -m "[done] monthly-bank-fees 2026-03: first period complete"
```

## 6.3 Adding Classes

New classes are added via `/onboard` from the root level. The `init-class.py` script scaffolds the class directory structure.

**Usage:** Run from the engagement root (must contain `.context-root`).

```bash
init-class.py <name>
# name: folder name in kebab-case (e.g., treasury, reporting)
```

**What it creates:**

```
<name>/
├── .class.yaml         ← orchestration manifest (empty, no tasks yet)
├── AGENT.md            ← class context template (minimal)
├── tools/              ← empty, for class-level shared tools
└── requirements.txt    ← empty, for class-level Python dependencies
```

**`.class.yaml` initial template:**

```yaml
schema_version: 1
name: <Name>
description: ""

manifest: []
```

**`AGENT.md` template** (name is interpolated from the argument):

```markdown
# <Name>

## What This Class Covers

<!-- One or two sentences: what group of work does this class represent? -->

## Key Concepts

<!-- Domain terms or conventions that task agents need to know. Keep it short. -->
```

**Validation:** The script checks that `.context-root` exists in the current directory (confirms you're at the engagement root) and that the target directory doesn't already exist. It exits with an error if either check fails.

AGENT.md is **minimal by design**. It provides just enough context for task agents to understand what class they're operating in — not a comprehensive domain manual. It grows organically as tasks are onboarded and patterns emerge, but should stay concise. If AGENT.md is getting long, the information probably belongs in a task's SKILL.md instead.

## 6.4 Adding Tasks

New tasks are added via `/onboard` within a class directory. The `init-task.py` script scaffolds the standard structure.

**Usage:** Run from a class directory (must contain `.class.yaml`).

```bash
init-task.py <name>
# name: folder name in kebab-case (e.g., monthly-bank-fees)
```

**What it creates:**

```
<name>/
├── SKILL.md           ← template (see below)
├── learned.md         ← template (see below)
├── status.yaml        ← initialized (see below)
├── tools/             ← empty, for task-specific scripts
├── periods/           ← empty, populated by init-period.py
└── requirements.txt   ← empty, for task-specific Python dependencies
```

**`status.yaml` initial template:**

```yaml
schema_version: 1
period: ""
status: not_started
issues: []
done_at: null
```

**`SKILL.md` template** (name is interpolated from the argument):

```markdown
---
name: <name>
description: >
  TODO — describe what this folder produces.
version: 0.1.0
---

# <name>

## Purpose

<!-- What does this produce? Which accounts does it touch? -->

## Data Sources

<!-- Where does the data come from? Format? What if it's missing? -->

## Procedure

<!-- Step-by-step processing logic. Reference shared tools by path. -->

## Validation

<!-- How to verify the output is correct. -->

## Contacts

<!-- Who to ask when something goes wrong. -->

## Completion Criteria

<!-- What does a completed task look like? What artifacts must exist? -->
```

**`learned.md` template:**

```markdown
# Learned Patterns

## Review History

| Period | Outcome | Key Number | Note |
|--------|---------|------------|------|

## Patterns

<!-- Entries use structured delta format:
- **Pattern description**
  Confirmed: N | Contradicted: N | First seen: YYYY-MM
  Used for: how this pattern informs execution
-->

## What Didn't Work

<!-- Entries use structured delta format:
- **What was attempted**
  Confirmed: N | Contradicted: N | First seen: YYYY-MM
  Result: what happened | Fix: how it was resolved
-->

## Open Questions

```

**Validation:** The script checks that `.class.yaml` exists in the current directory (confirms you're in a class) and that the target folder doesn't already exist. It exits with an error if either check fails.

The `/onboard` skill then does the real work: it walks the human preparer through a structured conversation that extracts their knowledge — what the task produces, where data comes from, what the step-by-step procedure is, what validation looks like, what goes wrong. It writes that knowledge into SKILL.md, builds tools, validates everything against real data (dry run), and adds the task to `.class.yaml`'s manifest. This is the bridge between human expertise and agent-executable procedure.

**`/onboard` is level-aware.** It detects whether it's being run from the root or from a class directory and executes the appropriate flow.

**Class-level onboarding** (from root — creates a new class):

1. **Step 0 — Load context:** `load-context.py --level root` loads engagement context.
2. **Step 1 — Create class:** `init-class.py <name>` scaffolds the class directory.
3. **Step 2 — Interview:** Brief conversation with the user about what this class of work covers, key domain concepts, and conventions. Writes AGENT.md (kept minimal — just enough for task agents to understand their broader context).
4. **Finalize:** Git commit.

The user can then navigate into the new class and `/onboard` a task.

**Task-level onboarding** (from class — creates a new task):

1. **Step 1 — Setup:** `onboard-setup.py <name>` loads class context (`load-context.py --level class`) and scaffolds the task folder (`init-task.py <name>`) in a single call. Returns context to stdout.
2. **Step 2 — Interview:** Structured conversation with the user that extracts their knowledge — what the task produces, where data comes from, step-by-step procedure, validation rules, what goes wrong. Writes SKILL.md, seeds learned.md, builds tools in tools/.
3. **Step 3 — Register:** `onboard-register.py <name> --order N --period-format fmt --anchor anchor [--description "text"]` installs dependencies (`init-venv.py` + `install-deps.py`), adds the task to `.class.yaml` manifest (`edit-class-yaml.py add-task`), and optionally sets the class description. This must happen before the first period execution because `init-period.py` needs the task's `period_format` from the manifest.
4. **Step 4 — First period execution:** Runs `start-setup.py --period "<period>"` from the task directory to set `in_progress`, install deps, scaffold the period, and load context. Then executes the procedure, produces a draft, and sets `review_ready`. The user then runs `/done` in the same conversation to complete the first period — capturing learnings, setting `done`, and archiving to Drive.
5. **Finalize:** Git commit covers scaffolding + first period output. `/done` produces a separate commit for learnings and completion.

`/start` is only used from the **next period onward**. The first period is executed as part of onboarding to validate that the task works end-to-end with real data.

## 6.5 Adding Periods

Each execution cycle gets a new period directory within a task.

**Usage:** Run from a task directory (must contain SKILL.md).

```bash
init-period.py <period>
# period: YYYY-MM format (e.g., 2026-03)
```

**What it creates:**

```
periods/<period>/
├── data/              ← inputs (bank statements, exports, etc.)
├── workpapers/        ← outputs (JE drafts, reconciliations, etc.)
└── review-notes/      ← feedback from human review
```

`init-period.py` is a **pure scaffolding script** — it creates the period directory structure. It does not modify `status.yaml`. Status transitions are handled by `/start` via `set-status.py`.

**Guard:** Before creating a new period, the script reads `status.yaml` and checks that the current status is `in_progress`. `/start` sets `in_progress` before calling `init-period.py`. This ensures the task is actively being worked before scaffolding a new period.

**Period string convention:** The period string is a label for the work being done in this cycle. For example, period `2026-03` labels March's work. The anchor system (see Section 6.6) determines when the next cycle begins.

**Period naming formats:** Period format is configurable per task via the `period_format` field in `.class.yaml` (see `02-architecture.md` Section 3, Manifest fields). The default is `monthly`. These formats define the directory names used under each task's `periods/` folder.

| Format | Directory Pattern | Regex (validated by `init-period.py`) | Example Directory |
|--------|-------------------|---------------------------------------|-------------------|
| `monthly` | `YYYY-MM` | <code>^[0-9]{4}-(0[1-9]&#124;1[0-2])$</code> | `periods/2026-03/` |
| `weekly` | `YYYY-WNN` | <code>^[0-9]{4}-W(0[1-9]&#124;[1-4][0-9]&#124;5[0-3])$</code> | `periods/2026-W12/` |
| `quarterly` | `YYYY-QN` | `^[0-9]{4}-Q[1-4]$` | `periods/2026-Q1/` |
| `adhoc` | any string | *(no validation)* | `periods/year-end-true-up/` |

`init-period.py` reads the task's `period_format` from the parent class's `.class.yaml` manifest and validates accordingly. If the task is not found in the manifest or `period_format` is omitted, it defaults to `monthly`.

- `status.yaml` stores the current period string in whatever format the task uses.
- The `/start` skill creates the period directory via `init-period.py` if it doesn't exist.
- Within a single class, different tasks can use different period formats (e.g., monthly JEs alongside a quarterly reconciliation).

**Validation:** Checks that SKILL.md exists in cwd. Validates the period string against the task's `period_format` from the parent class's `.class.yaml` (defaults to `monthly` / YYYY-MM if not found). Exits with an error if the period directory already exists.

## 6.6 Automatic Period Reset: `check-periods.py`

Tasks reset automatically when their next anchor date arrives. No human trigger needed. `check-periods.py` is a **scheduled infrastructure script** that walks the hierarchy and resets tasks that are due for their next period. It writes `status.yaml` **directly** (not through `set-status.py`) because it operates outside of agent sessions as a cron job.

**Usage:** Run from the engagement root (must contain `.context-root`). Designed to run on a schedule (e.g., cron at 6am, launchd, or a scheduled task) — early morning when no agent sessions are active.

```bash
check-periods.py
```

**Algorithm:**

```
1. Walk all classes in the engagement root (immediate subdirectories containing `.class.yaml`)
2. For each enabled task in each class's .class.yaml manifest:
   a. Read task's status.yaml
   b. Skip if status is not terminal (done or abandoned)
   c. Read done_at timestamp from status.yaml
   d. Read task's anchor and period_format from .class.yaml
   e. Compute next_per = next_period_string(current_period)
   f. Compute anchor_date (one-ahead logic):
      - monthly + first_<weekday>: first <weekday> of the NEXT period's month
      - monthly + last_<weekday>: last <weekday> of the NEXT period's month
      - quarterly + first_<weekday>: first <weekday> of the first month of the NEXT quarter
      - quarterly + last_<weekday>: last <weekday> of the final month of the NEXT quarter
      - weekly + <weekday>: that weekday of the next ISO week
      - adhoc: skip (cannot auto-compute; requires manual /start)
   g. Late-completion guard: if anchor_date <= done_at, the task finished
      after the anchor already passed. Push both next_per and anchor_date
      forward by one more cycle.
   h. If today >= anchor_date:
      - Reset status.yaml: period → next_per, status → not_started,
        issues → [], done_at → null
3. Git commit per class (if any resets occurred in that class):
      "[check] class-name: reset N tasks for new period"
      One commit per class that had resets. No commit if nothing changed.
```

**Key behaviors:**

- **Per-task evaluation.** Each task is evaluated independently based on its own `done_at`, `anchor`, and `period_format`. A weekly task resets weekly; a monthly task resets monthly. They don't block each other.
- **Idempotent.** Running `check-periods.py` multiple times is safe — a task that's already `not_started` is skipped. A task whose anchor hasn't arrived yet is skipped.
- **`adhoc` tasks are excluded.** Tasks with `period_format: adhoc` cannot auto-compute their next period. In MVP, adhoc tasks are single-use — once terminal, they stay there. See Open Questions, item 12.
- **`done_at` is the clock.** The timestamp is set automatically by `set-status.py` when a task reaches `done` or `abandoned`. This is how the system knows when the task finished and when the next anchor falls.

**Scheduling:** In MVP, `check-periods.py` runs as a cron job (e.g., daily at 6am). It's a lightweight script — reads YAML files, checks dates, writes resets. In future state, the orchestrator can call it directly or the scheduling can be more sophisticated.

**Year boundary handling:** Period string increment must handle year rollover: `2026-12` → `2027-01` (monthly), `2026-Q4` → `2027-Q1` (quarterly), `2026-W52` → `2027-W01` (weekly). Implementers must account for ISO week numbering edge cases (some years have W53).

**Example:** A monthly task with `anchor: first_monday` finishes March's period on April 3 (`done_at: "2026-04-03T14:30:00Z"`). The next period is April. The one-ahead anchor is the first Monday of April = April 6. Since done_at (April 3) is before the anchor (April 6), no late-completion guard fires. `check-periods.py` runs daily. On April 6, it detects that today >= April 6, resets the task to `not_started` for period `2026-04`, and clears `done_at`.

**Late-completion example:** Same task, but finished on April 20 (`done_at: "2026-04-20T14:30:00Z"`). The anchor (April 6) has already passed by done_at, so the late-completion guard fires: next_per advances from `2026-04` to `2026-05`, and the anchor advances to the first Monday of May = May 4. On May 4, the task resets to `not_started` for period `2026-05`.

**What `/status` shows.** `/status` reads the current state — if `check-periods.py` has reset tasks, they show as `not_started` and ready for `/start`. If the anchor hasn't arrived yet, they show as `done` with a "next due" date derived from `done_at` + anchor.

### Anchor Values

The `anchor` field in `.class.yaml` defines **when** a task should be triggered within its period cycle. It is separate from `period_format` (which defines how to **name** the period folder). `anchor` is set during `/onboard` and lives on each task in the manifest.

**Default:** `first_monday` — the first Monday after the period ends. Omitting `anchor` uses this default.

| Pattern | Meaning | Use case |
|---------|---------|----------|
| `first_monday` .. `first_sunday` | First occurrence of that weekday in the next period's month/quarter | Monthly/quarterly tasks (e.g., close starts first Monday of the new month) |
| `last_monday` .. `last_sunday` | Last occurrence of that weekday in the next period's month/quarter | Pre-close tasks (e.g., preliminary reconciliation last Friday of the month) |
| `monday` .. `sunday` | That weekday of the next ISO week | Weekly tasks (e.g., cash position every Monday) |

**MVP behavior:** `anchor` is **advisory**. The human reads it as a scheduling reminder when `/status` displays the class dashboard. The human still invokes `/start` manually — the anchor tells them *when* they should.

**Future behavior:** The orchestrator reads `anchor` to compute the actual trigger date for automated execution. For `first_monday` with a monthly period ending 2026-03-31, the trigger date is 2026-04-07 (first Monday in April). Holiday handling is a future concern — MVP relies on human judgment.

**`/onboard` sets the anchor.** During the task onboarding interview, the agent asks: "When does this task typically run?" and maps the answer to an anchor value. If the user says "first Monday after month-end" or doesn't have a strong preference, it stays at the default.

**Example `/status` output with anchors:**
```
Treasury — March 2026 — Done (3/3 done)
  ✓ monthly-bank-fees    done  Apr 7    next due: first_monday (May 5)
  ✓ zba-entries          done  Apr 7    next due: first_monday (May 5)
  ✓ bank-reconciliation  done  Apr 9    next due: first_wednesday (May 7)
```

When `check-periods.py` resets tasks (e.g., on May 5):
```
Treasury — April 2026 — In Progress (0/3 done)
  · monthly-bank-fees    not_started   anchor: first_monday
  · zba-entries          not_started   anchor: first_monday
  ✓ bank-reconciliation  done          next due: first_wednesday (May 7)
```

## 6.7 Script Failure Contracts

All scripts follow consistent failure behavior:

**Exit codes:**

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Validation error (bad input, invalid transition, missing prerequisite) |
| 2 | System error (couldn't write file, filesystem issue) |

**Side-effect guarantee:** If a script exits non-zero, it must not have modified any files. Scripts write to a temporary location and move on success, or validate all preconditions before writing.

**Idempotency:** All scripts are safe to re-run:

| Script | Idempotent | Notes |
|--------|-----------|-------|
| `load-context.py` | Yes | Pure read — no side effects |
| `install-deps.py` | Yes | pip handles already-installed packages |
| `set-status.py` | Yes | `in_progress → in_progress` is a defined no-op; other duplicate transitions are rejected (exit 1) |
| `init-class.py` | No | Exits with error if directory exists |
| `init-task.py` | No | Exits with error if directory exists |
| `init-period.py` | No | Exits with error if period directory exists |
| `check-periods.py` | Yes | Skips tasks already at `not_started` |
| `archive-period.py` | Yes | Skips if already uploaded (checks Drive for existing folder) |

**Known limitation:** `requirements.txt` files exist at three levels (root, class, task). `install-deps.py` installs top-down (root → class → task). If version conflicts exist between levels, pip's resolution determines the outcome (last install wins). This is a known limitation — in practice, task-level requirements are for niche packages that don't conflict with global ones.

## 6.8 Git Versioning

The hierarchy is initialized as a git repository during scaffolding. The agent commits every structural change automatically — adding tasks, updating procedures, capturing learnings. This gives the hierarchy full version history with zero effort from the user.

### Initialization

During scaffolding, the agent runs:

```
git init
git add .context-root AGENT.md .claude/ .gitignore requirements.txt
git add treasury/ reporting/ ...
git commit -m "Initial scaffold by accounting plugin"
```

### .gitignore

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

### Automatic Commits

**Skills own commits.** Each skill (`/onboard`, `/start`, `/done`) includes a git commit as its final step. Scripts (`set-status.py`, `init-period.py`, `load-context.py`, `archive-period.py`, etc.) have no git side effects — they modify files, and the calling skill commits the aggregate changes when it completes. This is what makes commits **atomic per skill invocation** — each `/onboard`, `/start`, and `/done` produces exactly one commit, whether the outcome is success or error.

`/done` also calls `archive-period.py` to upload workpapers and data to Google Drive after committing.

### Failure Modes

Two distinct failure modes:

- **Blocked (committed).** The skill ran to completion but the outcome was blocked — e.g., an API returned 401, a validation check failed, a data source was missing. This is a valid, recorded status. The skill sets `status: blocked` in `status.yaml` via `set-status.py` and commits. The commit message includes the reason (see examples below). Blocked states are part of the audit trail.
- **Partial failure (not committed).** The skill crashed or was interrupted mid-execution — e.g., Claude's session dropped, a script threw an unhandled exception, the user aborted. The skill never reached its commit step, so nothing is committed. The working tree may contain intermediate state; the human can inspect and either retry or reset via `git checkout .`.

### Branch Strategy

**Branch strategy (MVP):** Everything on `main`. Single user, local only — no branching needed. Future multi-user state may introduce per-class or per-period branches.

### Commit Message Format

**Format:** `[skill] task-name period: summary`

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

### What This Enables

- **Undo.** "Undo that last change" -> `git revert HEAD`
- **History.** "What did we change last week?" -> `git log --since="1 week ago"`
- **Diff.** "How has this SKILL.md evolved?" -> `git log -p -- treasury/monthly-bank-fees/SKILL.md`
- **Audit trail.** Every execution, every review, every learning is a commit. Full traceability.

### Developer Access

Developers can interact with the git repo directly:

```bash
cd ~/Documents/Accounting
git log --oneline
git diff HEAD~1
```

The agent treats the git repo as its own — it doesn't expect manual commits. But if a developer hand-edits files, the agent picks up their changes on next session.
