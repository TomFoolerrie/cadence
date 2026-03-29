#!/usr/bin/env python3
"""Scaffold a new class directory under an engagement root."""

import json
import sys
from pathlib import Path

import yaml


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: init-class.py <name>", file=sys.stderr)
        return 1

    name = sys.argv[1]
    cwd = Path.cwd()

    # --- Preconditions (validate before writing) ---

    context_root = cwd / ".context-root"
    if not context_root.is_file():
        print("Not at engagement root (no .context-root)", file=sys.stderr)
        return 1

    # Validate .context-root is parseable YAML
    try:
        with open(context_root) as f:
            yaml.safe_load(f)
    except yaml.YAMLError:
        print("Invalid .context-root file", file=sys.stderr)
        return 1

    target = cwd / name
    if target.exists():
        print(f"Directory {name}/ already exists", file=sys.stderr)
        return 1

    # --- Write files ---

    title = name.replace("-", " ").title()

    try:
        target.mkdir(parents=True)

        # .class.yaml
        data = {
            "schema_version": 1,
            "name": title,
            "description": "",
            "manifest": [],
        }
        with open(target / ".class.yaml", "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

        # AGENT.md
        agent_md = (
            f"# {title}\n"
            "\n"
            "## What This Class Covers\n"
            "<!-- Domain description -->\n"
            "\n"
            "## Key Concepts\n"
            "<!-- Shared conventions for task agents -->\n"
        )
        (target / "AGENT.md").write_text(agent_md)

        # tools/
        (target / "tools").mkdir()

        # .claude/settings.json (write scope enforcement)
        (target / ".claude").mkdir()
        settings = {
            "permissions": {
                "allow": ["Read", "Write(./**)"],
                "deny": ["Write(../**)"],
            }
        }
        with open(target / ".claude" / "settings.json", "w") as f:
            json.dump(settings, f, indent=2)
            f.write("\n")

        # requirements.txt
        (target / "requirements.txt").write_text("")

    except OSError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
