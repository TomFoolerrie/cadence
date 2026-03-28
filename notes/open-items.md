# Open Items

Priorities revised after second dry run (2026-03-28).

> Item numbers are stable IDs (referenced across design docs), sorted by priority — not sequential.

| # | Item | Priority | Notes |
|---|------|----------|-------|
| 1 | ~~Build `init-engagement.py` with git init~~ | Done | Implemented with git init, .context-root, AGENT.md, .gitignore, .claude/settings.json scaffolding. |
| 2 | ~~Build `edit-class-yaml.py` with enum validation~~ | Done | Gateway for all .class.yaml mutations. Also closes Item 8 (empty description) via `set-description`. |
| 3 | ~~Auto-generate `.claude/settings.json` (write scope) in `init-class.py` and `init-task.py`~~ | Done | Both scripts now generate .claude/settings.json with deny rules for parent paths and protected YAML files. |
| 5 | ~~Refactor onboard first-period execution~~ | Done | **Resolved differently than originally planned.** Instead of delegating to `/start`, first period execution is now inline in onboard with proper sub-steps (8a-8d). Rationale: onboard needs full write scope to iterate on SKILL.md/tools if execution reveals problems; `/start` is a prompt injection (not a sub-agent) so delegation caused mode-switching issues. Script gating (Items 1-3) solved the "agent bypasses scripts" problem directly. |
| 6 | ~~Update onboard SKILL.md to use `edit-class-yaml.py`~~ | Done | Onboard Step 8 calls `edit-class-yaml.py add-task` and `set-description`. |
| 4 | ~~Auto-generate `reference.md` in `init-task.py`~~ | Done | `init-task.py` generates reference.md with write restrictions and plugin script docs. |
| 7 | ~~Add "scripts are mandatory" constraint block to onboard SKILL.md~~ | Done | Constraints section in onboard SKILL.md explicitly requires all scaffolding through scripts. |
| 8 | ~~Populate `.class.yaml` description during onboard~~ | Done | Covered by Item 6 — onboard Step 8 calls `edit-class-yaml.py set-description`. |
| 12 | ~~Redesign anchor system in `check-periods.py`~~ | Done | One-ahead anchor logic, `last_*` anchors, weekend days in `WEEKDAY_MAP`, late-completion guard. Expanded `VALID_ANCHORS` in `edit-class-yaml.py`. 6 new tests. |
| 14 | ~~Script quality fixes~~ | Done | Normalized exit patterns (`sys.exit()` → `return`) in `set-status.py`, `edit-class-yaml.py`, `archive-period.py`, `install-deps.py`. Custom exceptions (`ScriptValidationError`/`ScriptSystemError`) in `edit-class-yaml.py`. Validate-then-write in `init-engagement.py`. `load-context.py` emits `reference.md` for task-level output. |
| 15 | ~~Engagement venv support~~ | Done | `init-venv.py` creates per-engagement venv. `install-deps.py` uses venv pip. `init-engagement.py` creates venv after scaffold. `start-setup.py` calls `init-venv.py` before deps. |
| 16 | ~~Consolidate `/onboard` to 3 script calls~~ | Done | `onboard-setup.py` (context + scaffold), `onboard-register.py` (venv + deps + manifest), `start-setup.py` reuse for first period. Reduced from 7-8 calls. |
| 17 | ~~Cowork sandbox compatibility~~ | Done | `.resolve()` → `.absolute()` in all walk-up functions (4 scripts). Venv init non-fatal in wrapper scripts. `install-deps.py` falls back to system pip. `/onboard` defers tool building until real data arrives. |
| 9 | Test Chase PDF parsing (only BofA tested so far) | Medium | |
| 10 | Test `/start` flow (second period onward) | Next | Dry run 2 (2026-03-28) validated `/onboard` through `review_ready`. Next: complete `/done`, then test `/start` for period 2. |
| 11 | Test `/done` with corrections (only tested approved path) | Next | |
| 13 | Finish `archive-period.py` | Medium | Script is a stub — checks Google Drive credentials then exits 2. `/done` treats this as non-blocking. |
| 18 | Update skills to work from engagement root | Next | Cowork sessions must mount from engagement root. Skills currently assume cwd is class/task dir. `/status` needs `cd <class>/`. `/start` and `/done` need `cd <class>/<task>/`. `/onboard` class-level works; task-level needs navigation from root. |
| 19 | Git operations fail in Cowork sandbox | Next | Sandbox allows read/write but restricts file deletion. Git needs to delete lock files (`.git/index.lock`) during normal operations like `git add`. All skill commits fail silently. Options: (a) skills skip git in sandbox, user commits locally; (b) investigate Cowork sandbox permissions. Git repos should be initialized locally, not from within the sandbox. |

## Post-Dry-Run Review (2026-03-26)

### Review Summary

The dry run surfaced exactly the right class of failure — agent bypassing infrastructure scripts — at the right time, before building more on top of a weak foundation. The proposed fixes follow a coherent philosophy: **don't add more instructions, add harder boundaries.**

The three critical fixes form a triangle:
1. **Write scope enforcement** — hard permission boundaries that prevent direct YAML/directory manipulation
2. **Script gating of all YAML state** — `edit-class-yaml.py` closes the last unguarded mutation path
3. **Inline first-period execution with script guardrails** — onboard executes the first period directly (not via `/start`) but all YAML mutations go through scripts. Write scope + script gating solve mode-switching; `/start` delegation proved unnecessary once the hard boundaries were in place.

### Key Insight

The root cause analysis (see `dry-run-2026-03-25.md`, "Root Cause Analysis" section) correctly identifies that the problem isn't insufficient instructions — it's a fundamental mode-switching issue with long-running agent conversations. After 30 minutes of direct file creation during the interview/builder phases, the agent cannot reliably switch to "use scripts for everything" mode. The fixes address the root cause (hard boundaries + delegation), not the symptom (more instructions).
