# Architecture

## 1. The Three Levels

```
engagement-root/                    <- ROOT
├── .context-root                   <- root marker (YAML: engagement name, schema version)
├── AGENTS.md                        <- root context (entity details)
├── requirements.txt                <- global dependencies
├── venv/                           <- Python virtual environment (created by init-venv.py)
├── .claude/
│   └── tools/                      <- global shared tools
├── treasury/                       <- CLASS
│   ├── .class.yaml                 <- orchestration manifest (tasks, order)
│   ├── AGENTS.md                    <- class context for task agents
│   ├── requirements.txt            <- class-level dependencies
│   ├── tools/                      <- class-level shared tools
│   └── monthly-bank-fees/          <- TASK
│       ├── SKILL.md                <- what to do
│       ├── learned.md              <- what's been learned
│       ├── status.yaml             <- current state
│       ├── tools/                  <- task-level tools
│       ├── requirements.txt        <- task-level dependencies
│       └── periods/                <- period-specific work
│           └── 2026-03/
│               ├── data/           <- inputs
│               ├── workpapers/     <- outputs
│               └── review-notes/   <- feedback
├── reporting/                      <- CLASS
│   ├── .class.yaml
│   ├── AGENTS.md
│   ├── tools/
│   └── ...
└── collections/                    <- CLASS
    ├── .class.yaml
    ├── AGENTS.md
    └── ...
```

**Hierarchy depth constraint:** The hierarchy is exactly three levels deep: root -> class -> task. No nesting beyond this (e.g., no `treasury/subcategory/task/`). See Section 7.

## 2. Root Level

The root is the engagement folder -- the top-level directory the user mounts in Cowork. It holds context that applies to everything: entity information, materiality thresholds, system access, key contacts.

**Key files:**

| File | Purpose |
|------|---------|
| `.context-root` | Root marker file. A YAML file containing the engagement name and schema version. Used by `load-context.py` to locate the engagement root when walking up the directory tree. Prevents collision with other `.claude/` directories in parent paths. Schema: `engagement: "Acme Corp"`, `schema_version: 1`. |
| `AGENTS.md` | Root-level context -- entity name, fiscal year, reporting basis, materiality, systems, key contacts. Loaded into every session regardless of which task is being worked. |
| `requirements.txt` | Global Python dependencies shared across all classes and tasks. |
| `.claude/tools/` | Global shared tools (e.g., JE formatter, PDF parser) available to all tasks. |
| `.gitignore` | What git tracks vs. ignores. |
| `venv/` | Python virtual environment for the engagement. Created by `init-venv.py`. All dependencies are installed here via `install-deps.py`. |

The user rarely interacts at the root level after initial setup. The root is context, not a workspace.

## 3. Class Level

A class groups related work. Treasury, reporting, procure-to-pay, order-to-cash, collections -- each is a class. Classes are created via `/onboard` from the root level, which runs `init-class.py` to scaffold the directory and conducts a brief interview to populate AGENTS.md. A class has two defining files: `.class.yaml` (orchestration manifest -- tasks and execution order) and `AGENTS.md` (class context that flows down to task agents). AGENTS.md is **minimal by design** -- just enough for task agents to understand their broader context, not a comprehensive domain manual.

**Key files:**

| File | Purpose |
|------|---------|
| `.class.yaml` | Orchestration manifest. Declares tasks and execution order. **What to run.** Read by the orchestrator and skills -- not loaded into task agent context. |
| `AGENTS.md` | Class context for task agents. Describes what this class of work is, key domain concepts, shared conventions. **Loaded into every task session within this class.** |
| `requirements.txt` | Class-level Python dependencies shared across tasks in this class. |
| `tools/` | Class-level shared tools (e.g., a Chase statement parser shared across all treasury journal entries). |

### `.class.yaml` Schema

```yaml
# treasury/.class.yaml
schema_version: 1
name: Treasury
description: Cash management, banking relationships, and financing activities.

manifest:
  - task: monthly-bank-fees
    order: 1
    enabled: true
    period_format: monthly          # values: monthly (default), weekly, quarterly, adhoc

  - task: zba-entries
    order: 1
    enabled: true

  - task: bank-reconciliation
    order: 2
    enabled: true
    anchor: first_wednesday         # day-of-week anchor for period triggering
```

The manifest is what an orchestrator reads. Today a human picks a task. Tomorrow an orchestrator agent reads `.class.yaml` and processes it phase by phase -- all order-1 tasks run in parallel, and once all phase 1 tasks complete, order-2 tasks start. No phase 2 task runs until every phase 1 task is done. Each task gets a fresh sub-agent that reads the task folder and executes.

**`AGENTS.md`** describes what this class of work is -- domain concepts, shared conventions, key contacts, anything a task agent needs to understand its broader context. Unlike `.class.yaml` (which is orchestration machinery), `AGENTS.md` is written for the agent that *executes* tasks. The `/onboard` skill populates it initially; it evolves as the class matures.

Note: `enabled` in `.class.yaml` is **membership** -- is this task part of the active roster? Status is tracked at the task level in `status.yaml` (execution state). Class-level status is computed on the fly by `/status`, which reads all task `status.yaml` files and derives a rollup.

**Manifest fields:**

| Field | Purpose |
|-------|---------|
| `task` | Folder name (kebab-case). Must match a subdirectory with SKILL.md. |
| `order` | Execution phase. Tasks with the same `order` value run in parallel. All tasks in phase N must complete before any phase N+1 task starts. The orchestrator processes phases strictly sequentially -- `order` is authoritative. |
| `enabled` | `true` or `false`. Only enabled tasks are executed by the orchestrator. Set to `false` to pause a task without removing it from the manifest. |
| `period_format` | Period naming convention for this task. Values: `monthly` (default), `weekly`, `quarterly`, `adhoc`. Omit to use `monthly`. |
| `anchor` | Day-of-week anchor for when this task should be triggered within its period cycle. Values: `first_monday` (default), `first_tuesday` .. `first_friday`, `last_monday` .. `last_friday`, `monday` .. `sunday`. Omit to use `first_monday`. Set during `/onboard`. |

**Who writes `.class.yaml` and when:**

| Event | What changes | Who writes |
|-------|-------------|------------|
| `/onboard` completes | New task entry added to manifest (`enabled: true`) | The `/onboard` skill |
| User pauses a task | `enabled: false` | Agent (via conversation) |
| User retires a task | Entry removed from manifest | Agent (via conversation) |
| Task order changes | `order` updated | Agent (via conversation) or orchestrator |

`.class.yaml` changes **rarely** -- only when the roster of tasks changes, not during normal execution cycles.

See `03-status-machine.md` for the full status transition rules, including period advancement via `check-periods.py` and the `set-status.py` transition table.

## 4. Task Level

The task is where the user lives. Each task is a self-contained work folder with everything an agent needs to execute: procedure, learning history, tools, and period-organized work.

**Key files:**

| File | Purpose |
|------|---------|
| `SKILL.md` | The operating manual. What this task produces, where data comes from, step-by-step procedure, validation rules, contacts. A fresh agent instance reads this and executes. |
| `learned.md` | Accumulated learnings. Review history, amount patterns, what didn't work, open questions. Updated after every review cycle via `/done`. |
| `status.yaml` | Current **execution state** for this period. Not to be confused with `enabled` in `.class.yaml` (which is membership). |
| `tools/` | Task-specific Python scripts for data transformation and validation. |
| `requirements.txt` | Task-specific Python dependencies. |
| `periods/` | Period-organized work directories, each containing `data/` (inputs), `workpapers/` (outputs), and `review-notes/` (feedback). |

**The task lifecycle:**

1. **Onboard** (`/onboard`) -- The mechanism for bringing human knowledge into the agent's world. A structured conversation that extracts procedural knowledge and writes it into SKILL.md (procedure), learned.md (patterns and edge cases), and tools/ (automation scripts). The output is validated with a dry run that reaches `review_ready`. The user then runs `/done` to complete the first period.

2. **Start** (`/start`) -- The recurring execution cycle. A fresh agent reads SKILL.md and learned.md, pulls data, runs tools, produces a draft in `periods/{period}/workpapers/`. On success, sets `review_ready`; on failure, sets `blocked`. Also handles recovery: retry from `blocked`, re-execute from `review_ready` (rejected draft), and idempotent re-entry from `in_progress` (crash recovery).

3. **Done** (`/done`) -- After human review. Runs in the **same conversation** as the preceding `/start` or `/onboard` -- does not load context independently. Sets the task to `done`, processes review feedback (updates learned.md, proposes SKILL.md changes with human approval), and archives the completed period to Google Drive.

4. **Status** (`/status`) -- Human orchestrator's dashboard. Run from a **class directory**. Reads all task-level `status.yaml` files and computes the class rollup on the fly. Read-only -- no side effects.

**Fresh agent per task.** Each execution gets a fresh Claude instance. The folder is the memory, not the agent. Claude reads the docs, runs the tools, produces output, and terminates. Nothing carries over except what's written to the folder.

See `03-status-machine.md` for the full status state machine, valid transitions, and write-path authority model.

### Task-Level File Authority

The two core task files have different authority models reflecting their risk profiles:

| File | Who writes | Review required | Self-managed |
|------|-----------|----------------|-------------|
| `learned.md` | Agent (during `/done`) | No | Yes -- agent consolidates, prunes, and restructures freely |
| `SKILL.md` | Agent (proposes during `/done`) | Yes -- human (MVP) or orchestrator (future) approves | No |

**`learned.md`** uses a four-section structure. `init-task.py` provides a starting template with anchor headings (`## Review History`, `## Patterns`, `## What Didn't Work`, `## Open Questions`) that the agent is free to restructure as the task evolves. The anchor headings exist so the future orchestrator can locate key sections when reviewing task output against learned patterns.

**Structured delta convention.** Entries under `## Patterns` and `## What Didn't Work` may carry optional metadata:

```markdown
## Patterns

- **Monthly fees typically $12,000-13,000**
  Confirmed: 4 | Contradicted: 1 | First seen: 2025-09
  Used for: validating draft totals against expected range
```

Counters (`Confirmed`, `Contradicted`, `First seen`) are optional metadata -- useful for tracking confidence but not required on every entry. The agent updates `learned.md` during `/done` with observations from the current cycle. When the file gets long (guideline: ~150 lines), the agent consolidates.

**Contradiction handling:** When a pattern is contradicted, the agent uses domain judgment to decide whether the contradiction represents an edge case, a data error, or a genuinely shifting pattern. Counters inform; they do not decide.

**`SKILL.md`** changes are high-stakes -- a bad procedure change breaks every future cycle. During `/done`, the agent *proposes* changes and presents them for approval. In MVP, the human approves or rejects verbally. In future state, the orchestrator reviews diffs before applying them.

### `status.yaml` Schema

```yaml
schema_version: 1
period: "2026-03"
status: done               # not_started | in_progress | review_ready | blocked | done | abandoned
issues: []                 # populated on error; cleared on success
done_at: "2026-04-07T14:30:00Z"  # timestamp when done or abandoned; null otherwise
```

### Completion Criteria

`status.yaml` changes **frequently** -- every execution cycle. It is the handoff between the agent that runs the task and whoever (human or orchestrator) reviews it.

## 5. Context Inheritance

Context flows downward through the hierarchy. A task agent automatically sees its class context and root context. Context loading and system management are **separate concerns**:

- **`load-context.py`** -- Pure context assembly. Reads files, prints them to stdout. No side effects.
- **Management scripts** -- `init-class.py`, `init-task.py`, `init-period.py`, `install-deps.py`, `check-periods.py`, `archive-period.py`. These have side effects (write files, install packages, upload to Drive).
- **Skills** -- Each skill (`/start`, `/onboard`, `/done`, `/status`) composes the scripts it needs. The skill is the orchestrator of these pieces.

**Claude manages all folder navigation.** The user never manually `cd`s into hierarchy directories. Claude knows which level it's operating at because it (or the orchestrator) chose to enter that folder.

### What Gets Loaded at Each Level

**Task level** (`--level task`):
```
root/AGENTS.md -> class/AGENTS.md -> SKILL.md + learned.md + status.yaml [+ recovery hint if blocked]
```

**Class level** (`--level class`):
```
root/AGENTS.md -> class/AGENTS.md
```

**Class level as orchestrator** (`--level class --orchestrator`) *(future state)*:
```
root/AGENTS.md -> class/AGENTS.md -> .class.yaml (manifest)
```

**Root level** (`--level root`):
```
root/AGENTS.md
```

Task agents and class-level agents both receive `AGENTS.md` (class context). Class agents do NOT receive `.class.yaml` by default. The `--orchestrator` flag additionally loads `.class.yaml` including the manifest. This keeps non-orchestrator agents focused on *what to do* without exposing manifest details they don't need.

### `load-context.py` Behavior

`load-context.py` is a **pure context assembly script** -- reads files, prints to stdout, no side effects. The `--level` argument is required and always passed explicitly by the caller. There is no filesystem-based detection of the context level.

The tree walk for finding the engagement root uses filesystem detection (presence of `.context-root` with valid YAML containing `engagement` key), but the *context level* is never guessed -- it's always declared by the caller.

**Recovery hints.** When loading at the task level, if `status.yaml` indicates `blocked`, the script appends a recovery hint after the status output.

**`install-deps.py`** handles Python dependency installation as a separate concern. It walks the hierarchy and installs `requirements.txt` files top-down (global -> class -> task). Idempotent -- safe to run multiple times.

**Prior-period guard.** `/done` runs in the same conversation as `/start` or `/onboard` -- it does not load context independently. This is a design constraint: `/done` is not a standalone skill that can be invoked in a fresh session. Script behavior details live in `05-scripts.md`.

## 6. Tool Inheritance

Tools are organized in layers so common logic is not duplicated:

```
Global    .claude/tools/         -- JE formatter, PDF parser
Class     {class}/tools/         -- Shared within a class (e.g., Chase parser)
Task      {task}/tools/          -- Task-specific transformation logic
```

**Resolution order: task > class > global.** When tools exist at multiple levels with the same name, the most specific level wins. A task-level `validate.py` shadows a class-level `validate.py`. Common logic should live at the highest appropriate level to avoid duplication.

**Resolution mechanism.** `load-context.py --level task` outputs the resolved tool paths in priority order as part of its context assembly:

```
-- tools --
task:   treasury/monthly-bank-fees/tools/
class:  treasury/tools/
global: .claude/tools/
```

The agent uses the first match when a tool name appears at multiple levels. No registry or PATH variable -- just an ordered list the agent follows.

Dependencies follow the same pattern. Global `requirements.txt` for shared libraries, class-level for class-shared, task-level for task-specific. `install-deps.py` installs top-down: global first, class second, task last. Task-level version pins take precedence.

## 7. Hierarchy Depth

The hierarchy is exactly three levels deep: **root -> class -> task**. There is exactly one directory level between the root and each task. `load-context.py` relies on this structure -- it walks up from the task's cwd, finds `AGENTS.md` in the parent (class), and `.context-root` in the grandparent (root). Nested subdirectories within a class (e.g., `treasury/subcategory/monthly-bank-fees/`) are not supported and will break context loading.

## 8. Orchestration Model

### MVP: Human as Orchestrator

The human picks tasks, navigates to the task folder, runs `/start`, reviews the draft, and runs `/done`. The working directory IS the task context -- there is no natural-language resolution of task names. `/status` (run from a class directory) reads task-level `status.yaml` files and computes class progress on the fly.

The data model (`.class.yaml` manifests, phase ordering) is in place for future automation, but nothing reads it for automated execution in MVP.

**Class creation:** Before working on tasks, the user creates classes via `/onboard` from the root level. This runs `init-class.py` to scaffold the class directory and conducts a brief interview to populate AGENTS.md. Classes are created on demand, not pre-built in the engagement template.

**Concurrency:** In MVP, the human drives one task at a time in a single conversation, so concurrent writes cannot occur. The orchestrator (future state) addresses concurrency for the automated multi-task case.

### Future State: Orchestrator Agent

The orchestrator is an agent that reads `.class.yaml` (via `load-context.py --level class --orchestrator`), processes the manifest phase by phase, and launches sub-agents per task. All order-N tasks run in parallel; no phase N+1 task starts until every phase N task is done. Each sub-agent is a fresh instance that reads its task folder via `load-context.py --level task` and executes independently.

The orchestrator does two things: **coordinates** (reads manifest, processes phases sequentially, launches sub-agents) and **reviews** (reads each task's output, evaluates it against learned.md patterns, writes review notes). Sub-agents set `review_ready` on completion; the orchestrator reviews and sets `done` -- mirroring the human's role in MVP.

**Class-level state** is computed on demand. The orchestrator reads task-level `status.yaml` files directly and computes the rollup on the fly. There is no cached class-level state file.

**Architectural properties (designed into MVP, exercised by orchestrator in future state):**

- **One context-loading path.** The orchestrator uses the same `load-context.py` as any agent, with `--level class --orchestrator` to include the manifest. No separate bootstrapping mechanism.
- **`.class.yaml` is the orchestration spec.** Machine-readable manifest declaring tasks and execution order. The orchestrator follows `order` strictly.
- **Tasks are self-contained.** Each task has everything a sub-agent needs. No external dependencies except inherited context from root and class.
- **`status.yaml` is the handoff.** After a sub-agent completes, `status.yaml` reflects the result. The orchestrator reads it to decide what to do next.
- **The error protocol governs recovery.** The orchestrator follows the same status transitions as the human-driven flow.
- **The orchestrator reviews, not just coordinates.** It reads workpapers, compares against learned.md patterns, and writes review notes -- replacing the human reviewer for routine checks. The human provides final sign-off.
- **The hierarchy is just folders.** An orchestrator is just another agent that can parse YAML and launch sub-processes. No special runtime, no message bus, no coordination protocol.
