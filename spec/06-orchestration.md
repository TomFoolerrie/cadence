# The Orchestration Model

**MVP: The human is the orchestrator.** They pick tasks, run them, review output, and direct Claude between tasks. The class level exists as a grouping mechanism and provides status rollups via `/status`. The data model (`.class.yaml` manifests, phase ordering) is in place for future automation, but nothing reads it for automated execution in MVP.

## 7.1 How It Works Today (MVP)

```
Human:   /status (from treasury/) → reads task-level status.yaml files,
         computes class rollup on the fly, displays class progress dashboard
Human:   "Work on monthly bank fees"
Agent:   Navigates to treasury/monthly-bank-fees/
Human:   /start
Agent:   Reads status.yaml → routes
         → set-status.py in_progress
         → install-deps.py
         → init-period.py 2026-03 (scaffolds period directory, if needed)
         → load-context.py --level task
         → reads SKILL.md, learned.md → executes → produces draft
         → set-status.py review_ready
         → git commit (atomic commit of all changes from /start)
Agent:   "Draft ready for review"
Human:   Reviews draft
Human:   /done → captures learnings in learned.md
         → sets done via set-status.py
         → git commit (atomic commit of all changes from /done)
         → archive-period.py uploads workpapers and data to Google Drive
Human:   "Work on zba entries"
Agent:   Navigates to treasury/zba-entries/
Human:   /start → repeats
Human:   /status → sees updated progress
```

The human is the orchestrator. They decide order, manage dependencies, and navigate to each task folder before invoking `/start`. The working directory IS the task context — there is no natural-language resolution of task names. The `/start` skill calls `load-context.py --level task`, which loads context top-down from the engagement root. `/done` runs in the **same conversation** as `/start` — it does not load context independently. `/status` reads task-level `status.yaml` files directly and computes class progress on the fly, giving the human visibility into what's done, what's next, and what's blocked.

> **Class creation:** Before working on tasks, the user creates classes via `/onboard` from the root level. This runs `init-class.py` to scaffold the class directory and conducts a brief interview to populate AGENT.md. Classes are not pre-built in the engagement template — they're created on demand as the user sets up their workflow.

> **Concurrency note:** In MVP, the human drives one task at a time in a single conversation, so concurrent writes cannot occur. The orchestrator (Section 7.2) addresses concurrency for the automated multi-task case.

## 7.2 How It Works Tomorrow (Future State)

> **Note:** This section describes future capability. The orchestrator agent, its review logic, and automated sub-agent coordination are not part of the MVP. The hierarchy is designed to support this — `.class.yaml`, `status.yaml`, and the error protocol (Section 4) are all in place — but the orchestrator itself is unspecified. MVP is human-as-orchestrator (Section 7.1).

```
Human:   Opens treasury/ in Cowork
Human:   "Run the close"
Orchestrator:  load-context.py --level class --orchestrator loads:
               root/AGENT.md → class/AGENT.md → .class.yaml (including manifest)
Orchestrator:  Reads manifest — phase 1: monthly-bank-fees and zba-entries
               (both order 1) → launches both as parallel sub-agents
Sub-agent 1:   Enters monthly-bank-fees/, load-context.py --level task loads context
               → executes → produces draft → set-status.py review_ready
Sub-agent 2:   Enters zba-entries/, same flow → set-status.py review_ready
Orchestrator:  Both at review_ready → reads their workpapers/
               → reviews output against learned.md patterns and SKILL.md
               → writes review to each task's review-notes/
               → set-status.py done for each task (after review passes)
Orchestrator:  Phase 1 complete → phase 2: bank-reconciliation (order 2)
               → launches sub-agent
Orchestrator:  "Treasury close complete. 3 tasks executed.
                Monthly bank fees: $12,340 (within range). Done.
                ZBA entries: $45,200. Done.
                Bank rec: reconciled, no exceptions. Done.
                All review notes written. Ready for your sign-off."
```

The orchestrator does two things: **coordinates** (reads `.class.yaml`, processes phases strictly sequentially — all tasks in a phase run in parallel, no phase N+1 task starts until every phase N task is done) and **reviews** (reads each task's output and evaluates it against learned patterns). Each sub-agent is a fresh instance that reads its task folder via `load-context.py --level task` and executes independently. Sub-agents set `review_ready` on completion; the orchestrator reviews and sets `done` — mirroring the human's role in MVP.

**Class-level state.** Class-level status is computed on demand — the `/status` skill (and future orchestrator) reads task-level `status.yaml` files directly and computes the rollup on the fly. There is no cached class-level state file. In the orchestrator model, sub-agents write task-level `status.yaml` (via `set-status.py`), and the orchestrator reads those files to determine class progress.

## 7.3 What Makes This Work (Future State)

> **Note:** These architectural properties are designed into the MVP hierarchy but exercised by the orchestrator only in future state.

The hierarchy is designed so that orchestration requires no special infrastructure:

- **One context-loading path.** The orchestrator uses the same `load-context.py` as any agent, with `--level class --orchestrator` to load `.class.yaml` including the manifest. No separate bootstrapping mechanism.
- **`.class.yaml` is the orchestration spec.** The manifest declares tasks and execution order in a machine-readable format. The orchestrator follows the `order` sequence strictly — all tasks in phase N complete before any phase N+1 task starts.
- **Tasks are self-contained.** Each task has everything a sub-agent needs. No external dependencies except the inherited context from root and class.
- **status.yaml is the handoff.** After a sub-agent completes, status.yaml reflects the result. The orchestrator reads it to decide what to do next. Class-level progress is computed on demand from task-level `status.yaml` files.
- **The error protocol (Section 4) governs recovery.** The orchestrator follows the same status transitions as the human-driven flow. Future state may add retry policies on top.
- **The orchestrator reviews, not just coordinates.** It reads workpapers, compares against learned.md patterns, and writes review notes — replacing the human reviewer for routine checks. The human provides final sign-off. *(How the orchestrator validates non-trivial work product — spreadsheets, JE drafts — is an open design question.)*
- **The hierarchy is just folders.** An orchestrator is just another agent that can parse YAML and launch sub-processes. No special runtime, no message bus, no coordination protocol.
