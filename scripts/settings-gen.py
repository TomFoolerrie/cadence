#!/usr/bin/env python3
"""
settings-gen.py — Generate the Claude-track write-scope enforcement file.

Writes `<dir>/.claude/settings.json` with the per-level `permissions` block that
Cowork uses to confine an agent to its own directory. This is the Claude track's
enforcement mechanism; the Pi track replaces it with the in-process tool_call
gate (see `pi/extension/`), so this script is only invoked when
`CADENCE_TRACK=claude` (the default).

Lives in the shared `scripts/` dir — not `claude/` — so it ships inside the
assembled Cowork plugin root alongside the init scripts that call it
(`claude/` is a sibling of the plugin root and is not distributed).

Levels:
    root   — allow-only (the engagement root; no upward escape to guard).
    class  — deny writes above the class root and direct `.class.yaml` edits.
    task   — deny writes above the task root and direct `status.yaml` edits.

Idempotent: rewrites `.claude/settings.json` to the canonical content each run.

Usage:
    settings-gen.py <dir> <level>     # level in {root, class, task}

Exit codes:
    0 — success
    1 — validation error (unknown level, bad args)
    2 — filesystem error
"""

import argparse
import json
import sys
from pathlib import Path

# The canonical per-level permission blocks. These reproduce, byte-for-byte, the
# settings.json content the three scaffolders used to inline.
PERMISSIONS = {
    "root": {
        "allow": ["Read", "Write(./**)"],
    },
    "class": {
        "allow": ["Read", "Write(./**)"],
        "deny": ["Write(../**)", "Write(./.class.yaml)"],
    },
    "task": {
        "allow": ["Read", "Write(./**)"],
        "deny": ["Write(../**)", "Write(./status.yaml)"],
    },
}


def write_settings(target: Path, level: str) -> int:
    perms = PERMISSIONS[level]
    claude_dir = target / ".claude"
    try:
        claude_dir.mkdir(parents=True, exist_ok=True)
        with open(claude_dir / "settings.json", "w") as f:
            json.dump({"permissions": perms}, f, indent=2)
            f.write("\n")
    except OSError as exc:
        print(f"Filesystem error: {exc}", file=sys.stderr)
        return 2
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate .claude/settings.json for the Claude track."
    )
    parser.add_argument("dir", help="Target directory (root, class, or task dir)")
    parser.add_argument("level", choices=sorted(PERMISSIONS.keys()),
                        help="Hierarchy level")
    args = parser.parse_args()

    target = Path(args.dir).resolve()
    if not target.is_dir():
        print(f"Not a directory: {target}", file=sys.stderr)
        return 1

    return write_settings(target, args.level)


if __name__ == "__main__":
    sys.exit(main())
