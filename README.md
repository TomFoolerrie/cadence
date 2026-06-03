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
- **Hard boundaries over instructions.** Write scope enforcement (`.claude/settings.json`) prevents agents from bypassing scripts. Scripts gate all YAML mutations.
- **The hierarchy belongs to the user.** It's folders and markdown on a filesystem. Uninstalling the plugin doesn't delete their data. Any runtime that can parse YAML and run Python can execute it.
- **Git-versioned.** Every change is committed automatically. Full undo history.

## Repository Layout

```
cadence/
├── plugin/                  # The Cowork plugin
│   ├── .claude-plugin/      #   Plugin manifest (plugin.json)
│   ├── scripts/             #   14 Python scripts (infrastructure)
│   └── skills/              #   4 skill definitions (SKILL.md files)
├── spec/                    # Design specification (source of truth)
├── tests/                   # 299 unit + e2e tests
├── notes/                   # Build specs for unimplemented features, dry run findings
├── docs/                    # Background research (landscape analysis, design outline)
├── engagement-template/     # Starter scaffold for new engagements (used by Cowork)
├── test-artifacts/          # Sample inputs for manual dry runs (greenfield-manufacturing, oakwood-properties)
├── pyproject.toml           # Project config (cadence v0.1.0)
└── venv/                    # Python virtual environment
```

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
| `init-class.py` | Scaffold a new class directory (generates `.claude/settings.json`) |
| `init-task.py` | Scaffold a new task directory (generates `.claude/settings.json`) |
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

## Running Tests

```bash
source venv/bin/activate
python -m pytest tests/
```

299 tests (unit + e2e). Markers: `@pytest.mark.mid` for component tests, `@pytest.mark.e2e` for workflow tests.

## Current Status

- **v0.1.0** — All 14 scripts implemented and tested. 4 skill definitions written.
- **Dry run 1** (2026-03-25) — Validated the core flow on Cowork but surfaced critical issues around agent script bypass.
- **Post-dry-run-1 fixes** — All three critical items resolved: `init-engagement.py` (git init), `edit-class-yaml.py` (enum-validated YAML gateway), write scope enforcement (`.claude/settings.json` auto-generated by scaffolding scripts).
- **v0.1.1** — Anchor system redesigned (one-ahead with `last_*` support, late-completion guard). Engagement venv support added. `/onboard` consolidated from 7-8 script calls to 3. Script exit patterns normalized. Cowork sandbox compatibility (`.absolute()` walk-up, system-pip fallback).
- **Dry run 2** (2026-03-28) — Full lifecycle completed end-to-end in Cowork: `/onboard` → `/done` (approved 2026-02) → `check-periods.py` auto-reset → `/start` (2026-03) → `review_ready`. Four clean git commits. Workpapers balanced ($998.25 for 2026-02, $1,017.75 for 2026-03). Script gating held; tool-deferral worked. Remaining gaps are ergonomic (e.g. AGENTS.md prompting), not structural. See `notes/dry-run-2026-03-25.md` and `notes/open-items.md` Post-Dry-Run 2 section.
- **Next** — See `notes/open-items.md` for the priority queue.
