# Open Items

Priorities revised after post-dry-run review (2026-03-26).

> Item numbers are stable IDs (referenced across design docs), sorted by priority — not sequential.

| # | Item | Priority | Notes |
|---|------|----------|-------|
| 1 | Build `init-engagement.py` with git init | Critical | Blocks every skill path. No fallback — fail loud if missing. |
| 2 | Build `edit-class-yaml.py` with enum validation | Critical | Also closes Item 8 (empty description) via `set-description`. |
| 3 | Auto-generate `.claude/settings.json` (write scope) in `init-class.py` and `init-task.py` | Critical | The architectural fix. Instructions failed; permissions won't. |
| 5 | Refactor onboard SKILL.md Step 8 to invoke `/start` instead of reimplementing it | Critical | **Promoted from Medium.** Highest-value simplification — prevents the entire class of "agent bypasses scripts during onboard" problems. Verify `/start` handles first-period case (empty period in status.yaml). |
| 6 | Update onboard SKILL.md Step 9 to use `edit-class-yaml.py` | Medium | Blocked by Item 2. Natural pairing. |
| 4 | Auto-generate `reference.md` (plugin scripts + write restrictions only) in `init-task.py` | Low | **Demoted from Medium.** `load-context.py` already outputs tool paths. Nice-to-have, not load-bearing. Drop "Task-Specific Tools" section from template. |
| 7 | Add "scripts are mandatory" constraint block to onboard SKILL.md | Low | **Demoted from Medium.** Write scope (Item 3) is the real enforcement. This is documentation/belt-and-suspenders, not the primary defense. |
| 8 | Populate `.class.yaml` description during onboard (via `edit-class-yaml.py set-description`) | Minor | Covered by Item 2's script. Just needs a step in onboard skill. |
| 9 | Test Chase PDF parsing (only BofA tested so far) | Medium | |
| 10 | Test `/start` flow (second period onward) | Next | |
| 11 | Test `/done` with corrections (only tested approved path) | Next |

## Post-Dry-Run Review (2026-03-26)

### Review Summary

The dry run surfaced exactly the right class of failure — agent bypassing infrastructure scripts — at the right time, before building more on top of a weak foundation. The proposed fixes follow a coherent philosophy: **don't add more instructions, add harder boundaries.**

The three critical fixes form a triangle:
1. **Write scope enforcement** — hard permission boundaries that prevent direct YAML/directory manipulation
2. **Script gating of all YAML state** — `edit-class-yaml.py` closes the last unguarded mutation path
3. **Delegate onboard dry run to `/start`** — eliminates the mode-switching problem entirely

### Key Insight

The root cause analysis (see `dry-run-2026-03-25.md`, "Root Cause Analysis" section) correctly identifies that the problem isn't insufficient instructions — it's a fundamental mode-switching issue with long-running agent conversations. After 30 minutes of direct file creation during the interview/builder phases, the agent cannot reliably switch to "use scripts for everything" mode. The fixes address the root cause (hard boundaries + delegation), not the symptom (more instructions).
