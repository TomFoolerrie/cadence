#!/usr/bin/env python3
"""Scaffold a new task folder within a class directory.

Usage: init-task.py <name>

Preconditions:
  - cwd contains .class.yaml
  - Target directory does not already exist

Exit codes: 0 = success, 1 = precondition failed, 2 = filesystem error
"""

import json
import sys
from pathlib import Path

import yaml


SKILL_MD_TEMPLATE = """\
---
name: {name}
description: >
  TODO — describe what this folder produces.
---

# {name}

## Purpose

<!-- What does this produce? Which accounts does it touch? -->

## Data Sources

<!-- Where does the data come from? Format? What if it's missing? -->

## Procedure

<!-- Step-by-step processing logic. Reference shared tools by path. -->

## Validation

<!-- How to verify the output is correct. -->

## Contacts

<!-- Who to ask when something goes wrong. -->

## Completion Criteria

<!-- What does a completed task look like? What artifacts must exist? -->
"""

REFERENCE_MD_TEMPLATE = """\
# reference — {name}

## Write Restrictions
- `status.yaml` — Do not edit directly. Use: `python ${{CLAUDE_PLUGIN_ROOT}}/scripts/set-status.py <status>`
- Do not create directories with mkdir. Use: `python ${{CLAUDE_PLUGIN_ROOT}}/scripts/init-period.py <period>`

## Plugin Scripts
| Script | Purpose | Usage |
|--------|---------|-------|
| `set-status.py` | Change task status | `python ${{CLAUDE_PLUGIN_ROOT}}/scripts/set-status.py <status>` |
| `init-period.py` | Scaffold a new period directory | `python ${{CLAUDE_PLUGIN_ROOT}}/scripts/init-period.py <period>` |
"""

LEARNED_MD_TEMPLATE = """\
# Learned Patterns

## Review History

| Period | Outcome | Key Number | Note |
|--------|---------|------------|------|

## Patterns

<!-- Entries use structured delta format:
- **Pattern description**
  Confirmed: N | Contradicted: N | First seen: YYYY-MM
  Used for: how this pattern informs execution
-->

## What Didn't Work

<!-- Entries use structured delta format:
- **What was attempted**
  Confirmed: N | Contradicted: N | First seen: YYYY-MM
  Result: what happened | Fix: how it was resolved
-->

## Open Questions
"""


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: init-task.py <name>", file=sys.stderr)
        return 1

    name = sys.argv[1]
    cwd = Path.cwd()

    # --- Preconditions ---
    class_yaml = cwd / ".class.yaml"
    if not class_yaml.is_file():
        print("Not in a class directory (no .class.yaml)", file=sys.stderr)
        return 1

    # Validate that .class.yaml is parseable
    try:
        with open(class_yaml) as f:
            yaml.safe_load(f)
    except yaml.YAMLError:
        print("Invalid .class.yaml", file=sys.stderr)
        return 1

    task_dir = cwd / name
    if task_dir.exists():
        print(f"Directory {name}/ already exists", file=sys.stderr)
        return 1

    # --- Create task structure ---
    try:
        task_dir.mkdir(parents=True)

        # SKILL.md
        (task_dir / "SKILL.md").write_text(SKILL_MD_TEMPLATE.format(name=name))

        # learned.md
        (task_dir / "learned.md").write_text(LEARNED_MD_TEMPLATE)

        # reference.md
        (task_dir / "reference.md").write_text(REFERENCE_MD_TEMPLATE.format(name=name))

        # status.yaml
        status_data = {
            "schema_version": 1,
            "period": "",
            "status": "not_started",
            "issues": [],
            "done_at": None,
        }
        with open(task_dir / "status.yaml", "w") as f:
            yaml.dump(status_data, f, default_flow_style=False, sort_keys=False)

        # tools/
        (task_dir / "tools").mkdir()

        # periods/
        (task_dir / "periods").mkdir()

        # .claude/settings.json (write scope enforcement)
        (task_dir / ".claude").mkdir()
        settings = {
            "permissions": {
                "allow": ["Read", "Write(./**)"],
                "deny": ["Write(../**)", "Write(./status.yaml)"],
            }
        }
        with open(task_dir / ".claude" / "settings.json", "w") as f:
            json.dump(settings, f, indent=2)
            f.write("\n")

        # requirements.txt
        (task_dir / "requirements.txt").write_text("")

    except OSError as e:
        print(f"Filesystem error: {e}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
