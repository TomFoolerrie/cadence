# Cadence — Project Notes

Read `README.md` first for project orientation and architecture overview.

## Dev Environment
- Python virtualenv at `venv/` — activate with `source venv/bin/activate`
- Run tests: `python -m pytest tests/` (265 tests must pass)
- `.claude/settings.local.json` has project-level permissions (WebSearch, WebFetch for agentic-design.ai only)

## Source of Truth
- `spec/` is the authoritative design specification
- `notes/open-items.md` has the current build priority queue (start here for what to implement next)
- `notes/dry-run-*.md` are historical test findings

## Key Conventions
- `engagement-template/` is a working directory for Cowork — not test data, do not modify casually
- Tests use temporary directories via `tests/conftest.py` fixtures (never the engagement-template)
- Scripts live in `plugin/scripts/`, skills in `plugin/skills/`
- All scripts follow the exit-code contract: 0 = success, 1 = validation error, 2 = system error
