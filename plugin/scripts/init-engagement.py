#!/usr/bin/env python3
"""Scaffold a new engagement directory with git initialized.

Usage: init-engagement.py <path> [--name <engagement-name>]

Creates the engagement root directory with all required files and initializes
a git repository with an initial commit.

Exit codes: 0 = success, 1 = validation error, 2 = system error
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml


AGENT_MD_TEMPLATE = """\
# {engagement}

## Entity Details
<!-- Legal name, fiscal year, materiality, systems, contacts -->
"""

GITIGNORE_CONTENT = """\
**/periods/*/data/
**/periods/*/workpapers/
.context-cache/
.DS_Store
venv/
"""


def derive_name(path_str: str) -> str:
    """Derive engagement name from directory basename.

    Converts hyphens and underscores to spaces, then title-cases.
    """
    basename = Path(path_str.rstrip("/")).name
    return basename.replace("-", " ").replace("_", " ").title()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scaffold a new engagement directory."
    )
    parser.add_argument("path", help="Path for the new engagement directory")
    parser.add_argument(
        "--name",
        dest="name",
        default=None,
        help="Engagement name (default: derived from directory basename)",
    )

    args = parser.parse_args()

    target = Path(args.path).resolve()
    engagement_name = args.name if args.name else derive_name(args.path)

    # --- Preconditions ---

    # Check git availability before writing any files (side-effect guarantee)
    try:
        subprocess.run(
            ["git", "--version"],
            capture_output=True,
            check=True,
        )
    except FileNotFoundError:
        print("git is not available", file=sys.stderr)
        return 2

    if target.exists():
        print(f"Path already exists: {target}", file=sys.stderr)
        return 1

    # --- Write files ---

    try:
        target.mkdir(parents=True)

        # .context-root
        context_root_data = {
            "engagement": engagement_name,
            "schema_version": 1,
        }
        with open(target / ".context-root", "w") as f:
            yaml.dump(context_root_data, f, default_flow_style=False, sort_keys=False)

        # AGENT.md
        (target / "AGENT.md").write_text(
            AGENT_MD_TEMPLATE.format(engagement=engagement_name)
        )

        # .claude/tools/
        (target / ".claude" / "tools").mkdir(parents=True)

        # .claude/settings.json (write scope enforcement)
        settings = {
            "permissions": {
                "allow": ["Read", "Write(./**)"],
            }
        }
        with open(target / ".claude" / "settings.json", "w") as f:
            json.dump(settings, f, indent=2)
            f.write("\n")

        # .gitignore
        (target / ".gitignore").write_text(GITIGNORE_CONTENT)

        # requirements.txt
        (target / "requirements.txt").write_text("")

    except OSError as exc:
        print(f"Filesystem error: {exc}", file=sys.stderr)
        return 2

    # --- Git init and initial commit ---

    try:
        subprocess.run(
            ["git", "init"],
            cwd=str(target),
            capture_output=True,
            text=True,
            check=True,
        )
        subprocess.run(
            ["git", "add", "."],
            cwd=str(target),
            capture_output=True,
            text=True,
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", f"[init] {engagement_name}: engagement created"],
            cwd=str(target),
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        print("git is not available", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as exc:
        print(f"git error: {exc.stderr.strip()}", file=sys.stderr)
        return 2

    # Create engagement venv
    try:
        subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parent / "init-venv.py")],
            cwd=str(target),
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        print(f"Warning: venv creation failed: {exc.stderr.strip()}", file=sys.stderr)
        # Non-fatal — engagement is usable without venv

    return 0


if __name__ == "__main__":
    sys.exit(main())
