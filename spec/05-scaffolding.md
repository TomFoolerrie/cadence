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

1. **Step 0 — Load context:** `load-context.py --level class` loads root AGENT.md and class AGENT.md so the agent understands what class it's onboarding into.
2. **Step 1 — Create task:** `init-task.py <name>` scaffolds the task folder with SKILL.md, learned.md, status.yaml templates, tools/, periods/, and requirements.txt.
3. **Step 2 — Interview:** Structured conversation with the user that extracts their knowledge — what the task produces, where data comes from, step-by-step procedure, validation rules, what goes wrong. Writes SKILL.md, seeds learned.md, builds tools in tools/.
4. **Step 3 — First period execution:** Executes the task for the current period to validate the knowledge transfer. Sets `in_progress` via `set-status.py`, calls `init-period.py` to scaffold the period, executes the procedure, produces a draft, and sets `review_ready`. The user then runs `/done` in the same conversation to complete the first period — capturing learnings, setting `done`, and archiving to Drive.
5. **Finalize:** Adds the task to `.class.yaml` manifest with `enabled: true`. Git commit covers scaffolding + dry run output. `/done` produces a separate commit for learnings and completion.

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

**Period string convention:** The period string refers to the **period being closed**, not the current calendar period. For example, period `2026-03` is worked on in April — the March books are closed during the April cycle. This is a domain convention that aligns with how accounting close processes work.

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
   e. Compute next_anchor_date from done_at + anchor + period_format:
      - monthly, anchor first_monday: first Monday of the month after current period
      - weekly, anchor monday: the next Monday after done_at
      - quarterly, anchor first_monday: first Monday of the quarter after current period
      - adhoc: skip (cannot auto-compute; requires manual /start)
   f. If today >= next_anchor_date:
      - Compute next period string from period_format (2026-03 → 2026-04, etc.)
      - Reset status.yaml: period → next_period, status → not_started,
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

**Example:** A monthly task with `anchor: first_monday` finishes March's period on April 7 (`done_at: "2026-04-07T14:30:00Z"`). The next period is April, and `first_monday` after April ends is May 5. `check-periods.py` runs daily. On May 5, it detects that today >= May 5, resets the task to `not_started` for period `2026-04`, and clears `done_at`.

**What `/status` shows.** `/status` reads the current state — if `check-periods.py` has reset tasks, they show as `not_started` and ready for `/start`. If the anchor hasn't arrived yet, they show as `done` with a "next due" date derived from `done_at` + anchor.

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
