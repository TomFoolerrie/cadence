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

### Step 1 — Load Context

Run:

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/load-context.py --level class
```

This loads both root AGENT.md and class AGENT.md so you understand the full context.

### Step 2 — Name the Task

Ask the user: *"What task is this? Give me a short name."*

Map to kebab-case (e.g., "Monthly bank fees" becomes `monthly-bank-fees`).

### Step 3 — Scaffold

Run (substituting the kebab-case name from Step 2):

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/init-task.py <name>
```

This creates the task folder with SKILL.md (template), learned.md (template), status.yaml, tools/, periods/, and requirements.txt.

### Step 4 — Deep Interview

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

### Step 5 — Check Existing Tools

Before writing new tools, check what already exists:

- `.claude/tools/` -- global tools (JE formatter, PDF parser)
- `{class}/tools/` -- class-level tools

Reuse what you can. If multiple tasks would parse the same source format, that parser belongs at the class level. Only build task-level tools for logic unique to this task.

### Step 6 — Build Files

Write the files based on the interview:

- **SKILL.md** -- Populate all sections from the template. The `## Procedure` section must reference tools by path and use standard period directories: source files go in `periods/{period}/data/`, outputs go in `periods/{period}/workpapers/`. Do not use custom directory names.
- **learned.md** -- Seed with what the preparer shared about quirks, expected ranges, and known failure modes. Use the four-section structure: Review History, Patterns, What Didn't Work, Open Questions.
- **tools/** -- Build the Python scripts that do transformation and validation work. Ensure all tool output paths default to the standard period subdirectories.
- **requirements.txt** -- Add task-specific Python dependencies. Check class-level and root-level requirements.txt first -- do not duplicate.

### Step 7 — Install Dependencies

Run:

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/install-deps.py
```

This installs requirements.txt files top-down (root, class, task).

### Step 8 — First-Period Dry Run

The first period validates the knowledge transfer. This is the proof that the folder works.

The period string is the **period being closed** (e.g., if it is April, use `2026-03` for March close). Ask the user which period to use for the dry run.

Set status and scaffold the period (substituting the period string):

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/set-status.py in_progress --period "<period>"
python ${CLAUDE_PLUGIN_ROOT}/scripts/init-period.py <period>
```

Execute the procedure:

1. Ask the user to provide the source data for the dry run period (via Cowork file attachment). Place files in `periods/{period}/data/`.
2. Follow SKILL.md `## Procedure` exactly as a fresh agent would -- this is the test.
3. Run the tools, produce the output, write results to `periods/{period}/workpapers/`.
4. Compare your output to what was actually produced for that period. The user should have the original output to compare against.

**If the dry run succeeds** (output matches or the user confirms it is correct):

Set status to review_ready:

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/set-status.py review_ready
```

Present the output to the user for review:
- What was prepared
- Key numbers (totals, line counts, significant amounts)
- Any items that need attention

Tell the user: *"Dry run complete. Review the output, then run `/done` to capture learnings and finalize."*

**If the dry run fails** (output does not match, tool errors, missing data):

Fix the issue -- update SKILL.md, fix tools, adjust procedure. Re-run. Do not stop until the dry run succeeds. If the issue is unrecoverable for this period (e.g., data is not available):

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/set-status.py blocked "reason"
```

Discuss with the user whether to retry with a different period or mark as blocked and continue.

### Step 9 — Add to Manifest

Add the task to the class's `.class.yaml` manifest:

```yaml
manifest:
  - task: <name>
    order: <N>
    enabled: true
    period_format: <format>
    anchor: <anchor>
```

Ask the user:
- *"Should this run in parallel with existing tasks, or does it depend on one finishing first?"* -- this determines the `order` value.
- Confirm the `period_format` and `anchor` from the scheduling discussion in Step 4.

### Step 10 — Finalize

Stage and commit:

```bash
git add <task-directory>/ <class>/.class.yaml
git commit -m "[onboard] <task-name>: SKILL.md, tools, dry run ready for review"
```

Tell the user: *"Task onboarded. Review the dry run output and run `/done` to complete the first period. From the next period onward, use `/start`."*

---

## Key Constraints

- **/onboard stops at review_ready.** The onboarding commit covers scaffolding, interview artifacts, and the dry run output. It does not set `done` or capture learnings -- that is `/done`'s job.
- **/done completes the first period.** After the user reviews the dry run, they run `/done` in the same conversation. `/done` captures review feedback, seeds learned.md, sets `done`, commits, and archives.
- **First period is part of onboarding.** `/start` is only used from the second period onward. The dry run validates the folder works end-to-end.
- **AGENT.md stays minimal.** Class-level AGENT.md should be concise. If information is specific to one task, it belongs in that task's SKILL.md.
- **Token cost awareness.** SKILL.md and learned.md are loaded every period. Keep them focused. Do not duplicate information between sections or between files.
