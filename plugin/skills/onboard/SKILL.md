---
name: onboard
description: >
  This skill should be used when the user says "/onboard" or asks to
  "set up a new class" or "teach Claude a new task." Guides knowledge
  transfer from a human preparer to Claude. Level-aware: from root
  creates a class, from a class creates a task with first-period
  validation.
version: 1.0.0
---

# /onboard

## Constraints

- **Scripts are mandatory.** Never create directories with mkdir or modify YAML files directly.
  All scaffolding goes through `init-*.py` scripts. All YAML state changes go through
  `set-status.py` or `edit-class-yaml.py`. The scripts validate inputs and enforce the schema.
- **Markdown files are the exception.** SKILL.md, learned.md, and AGENT.md are written directly
  by the agent — these are content files, not state files.

## Step 0 — Detect Level

Check the current working directory:

- If `.context-root` exists in cwd, proceed to **Class-Level Onboarding** below.
- If `.class.yaml` exists in cwd, proceed to **Task-Level Onboarding** below.
- Otherwise, tell the user: *"Run `/onboard` from the engagement root to create a class, or from a class directory to create a task."* Stop.

---

## Class-Level Onboarding

### Step 1 — Load Context

Run:

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/load-context.py --level root
```

This loads the engagement's root AGENT.md so you understand the entity context.

### Step 2 — Name the Class

Ask the user: *"What class of work is this? Give me a short name."*

Map the answer to a kebab-case folder name (e.g., "Treasury" becomes `treasury`, "Order to Cash" becomes `order-to-cash`).

### Step 3 — Scaffold

Run (substituting the kebab-case name from Step 2):

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/init-class.py <name>
```

This creates the class directory with `.class.yaml`, `AGENT.md` (template), `tools/`, and `requirements.txt`.

### Step 4 — Interview for AGENT.md

Conduct a brief interview to populate the class AGENT.md. Ask these questions:

1. *"What does this class cover?"* -- One or two sentences describing the group of work it represents.
2. *"What are the key domain concepts?"* -- Terms, conventions, or rules that task agents in this class need to know. Keep it short.
3. *"Any shared data sources or systems?"* -- Systems that multiple tasks in this class will access (e.g., "Chase portal for all treasury work").

Write the answers into `<class>/AGENT.md`. Keep it minimal by design -- just enough for task agents to understand their broader context. If content is getting long, it probably belongs in a task's SKILL.md instead.

### Step 5 — Finalize

Stage and commit:

```bash
git add <class-directory>/
git commit -m "[onboard] <class-name>: class created"
```

Tell the user: *"Class created. Navigate into `<name>/` and run `/onboard` again to add a task."*

---

## Task-Level Onboarding

### Step 1 — Name the Task

Ask the user: *"What task is this? Give me a short name."*

Map to kebab-case (e.g., "Monthly bank fees" becomes `monthly-bank-fees`).

### Step 2 — Setup

Run (substituting the kebab-case name from Step 1):

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/onboard-setup.py <name>
```

This loads class context (root AGENT.md + class AGENT.md) and scaffolds the task directory with SKILL.md (template), learned.md (template), status.yaml, tools/, periods/, and requirements.txt.

The loaded context is printed to stdout — read it to understand what class you are onboarding into.

### Step 3 — Deep Interview

This is the core of onboarding. Extract everything the preparer knows -- including things they consider "obvious." Ask follow-up questions. Do not rush.

Cover each topic below. Write answers to the indicated file and section as you go.

**Purpose** (writes to SKILL.md `## Purpose`)
- What does this produce?
- Which accounts does it touch?
- Is this a journal entry, workpaper, or reconciliation?
- Does this depend on another task finishing first? Does anything depend on this?

**Data Sources** (writes to SKILL.md `## Data Sources`)
- Where does the data come from?
- What format (CSV, PDF, portal export)?
- What do you do if it is missing or late?

**Procedure** (writes to SKILL.md `## Procedure`)
- Walk me through it step by step. What do you do first? Then what?
- What tools or formulas do you use?
- Go deep here. If the preparer says "I just reconcile it," ask *how* -- what are the columns, what is the matching logic, what is the tolerance.

**Validation** (writes to SKILL.md `## Validation`)
- How do you know the output is correct?
- What do you check? Expected ranges, tie-outs, cross-references?

**Completion Criteria** (writes to SKILL.md `## Completion Criteria`)
- What artifacts must exist when this task is done?
- What does "ready for review" look like?

**Contacts** (writes to SKILL.md `## Contacts`)
- Who do you call when something goes wrong?
- Who owns the data source?

**What Goes Wrong** (writes to learned.md `## Patterns` and `## What Didn't Work`)
- What breaks? What are the common surprises?
- What did you learn the hard way?
- Typical dollar amounts, line counts, variance thresholds?

**Scheduling** (writes to `.class.yaml` manifest)
- When does this task typically run? First Monday after month-end? Last Friday? Weekly?

**Interview principles:**

- Ask for examples. *"Can you show me a recent period's output?"* is more valuable than abstract description.
- Capture the implicit. Ask: *"Is there anything you do automatically that you haven't mentioned?"* and *"What would a new hire get wrong the first time?"*
- Be token-conscious. SKILL.md and learned.md are loaded every period. Keep them focused. Do not duplicate information between sections.

### Step 4 — Check Existing Tools

Before writing new tools, check what already exists:

- `.claude/tools/` -- global tools (JE formatter, PDF parser)
- `{class}/tools/` -- class-level tools

Reuse what you can. If multiple tasks would parse the same source format, that parser belongs at the class level. Only build task-level tools for logic unique to this task.

### Step 5 — Build Files

Write the files based on the interview:

- **SKILL.md** -- Populate all sections from the template. The `## Procedure` section must reference tools by path and use standard period directories: source files go in `periods/{period}/data/`, outputs go in `periods/{period}/workpapers/`. Do not use custom directory names.
- **learned.md** -- Seed with what the preparer shared about quirks, expected ranges, and known failure modes. Use the four-section structure: Review History, Patterns, What Didn't Work, Open Questions.
- **tools/** -- Build the Python scripts that do transformation and validation work. Ensure all tool output paths default to the standard period subdirectories.
- **requirements.txt** -- Add task-specific Python dependencies. Check class-level and root-level requirements.txt first -- do not duplicate.

### Step 6 — Register Task

Register the task in the class manifest **before** the first period execution — `init-period.py` needs the task's `period_format` from the manifest to validate the period string.

Ask the user:
- *"Should this run in parallel with existing tasks, or does it depend on one finishing first?"* — this determines the `order` value.
- Confirm the `period_format` and `anchor` from the scheduling discussion in Step 3.

Run (substituting values from the interview):

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/onboard-register.py <name> --order <N> --period-format <format> --anchor <anchor>
```

If the user mentioned a description for the class during the interview, add `--description "<description>"` to the same command.

This installs dependencies (init-venv + install-deps), adds the task to `.class.yaml` manifest, and optionally sets the class description.

### Step 7 — First Period Execution

Execute the first period inline to validate the knowledge transfer. This is not a dry run — it produces real output for a real period. You retain full write scope, so if execution reveals a problem with SKILL.md or tools, fix them and re-run while the preparer is still present.

#### 7a — Start Period

Ask the user: *"Which period should we execute? This is the label for the work (e.g., `2026-03` for monthly, `2026-Q1` for quarterly)."*

Run from the task directory (`<name>/`):

```bash
cd <name>/
python ${CLAUDE_PLUGIN_ROOT}/scripts/start-setup.py --period "<period>"
```

This sets status to `in_progress`, installs deps, scaffolds the period directory, and loads context. **Note:** The stdout context from `start-setup.py` can be disregarded — you already loaded context in Step 2.

#### 7b — Execute

Before running engagement tools, activate the venv: `source <root>/venv/bin/activate` where `<root>` is the engagement root containing `.context-root`.

Follow the `## Procedure` section of SKILL.md:

- Ask the user to provide source data files. Place them in `periods/{period}/data/`.
- All outputs go in `periods/{period}/workpapers/`.
- Reference tools by path: task `tools/` → class `tools/` → global `.claude/tools/`.
- Check `## Validation` and `## Completion Criteria` — output must satisfy these before setting `review_ready`.
- Compare results against `learned.md` patterns (expected ranges, line counts, known quirks).

**If execution fails:**

- **Fixable** (tool bug, SKILL.md gap, missing step): Fix the file, re-run. This is the advantage of executing during onboarding — iterate with the preparer present.
- **Not fixable** (data unavailable, external system down):
  ```bash
  python ${CLAUDE_PLUGIN_ROOT}/scripts/set-status.py blocked "description of what failed"
  ```
  Discuss with the user whether to retry later or continue onboarding without the first period.

#### 7c — Set Review Ready

When execution succeeds and validation passes:

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/set-status.py review_ready
```

Report to the user:
- What was produced
- Key numbers (totals, line counts, significant amounts)
- How results compare to learned.md patterns
- *"First period complete. Review the output, then run `/done` to capture learnings and finalize."*

### Step 8 — Finalize

```bash
git add <task-directory>/ <class>/.class.yaml
```

**If `review_ready`:**

```bash
git commit -m "[onboard] <task-name>: SKILL.md, tools, first period ready for review"
```

Tell the user: *"Task onboarded. Review the output and run `/done` to capture learnings and finalize. From the next period onward, use `/start`."*

**If `blocked`:**

```bash
git commit -m "[onboard] <task-name>: SKILL.md, tools ready; first period blocked"
```

Tell the user: *"Task onboarded. SKILL.md and tools are committed. Run `/start` when the blocker is resolved to execute the first period."*

---

## Key Constraints

- **/onboard stops at review_ready.** The onboarding commit covers scaffolding, interview artifacts, and the first period output. It does not set `done` or capture learnings -- that is `/done`'s job.
- **First period execution is inline.** Onboard executes the first period directly -- it does not delegate to `/start`. This keeps full write scope active so you can iterate on SKILL.md and tools if execution reveals problems. `/start` is used for all subsequent periods.
- **/done completes the first period.** After the user reviews the output, they run `/done` in the same conversation. `/done` captures review feedback, seeds learned.md, sets `done`, commits, and archives.
- **AGENT.md stays minimal.** Class-level AGENT.md should be concise. If information is specific to one task, it belongs in that task's SKILL.md.
- **Token cost awareness.** SKILL.md and learned.md are loaded every period. Keep them focused. Do not duplicate information between sections or between files.
