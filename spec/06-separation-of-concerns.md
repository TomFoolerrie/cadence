# Separation of Concerns

| Layer | What | Who Manages | User Touches |
|-------|------|-------------|--------------|
| **Plugin internals** | Skills (/onboard, /start, /done, /status), scripts, plugin manifest | Plugin system (cached in `~/.claude/plugins/`) | No |
| **Root context** | AGENT.md (root), global tools, global dependencies | Human (initial setup) + agent (maintenance) | Once (setup) |
| **Classes** | .class.yaml, AGENT.md, class tools, class dependencies | Agent (via conversation) + orchestrator (future) | Navigational + status checks |
| **Tasks** | SKILL.md, learned.md, status.yaml, tools, periods | Agent (executes) + human (reviews) | **This is where the user lives** |
| **Period work** | data/, workpapers/, review-notes/ | Agent (creates) + human (provides source data via Cowork UI, reviews outputs) | Per cycle |

The key separation: the **plugin** lives in the plugin cache and provides the skills and scripts. The **hierarchy** lives on the user's computer as root/classes/tasks. The **agent** is the bridge — it executes tasks on behalf of the user, and the user interacts through conversation and review.

## 6.1 The "Only Claude Writes" Rule

All structural and state modifications to the hierarchy — SKILL.md, learned.md, status.yaml, .class.yaml, tools — flow through Claude sessions and the scripts Claude invokes. The **end user** (the accountant — not a coder) never edits files directly; they interact exclusively through skills (`/onboard`, `/start`, `/done`, `/status`) and conversational review. The **developer** (who builds and maintains the plugin) *can* hand-edit files when needed — see "Developer escape hatch" below. Scripts are authorized writers because Claude invokes them — they are extensions of Claude's execution, not independent actors.

**`status.yaml` has two authorized writers, each with a distinct role:**

- **`set-status.py`** — the **agent/skill gateway**. All agent-initiated status changes — from `/start`, `/done`, and `/onboard` — go through this script. It validates state transitions before writing. This is the strongest invariant for agent-initiated changes.
- **`check-periods.py`** — the **infrastructure scheduler**. Runs as a cron job (early morning, e.g., 6am — when no agent sessions are active), writes `status.yaml` directly when resetting terminal tasks for a new period. This is the only non-agent writer.

The separation is deliberate: agents go through the state machine enforcer (`set-status.py`), while the infrastructure scheduler operates outside of agent sessions and manages lifecycle transitions (terminal → `not_started`) that agents cannot perform.

This is the foundational rule that makes the architecture reliable:

- Eliminates concurrent edit conflicts between humans and agents.
- Ensures every change has a git commit and audit trail.
- Means the agent can trust that files are in the state it last left them.

**The critical invariant** is `status.yaml` and `.class.yaml` consistency. These are the files the orchestrator and skills read to make decisions — if they're wrong, the system makes wrong decisions. Class-level status is computed on the fly by the `/status` skill from task-level `status.yaml` files. Hand-edits to `SKILL.md` or `learned.md` are safe by comparison: the agent reads them fresh each session and adapts. See `02-architecture.md` Section 4 ("Task Level") for the full authority model.

**In practice:** Review feedback is given verbally during a `/done` session — Claude writes the review notes and updates learned.md. Corrections to SKILL.md or tools go through a Claude session. Source documents (bank statements, exports) are provided by the human to Claude via the Cowork UI file attachment. Claude places them in `periods/{period}/data/`. The user does not write directly to the filesystem — even data inputs flow through a Claude session.

**Developer escape hatch:** Plugin *developers* (not end users) can hand-edit files directly — it's just a filesystem. The agent picks up their changes on the next session. But this is an escape hatch for plugin maintenance and debugging, not the normal end-user workflow. The end user's path is always through skills and conversation. At scale (see Open Questions, item 7: Multi-user and remote collaboration), write-scope enforcement and governance files would prevent unauthorized edits.

## 6.2 Agent Write Scope

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

### Write Scope Enforcement

Write scope is not just a documented convention — it is enforced via auto-generated `.claude/settings.json` files at each level of the hierarchy. When init scripts scaffold a task, class, or engagement root, they generate a settings file that configures the agent's write permissions as a hard boundary.

**Task-level config** (generated by `init-task.py`, lives at `{task}/.claude/settings.json`):

```json
{
  "permissions": {
    "allow": ["Read", "Write(./**)"],
    "deny": ["Write(../**)", "Write(./status.yaml)"]
  }
}
```

The task agent can write to SKILL.md, learned.md, tools/, periods/ — but cannot directly edit `status.yaml` (must use `set-status.py`) or any file above its directory. Scripts invoked via `Bash` are not restricted by `Write` permissions — they run as subprocesses with their own filesystem access.

**Class-level config** (generated by `init-class.py`, lives at `{class}/.claude/settings.json`):

```json
{
  "permissions": {
    "allow": ["Read", "Write(./**)"],
    "deny": ["Write(../**)", "Write(./.class.yaml)"]
  }
}
```

The class agent can write anywhere inside `{class}/` — including new task subdirectories and their `status.yaml` via scripts — but cannot directly edit `.class.yaml` (must use `edit-class-yaml.py`) or write to root level.

**Root-level config** (generated by `init-engagement.py`, lives at `{root}/.claude/settings.json`):

```json
{
  "permissions": {
    "allow": ["Read", "Write(./**)"]
  }
}
```

Root agent has full write access within the engagement.

**Key patterns:**
- `Write(./**)` — allow writes recursively within current directory
- `Write(../**)` in deny — block writes to parent directories
- `Read` with no path — allow reads everywhere (agents need full hierarchy context)
- Deny rules take precedence over allow
- `Bash` commands (including script invocations) are NOT restricted by `Write` permissions — the Write/Edit scope only applies to the agent's direct file editing tools

**Why enforcement matters:** The dry run proved that instructions alone don't work — the agent bypassed `init-period.py` and hand-edited `.class.yaml` despite the skill explicitly saying to use scripts. Write scope enforcement makes it a hard boundary: the agent tries to `mkdir periods/dry-run/` directly and gets permission denied, forcing it to use `init-period.py`. The agent tries to write `.class.yaml` and gets permission denied, forcing it to use `edit-class-yaml.py`. Scripts still work because they have their own filesystem permissions. This is defense in depth: instructions tell the agent what to do, write scope prevents it from doing anything else.

Period naming conventions and anchor scheduling are defined in `04-scaffolding.md` alongside the `init-period.py` and `check-periods.py` scripts that use them.
