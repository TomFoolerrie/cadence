# Context Inheritance

Context flows downward through the hierarchy. A task agent automatically sees its class context and root context. Context loading and system management are **separate concerns** handled by different scripts:

- **`load-context.py`** — Pure context assembly. Reads files, prints them to stdout. No side effects. Called by skills that need context.
- **Management scripts** — `init-class.py`, `init-task.py`, `init-period.py`, `install-deps.py`, `check-periods.py`, `archive-period.py`. These have side effects (write files, install packages, upload to Drive).
- **Skills** — Each skill (`/start`, `/onboard`, `/done`, `/status`) composes the scripts it needs. The skill is the orchestrator of these pieces.

**Claude manages all folder navigation.** The user never manually `cd`s into hierarchy directories. Claude knows which level it's operating at because it (or the orchestrator) chose to enter that folder. This eliminates heuristic detection — the level is always known by the caller.

## 5.1 What Gets Loaded at Each Level

**Task level** (`--level task`):
```
root/AGENT.md → class/AGENT.md → SKILL.md + learned.md + status.yaml [+ recovery hint if blocked]
```

**Class level** (`--level class`):
```
root/AGENT.md → class/AGENT.md
```

**Class level as orchestrator** (`--level class --orchestrator`) *(future state)*:
```
root/AGENT.md → class/AGENT.md → .class.yaml (manifest)
```

**Root level** (`--level root`):
```
root/AGENT.md
```

Task agents and class-level agents both receive **`AGENT.md`** (class context written for the executor). Class agents do NOT receive `.class.yaml` by default. The `--orchestrator` flag additionally loads `.class.yaml` including the manifest (task list and order). This keeps non-orchestrator agents focused on *what to do* without exposing manifest details or task ordering they don't need.

## 5.2 Context Loading: `load-context.py`

`load-context.py` is a **pure context assembly script** — it reads files and prints them to stdout. It has no side effects: no file writes, no dependency installation, no state changes. Skills call it when they need to load context for the agent.

**Usage:**
```bash
load-context.py --level <root|class|task> [--orchestrator]
```

The `--level` argument is required. Claude (or the orchestrator launching a sub-agent) always knows what level it's operating at and passes it explicitly. There is no filesystem-based detection of the context level.

**Algorithm:**

```
1. Accept --level argument (required: root, class, or task)
2. Walk up from cwd to engagement root (detected by .context-root YAML file containing `engagement` key)
3. Load context top-down based on --level:
   - root:  root/AGENT.md
   - class: root/AGENT.md → class/AGENT.md
   - task:  root/AGENT.md → class/AGENT.md → SKILL.md + learned.md + status.yaml
3a. If --level is task and status is blocked:
   - Append a recovery hint (see recovery hint table below)
4. Print each file to stdout with section headers
```

**Recovery hints.** When loading context at the task level, if `status.yaml` indicates `blocked`, the script appends a recovery hint after the status output. The hint is a suggestion, not binding — the agent (or human) decides what to do.

| Status | Recovery hint |
|--------|--------------|
| `blocked` | `⚠ Recovery: This task is blocked. Review issues[] and decide — retry (resets to not_started) or investigate further.` |

**Example output** (task-level context with `blocked` status):

```
── status.yaml ──
schema_version: 1
period: "2026-03"
status: blocked
issues: ["Chase API returned 401 — token expired"]

⚠ Recovery: This task is blocked. Review issues[] and decide — retry (resets to not_started) or investigate further.
```

### 5.2.1 Dependency Installation: `install-deps.py`

`install-deps.py` handles Python dependency installation as a **separate management concern**. It walks the hierarchy and installs `requirements.txt` files top-down (global → class → task).

**Usage:**
```bash
install-deps.py
```

Run from any level in the hierarchy. Walks up to the engagement root (via `.context-root`), then installs dependencies top-down. Idempotent — safe to run multiple times.

Runs on Cowork VM using system Python. Dependencies install globally within the VM. Idempotent — safe to run multiple times.

### 5.2.2 Status Transitions: `set-status.py`

`set-status.py` is the **agent/skill gateway** for task-level `status.yaml`. It validates that the requested state transition is legal before writing. If the transition is invalid, the script exits with an error and does not modify the file.

All agent-initiated `status.yaml` writes go through `set-status.py`. The only other writer is `check-periods.py`, an infrastructure script that writes directly when resetting terminal tasks for a new period (see Section 6.6).

**Usage:**
```bash
set-status.py <status> [reason] [--period <period>]
# status: not_started | in_progress | review_ready | blocked | done | abandoned
# reason: optional string, recorded in issues[] for blocked and abandoned states
# --period: optional, writes period field; only valid on not_started → in_progress
```

Run from a task directory (must contain `status.yaml`).

**Valid transitions:**

```
not_started  → in_progress    (/start begins executing)
in_progress  → in_progress    (idempotent — crash recovery)
in_progress  → review_ready   (/start completes — draft ready for review)
in_progress  → blocked        (/start fails)
review_ready → in_progress    (human rejects draft — /start re-executes)
review_ready → done           (/done after human review)
blocked      → not_started    (retry)
blocked      → abandoned      (unrecoverable)
```

All other transitions are rejected. This makes the script the **state machine enforcer** for agent-initiated changes — skills and agents request transitions, `set-status.py` validates and writes. Terminal-to-`not_started` transitions are handled exclusively by `check-periods.py` (Section 6.6).

**Side effects:**
- On `in_progress` (from `in_progress`): no-op — idempotent for crash recovery.
- On `in_progress` (from `review_ready`): clears `issues[]` — draft rejected, re-executing.
- On `done`: clears `issues[]`, sets `done_at` to current timestamp.
- On `review_ready`: clears `issues[]`.
- On `blocked`: populates `issues[]` with the provided reason.
- On `abandoned`: populates `issues[]` with the provided reason, sets `done_at` to current timestamp.
- On `not_started` (from `blocked`): clears `issues[]`, clears `done_at`.

### 5.2.3 Which Skills Call Which Scripts

Each skill composes only the scripts it needs:

| Skill | `load-context.py` | `install-deps.py` | `set-status.py` | `init-period.py` | `archive-period.py` |
|-------|-------------------|-------------------|-----------------|-------------------|----------------------|
| `/onboard` (class) | `--level root` | No | No | No | No |
| `/onboard` (task) | `--level class` (for context) | Yes | Yes (`in_progress`, then `review_ready` or `blocked`) | Yes (scaffolds first period) | No |
| `/start` | `--level task` | Yes | Yes (`in_progress`, then `review_ready` or `blocked`) | Yes (if period doesn't exist) | No |
| `/done` | No | No | Yes (`done`) | No | Yes |
| `/status` | No | No | No | No (computes rollup from task status.yaml files on the fly) | No |
| `check-periods.py` (scheduled) | No | No | No (writes status.yaml directly) | No | No |

**Note:** `check-periods.py` writes `status.yaml` directly when resetting terminal tasks — it does not go through `set-status.py`. `/status` computes class rollup on the fly from task-level `status.yaml` files.

**Note:** `/onboard` (class) also calls `init-class.py` to scaffold the class directory. `/onboard` (task) calls `init-task.py` to scaffold the task folder before executing the first period.

**Why `/done` doesn't load context.** `/done` always runs in the **same conversation** as the preceding `/start` or `/onboard`. The human reviews the draft, then invokes `/done` in that same session. The active conversation provides all the context the skill needs — no independent context loading is required. This is a design constraint: `/done` is not a standalone skill that can be invoked in a fresh session. This applies to the first period (after `/onboard`) and every subsequent period (after `/start`).

The tree walk for finding the engagement root (step 2) uses filesystem detection (presence of `.context-root` with valid YAML containing `engagement` key), but the *context level* is never guessed — it's always declared by the caller. This means the agent always knows:

- What entity it's working for (from root/AGENT.md)
- What class of work this is (from class/AGENT.md, or .class.yaml at class level with --orchestrator)
- Exactly what to do and what's been learned (from SKILL.md + learned.md)

### 5.2.4 Period Archival: `archive-period.py`

`archive-period.py` is called by `/done` after the git commit. It uploads the completed period's `workpapers/` and `data/` directories to Google Drive, mirroring the hierarchy structure: `Drive/Engagement/Class/Task/Period/`.

**Usage:** Run from a task directory (must contain `status.yaml` with `status: done`).

```bash
archive-period.py
```

**Behavior:**

- Reads `status.yaml` to determine the current period.
- Reads `.context-root` to determine the engagement name.
- Uploads `periods/<period>/workpapers/` and `periods/<period>/data/` to Google Drive using the Google Drive API.
- Target Drive path: `<Engagement>/<Class>/<Task>/<Period>/`
- Idempotent — skips upload if the target folder already exists on Drive (checks for existing folder before uploading).
- If upload fails, the agent reports the failure but does **not** change task status. The task remains `done` — archival failure is non-blocking.

**MVP implementation detail:** Requires Google Drive access configured in Cowork (service account or OAuth credentials available to the VM).

## 5.3 Hierarchy Depth Constraint

The hierarchy is exactly three levels deep: **root → class → task**. There is exactly one directory level between the root and each task. `load-context.py` relies on this structure — it walks up from the task's cwd, finds `AGENT.md` in the parent (class), and `.context-root` in the grandparent (root). Nested subdirectories within a class (e.g., `treasury/subcategory/monthly-bank-fees/`) are not supported and will break context loading.

## 5.4 Three-Tier Tool Inheritance

Tools are organized in layers so common logic isn't duplicated:

```
Global    .claude/tools/         — JE formatter, PDF parser
Class     {class}/tools/         — Shared within a class (e.g., Chase parser)
Task      {task}/tools/          — Task-specific transformation logic
```

**Resolution order: task > class > global.** When tools exist at multiple levels with the same name, the most specific level wins. A task-level `validate.py` shadows a class-level `validate.py`. Common logic should live at the highest appropriate level to avoid duplication.

**Resolution mechanism.** `load-context.py --level task` outputs the resolved tool paths in priority order as part of its context assembly:

```
── tools ──
task:   treasury/monthly-bank-fees/tools/
class:  treasury/tools/
global: .claude/tools/
```

The agent uses the first match when a tool name appears at multiple levels. No registry or PATH variable — just an ordered list the agent follows. This is derived from the hierarchy walk that `load-context.py` already performs.

Dependencies follow the same pattern. Global `requirements.txt` for shared libraries, class-level for class-shared, task-level for task-specific. `install-deps.py` installs top-down: global first, class second, task last. Task-level version pins take precedence over class or global pins.
