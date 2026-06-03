#!/usr/bin/env python3
"""Registration phase for /onboard skill.

Installs deps, adds task to manifest, optionally sets class description.

Usage: onboard-register.py <task-name> --order N --period-format fmt --anchor anchor [--description "text"]

Run from a class directory (must contain .class.yaml).

Exit codes:
    0 — task registered
    1 — precondition error (not in class dir, no SKILL.md)
    2 — system error (install or manifest failure)
"""

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent


def _run_script(name: str, args: list, cwd: str = None):
    """Run a sibling script. Returns CompletedProcess with captured stdout/stderr."""
    cmd = [sys.executable, str(SCRIPTS_DIR / name)] + args
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)


def main() -> int:
    parser = argparse.ArgumentParser(description="Registration phase for /onboard")
    parser.add_argument("task_name", help="Task name (directory name)")
    parser.add_argument("--order", type=int, required=True, help="Execution order")
    parser.add_argument("--period-format", default="monthly", help="Period format")
    parser.add_argument("--anchor", default="first_monday", help="Anchor day")
    parser.add_argument("--description", default=None, help="Class description (optional)")
    args = parser.parse_args()

    task_name = args.task_name

    # --- Precondition: must be in a class directory ---
    if not (Path.cwd() / ".class.yaml").exists():
        print("Not in a class directory (no .class.yaml)", file=sys.stderr)
        return 1

    # --- Precondition: task dir with SKILL.md must exist ---
    task_dir = Path.cwd() / task_name
    if not task_dir.is_dir():
        print(f"Task directory '{task_name}' does not exist", file=sys.stderr)
        return 1

    if not (task_dir / "SKILL.md").is_file():
        print(f"Task directory '{task_name}' has no SKILL.md", file=sys.stderr)
        return 1

    # --- Step 1: init-venv.py (idempotent, non-fatal in sandbox environments) ---
    result = _run_script("init-venv.py", [])
    if result.returncode != 0:
        warning = result.stderr.strip() or "init-venv.py failed"
        print(f"Warning: venv init skipped: {warning}", file=sys.stderr)
        # Non-fatal — install-deps will fall back to system pip

    # --- Step 2: install-deps.py (cwd = task directory) ---
    result = _run_script("install-deps.py", [], cwd=str(task_dir))
    if result.returncode != 0:
        error_msg = result.stderr.strip() or "install-deps.py failed"
        print(error_msg, file=sys.stderr)
        return 2

    # --- Step 3: edit-class-yaml.py add-task ---
    add_args = [
        "add-task", task_name,
        "--order", str(args.order),
        "--period-format", args.period_format,
        "--anchor", args.anchor,
    ]
    result = _run_script("edit-class-yaml.py", add_args)
    if result.returncode != 0:
        error_msg = result.stderr.strip() or "edit-class-yaml.py add-task failed"
        print(error_msg, file=sys.stderr)
        return result.returncode

    # --- Step 4: edit-class-yaml.py set-description (optional, non-fatal) ---
    if args.description is not None:
        result = _run_script("edit-class-yaml.py", ["set-description", args.description])
        if result.returncode != 0:
            warning = result.stderr.strip() or "set-description failed"
            print(f"Warning: could not set description: {warning}", file=sys.stderr)
            # Non-fatal — still exit 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
