# Context Engineer

A plugin for [Claude Cowork](https://claude.ai) that scaffolds and manages a 3-level context hierarchy for recurring professional workflows. It captures human expertise into executable procedures (SKILL.md files) that fresh Claude instances can run each period — so the agent that closes March knows everything the agent that closed February learned.

## Architecture

The plugin manages **engagement hierarchies** — folder structures that live outside this repo, on the user's filesystem. Each hierarchy has exactly three levels:

```
engagement-root/          # Root — entity context (.context-root, AGENT.md)
├── treasury/             # Class — a category of recurring work (.class.yaml)
│   ├── bank-fees/        # Task — one repeatable unit (SKILL.md, status.yaml)
│   │   ├── periods/      #   Period-organized work (2026-03/, 2026-04/, ...)
│   │   ├── learned.md    #   Patterns from past executions
│   │   └── tools/        #   Task-specific scripts
│   └── statement-norm/
└── reporting/
```

- **Root** — entity details (legal name, fiscal year, materiality, contacts)
- **Class** — a group of related tasks with a manifest (`.class.yaml`) defining execution order
- **Task** — a single repeatable procedure with its own SKILL.md, status tracking, and learning record

Context inherits downward: a task agent automatically sees its class and root context.

## Repository Layout

```
context_engineer/
├── plugin/                  # The Cowork plugin
│   ├── .claude-plugin/      #   Plugin manifest (plugin.json)
│   ├── scripts/             #   8 Python scripts (infrastructure)
│   └── skills/              #   4 skill definitions (SKILL.md files)
├── spec/                    # Design specification (source of truth)
├── tests/                   # 174 unit + e2e tests
├── notes/                   # Build specs for unimplemented features, dry run findings
├── docs/                    # Background research (landscape analysis, design outline)
├── engagement-template/     # Starter scaffold for new engagements (used by Cowork)
├── pyproject.toml           # Project config (context-engineer v0.1.0)
└── venv/                    # Python virtual environment
```

## Plugin Structure

### Skills (invoked by the user in Cowork)

| Skill | Purpose |
|-------|---------|
| `/onboard` | Knowledge transfer — interviews the human, creates SKILL.md, runs first period |
| `/start` | Executes a task for the current period |
| `/done` | Captures review feedback, updates learned.md, closes the period |
| `/status` | Read-only dashboard showing class progress |

### Scripts (called by skills, enforce validation)

| Script | Purpose |
|--------|---------|
| `init-class.py` | Scaffold a new class directory |
| `init-task.py` | Scaffold a new task directory |
| `init-period.py` | Scaffold a period directory (data/, workpapers/, review-notes/) |
| `load-context.py` | Assemble context from the hierarchy (pure read, no side effects) |
| `set-status.py` | Validate and apply status transitions |
| `install-deps.py` | Install requirements.txt files top-down through hierarchy |
| `check-periods.py` | Scheduled reset of completed tasks when next anchor date arrives |
| `archive-period.py` | Upload completed period to Google Drive |

All scripts follow the exit-code contract in `spec/script-contracts.md`: exit 0 = success, exit 1 = validation error, exit 2 = system error. Non-zero exit guarantees no side effects.

## Running Tests

```bash
source venv/bin/activate
python -m pytest tests/
```

174 tests (unit + e2e). Markers: `@pytest.mark.mid` for component tests, `@pytest.mark.e2e` for workflow tests.

## Current Status

- **v0.1.0** — All 8 scripts implemented and tested. 4 skill definitions written.
- **First dry run** completed 2026-03-25 on Cowork. Validated the core flow (`/onboard` → `/start` → `/done`) but surfaced critical issues around agent script bypass.
- **Next** — See `notes/open-items.md` for the priority queue. Critical items: `init-engagement.py` (git init), `edit-class-yaml.py` (enum validation), write scope enforcement (`.claude/settings.json` generation).
