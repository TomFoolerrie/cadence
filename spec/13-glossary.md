# Glossary

> Quick reference for terms used throughout this spec.

---

| Term | Definition |
|------|-----------|
| **Root** | The top-level engagement folder. Contains `.context-root` (a YAML file with `engagement` and `schema_version` fields) and `AGENT.md`. Provides entity context loaded into every session. |
| **Class** | A group of related work (e.g., treasury, reporting, collections). Contains `.class.yaml` (orchestration manifest) and `AGENT.md` (class context for agents). |
| **Task** | An individual unit of work within a class (e.g., monthly-bank-fees). Contains SKILL.md, learned.md, status.yaml, tools/, and periods/. This is where the user lives. |
| **Engagement** | The entity or client being worked on. Defined in root-level `AGENT.md`. |
| **Period** | A date-keyed execution cycle within a task (e.g., `2026-03`). The period string refers to the **period being closed**, not the current calendar period — e.g., period `2026-03` is worked on in April (closing March's books). Each period gets its own `data/`, `workpapers/`, and `review-notes/` directories. |
| **Manifest** | The `manifest` section of `.class.yaml`. Lists tasks, their execution order, enabled status, and period format. Read by the orchestrator (future) and skills. |
| **Skill** | A user-facing command (`/onboard`, `/start`, `/done`, `/status`) that composes scripts and agent behavior into a workflow. Skills live in the plugin. |
| **Script** | A Python utility (`load-context.py`, `set-status.py`, `init-class.py`, `init-task.py`, `init-period.py`, `check-periods.py`, `archive-period.py`, etc.) that performs a specific infrastructure operation. Scripts live in the plugin's `scripts/` directory. Skills call scripts; `check-periods.py` runs on a schedule. |
| **Orchestrator** | The agent (human in MVP, automated in future) that coordinates task execution across a class — deciding order, launching sub-agents, reviewing output. |
| **Sub-agent** | A fresh Claude instance launched by the orchestrator to execute a single task. Reads the task folder via `load-context.py --level task` and terminates after execution. |
| **Plugin** | The installable package that provides skills, scripts, and an engagement template. Lives in the plugin cache (`~/.claude/plugins/`). Does not contain the hierarchy — it scaffolds one. |
| **Hierarchy** | The root/class/task folder structure on the user's filesystem. Owned by the user, not the plugin. Any runtime that reads markdown/YAML can execute it. |
| **SKILL.md** | The operating manual for a task. Describes what to produce, where data comes from, step-by-step procedure, and validation rules. Changes require human approval. |
| **learned.md** | Accumulated patterns and review history for a task. Agent-managed. Counters are optional metadata. Agent consolidates when the file gets long. |
| **AGENT.md** | Context file used at both root and class levels. Root-level `AGENT.md` contains entity details (name, fiscal year, materiality, systems). Class-level `AGENT.md` describes what the class covers, key domain concepts, and shared conventions. Consistent naming across levels. Minimal by design — grows organically but stays concise. |
| **status.yaml** | Task-level execution state. Five fields: `schema_version`, `period`, `status`, `issues`, `done_at`. Two authorized writers: `set-status.py` (agent/skill gateway, validates transitions) and `check-periods.py` (infrastructure scheduler, resets terminal tasks directly). |
| **review_ready** | A task status indicating the agent completed execution and produced a draft. Awaits human review (MVP) or orchestrator review (future). Transitions: `in_progress → review_ready` (set by `/start`), `review_ready → done` (set by `/done`), `review_ready → in_progress` (human rejects draft, `/start` re-executes). |
| **.class.yaml** | Orchestration manifest for a class. Declares tasks, execution order, and enabled status. Read by skills and the orchestrator, not loaded into task agent context. |
| **Phase** | A group of tasks with the same `order` value in `.class.yaml`. All tasks in phase N must complete before any phase N+1 task starts. Tasks within a phase can run in parallel. |
| **Blocked** | A task status indicating execution failed. The agent records the reason in `issues[]`. Human investigates and decides to retry or abandon. |
| **Terminal state** | `done` or `abandoned`. A task must reach a terminal state before a new period can begin (prior-period guard). |
| **Anchor** | Day-of-week scheduling field in `.class.yaml` manifest. Defines when a task should trigger within its period cycle (e.g., `first_monday`, `wednesday`). Advisory in MVP; machine-readable for future orchestrator. Default: `first_monday`. |
| **check-periods.py** | Scheduled infrastructure script that walks the hierarchy and resets terminal tasks whose next anchor date has arrived. Writes `status.yaml` directly (not through `set-status.py`). Reads `done_at` + `anchor` + `period_format` per task. Runs as a cron job (early morning, e.g., 6am — when no agent sessions are active). Idempotent. |
| **done_at** | Timestamp field in task-level `status.yaml`. Auto-written by `set-status.py` when status reaches `done` or `abandoned`. Used by `check-periods.py` to calculate when the next period is due. |
| **Prior-period guard** | `init-period.py` checks that status is `in_progress` before creating a new period directory. `/start` sets `in_progress` first, then calls `init-period.py`. This ensures the task is actively being worked before scaffolding a new period. |
| **archive-period.py** | Script called by `/done` after git commit. Uploads completed period's `workpapers/` and `data/` to Google Drive, mirroring the hierarchy structure. |
| **Completion Criteria** | Section in `SKILL.md` defining what artifacts must exist for a task to be considered complete. Populated during `/onboard`. Checked by the agent before setting `review_ready`. |
| **.context-root** | YAML file at the root of an engagement hierarchy. Contains `engagement` (entity name) and `schema_version` fields. Serves as the hierarchy marker. |
| **Cowork** | The UI application where the user interacts with Claude. Source data is provided via Cowork's file attachment UI. |
