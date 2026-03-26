# Skill: `/onboard`

## Frontmatter

```yaml
---
name: onboard
description: >
  Guides knowledge transfer from a human preparer to Claude.
  Level-aware: from root creates a class, from a class creates
  a task and validates it against real data.
version: 1.0.0
---
```

## Purpose

Transfer knowledge of recurring work from a human preparer to Claude. `/onboard` is **level-aware** — it detects whether it's being run from the engagement root or from a class directory and executes the appropriate flow.

- **From root:** Creates a new class (brief interview → AGENT.md).
- **From class:** Creates a new task (deep interview → SKILL.md, learned.md, tools, first-period execution).
- **From task directory (or other):** Not supported. If the current directory contains neither `.context-root` nor `.class.yaml`, tell the user: *"Run `/onboard` from the engagement root to create a class, or from a class directory to create a task."* Stop.

The goal of task-level onboarding is to produce a self-contained work folder that a **fresh Claude instance** can execute next period with zero handholding.

---

## Class-Level Onboarding (from root)

Run when the user wants to create a new class of work (e.g., "I want to set up treasury work").

**Detection:** Current directory contains `.context-root`.

### Procedure

#### Step 0 — Load Context

```bash
load-context.py --level root
```

Loads the engagement's root `AGENT.md` so the agent understands the entity context.

#### Step 1 — Name the Class

Ask the user: *"What class of work is this? Give me a short name."*

Map the answer to a kebab-case folder name (e.g., "Treasury" → `treasury`, "Order to Cash" → `order-to-cash`).

#### Step 2 — Scaffold

```bash
init-class.py <name>
```

Creates the class directory with `.class.yaml` (empty manifest), `AGENT.md` (template), `tools/`, and `requirements.txt`.

#### Step 3 — Interview

Brief conversation to populate `AGENT.md`. Ask:

1. **What does this class cover?** — One or two sentences. What group of work does it represent?
2. **Key domain concepts?** — Terms, conventions, or rules that task agents working in this class need to know. Keep it short — AGENT.md is loaded into every task session in this class.
3. **Any shared data sources or systems?** — Systems that multiple tasks in this class will access (e.g., "Chase portal for all treasury work").

Write the answers into `AGENT.md`. Keep it **minimal by design** — just enough for task agents to understand their broader context. If it's getting long, the information probably belongs in a task's SKILL.md.

#### Step 4 — Finalize

```bash
git add <class-directory>/
git commit -m "[onboard] <class-name>: class created"
```

Tell the user: *"Class created. Navigate into `<name>/` and run `/onboard` again to add a task."*

---

## Task-Level Onboarding (from class)

Run when the user wants to teach Claude how to do a specific recurring task.

**Detection:** Current directory contains `.class.yaml`.

### Procedure

#### Step 0 — Load Context

```bash
load-context.py --level class
```

Loads root `AGENT.md` and class `AGENT.md` so the agent understands the engagement and class context.

#### Step 1 — Name the Task

Ask the user: *"What task is this? Give me a short name."*

Map to kebab-case (e.g., "Monthly bank fees" → `monthly-bank-fees`).

#### Step 2 — Scaffold

```bash
init-task.py <name>
```

Creates the task folder with SKILL.md (template), learned.md (template), status.yaml, tools/, periods/, and requirements.txt.

#### Step 3 — Interview

This is the core of onboarding. Extract everything the preparer knows — including the things they don't think to mention because they're "obvious." Ask follow-up questions. Don't rush.

**What to cover:**

| Topic | Questions | Writes to |
|-------|-----------|-----------|
| **Purpose** | What does this produce? Which accounts does it touch? Is this a journal entry or a workpaper/reconciliation? | SKILL.md `## Purpose` |
| **Data sources** | Where does the data come from? What format (CSV, PDF, portal export)? What do you do if it's missing or late? | SKILL.md `## Data Sources` |
| **Procedure** | Walk me through it step by step. What do you do first? Then what? What tools or formulas do you use? | SKILL.md `## Procedure` |
| **Validation** | How do you know the output is correct? What do you check? Expected ranges, tie-outs, cross-references? | SKILL.md `## Validation` |
| **Completion criteria** | What artifacts must exist when this task is done? What does "ready for review" look like? | SKILL.md `## Completion Criteria` |
| **Contacts** | Who do you call when something goes wrong? Who owns the data source? | SKILL.md `## Contacts` |
| **What goes wrong** | What breaks? What are the common surprises? What did you learn the hard way? | learned.md `## Patterns`, `## What Didn't Work` |
| **Expected ranges** | Typical dollar amounts, line counts, variance thresholds? | learned.md `## Patterns` |
| **Dependencies** | Does this depend on another task finishing first? Does anything depend on this? | SKILL.md `## Purpose` (note dependencies) |
| **Scheduling** | When does this task typically run? First Monday after month-end? Last Friday? Weekly? | `.class.yaml` manifest `anchor` and `period_format` |

**Interview principles:**

- **Go deep on procedure.** This is the section that makes or breaks execution. If the preparer says "I just reconcile it," ask *how* — what are the columns, what's the matching logic, what's the tolerance.
- **Ask for examples.** "Can you show me a recent period's output?" is more valuable than abstract description.
- **Capture the implicit.** Preparers skip steps they consider obvious. Ask: "Is there anything you do automatically that you haven't mentioned?" and "What would a new hire get wrong the first time?"
- **Be token-conscious.** SKILL.md and learned.md are loaded into context every period. Keep them focused. Don't duplicate information between sections.

#### Step 4 — Check Existing Tools

Before writing new tools, check what exists:

```
.claude/tools/          ← global tools (JE formatter, PDF parser)
{class}/tools/          ← class-level tools (e.g., Chase statement parser)
```

Reuse what you can. If multiple tasks would parse the same source format, that parser belongs at the class level, not the task level. Only build task-level tools for logic unique to this task.

#### Step 5 — Build

Write the files based on the interview:

- **SKILL.md** — Populate all sections from the template. The `## Procedure` section must reference tools by path and use the standard period directories: source files go in `periods/{period}/data/`, outputs go in `periods/{period}/workpapers/`. Do not use custom directory names.
- **learned.md** — Seed with what the preparer shared about quirks, expected ranges, and known failure modes. Use the four-section structure (Review History, Patterns, What Didn't Work, Open Questions).
- **tools/** — Build the Python scripts that do the transformation and validation work. Ensure all tool output paths default to the standard period subdirectories.
- **requirements.txt** — Add task-specific Python dependencies. Check the class-level and root-level `requirements.txt` first — don't duplicate.

#### Step 6 — Install Dependencies

```bash
install-deps.py
```

Installs requirements.txt files top-down (root → class → task).

#### Step 7 — First Period Execution (Dry Run)

The first period is executed as part of onboarding to validate the knowledge transfer. This is the proof that the folder works.

The period string is the **period being closed** (e.g., if it's April, use `2026-03` for March close). Ask the user which period to use for the dry run.

```bash
set-status.py in_progress --period "<period>"
init-period.py <period>
```

**Execute the procedure:**

1. Ask the user to provide the source data for the dry run period (via Cowork file attachment). Place files in `periods/{period}/data/`.
2. Follow SKILL.md `## Procedure` exactly as a fresh agent would — this is the test.
3. Run the tools, produce the output, write results to `periods/{period}/workpapers/`.
4. Compare your output to what was actually produced for that period. The user should have the original output to compare against.

**If the dry run succeeds** (output matches or the user confirms it's correct):

```bash
set-status.py review_ready
```

Present the output to the user for review:
- What was prepared
- Key numbers (totals, line counts, significant amounts)
- Any items that need attention

Tell the user: *"Dry run complete. Review the output, then run `/done` to capture learnings and finalize."*

`/done` handles the rest: captures review feedback, seeds `learned.md`, sets `done`, commits, and archives to Google Drive.

**If the dry run fails** (output doesn't match, tool errors, missing data):

Fix the issue — update SKILL.md, fix tools, adjust procedure. Re-run. You are not done until the dry run succeeds. If the issue is unrecoverable for this period (e.g., data is simply not available):

```bash
set-status.py blocked "reason"
```

Discuss with the user whether to retry with a different period or mark as blocked and continue.

#### Step 8 — Add to Manifest

Add the task to the class's `.class.yaml` manifest:

```yaml
manifest:
  # ... existing tasks ...
  - task: <name>
    order: <N>           # ask user or infer from dependencies
    enabled: true
    period_format: <format>   # from interview (default: monthly)
    anchor: <anchor>          # from interview (default: first_monday)
```

Ask the user:
- *"Should this run in parallel with existing tasks, or does it depend on one finishing first?"* → determines `order` value
- Confirm the `period_format` and `anchor` from the scheduling discussion in Step 3.

#### Step 9 — Finalize

```bash
git add <task-directory>/ <class>/.class.yaml
git commit -m "[onboard] <task-name>: SKILL.md, tools, dry run ready for review"
```

Tell the user: *"Task onboarded. Review the dry run output and run `/done` to complete the first period. From the next period onward, use `/start`."*

---

## Key Constraints

- **`/onboard` stops at `review_ready`.** The onboarding commit covers scaffolding, interview artifacts, and the dry run output. It does not set `done` or capture learnings — that's `/done`'s job.
- **`/done` completes the first period.** After the user reviews the dry run, they run `/done` in the same conversation. `/done` captures review feedback, seeds `learned.md`, sets `done`, commits, and archives to Google Drive. This is the same `/done` flow used for every subsequent period.
- **First period is part of onboarding.** `/start` is only used from the second period onward. The dry run validates that the folder works end-to-end.
- **AGENT.md stays minimal.** Class-level AGENT.md should be concise. If information is specific to one task, it belongs in that task's SKILL.md.
- **Token cost awareness.** SKILL.md and learned.md are loaded every period. Keep them focused. Avoid duplicating information between sections or between files.

---

## Script Composition

| Script | When called | Purpose |
|--------|------------|---------|
| `load-context.py --level root` | Class onboarding, Step 0 | Load engagement context |
| `load-context.py --level class` | Task onboarding, Step 0 | Load engagement + class context |
| `init-class.py <name>` | Class onboarding, Step 2 | Scaffold class directory |
| `init-task.py <name>` | Task onboarding, Step 2 | Scaffold task folder |
| `install-deps.py` | Task onboarding, Step 6 | Install Python dependencies |
| `set-status.py <status>` | Task onboarding, Step 7 | Transition task status (`in_progress`, `review_ready`, or `blocked`) |
| `init-period.py <period>` | Task onboarding, Step 7 | Scaffold period directory |
