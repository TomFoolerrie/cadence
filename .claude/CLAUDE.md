# Cadence — Project Notes (MVP Branch)

Read `README.md` first for project orientation and architecture overview.

## Dev Environment
- Python virtualenv at `venv/` — activate with `source venv/bin/activate`
- Run tests: `python -m pytest tests/`
- `.claude/settings.local.json` has project-level permissions (WebSearch, WebFetch for agentic-design.ai only)

## Key Conventions
- Tests use temporary directories via `tests/conftest.py` fixtures
- Scripts live in `plugin/scripts/`, skills in `plugin/skills/`
- All scripts follow the exit-code contract: 0 = success, 1 = validation error, 2 = system error
- Skills write `status.yaml` and `.class.yaml` directly (no gated scripts for YAML)
