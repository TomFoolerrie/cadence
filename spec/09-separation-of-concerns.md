# Separation of Concerns

| Layer | What | Who Manages | User Touches |
|-------|------|-------------|--------------|
| **Plugin internals** | Skills (/onboard, /start, /done, /status), scripts, plugin manifest | Plugin system (cached in `~/.claude/plugins/`) | No |
| **Root context** | AGENT.md (root), global tools, global dependencies | Human (initial setup) + agent (maintenance) | Once (setup) |
| **Classes** | .class.yaml, AGENT.md, class tools, class dependencies | Agent (via conversation) + orchestrator (future) | Navigational + status checks |
| **Tasks** | SKILL.md, learned.md, status.yaml, tools, periods | Agent (executes) + human (reviews) | **This is where the user lives** |
| **Period work** | data/, workpapers/, review-notes/ | Agent (creates) + human (provides source data via Cowork UI, reviews outputs) | Per cycle |

The key separation: the **plugin** lives in the plugin cache and provides the skills and scripts. The **hierarchy** lives on the user's computer as root/classes/tasks. The **agent** is the bridge — it executes tasks on behalf of the user, and the user interacts through conversation and review.

## 10.1 The "Only Claude Writes" Rule

All structural and state modifications to the hierarchy — SKILL.md, learned.md, status.yaml, .class.yaml, tools — flow through Claude sessions and the scripts Claude invokes. The **end user** (the accountant — not a coder) never edits files directly; they interact exclusively through skills (`/onboard`, `/start`, `/done`, `/status`) and conversational review. The **developer** (who builds and maintains the plugin) *can* hand-edit files when needed — see "Developer escape hatch" below. Scripts are authorized writers because Claude invokes them — they are extensions of Claude's execution, not independent actors.

**`status.yaml` has two authorized writers, each with a distinct role:**

- **`set-status.py`** — the **agent/skill gateway**. All agent-initiated status changes — from `/start`, `/done`, and `/onboard` — go through this script. It validates state transitions before writing. This is the strongest invariant for agent-initiated changes.
- **`check-periods.py`** — the **infrastructure scheduler**. Runs as a cron job (early morning, e.g., 6am — when no agent sessions are active), writes `status.yaml` directly when resetting terminal tasks for a new period. This is the only non-agent writer.

The separation is deliberate: agents go through the state machine enforcer (`set-status.py`), while the infrastructure scheduler operates outside of agent sessions and manages lifecycle transitions (terminal → `not_started`) that agents cannot perform.

This is the foundational rule that makes the architecture reliable:

- Eliminates concurrent edit conflicts between humans and agents.
- Ensures every change has a git commit and audit trail.
- Means the agent can trust that files are in the state it last left them.

**The critical invariant** is `status.yaml` and `.class.yaml` consistency. These are the files the orchestrator and skills read to make decisions — if they're wrong, the system makes wrong decisions. Class-level status is computed on the fly by the `/status` skill from task-level `status.yaml` files. Hand-edits to `SKILL.md` or `learned.md` are safe by comparison: the agent reads them fresh each session and adapts. See Section 3.4 ("Task-level file authority") for the full authority model.

**In practice:** Review feedback is given verbally during a `/done` session — Claude writes the review notes and updates learned.md. Corrections to SKILL.md or tools go through a Claude session. Source documents (bank statements, exports) are provided by the human to Claude via the Cowork UI file attachment. Claude places them in `periods/{period}/data/`. The user does not write directly to the filesystem — even data inputs flow through a Claude session.

**Developer escape hatch:** Plugin *developers* (not end users) can hand-edit files directly — it's just a filesystem. The agent picks up their changes on the next session. But this is an escape hatch for plugin maintenance and debugging, not the normal end-user workflow. The end user's path is always through skills and conversation. At scale (see Open Questions, item 7: Multi-user and remote collaboration), write-scope enforcement and governance files would prevent unauthorized edits.

## 10.2 Agent Write Scope

Each Claude agent is **write-scoped to its own working level**, with **read access to the entire hierarchy**. This prevents agents from accidentally modifying files outside their responsibility.

| Agent context | Write scope | Read scope |
|--------------|-------------|------------|
| Task agent (during `/start`, `/done`) | Task folder and below (`{task}/`) | Entire hierarchy (root, class, task) |
| Class agent (during `/onboard` task-level) | Class folder and below (`{class}/`) | Entire hierarchy |
| Root agent (during `/onboard` class-level) | Engagement root and below | Entire hierarchy |

**Key rules:**

- A task agent in `treasury/monthly-bank-fees/` can read `root/AGENT.md` and `treasury/AGENT.md` but cannot write to them. It writes only within `treasury/monthly-bank-fees/`.
- Scripts invoked by the agent (e.g., `set-status.py`, `init-period.py`, `init-task.py`) operate with their own filesystem permissions and can write wherever their contracts specify. Scripts are infrastructure — they are not bound by the agent's write scope.
- `/onboard` (task-level) needs class-level write scope because it adds the new task to `.class.yaml`'s manifest (Step 8). This is appropriate — the onboarding agent operates from the class directory.
- The agent must never directly edit `status.yaml` — all status transitions go through `set-status.py`. The agent must never directly edit `.class.yaml` manifest entries outside of `/onboard`.

This constraint is **configured on the agent**, not enforced by the filesystem. It is a permission boundary that prevents task agents from interfering with each other or with class/root-level configuration.

## 10.3 Period Naming Convention

Period format is **configurable per task** via the `period_format` field in `.class.yaml` (see Section 3.3, Manifest fields). The default is `monthly`. These formats define the **directory names** used by `init-period.py` under each task's `periods/` folder.

| Format | Directory Pattern | Regex (validated by `init-period.py`) | Example Directory |
|--------|-------------------|---------------------------------------|-------------------|
| `monthly` | `YYYY-MM` | <code>^[0-9]{4}-(0[1-9]&#124;1[0-2])$</code> | `periods/2026-03/` |
| `weekly` | `YYYY-WNN` | <code>^[0-9]{4}-W(0[1-9]&#124;[1-4][0-9]&#124;5[0-3])$</code> | `periods/2026-W12/` |
| `quarterly` | `YYYY-QN` | `^[0-9]{4}-Q[1-4]$` | `periods/2026-Q1/` |
| `adhoc` | any string | *(no validation)* | `periods/year-end-true-up/` |

`init-period.py` reads the task's `period_format` from the parent class's `.class.yaml` manifest and validates accordingly. If the task is not found in the manifest or `period_format` is omitted, it defaults to `monthly`. These formats are filesystem paths. `init-period.py` validates the period string against the task's `period_format` before creating the directory.

- `status.yaml` stores the current period string in whatever format the task uses.
- The `/start` skill creates the period directory via `init-period.py` if it doesn't exist.
- Within a single class, different tasks can use different period formats (e.g., monthly JEs alongside a quarterly reconciliation).

## 10.4 Anchor (Scheduling)

The `anchor` field in `.class.yaml` defines **when** a task should be triggered within its period cycle. It is separate from `period_format` (which defines how to **name** the period folder). `anchor` is set during `/onboard` and lives on each task in the manifest.

**Default:** `first_monday` — the first Monday after the period ends. Omitting `anchor` uses this default.

| Pattern | Meaning | Use case |
|---------|---------|----------|
| `first_monday` .. `first_friday` | First occurrence of that weekday after the period ends | Monthly/quarterly tasks (e.g., close starts first Monday of the new month) |
| `last_monday` .. `last_friday` | Last occurrence of that weekday before the period ends | Pre-close tasks (e.g., preliminary reconciliation last Friday of the month) |
| `monday` .. `sunday` | Every occurrence of that weekday within the period | Weekly tasks (e.g., cash position every Monday) |

**MVP behavior:** `anchor` is **advisory**. The human reads it as a scheduling reminder when `/status` displays the class dashboard. The human still invokes `/start` manually — the anchor tells them *when* they should.

**Future behavior:** The orchestrator reads `anchor` to compute the actual trigger date for automated execution. For `first_monday` with a monthly period ending 2026-03-31, the trigger date is 2026-04-07 (first Monday in April). Holiday handling is a future concern — MVP relies on human judgment.

**`/onboard` sets the anchor.** During the task onboarding interview, the agent asks: "When does this task typically run?" and maps the answer to an anchor value. If the user says "first Monday after month-end" or doesn't have a strong preference, it stays at the default.

**Example `/status` output with anchors:**
```
Treasury — March 2026 — Done (3/3 done)
  ✓ monthly-bank-fees    done  Apr 7    next due: first_monday (May 5)
  ✓ zba-entries          done  Apr 7    next due: first_monday (May 5)
  ✓ bank-reconciliation  done  Apr 9    next due: first_wednesday (May 7)
```

When `check-periods.py` resets tasks (e.g., on May 5):
```
Treasury — April 2026 — In Progress (0/3 done)
  · monthly-bank-fees    not_started   anchor: first_monday
  · zba-entries          not_started   anchor: first_monday
  ✓ bank-reconciliation  done          next due: first_wednesday (May 7)
```
