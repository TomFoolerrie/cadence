# Test Run Notes — First Dry Run (2026-03-25)

## Setup

- Template: `engagement-template/` copied to `engagement-template-dry-run/`
- Platform: Claude Cowork (web UI), plugin registered under Customize > Personal plugins
- Task: `/onboard` from treasury class → statement-normalization task
- Source data: BofA statement PDF (May 2019), Chase statement as image (not PDF — couldn't parse)

---

## Issues Found

### 1. No git repo initialized (Critical)

The engagement template is just a folder — no `.git/`. Every skill (onboard, start, done) ends with `git add` + `git commit`, so the agent hit errors on every commit step.

**Fix needed:** Build `init-engagement.py` (see design notes below) as the single entry point for creating engagements.

**Decision (post-review):** Do NOT add a `.git/` fallback check in onboard. If `init-engagement.py` is the entry point, a missing `.git/` means the user bypassed setup — better to fail loud with a clear error than silently init a repo mid-skill. One correct path, not three fallbacks.

### 2. `.class.yaml` manifest — wrong enum values (Medium)

The Cowork agent wrote:
```yaml
period_format: "YYYY-MM"                    # Should be: monthly
anchor: "first Monday after month-end"       # Should be: first_monday
```

**Root cause:** No script gates `.class.yaml` manifest writes. The onboard SKILL.md Step 9 shows a YAML template with `<format>` and `<anchor>` placeholders but never lists the valid enum values. The agent guessed with English prose.

**Fix needed:** Build `edit-class-yaml.py` script that validates enum values:
- `period_format`: `monthly`, `weekly`, `quarterly`, `adhoc`
- `anchor`: `first_monday`, `first_tuesday`, ... `last_friday`

This keeps `.class.yaml` gated through scripts, consistent with how `status.yaml` works through `set-status.py`.

### 3. Agent bypassed `init-period.py` (Medium)

The agent manually created `periods/dry-run/` with `data/` and `workpapers/` subdirectories instead of running `init-period.py`. This means:
- No validation that the period string matches the task's `period_format`
- Missing `review-notes/` subdirectory (which `init-period.py` creates)
- Sets a bad precedent — if the agent can freestyle directory creation, the folder structure drifts from spec

**Root cause:** The onboard SKILL.md Step 8 does call `init-period.py`, but the agent apparently created the directories itself during execution instead. Nothing prevents the agent from using `mkdir` directly.

**Fix needed:** This is a discipline issue more than a tooling issue. Options:
- Make `init-period.py` idempotent and have the normalization tool check for it before writing
- Add a validation step that checks period directories match the expected structure
- Emphasize in SKILL.md that period scaffolding MUST go through `init-period.py`

**Decision (post-review):** Write scope enforcement (`.claude/settings.json`) is the real fix here, not more instructions. The agent physically cannot `mkdir` via the Write/Edit tools if permissions deny it. Combined with delegating the dry run to `/start` (which already calls `init-period.py`), this issue is addressed by Items 3 and 5 — no standalone fix needed.

### 4. `.class.yaml` description field empty (Minor)

```yaml
description: ''
```

The onboard interview asks "What does this class cover?" but the answer only goes to `AGENT.md`. The `.class.yaml` `description` field is never populated.

**Fix needed:** Either `edit-class-yaml.py` or a separate step should populate this, or the class-level interview should write to both files.

### 5. `!` backtick syntax caused bash errors (Critical — already fixed)

Commands with placeholders like `<name>` were auto-executed literally by Cowork, causing:
```
syntax error near unexpected token 'newline'
```

**Fixed in this session:** All skill files converted from `!` backtick to regular `bash` code blocks.

---

## What Worked Well

- **Level detection** — `/onboard` correctly detected `.class.yaml` in cwd and routed to task-level flow
- **Deep interview** — Cowork agent followed the interview structure, asked good follow-up questions, captured implicit knowledge
- **SKILL.md quality** — All 6 required sections populated, frontmatter correct, procedure references tools by path
- **learned.md delta format** — Patterns captured with `Confirmed: N | Contradicted: N | First seen:` metadata
- **OCR fallback discovery** — Agent discovered BofA page 2 was image-based, added pytesseract fallback, documented it in learned.md
- **Validation tie-out** — Deposit and withdrawal totals tied to statement summary ($200/$200)
- **Status transitions** — `not_started → in_progress → review_ready → done` all clean
- **`${CLAUDE_PLUGIN_ROOT}`** — Resolved correctly in Cowork's shell environment

---

## Root Cause Analysis: Why the Agent Bypassed Scripts

The task-level onboard flow is **10 steps** doing three fundamentally different jobs:

1. **Interviewer** (Steps 1-4) — Ask questions, understand the work
2. **Builder** (Steps 5-7) — Write files, build tools, install deps
3. **Executor** (Step 8) — Run the task for the first time

By Step 8, the agent has been directly creating and editing files for the entire conversation. It's in "I build things" mode. So when it needs a period directory, it just makes one — it's been making directories and writing files for 30 minutes.

### Specific design issues

1. **"Write as you go" trains the wrong instinct.** Step 4 says "Write answers to the indicated file and section as you go." This puts the agent in direct-edit mode. Then later it's supposed to switch to "use scripts for everything" — but that rule is never stated.

2. **No "scripts are mandatory" constraint.** The constraints section mentions token cost and AGENT.md staying minimal. Nothing says: "All YAML state files and directory scaffolding must go through scripts." The agent doesn't know scripts are guardrails, not suggestions.

3. **Step 9 (manifest) has no script — just raw YAML.** Every other state change has a script. Manifest is the one place the agent is told to hand-edit `.class.yaml`. No validation, no enum list. The agent guesses at values after a long conversation.

4. **Step 8 reimplements `/start`.** The dry run is basically `/start` but inlined. The agent has to do status transitions, period scaffolding, execution, and validation — all from memory of earlier steps. The `init-period.py` call is easy to skip because the agent is deep in execution mode.

### Fix direction

The answer isn't "add more instructions" — that makes the overload worse:
- Add one hard constraint at the top: "Never create directories or modify YAML files directly. Always use the provided scripts."
- Build `edit-class-yaml.py` so there's no hand-editing of `.class.yaml`
- ~~Consider whether~~ Step 8 should invoke `/start` instead of reimplementing it

---

## Design Notes: Agent Write Scope Enforcement

The spec (Section 10.2) already defines write scopes per agent context level, but they're not enforced. The spec says: *"This constraint is configured on the agent, not enforced by the filesystem."* Cowork supports this — we can configure what paths the agent is allowed to write to.

### Write Scope Table (from spec)

| Agent context | Write scope | Read scope |
|--------------|-------------|------------|
| Task agent (`/start`, `/done`) | `{task}/` only | Entire hierarchy |
| Class agent (`/onboard` task-level) | `{class}/` and below | Entire hierarchy |
| Root agent (`/onboard` class-level) | Engagement root and below | Entire hierarchy |

### What This Prevents

If the task agent during `/start` can only write to `{task}/`, it physically **cannot**:
- Hand-edit `.class.yaml` (lives at class level)
- Create directories outside its task folder
- Modify another task's files

It **can** still:
- Write to `periods/{period}/data/` and `periods/{period}/workpapers/` (inside task folder)
- Edit `SKILL.md`, `learned.md` (inside task folder)
- Invoke scripts that write elsewhere (scripts have their own permissions — spec says *"Scripts are infrastructure — they are not bound by the agent's write scope"*)

### Implementation: Auto-generate `.claude/settings.json` on scaffold

Cowork uses the same config format as Claude Code. Write scope is controlled via `.claude/settings.json` with `permissions` and `sandbox` blocks. Each level gets its own settings file auto-generated by the init script.

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
- Deny rules take precedence over allow (first-match-wins)
- `Bash` commands (including script invocations) are NOT restricted by `Write` permissions — the Write/Edit scope only applies to the agent's direct file editing tools

### Why This Is Better Than Instructions

The dry run proved that instructions alone don't work — the agent bypassed `init-period.py` and hand-edited `.class.yaml` despite the skill saying to use scripts. Write scope enforcement makes it a hard boundary:
- Agent tries to `mkdir periods/dry-run/` directly → permission denied → forced to use `init-period.py`
- Agent tries to write `.class.yaml` → permission denied → forced to use `edit-class-yaml.py`
- Scripts still work because they have their own filesystem permissions

This is defense in depth: instructions tell the agent what to do, write scope prevents it from doing anything else.

---

## Design Notes: `edit-class-yaml.py`

Script to gate all `.class.yaml` mutations, matching the `set-status.py` pattern for `status.yaml`.

### CLI Interface

```
edit-class-yaml.py set-description <description>
edit-class-yaml.py add-task <task> --order <N> [--enabled] [--no-enabled] [--period-format <fmt>] [--anchor <anchor>]
edit-class-yaml.py update-task <task> [--order <N>] [--enabled] [--no-enabled] [--period-format <fmt>] [--anchor <anchor>]
edit-class-yaml.py remove-task <task>
```

### Valid Enums

```python
VALID_PERIOD_FORMATS = {"monthly", "weekly", "quarterly", "adhoc"}

VALID_ANCHORS = {
    "first_monday", "first_tuesday", "first_wednesday", "first_thursday", "first_friday",
    "last_monday", "last_tuesday", "last_wednesday", "last_thursday", "last_friday",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
}
```

### Preconditions

- cwd contains `.class.yaml` (exit 1 if missing)
- `.class.yaml` is valid YAML with a `manifest` list (exit 2 if corrupt)
- `add-task`: task not already in manifest, task directory exists with `SKILL.md`
- `update-task`: task exists in manifest, at least one field provided
- `remove-task`: task exists in manifest
- `--order` must be a positive integer
- `--period-format` and `--anchor` must be valid enum values

### Defaults

- `--enabled`: defaults to `true` on `add-task`
- `--period-format`: defaults to `monthly`
- `--anchor`: defaults to `first_monday`
- All fields written explicitly (no omission) to prevent ambiguity

### Exit Codes

- 0: success
- 1: validation error (bad input, invalid enum, task not found/already exists)
- 2: system error (corrupt YAML, filesystem failure)

### Onboard Skill Change

Step 9 changes from raw YAML block to:

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/edit-class-yaml.py add-task <name> --order <N> --period-format <format> --anchor <anchor>
```

Step 4 (class-level) adds after AGENT.md write:

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/edit-class-yaml.py set-description "<description from interview>"
```

---

## Design Notes: `init-engagement.py`

Script to replace manual template copying. Scaffolds a new engagement directory with git initialized.

### Usage

```
init-engagement.py <path> [--name <engagement-name>]
```

### What It Does

1. Creates the directory at `<path>`
2. Writes `.context-root` with engagement name and `schema_version: 1`
3. Writes template `AGENT.md` with entity detail fields
4. Creates `.claude/tools/` directory
5. Writes `.gitignore` (excludes `**/periods/*/data/`, `**/periods/*/workpapers/`, `.context-cache/`, `.DS_Store`)
6. Writes empty `requirements.txt`
7. Runs `git init`
8. Creates initial commit: `[init] <engagement-name>: engagement created`

### Why

Every skill ends with `git add` + `git commit`. Without a git repo, all commits fail silently. This was the #1 issue in the dry run — the agent couldn't commit anything.

---

## Design Notes: Onboard Skill Constraints

Add a hard constraint block near the top of the onboard SKILL.md (both class and task flows):

```markdown
## Constraints

- **Scripts are mandatory.** Never create directories with mkdir or modify YAML files directly.
  All scaffolding goes through `init-*.py` scripts. All YAML state changes go through
  `set-status.py` or `edit-class-yaml.py`. The scripts validate inputs and enforce the schema.
- **Markdown files are the exception.** SKILL.md, learned.md, and AGENT.md are written directly
  by the agent — these are content files, not state files.
```

### Decision: Step 8 should invoke `/start`

The dry run proved that reimplementing `/start` inline is a mistake. By Step 8 the agent has been in "builder" mode for 30 minutes — it's been writing files, installing deps, building tools. Asking it to also remember status transitions, period scaffolding via `init-period.py`, and validation rules from earlier in the document is too much. It just freestyles.

`/start` already handles all of this correctly — status transitions, `init-period.py`, execution, validation. Step 8 should delegate to it instead of reimplementing it. This:
- Removes ~40% of the onboard skill's execution complexity
- Ensures the dry run follows the exact same path as every future period
- Means fixes to `/start` automatically apply to onboarding too

**Action:** Replace Step 8's inline procedure with a single instruction: "Invoke `/start` to execute the first period." Remove all the inlined status/scaffolding/validation steps from onboard.

**Note (post-review):** Verify that `/start`'s period-detection logic handles the first-period case cleanly. After `init-task.py`, `status.yaml` has `period: ''` and `status: not_started` — this is the normal `/start` entry point. Step 1 of `/start` says "If status.yaml period is empty or a new period is needed" it prompts the user. This should work, but needs explicit testing during implementation.

---

## Design Notes: Task-Level `reference.md` (Auto-Generated)

### Problem

The SKILL.md loads once at skill invocation. It contains the full procedure, validation rules, and script paths. But by the time the agent is deep into execution — parsing PDFs, debugging OCR, fixing edge cases — the skill instructions are buried in conversation history. The agent has to remember which scripts to use, what the write restrictions are, and where files go.

The agent saw `python tools/normalize_statements.py --period {period}` once in Step 2. Twenty messages later it's guessing at the command, or just writing files directly.

### Solution: `reference.md` at task level

A simple reference file generated by `init-task.py`. Not auto-loaded — the agent reads it when needed. The SKILL.md mentions it: "See `reference.md` for available commands."

This is a reference card, not instructions. The SKILL.md tells the agent *what to do*. `reference.md` reminds it *how*.

### Template (generated by `init-task.py`)

```markdown
# reference — {task-name}

## Write Restrictions
- `status.yaml` — Do not edit directly. Use: `python ${CLAUDE_PLUGIN_ROOT}/scripts/set-status.py <status>`
- Do not create directories with mkdir. Use: `python ${CLAUDE_PLUGIN_ROOT}/scripts/init-period.py <period>`

## Plugin Scripts
| Script | Purpose | Usage |
|--------|---------|-------|
| `set-status.py` | Change task status | `python ${CLAUDE_PLUGIN_ROOT}/scripts/set-status.py <status>` |
| `init-period.py` | Scaffold a new period directory | `python ${CLAUDE_PLUGIN_ROOT}/scripts/init-period.py <period>` |

```

**Decision (post-review):** Drop the "Task-Specific Tools" section from the template. At `init-task.py` time, no task-specific tools exist yet — they get built during onboarding. And `load-context.py --level task` already outputs the full tool index at execution time. Keep `reference.md` scoped to plugin scripts and write restrictions only.

### Why task-level only (for now)

The task agent is where the bulk of execution happens — `/start` and `/done` run at this level. Class-level and root-level agents primarily run during `/onboard`, which is a guided skill flow with less risk of the agent losing track of commands mid-execution. Class-level `reference.md` can be added later if needed.

### Relationship to other artifacts

| Artifact | Loaded | Purpose | Mutable by agent? |
|----------|--------|---------|-------------------|
| SKILL.md | Once, at skill invocation | Full procedure, validation rules | Yes (during onboard) |
| reference.md | On demand (agent reads it) | Script quick-reference, write restrictions | No (generated by init) |
| settings.json | Every conversation, automatically | Hard write scope enforcement | No (generated by init) |
| AGENT.md | On demand | Entity context, domain knowledge | Yes (during onboard) |
| learned.md | On demand | Patterns from past periods | Yes (during /done) |
| status.yaml | On demand, write via script | Current task state | No (via set-status.py only) |

---

## Open Items for Next Iteration

Priorities revised after post-dry-run review (2026-03-26).

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

---

## Post-Dry-Run Review (2026-03-26)

### Review Summary

The dry run surfaced exactly the right class of failure — agent bypassing infrastructure scripts — at the right time, before building more on top of a weak foundation. The proposed fixes follow a coherent philosophy: **don't add more instructions, add harder boundaries.**

The three critical fixes form a triangle:
1. **Write scope enforcement** — hard permission boundaries that prevent direct YAML/directory manipulation
2. **Script gating of all YAML state** — `edit-class-yaml.py` closes the last unguarded mutation path
3. **Delegate onboard dry run to `/start`** — eliminates the mode-switching problem entirely

### Key Insight

The root cause analysis (see above) correctly identifies that the problem isn't insufficient instructions — it's a fundamental mode-switching issue with long-running agent conversations. After 30 minutes of direct file creation during the interview/builder phases, the agent cannot reliably switch to "use scripts for everything" mode. The fixes address the root cause (hard boundaries + delegation), not the symptom (more instructions).
