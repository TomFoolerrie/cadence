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
- `status.yaml` and `.class.yaml` are written directly by the agent (no gated scripts).
- Markdown files (`SKILL.md`, `learned.md`, `AGENT.md`) are written directly by the agent.
- One git commit per skill invocation.

## Step 0 — Detect Level

Check the current working directory:

- If `.context-root` exists in cwd → **Class-Level Onboarding**
- If `.class.yaml` exists in cwd → **Task-Level Onboarding**
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

### Step 5 — Write Task Files

Based on the interview, write:

- **`<name>/SKILL.md`** — The step-by-step procedure. Outputs go in `periods/{period}/workpapers/`, source data in `periods/{period}/data/`.
- **`<name>/learned.md`** — Known patterns, expected ranges, failure modes.
- **`<name>/tools/`** — Any automation scripts needed.
- **`<name>/requirements.txt`** — Python dependencies for tools.

Keep SKILL.md and learned.md focused — they are loaded every period.

### Step 6 — Register Task in `.class.yaml`

Read the current `.class.yaml`, add a manifest entry. Ask the user for `period_format` and `anchor`:

```yaml
manifest:
  - task: <name>
    order: 1
    period_format: monthly    # or weekly, quarterly, adhoc
    anchor: first_monday      # when this task becomes due
    enabled: true
```

Write the updated `.class.yaml` directly.

### Step 7 — Install Dependencies

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/install-deps.py
```

### Step 8 — First Period Execution

**8a.** Ask the user: *"What period is this for?"* (e.g., `2026-03`)

**8b.** Write `<name>/status.yaml`:

```yaml
schema_version: 1
status: in_progress
period: "<period>"
issues: []
done_at: null
```

**8c.** Scaffold the period:

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/init-period.py <period>
```

**8d.** Load task context:

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/load-context.py --level task
```

**8e.** Execute the procedure from SKILL.md. Place outputs in `periods/<period>/workpapers/`.

### Step 9 — Mark Review Ready

On success, update `<name>/status.yaml`:

```yaml
schema_version: 1
status: review_ready
period: "<period>"
issues: []
done_at: null
```

### Step 10 — Commit

```bash
git add -A && git commit -m "[onboard] Add task: <name>"
```

Tell the user: *"Task onboarded. Run /done to review the output."*
