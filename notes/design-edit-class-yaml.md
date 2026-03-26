# Design: `edit-class-yaml.py`

Script to gate all `.class.yaml` mutations, matching the `set-status.py` pattern for `status.yaml`.

## CLI Interface

```
edit-class-yaml.py set-description <description>
edit-class-yaml.py add-task <task> --order <N> [--enabled] [--no-enabled] [--period-format <fmt>] [--anchor <anchor>]
edit-class-yaml.py update-task <task> [--order <N>] [--enabled] [--no-enabled] [--period-format <fmt>] [--anchor <anchor>]
edit-class-yaml.py remove-task <task>
```

## Valid Enums

```python
VALID_PERIOD_FORMATS = {"monthly", "weekly", "quarterly", "adhoc"}

VALID_ANCHORS = {
    "first_monday", "first_tuesday", "first_wednesday", "first_thursday", "first_friday",
    "last_monday", "last_tuesday", "last_wednesday", "last_thursday", "last_friday",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
}
```

## Preconditions

- cwd contains `.class.yaml` (exit 1 if missing)
- `.class.yaml` is valid YAML with a `manifest` list (exit 2 if corrupt)
- `add-task`: task not already in manifest, task directory exists with `SKILL.md`
- `update-task`: task exists in manifest, at least one field provided
- `remove-task`: task exists in manifest
- `--order` must be a positive integer
- `--period-format` and `--anchor` must be valid enum values

## Defaults

- `--enabled`: defaults to `true` on `add-task`
- `--period-format`: defaults to `monthly`
- `--anchor`: defaults to `first_monday`
- All fields written explicitly (no omission) to prevent ambiguity

## Exit Codes

- 0: success
- 1: validation error (bad input, invalid enum, task not found/already exists)
- 2: system error (corrupt YAML, filesystem failure)

## Onboard Skill Change

Step 9 changes from raw YAML block to:

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/edit-class-yaml.py add-task <name> --order <N> --period-format <format> --anchor <anchor>
```

Step 4 (class-level) adds after AGENT.md write:

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/edit-class-yaml.py set-description "<description from interview>"
```
