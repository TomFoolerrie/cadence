---
name: onboard
description: >
  Triggered by "/onboard". Level-aware: from engagement root creates a class,
  from a class directory creates a task with first-period execution.
version: 2.0.0
---

# /onboard

## Constraints

- All directory creation MUST go through `init-*.py` scripts. Never use `mkdir`.
- Markdown files (`SKILL.md`, `learned.md`, `AGENT.md`) are written directly by the agent.
- One git commit per skill invocation.

## Step 0 — Detect Level

Check the current working directory:

- If `.context-root` exists in cwd → **Class-Level Onboarding**
- If `.class` exists in cwd → **Task-Level Onboarding**
- Otherwise → tell the user: *"Run /onboard from the engagement root or a class directory."* Stop.

---

## Class-Level Onboarding

### Step 1 — Load Context

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/load-context.py --level root
```

### Step 2 — Interview

Ask the user what category of recurring work this class covers. Get enough to write a useful AGENT.md (scope, key domain concepts, shared systems).

### Step 3 — Name the Class

Map the answer to a kebab-case name (e.g., "Treasury" → `treasury`).

### Step 4 — Scaffold

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/init-class.py <name>
```

### Step 5 — Write AGENT.md

Write `<name>/AGENT.md` based on the interview. Keep it minimal — just enough for task agents to understand the class context.

### Step 6 — Commit

```bash
git add -A && git commit -m "[onboard] Add class: <name>"
```

### Step 7 — Next Steps

Ask: *"Want to add a task to this class now?"* If yes, tell the user to `cd <name>/` and run `/onboard` again.

---

## Task-Level Onboarding

### Step 1 — Load Context

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/load-context.py --level class
```

### Step 2 — Interview

Deep dive into the task. Cover:

- **Purpose** — What does this produce? What accounts does it touch?
- **Data Sources** — Where does the data come from? What format?
- **Procedure** — Step by step. If the user says "I reconcile it," ask *how*.
- **Validation** — How do you know the output is correct?
- **Completion Criteria** — What artifacts must exist when done?
- **What Goes Wrong** — Common surprises, expected ranges, failure modes.
- **Scheduling** — When does this run? (monthly, weekly, quarterly, adhoc)

Ask for examples. Capture the implicit: *"What would a new hire get wrong?"*

### Step 3 — Name the Task

Map to kebab-case (e.g., "Monthly bank fees" → `monthly-bank-fees`).

### Step 4 — Scaffold

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/init-task.py <name>
```

### Step 5 — Write Procedure Files

Based on the interview, write:

- **`<name>/SKILL.md`** — The step-by-step procedure. Outputs go in `periods/{period}/workpapers/`, source data in `periods/{period}/data/`.
- **`<name>/learned.md`** — Known patterns, expected ranges, failure modes.

**Do NOT build tools yet.** Wait until you have real data in Step 7.

### Step 6 — First Period Setup

Ask the user: *"What period is this for?"* (e.g., `2026-03`)

Scaffold the period:

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/init-period.py <period>
```

Ask the user to provide real source data. Place it in `periods/<period>/data/`.

### Step 7 — Build Tools from Real Data

Now that you have actual data, build any automation scripts needed:

- **`<name>/tools/`** — Scripts that process the real data format.
- **`<name>/requirements.txt`** — Python dependencies for tools.

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/install-deps.py
```

### Step 8 — Execute First Period

Execute the procedure from SKILL.md. Place outputs in `periods/<period>/workpapers/`.

### Step 9 — Commit

```bash
git add -A && git commit -m "[onboard] Add task: <name>"
```

Tell the user: **"Task onboarded. Review the output — when you're happy with it, run /done to close out the period."**
