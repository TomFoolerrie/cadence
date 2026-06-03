# Cadence — Project Notes

Read `README.md` first for project orientation and architecture overview.

## Dev Environment
- Python virtualenv at `venv/` — activate with `source venv/bin/activate`
- Run Python tests: `python -m pytest tests/` (310 tests must pass)
- Run Pi-gate TS tests (no key/container): `npm install` once, then `npm run test:gate` + `npm run typecheck`
- After editing the Cowork plugin sources, re-run `python claude/assemble.py` (the assembled `claude/plugin/scripts`+`skills` are gitignored symlinks)
- Git note: this repo's scaffolders shell out to `git commit`; if the host has commit signing on, disable it (`git config --global commit.gpgsign false`) or the init/check-periods tests fail
- `.claude/settings.local.json` has project-level permissions (WebSearch, WebFetch for agentic-design.ai only)

## Source of Truth
- `spec/` is the authoritative design specification
- `notes/open-items.md` has the current build priority queue (start here for what to implement next)
- `notes/dry-run-*.md` are historical test findings

## Key Conventions
- `engagement-template/` is a working directory for Cowork — not test data, do not modify casually
- Tests use temporary directories via `tests/conftest.py` fixtures (never the engagement-template)
- **Two-track layout** (Pi migration, in progress): `scripts/` + `skills/` are the
  **shared** top-level sources of truth; `claude/` holds the Cowork glue and
  `pi/` the Pi glue. The Cowork plugin root (`claude/plugin/`) is **assembled**
  from the shared dirs by `claude/assemble.py` (symlinks `./scripts`/`./skills`,
  gitignored) — never hand-maintain it. Tests split: `tests/unit/` (shared,
  harness-neutral) + `tests/claude/` + `tests/pi/`, with `tests/conftest.py`
  shared at the root. See `spec/tickets/ticket-pi-migration.md`.
- All scripts follow the exit-code contract: 0 = success, 1 = validation error, 2 = system error
