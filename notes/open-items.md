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
| 10 | ~~Test `/start` flow (second period onward)~~ | Done | Dry run 2 (2026-03-28): `/start` for 2026-03 worked end-to-end. `check-periods.py` reset the task, `start-setup.py` set up the period, tool produced correct workpapers, status reached `review_ready`. |
| 11 | Test `/done` with corrections (only tested approved path) | Next | |
| 13 | Finish `archive-period.py` | Medium | Script is a stub — checks Google Drive credentials then exits 2. `/done` treats this as non-blocking. |
| 18 | Update skills to work from engagement root | Next | Cowork sessions must mount from engagement root. Skills currently assume cwd is class/task dir. `/status` needs `cd <class>/`. `/start` and `/done` need `cd <class>/<task>/`. `/onboard` class-level works; task-level needs navigation from root. |
| 19 | Git operations in Cowork sandbox | Investigate | Dry run 1 reported git failures due to sandbox lock file deletion restriction. But dry run 2 produced 4 clean commits in the sandbox. Behavior may be intermittent or depend on sandbox configuration. Needs more observation. |
| 20 | AGENT.md not populated during onboard | Next | Dry run 2: AGENT.md left as blank template (entity name, FYE, materiality all empty). `.context-root` engagement name also empty. Onboard SKILL.md should prompt user to fill in entity details. |

## Post-Dry-Run 2 Review (2026-03-28)

### What Worked

Full lifecycle completed in Cowork sandbox: `/onboard` → `/done` (approved 2026-02) → `check-periods.py` auto-reset → `/start` (2026-03) → `review_ready`. Four clean git commits.

- **Script gating held.** All scaffolding went through scripts. Write scope enforcement prevented direct YAML manipulation. The "hard boundaries" strategy from dry run 1 is validated.
- **Tool building deferred until real data.** SKILL.md change (defer tools to Step 7b) worked — agent waited for CashPro CSV before building `categorize_fees.py`. Tool matched SKILL.md procedure exactly.
- **Workpapers correct.** Both periods produced balanced JEs ($998.25 for 2026-02, $1,017.75 for 2026-03). All rows categorized, no "Other" bucket items.
- **`learned.md` populated.** Review history, confirmed patterns, and anticipatory failure modes recorded after first period.
- **`check-periods.py` triggered correctly.** Detected anchor passed, reset task for new period.

### Issues Found

1. **AGENT.md left blank** — onboard never prompted user to fill in entity details (legal name, FYE, materiality, key systems, primary contact). `.context-root` engagement name also empty. Task agents won't have entity context. → Item 20.
2. **Git worked in sandbox** — contradicts dry run 1 findings (Item 19). Either the sandbox permissions vary between sessions or the lock file issue is intermittent. Downgraded Item 19 to "Investigate."
3. **Sandbox path issues fixed same-day** — `.resolve()` → `.absolute()` and venv system pip fallback resolved the Cowork compatibility issues (Item 17).

### Verdict

The core system works. The full `/onboard` → `/done` → `/start` cycle ran successfully with correct output. Remaining gaps are ergonomic (AGENT.md prompting) not structural.

---

## Post-Dry-Run Review (2026-03-26)

### Review Summary

The dry run surfaced exactly the right class of failure — agent bypassing infrastructure scripts — at the right time, before building more on top of a weak foundation. The proposed fixes follow a coherent philosophy: **don't add more instructions, add harder boundaries.**

The three critical fixes form a triangle:
1. **Write scope enforcement** — hard permission boundaries that prevent direct YAML/directory manipulation
2. **Script gating of all YAML state** — `edit-class-yaml.py` closes the last unguarded mutation path
3. **Inline first-period execution with script guardrails** — onboard executes the first period directly (not via `/start`) but all YAML mutations go through scripts. Write scope + script gating solve mode-switching; `/start` delegation proved unnecessary once the hard boundaries were in place.

### Key Insight

The root cause analysis (see `dry-run-2026-03-25.md`, "Root Cause Analysis" section) correctly identifies that the problem isn't insufficient instructions — it's a fundamental mode-switching issue with long-running agent conversations. After 30 minutes of direct file creation during the interview/builder phases, the agent cannot reliably switch to "use scripts for everything" mode. The fixes address the root cause (hard boundaries + delegation), not the symptom (more instructions).
