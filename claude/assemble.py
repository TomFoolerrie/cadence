#!/usr/bin/env python3
"""
assemble.py — Assemble the Cowork plugin root for the Claude track.

The shared sources of truth live at the repository top level (`scripts/`,
`skills/`). Claude Code / Cowork forbids `../` escaping in `plugin.json` paths
(they "must be relative to the plugin root and start with `./`"), so the
plugin's install root must physically contain `scripts/` and `skills/`.

This step links (or copies, with --copy) the top-level `scripts/` and `skills/`
under `claude/plugin/` as `./scripts` and `./skills`, so `${CLAUDE_PLUGIN_ROOT}`
resolves to a directory that contains them. The assembled entries are generated
artifacts (gitignored) — never hand-maintained. Idempotent.

Usage:
    python claude/assemble.py [--copy]

Exit codes:
    0 — success
    2 — filesystem error
"""

import argparse
import os
import shutil
import sys
from pathlib import Path

# Top-level shared dirs to expose under the plugin root, as ./<name>.
LINKED = ["scripts", "skills"]


def assemble(copy: bool) -> int:
    repo_root = Path(__file__).resolve().parent.parent
    plugin_root = repo_root / "claude" / "plugin"
    plugin_root.mkdir(parents=True, exist_ok=True)

    for name in LINKED:
        src = repo_root / name
        if not src.is_dir():
            print(f"missing source dir: {src}", file=sys.stderr)
            return 2

        dst = plugin_root / name

        # Clear any prior assembly (stale symlink, copy, or dir).
        if dst.is_symlink() or dst.is_file():
            dst.unlink()
        elif dst.is_dir():
            shutil.rmtree(dst)

        if copy:
            shutil.copytree(src, dst)
        else:
            # Relative symlink so the plugin root is relocatable.
            rel = os.path.relpath(src, plugin_root)
            dst.symlink_to(rel, target_is_directory=True)

        print(f"assembled claude/plugin/{name} -> {src.relative_to(repo_root)}"
              f"{' (copy)' if copy else ''}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Assemble the Cowork plugin root.")
    parser.add_argument("--copy", action="store_true",
                        help="Copy instead of symlink (for packaging/distribution).")
    args = parser.parse_args()
    try:
        return assemble(args.copy)
    except OSError as exc:
        print(f"assemble error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
