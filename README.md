# Cadence

A plugin for [Claude Cowork](https://claude.ai) that scaffolds and manages a 3-level context hierarchy for recurring professional workflows. It captures human expertise into executable procedures (SKILL.md files) that fresh Claude instances can run each period — so the agent that closes March knows everything the agent that closed February learned.

## Architecture

The plugin manages **engagement hierarchies** — folder structures that live outside this repo, on the user's filesystem. Each hierarchy has exactly three levels (root → class → task):

```
engagement-root/                # Root — entity context
├── .context-root               #   Root marker (YAML: engagement name, schema version)
├── AGENT.md                    #   Entity details (legal name, fiscal year, materiality, contacts)
├── requirements.txt            #   Global dependencies
├── .claude/tools/              #   Global shared tools
├── treasury/                   # Class — a category of recurring work
│   ├── .class                  #   Class directory marker
│   ├── AGENT.md                #   Class context for task agents
│   ├── tools/                  #   Class-level shared tools
│   └── monthly-bank-fees/      # Task — one repeatable unit
│       ├── SKILL.md            #   The procedure (what to do, step by step)
│       ├── learned.md          #   Patterns from past executions
│       ├── reference.md        #   Script docs
│       ├── tools/              #   Task-specific scripts
│       └── periods/            #   Period-organized work
│           └── 2026-03/
│               ├── data/       #   Inputs
│               ├── workpapers/ #   Outputs
│               └── review-notes/
└── reporting/                  # Another class
```

### Levels

- **Root** — engagement-wide context: entity details, materiality thresholds, system access, key contacts.
- **Class** — groups related tasks (treasury, reporting, collections). `AGENT.md` provides class context that flows down to task agents.
- **Task** — where the user lives. Each task is self-contained: `SKILL.md` (procedure), `learned.md` (accumulated learnings), `tools/` (automation scripts), and `periods/` (period-organized work).

### Context Inheritance

Context flows downward: a task agent automatically sees root `AGENT.md` → class `AGENT.md` → task files. `load-context.py` assembles this chain. Tools resolve task → class → global (most specific wins).

### State

The folder hierarchy is the state. No YAML state files — folder existence tells the story:

- Class directory exists → class is set up
- Task directory exists → task is set up
- Period directory exists → work started
- Workpapers populated → work done

### Design Principles

- **The folder is the memory, not the agent.** Each execution gets a fresh Claude instance. Nothing carries over except what's written to the folder.
- **Scripts for structure, agent for content.** Init scripts handle directory scaffolding. The agent writes markdown and code directly.
- **The hierarchy belongs to the user.** It's folders and markdown on a filesystem. Uninstalling the plugin doesn't delete their data.
- **Human-driven.** The user decides when to run each skill. No automation, no state machine.
- **Git-versioned.** Every change is committed automatically. Full undo history.

## Repository Layout

```
cadence/
├── plugin/                  # The Cowork plugin
│   ├── .claude-plugin/      #   Plugin manifest (plugin.json)
│   ├── scripts/             #   7 Python scripts (infrastructure)
│   └── skills/              #   3 skill definitions (SKILL.md files)
├── tests/                   # 88 tests
├── pyproject.toml           # Project config (cadence v0.1.0-mvp)
└── venv/                    # Python virtual environment
```

## Plugin Structure

### Skills (invoked by the user in Cowork)

| Skill | Run from | Purpose |
|-------|----------|---------|
| `/onboard` | Root or class dir | Knowledge transfer — interviews the human, scaffolds class/task, builds tools from real data, executes first period |
| `/start` | Task dir | Executes a task for the current period |
| `/done` | Task dir (same conversation as `/start`) | Captures learnings from the conversation, updates learned.md, proposes SKILL.md changes, commits |

### Scripts (called by skills, handle scaffolding)

| Script | Purpose |
|--------|---------|
| `init-engagement.py` | Scaffold a new engagement root with git init |
| `init-class.py` | Scaffold a new class directory (`.class` marker, AGENT.md, tools/) |
| `init-task.py` | Scaffold a new task directory (SKILL.md, learned.md, reference.md, tools/, periods/) |
| `init-period.py` | Scaffold a period directory (data/, workpapers/, review-notes/) |
| `init-venv.py` | Create Python venv at engagement root (idempotent) |
| `load-context.py` | Assemble context from the hierarchy (pure read, no side effects) |
| `install-deps.py` | Install requirements.txt files top-down through hierarchy |

All scripts follow the exit-code contract: exit 0 = success, exit 1 = validation error, exit 2 = system error.

## Running Tests

```bash
source venv/bin/activate
python -m pytest tests/
```

88 tests. Markers: `@pytest.mark.mid` for component tests.

## Current Status

**MVP branch** — 7 scripts, 3 skills, 88 tests. Fully human-driven: scaffolding scripts handle directory structure, the agent handles everything else.
