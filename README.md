# Cadence

A plugin for [Claude](https://claude.ai) that scaffolds and manages a 3-level context hierarchy for recurring professional workflows. It captures human expertise into executable procedures (SKILL.md files) that fresh Claude instances can run each period — so the agent that closes March knows everything the agent that closed February learned.

## Architecture

The plugin manages **engagement hierarchies** — folder structures that live outside this repo, on the user's filesystem. Each hierarchy has exactly three levels deep (no nesting beyond root → class → task):

```
engagement-root/                # Root — entity context
├── .context-root               #   Root marker (YAML: engagement name, schema version)
├── AGENTS.md                    #   Entity details (legal name, fiscal year, materiality, contacts)
├── requirements.txt            #   Global dependencies
├── .claude/tools/              #   Global shared tools (JE formatter, PDF parser)
├── treasury/                   # Class — a category of recurring work
│   ├── .class.yaml             #   Orchestration manifest (tasks, order, period format)
│   ├── AGENTS.md                #   Class context for task agents
│   ├── tools/                  #   Class-level shared tools
│   └── monthly-bank-fees/      # Task — one repeatable unit
│       ├── SKILL.md            #   The procedure (what to do, step by step)
│       ├── learned.md          #   Patterns from past executions
│       ├── status.yaml         #   Current execution state
│       ├── reference.md        #   Write restrictions + script docs
│       ├── tools/              #   Task-specific scripts
│       └── periods/            #   Period-organized work
│           └── 2026-03/
│               ├── data/       #   Inputs
│               ├── workpapers/ #   Outputs
│               └── review-notes/
└── reporting/                  # Another class
```

### Levels

- **Root** — engagement-wide context: entity details, materiality thresholds, system access, key contacts. The user rarely interacts here after initial setup.
- **Class** — groups related tasks (treasury, reporting, collections). `.class.yaml` declares the task manifest with execution phases — tasks at the same `order` value run in parallel, all must complete before the next phase starts. `AGENTS.md` provides class context that flows down to task agents.
- **Task** — where the user lives. Each task is self-contained: `SKILL.md` (procedure), `learned.md` (accumulated learnings), `status.yaml` (execution state), `tools/` (automation scripts), and `periods/` (period-organized work).

### Context Inheritance

Context flows downward: a task agent automatically sees root `AGENTS.md` → class `AGENTS.md` → task files. `load-context.py` assembles this chain. Tools resolve task → class → global (most specific wins).

### Status Machine

Tasks follow a strict state machine enforced by `set-status.py`:

```
not_started → in_progress → review_ready → done
                  ↑              │
                  └──────────────┘  (rejection — re-execute)
              in_progress → blocked → not_started (retry)
                                    → abandoned   (give up)
done/abandoned → not_started  (check-periods.py — next period due)
```

Class status is always derived on the fly from task statuses — never stored.

### Design Principles

- **The folder is the memory, not the agent.** Each execution gets a fresh Claude instance. Nothing carries over except what's written to the folder.
- **Hard boundaries over instructions.** Write scope enforcement (`.claude/settings.json` on the Claude track, the in-process `tool_call` gate on the Pi track) prevents agents from bypassing scripts. Scripts gate all YAML mutations.
- **The hierarchy belongs to the user.** It's folders and markdown on a filesystem. Uninstalling the plugin doesn't delete their data. Any runtime that can parse YAML and run Python can execute it — and Cadence ships glue for two (Cowork and Pi).
- **Git-versioned.** Every change is committed automatically. Full undo history.

## Repository Layout

```
cadence/
├── scripts/                # 14 Python scripts (shared, harness-agnostic)
├── skills/                 # 4 skill definitions (shared SKILL.md files)
├── claude/                 # Claude/Cowork glue
│   ├── plugin/             #   Plugin root — .claude-plugin/ + assembled ./scripts, ./skills
│   └── assemble.py         #   Assembles the plugin root from the shared dirs
├── pi/                     # Pi-harness glue (extension/ — the tool_call gate)
├── spec/                   # Design specification (source of truth)
├── tests/                  # unit/ (shared) + claude/ + pi/, with a shared conftest.py
├── notes/                  # Build specs for unimplemented features, dry run findings
├── docs/                   # Background research (landscape analysis, design outline)
├── engagement-template/    # Starter scaffold for new engagements (used by Cowork)
├── test-artifacts/         # Sample inputs for manual dry runs (greenfield-manufacturing, oakwood-properties)
├── pyproject.toml          # Project config (cadence v0.1.0)
└── venv/                   # Python virtual environment
```

The migration to two tracks (Cowork + Pi) over one shared spine is in progress —
see `spec/tickets/ticket-pi-migration.md`.

## Plugin Structure

### Skills (invoked by the user in Cowork)

| Skill | Run from | Purpose |
|-------|----------|---------|
| `/onboard` | Root or class dir | Knowledge transfer — interviews the human, scaffolds class/task, creates SKILL.md and tools, runs first period to `review_ready` |
| `/start` | Task dir | Executes a task for the current period. Handles first run, retry from `blocked`, and re-execution after rejection. Sets `review_ready` on success, `blocked` on failure |
| `/done` | Task dir (same conversation as `/start`) | Captures review feedback, updates learned.md, proposes SKILL.md changes (human-approved), sets `done`, archives to Google Drive |
| `/status` | Class dir | Read-only dashboard — reads all task `status.yaml` files, computes class rollup on the fly |

### Scripts (called by skills, enforce validation)

| Script | Purpose |
|--------|---------|
| `init-engagement.py` | Scaffold a new engagement root with git init |
| `init-class.py` | Scaffold a new class directory (Claude track also gets `.claude/settings.json`) |
| `init-task.py` | Scaffold a new task directory (Claude track also gets `.claude/settings.json`) |
| `settings-gen.py` | Generate the Claude-track `.claude/settings.json` for a level (invoked by the init scripts when `CADENCE_TRACK=claude`) |
| `init-period.py` | Scaffold a period directory (data/, workpapers/, review-notes/) |
| `edit-class-yaml.py` | Gateway for `.class.yaml` mutations (enum-validated) |
| `load-context.py` | Assemble context from the hierarchy (pure read, no side effects) |
| `set-status.py` | Validate and apply status transitions |
| `start-setup.py` | Atomic setup phase for `/start` (status + deps + period + context) |
| `install-deps.py` | Install requirements.txt files top-down through hierarchy |
| `check-periods.py` | Scheduled reset of completed tasks when next anchor date arrives |
| `archive-period.py` | Upload completed period to Google Drive |
| `init-venv.py` | Create Python venv at engagement root (idempotent) |
| `onboard-setup.py` | Atomic setup for `/onboard` (context + task scaffold) |
| `onboard-register.py` | Register task in manifest (venv + deps + manifest + description) |

All scripts follow the exit-code contract (see `spec/05-scripts.md`): exit 0 = success, exit 1 = validation error, exit 2 = system error. Non-zero exit guarantees no side effects.

## Installation — two tracks, one repo

Cadence runs on two agent harnesses over the same shared spine (`scripts/` +
`skills/`). The engagement folder it produces is identical either way — *the
folder is the memory, not the agent* — so a hierarchy is portable between them.

### Claude / Cowork (the original track)

Install the Cowork plugin. The plugin root is assembled from the shared sources
by `claude/assemble.py`, which links the top-level `scripts/` + `skills/` under
`claude/plugin/` (Cowork forbids `../` in manifest paths, so the install root
must be self-contained):

```bash
python claude/assemble.py        # link scripts/ + skills/ under claude/plugin/
python claude/assemble.py --copy # or copy, for packaging/distribution
```

Then point Cowork at `claude/plugin/`. Write-scope enforcement comes from the
`.claude/settings.json` files the scaffolders generate (`CADENCE_TRACK` unset or
`claude`).

### Pi (the second track)

Cadence is a [Pi](https://github.com/earendil-works/pi) package — declared by the
`pi` key in the root `package.json` (`extensions: ["./pi/extension"]`,
`skills: ["./skills"]`). Install it straight from the repo:

```bash
pi install git:github.com/tomfoolerrie/cadence@<ref>
```

Pi clones the whole repo and reads the root manifest. There is **no** assembly
step — Pi references the shared `skills/` in place. Write-scope enforcement comes
from the in-process `tool_call` gate (`pi/extension/`), which reproduces the
Claude track's two deny rules **and** adds a Bash gate (head whitelist +
banned-pattern scan) that `settings.json` cannot express. The extension sets
`CADENCE_TRACK=pi`, so the scaffolders emit no `.claude/`.

## Running Tests

**Python (the shared spine + both tracks' scaffolding):**

```bash
source venv/bin/activate
python -m pytest tests/        # 310 tests: tests/unit/ (shared) + tests/claude/ + tests/pi/
```

Markers: `@pytest.mark.mid` for component tests, `@pytest.mark.e2e` for workflow
tests. `tests/unit/` is harness-neutral; `tests/claude/` asserts the generated
`.claude/settings.json`; `tests/pi/` asserts the `CADENCE_TRACK=pi` no-`.claude/`
contract.

**TypeScript (the Pi gate — no key, no container):**

```bash
npm install          # one-time: tsx + typescript + the pinned Pi SDK (devDeps)
npm run test:gate    # the pure policy classifier + the factory wiring
npm run typecheck    # tsc over pi/extension/*.ts
```

## Current Status

- **v0.1.0** — All 14 scripts implemented and tested. 4 skill definitions written.
- **Dry run 1** (2026-03-25) — Validated the core flow on Cowork but surfaced critical issues around agent script bypass.
- **Post-dry-run-1 fixes** — All three critical items resolved: `init-engagement.py` (git init), `edit-class-yaml.py` (enum-validated YAML gateway), write scope enforcement (`.claude/settings.json` auto-generated by scaffolding scripts).
- **v0.1.1** — Anchor system redesigned (one-ahead with `last_*` support, late-completion guard). Engagement venv support added. `/onboard` consolidated from 7-8 script calls to 3. Script exit patterns normalized. Cowork sandbox compatibility (`.absolute()` walk-up, system-pip fallback).
- **Dry run 2** (2026-03-28) — Full lifecycle completed end-to-end in Cowork: `/onboard` → `/done` (approved 2026-02) → `check-periods.py` auto-reset → `/start` (2026-03) → `review_ready`. Four clean git commits. Workpapers balanced ($998.25 for 2026-02, $1,017.75 for 2026-03). Script gating held; tool-deferral worked. Remaining gaps are ergonomic (e.g. AGENTS.md prompting), not structural. See `notes/dry-run-2026-03-25.md` and `notes/open-items.md` Post-Dry-Run 2 section.
- **Pi migration** (in progress, `spec/tickets/ticket-pi-migration.md`) — Two tracks over one shared spine. Phases 1–5 done and host-verified: the in-place cleanups, the two-track restructure, `settings-gen.py` + `CADENCE_TRACK`, the Pi `tool_call` gate + root `pi` manifest, and the parity tests (310 pytest + 22 TS gate tests green; the Pi extension + all 4 skills load through the real Pi 0.75.4 machinery). Phase 6 — a live dry-run-3 on a non-Anthropic model — is the remaining acceptance proof (needs Pi + a key; not yet run).
- **Next** — See `notes/open-items.md` for the priority queue.
