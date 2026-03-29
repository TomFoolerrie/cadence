# Cadence

A plugin for [Claude Cowork](https://claude.ai) that scaffolds and manages a 3-level context hierarchy for recurring professional workflows. It captures human expertise into executable procedures (SKILL.md files) that fresh Claude instances can run each period — so the agent that closes March knows everything the agent that closed February learned.

## Architecture

The plugin manages **engagement hierarchies** — folder structures that live outside this repo, on the user's filesystem. Each hierarchy has exactly three levels deep (no nesting beyond root → class → task):

```
engagement-root/                # Root — entity context
├── .context-root               #   Root marker (YAML: engagement name, schema version)
├── AGENT.md                    #   Entity details (legal name, fiscal year, materiality, contacts)
├── requirements.txt            #   Global dependencies
├── .claude/tools/              #   Global shared tools (JE formatter, PDF parser)
├── treasury/                   # Class — a category of recurring work
│   ├── .class.yaml             #   Orchestration manifest (tasks, order, period format)
│   ├── AGENT.md                #   Class context for task agents
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
- **Class** — groups related tasks (treasury, reporting, collections). `.class.yaml` declares the task manifest with execution phases — tasks at the same `order` value run in parallel, all must complete before the next phase starts. `AGENT.md` provides class context that flows down to task agents.
- **Task** — where the user lives. Each task is self-contained: `SKILL.md` (procedure), `learned.md` (accumulated learnings), `status.yaml` (execution state), `tools/` (automation scripts), and `periods/` (period-organized work).

### Context Inheritance

Context flows downward: a task agent automatically sees root `AGENT.md` → class `AGENT.md` → task files. `load-context.py` assembles this chain. Tools resolve task → class → global (most specific wins).

### Status Tracking

Task status is tracked in `status.yaml`, written directly by skills. No enforced state machine.

### Design Principles

- **The folder is the memory, not the agent.** Each execution gets a fresh Claude instance. Nothing carries over except what's written to the folder.
- **Hard boundaries over instructions.** Scripts handle scaffolding and validation. Structural mutations go through scripts, not raw file writes.
- **The hierarchy belongs to the user.** It's folders and markdown on a filesystem. Uninstalling the plugin doesn't delete their data. Any runtime that can parse YAML and run Python can execute it.
- **Git-versioned.** Every change is committed automatically. Full undo history.

## Repository Layout

```
cadence/
├── plugin/                  # The Cowork plugin
│   ├── .claude-plugin/      #   Plugin manifest (plugin.json)
│   ├── scripts/             #   7 Python scripts (infrastructure)
│   └── skills/              #   3 skill definitions (SKILL.md files)
├── tests/                   # ~100 unit + e2e tests
├── pyproject.toml           # Project config (cadence v0.1.0)
└── venv/                    # Python virtual environment
```

## Plugin Structure

### Skills (invoked by the user in Cowork)

| Skill | Run from | Purpose |
|-------|----------|---------|
| `/onboard` | Root or class dir | Knowledge transfer — interviews the human, scaffolds class/task, creates SKILL.md and tools |
| `/start` | Task dir | Executes a task for the current period |
| `/done` | Task dir (same conversation as `/start`) | Captures review feedback, updates learned.md, proposes SKILL.md changes (human-approved) |

### Scripts (called by skills, enforce validation)

| Script | Purpose |
|--------|---------|
| `init-engagement.py` | Scaffold a new engagement root with git init |
| `init-class.py` | Scaffold a new class directory |
| `init-task.py` | Scaffold a new task directory |
| `init-period.py` | Scaffold a period directory (data/, workpapers/, review-notes/) |
| `init-venv.py` | Create Python venv at engagement root (idempotent) |
| `load-context.py` | Assemble context from the hierarchy (pure read, no side effects) |
| `install-deps.py` | Install requirements.txt files top-down through hierarchy |

All scripts follow the exit-code contract (see `spec/05-scripts.md`): exit 0 = success, exit 1 = validation error, exit 2 = system error. Non-zero exit guarantees no side effects.

## Running Tests

```bash
source venv/bin/activate
python -m pytest tests/
```

~100 tests (unit + e2e). Markers: `@pytest.mark.mid` for component tests, `@pytest.mark.e2e` for workflow tests.

## Current Status

**MVP branch** — 7 scripts, 3 skills. Scaffolding and context loading. Human-driven execution with direct YAML state management.
