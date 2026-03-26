# The Three Levels

## 3.1 Overview

```
engagement-root/                    ← ROOT
├── .context-root                   ← root marker (YAML: engagement name, schema version)
├── AGENT.md                        ← root context (entity details)
├── requirements.txt                ← global dependencies
├── .claude/
│   └── tools/                      ← global shared tools
├── treasury/                       ← CLASS
│   ├── .class.yaml                 ← orchestration manifest (tasks, order)
│   ├── AGENT.md                    ← class context for task agents
│   ├── requirements.txt            ← class-level dependencies
│   ├── tools/                      ← class-level shared tools
│   └── monthly-bank-fees/          ← TASK
│       ├── SKILL.md                ← what to do
│       ├── learned.md              ← what's been learned
│       ├── status.yaml             ← current state
│       ├── tools/                  ← task-level tools
│       ├── requirements.txt        ← task-level dependencies
│       └── periods/                ← period-specific work
│           └── 2026-03/
│               ├── data/           ← inputs
│               ├── workpapers/     ← outputs
│               └── review-notes/   ← feedback
├── reporting/                      ← CLASS
│   ├── .class.yaml
│   ├── AGENT.md
│   ├── tools/
│   └── ...
└── collections/                    ← CLASS
    ├── .class.yaml
    ├── AGENT.md
    └── ...
```

**Hierarchy depth constraint:** The hierarchy is exactly three levels deep: root → class → task. No nesting beyond this (e.g., no `treasury/subcategory/task/`). See Section 5.3.

## 3.2 Root Level

The root is the engagement folder — the top-level directory the user mounts in Cowork. It holds context that applies to everything: entity information, materiality thresholds, system access, key contacts.

**Key files:**

| File | Purpose |
|------|---------|
| `.context-root` | Root marker file. A YAML file containing the engagement name and schema version. Used by `load-context.py` to locate the engagement root when walking up the directory tree. Prevents collision with other `.claude/` directories in parent paths. Schema: `engagement: "Acme Corp"`, `schema_version: 1`. |
| `AGENT.md` | Root-level context — entity name, fiscal year, reporting basis, materiality, systems, key contacts. Loaded into every session regardless of which task is being worked. Uses the same filename as class-level context for consistency across levels. |
| `requirements.txt` | Global Python dependencies shared across all classes and tasks. |
| `.claude/tools/` | Global shared tools (e.g., JE formatter, PDF parser) available to all tasks. |
| `.gitignore` | What git tracks vs. ignores. |

The user rarely interacts at the root level after initial setup. The root is context, not a workspace.

## 3.3 Class Level

A class groups related work. Treasury, reporting, procure-to-pay, order-to-cash, collections — each is a class. Classes are created via `/onboard` from the root level, which runs `init-class.py` to scaffold the directory and conducts a brief interview to populate AGENT.md. A class has two defining files: `.class.yaml` (orchestration manifest — tasks and execution order) and `AGENT.md` (class context that flows down to task agents). AGENT.md is **minimal by design** — just enough for task agents to understand their broader context, not a comprehensive domain manual.

**Key files:**

| File | Purpose |
|------|---------|
| `.class.yaml` | Orchestration manifest. Declares tasks and execution order. **What to run.** Read by the orchestrator and skills — not loaded into task agent context. |
| `AGENT.md` | Class context for task agents. Describes what this class of work is, key domain concepts, shared conventions, and anything a task agent needs to understand its broader context. **Loaded into every task session within this class.** |
| `requirements.txt` | Class-level Python dependencies shared across tasks in this class. |
| `tools/` | Class-level shared tools (e.g., a Chase statement parser shared across all treasury journal entries). |

**`.class.yaml`** is the orchestration spec for the class:

```yaml
# treasury/.class.yaml
schema_version: 1
name: Treasury
description: Cash management, banking relationships, and financing activities.

manifest:
  - task: monthly-bank-fees
    order: 1
    enabled: true
    period_format: monthly          # see Section 10.2 for formats (default: monthly)
    # anchor omitted → defaults to first_monday

  - task: zba-entries
    order: 1
    enabled: true
    # period_format defaults to monthly when omitted
    # anchor defaults to first_monday when omitted

  - task: bank-reconciliation
    order: 2
    enabled: true
    anchor: first_wednesday         # see Section 10.3 for anchor values
```

The manifest is what an orchestrator reads. Today a human picks a task. Tomorrow an orchestrator agent reads `.class.yaml` and processes it phase by phase — all order-1 tasks (monthly-bank-fees, zba-entries) run in parallel, and once all phase 1 tasks complete, order-2 tasks (bank-reconciliation) start. No phase 2 task runs until every phase 1 task is done. Each task gets a fresh sub-agent that reads the task folder and executes.

**`AGENT.md`** is the class context that flows down to task agents. It describes what this class of work is — domain concepts, shared conventions, key contacts, anything a task agent needs to understand its broader context. Unlike `.class.yaml` (which is orchestration machinery), `AGENT.md` is written for the agent that *executes* tasks. The `/onboard` skill populates it initially; it evolves as the class matures.

Note: `enabled` in `.class.yaml` is **membership** — is this task part of the active roster? Status is tracked at the task level in `status.yaml` (execution state: not_started, in_progress, review_ready, blocked, done, abandoned). Class-level status is computed on the fly by `/status`, which reads all task `status.yaml` files and derives a rollup.

**Manifest fields:**

| Field | Purpose |
|-------|---------|
| `task` | Folder name (kebab-case). Must match a subdirectory with SKILL.md. |
| `order` | Execution phase. Tasks with the same `order` value run in parallel. All tasks in phase N must complete before any phase N+1 task starts. The orchestrator processes phases strictly sequentially — `order` is authoritative. |
| `enabled` | `true` or `false`. Only enabled tasks are executed by the orchestrator. Set to `false` to pause a task without removing it from the manifest. |
| `period_format` | Period naming convention for this task. Values: `monthly` (default), `weekly`, `quarterly`, `adhoc`. See Section 10.2 for format strings. Omit to use `monthly`. |
| `anchor` | Day-of-week anchor for when this task should be triggered within its period cycle. Values: `first_monday` (default), `first_tuesday` .. `first_friday`, `last_monday` .. `last_friday`, `monday` .. `sunday`. See Section 10.3 for details. Omit to use `first_monday`. Set during `/onboard`. |

**Who writes `.class.yaml` and when:**

| Event | What changes | Who writes |
|-------|-------------|------------|
| `/onboard` completes | New task entry added to manifest (`enabled: true`) | The `/onboard` skill |
| User pauses a task | `enabled: false` | Agent (via conversation) |
| User retires a task | Entry removed from manifest | Agent (via conversation) |
| Task order changes | `order` updated | Agent (via conversation) or orchestrator |

`.class.yaml` changes **rarely** — only when the roster of tasks changes, not during normal execution cycles. `anchor` is set once during `/onboard` and updated only if the user requests a schedule change.

**Period advancement mechanism:** Tasks reset automatically when their next anchor date arrives. `check-periods.py` is a scheduled script (cron, early morning — e.g., 6am — when no agent sessions are active) that walks the hierarchy, reads each terminal task's `done_at` timestamp and `anchor` field, and resets tasks whose next period is due. `check-periods.py` writes `status.yaml` directly (not through `set-status.py`) as an infrastructure script. See Section 6.6 for details.

| Event | What changes | Who writes |
|-------|-------------|------------|
| Scheduled `check-periods.py` detects a task's next anchor has arrived | Task `status.yaml` resets to `not_started` with new period | `check-periods.py` (direct write) |

**Who writes task-level `status.yaml`:**

There are two authorized writers for `status.yaml`, each serving a different role:

- **`set-status.py`** — the **agent/skill gateway**. All agent-initiated status changes — from `/start`, `/done`, and `/onboard` — go through this script. It validates that the requested transition is legal before writing.
- **`check-periods.py`** — the **infrastructure scheduler**. Runs as a cron job (no agent session), writes `status.yaml` directly when resetting terminal tasks for a new period. This is the only non-agent writer.

**Agent transitions via `set-status.py`:**

| Caller | Calls | Transition |
|--------|-------|------------|
| `/start` skill | `set-status.py in_progress` | `not_started → in_progress` |
| `/start` skill | `set-status.py in_progress` | `in_progress → in_progress` (idempotent — crash recovery) |
| `/start` skill | `set-status.py in_progress` | `review_ready → in_progress` (human rejects draft, re-execute) |
| `/start` skill | `set-status.py review_ready` | `in_progress → review_ready` (draft ready for human review) |
| `/start` skill | `set-status.py blocked "reason"` | `in_progress → blocked` (populates `issues`) |
| `/done` skill | `set-status.py done` | `review_ready → done` (clears `issues`) |
| `/start` skill | `set-status.py not_started` | `blocked → not_started` (retry) |
| `/start` skill | `set-status.py abandoned "reason"` | `blocked → abandoned` (records reason in `issues`) |

**Infrastructure transitions (direct writes by `check-periods.py`):**

| Event | Transition |
|-------|------------|
| Next anchor date arrived | `done → not_started` (new period) |
| Next anchor date arrived | `abandoned → not_started` (new period) |

## 3.4 Task Level

The task is where the user lives. Each task is a self-contained work folder with everything an agent needs to execute: procedure, learning history, tools, and period-organized work.

**Key files:**

| File | Purpose |
|------|---------|
| `SKILL.md` | The operating manual. What this task produces, where data comes from, step-by-step procedure, validation rules, contacts. A fresh agent instance reads this and executes. |
| `learned.md` | Accumulated learnings. Review history, amount patterns, what didn't work, open questions. Updated after every review cycle via `/done`. |
| `status.yaml` | Current **execution state** for this period. Not to be confused with `enabled` in `.class.yaml` (which is membership). See write-path table below. |
| `tools/` | Task-specific Python scripts for data transformation and validation. |
| `requirements.txt` | Task-specific Python dependencies. |
| `periods/` | Period-organized work directories, each containing `data/` (inputs), `workpapers/` (outputs), and `review-notes/` (feedback). |

**The task lifecycle:**

1. **Onboard** (`/onboard`) — The mechanism for bringing human knowledge into the agent's world. A human preparer knows how to do a task — what to check, where to get data, what the output should look like, what goes wrong. `/onboard` is the structured conversation that extracts that knowledge and writes it into agent-accessible files: SKILL.md (procedure), learned.md (patterns and edge cases), and tools/ (automation scripts). The output is validated against real data with a dry run that reaches `review_ready`. The user then runs `/done` in the same conversation to complete the first period — capturing learnings, setting `done`, and archiving to Drive. Once complete, a fresh agent can execute the task without the human's involvement.

2. **Start** (`/start`) — The recurring execution cycle. A fresh agent reads SKILL.md and learned.md, pulls data, runs tools, produces a draft in `periods/{period}/workpapers/`. The agent reports what was prepared, key numbers, and any issues. On success, sets `status.yaml` to `review_ready` — the draft is ready for human review. On failure, sets `status.yaml` to `blocked`. `/start` also handles recovery: if the task is `blocked`, the human can retry (→ `not_started`) or abandon (→ `abandoned`). If the task is `review_ready` and the human rejects the draft, `/start` moves it back to `in_progress` for re-execution. If the task is stuck `in_progress` from a crashed session, `/start` re-enters `in_progress` idempotently.

3. **Done** (`/done`) — After human review. `/done` runs in the **same conversation** as the preceding `/start` or `/onboard` — it does not load context independently, relying on the active conversation's context. `/done` sets the task status to `done` via `set-status.py`. It processes review feedback: updates `learned.md` with observations from the current cycle, proposes `SKILL.md` changes if the procedure itself was wrong (with human approval), fixes output if the human found issues. `/done` also archives the completed period to Google Drive via `archive-period.py`. The folder gets smarter each cycle. `/done` can only be called when status is `review_ready`.

4. **Status** (`/status`) — Human orchestrator's dashboard. Run from a **class directory**. Reads all task-level `status.yaml` files and computes the class rollup on the fly, presenting a human-readable summary of class progress. Read-only — no side effects.

**Example `/status` output:**
```
Treasury — March 2026 — In Progress (2/3 done)
  ✓ monthly-bank-fees    done
  ✓ zba-entries          done
  ✗ bank-reconciliation  blocked: "Chase API returned 401 — token expired"
```

**Fresh agent per task.** Each execution gets a fresh Claude instance. The folder is the memory, not the agent. Claude reads the docs, runs the tools, produces output, and terminates. Nothing carries over except what's written to the folder.

**Task-level file authority:**

The two core task files have different authority models reflecting their risk profiles:

| File | Who writes | Review required | Self-managed |
|------|-----------|----------------|-------------|
| `learned.md` | Agent (during `/done`) | No | Yes — agent consolidates, prunes, and restructures freely |
| `SKILL.md` | Agent (proposes during `/done`) | Yes — human (MVP) or orchestrator (future) approves | No |

**`learned.md`** uses a four-section structure. `init-task.py` provides a starting template with anchor headings (`## Review History`, `## Patterns`, `## What Didn't Work`, `## Open Questions`) that the agent is free to restructure as the task evolves. The anchor headings exist so the future orchestrator (Section 7.2) can locate key sections when reviewing task output against learned patterns.

**Structured delta convention.** Entries under `## Patterns` and `## What Didn't Work` may carry optional metadata:

```markdown
## Patterns

- **Monthly fees typically $12,000–13,000**
  Confirmed: 4 | Contradicted: 1 | First seen: 2025-09
  Used for: validating draft totals against expected range
```

Counters (`Confirmed`, `Contradicted`, `First seen`) are optional metadata — useful for tracking confidence but not required on every entry.

The agent updates `learned.md` during `/done` with observations from the current cycle. When the file gets long (guideline: ~150 lines), the agent consolidates — merging related entries, removing low-value patterns, and summarizing verbose notes.

**Contradiction handling:** When a pattern is contradicted, the agent uses domain judgment to decide whether the contradiction represents an edge case, a data error, or a genuinely shifting pattern. Counters inform; they do not decide.

A bad `learned.md` entry costs one cycle — it's low-stakes.

The structure is seeded by `init-task.py`'s template and maintained by the `/done` skill's instructions to the agent.

**`SKILL.md`** changes are high-stakes — a bad procedure change breaks every future cycle. During `/done`, if the agent determines the procedure itself was wrong (not just the data), it *proposes* changes to `SKILL.md` and presents them for approval. In MVP, the agent presents the proposed diff in the Cowork conversation and the human approves or rejects verbally — this is a convention, not an enforced gate. In future state, the orchestrator reviews `SKILL.md` diffs before applying them.

**Who writes `status.yaml` and when:**

All `status.yaml` writes go through `set-status.py` (see Section 5.2.2). The script validates transitions — invalid transitions are rejected.

| Event | `status` becomes | Who calls `set-status.py` |
|-------|-----------------|--------------------------|
| `/start` begins executing | `in_progress` | The `/start` skill |
| `/start` re-enters after crash | `in_progress` (idempotent no-op) | The `/start` skill |
| Human rejects draft, runs `/start` | `in_progress` (from `review_ready`) | The `/start` skill |
| `/start` completes successfully | `review_ready` | The `/start` skill |
| `/start` fails | `blocked` | The `/start` skill |
| `/done` after human review | `done` | The `/done` skill |
| Human says "retry" after blocked | `not_started` | The `/start` skill |
| Human says "abandon" after blocked | `abandoned` | The `/start` skill |

`status.yaml` changes **frequently** — every execution cycle. It is the handoff between the agent that runs the task and whoever (human or orchestrator) reviews it.

**Task-level `status.yaml` schema:**

```yaml
schema_version: 1
period: "2026-03"
status: done               # not_started | in_progress | review_ready | blocked | done | abandoned
issues: []                 # populated on error with details; cleared on success
done_at: "2026-04-07T14:30:00Z"  # timestamp when status reached done or abandoned; null otherwise
```
