#!/usr/bin/env python3
"""Scaffold a new class directory under an engagement root."""

import os
import subprocess
import sys
from pathlib import Path

import yaml


def emit_claude_settings(target: Path, level: str) -> int:
    """Generate `.claude/settings.json` via settings-gen.py — Claude track only.

    The harness sets `CADENCE_TRACK`; unset defaults to `claude`. On the Pi
    track this is a no-op (the tool_call gate enforces write scope instead).
    Returns 0 on success or skip, 2 if generation fails.
    """
    if os.environ.get("CADENCE_TRACK", "claude") != "claude":
        return 0
    settings_gen = Path(__file__).resolve().parent / "settings-gen.py"
    result = subprocess.run(
        [sys.executable, str(settings_gen), str(target), level],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"settings-gen failed: {result.stderr.strip()}", file=sys.stderr)
        return 2
    return 0


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

        # AGENTS.md
        agent_md = (
            f"# {title}\n"
            "\n"
            "## What This Class Covers\n"
            "<!-- Domain description -->\n"
            "\n"
            "## Key Concepts\n"
            "<!-- Shared conventions for task agents -->\n"
        )
        (target / "AGENTS.md").write_text(agent_md)

        # tools/
        (target / "tools").mkdir()

        # requirements.txt
        (target / "requirements.txt").write_text("")

    except OSError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    # Write-scope enforcement (Claude track only; Pi uses the tool_call gate).
    rc = emit_claude_settings(target, "class")
    if rc != 0:
        return rc

    return 0


if __name__ == "__main__":
    sys.exit(main())
