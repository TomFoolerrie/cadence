#!/usr/bin/env python3
"""Setup phase for /onboard skill (task-level).

Runs load-context and init-task in sequence.

Usage: onboard-setup.py <task-name>

Run from a class directory (must contain .class.yaml).

Exit codes:
    0 — setup complete, context printed to stdout
    1 — precondition error (not in class dir, task exists)
    2 — system error (script failure)
"""

import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent


def _run_script(name: str, args: list):
    """Run a sibling script. Returns CompletedProcess with captured stdout/stderr."""
    cmd = [sys.executable, str(SCRIPTS_DIR / name)] + args
    return subprocess.run(cmd, capture_output=True, text=True)


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: onboard-setup.py <task-name>", file=sys.stderr)
        return 1

    task_name = sys.argv[1]

    # --- Precondition: must be in a class directory ---
    if not (Path.cwd() / ".class.yaml").exists():
        print("Not in a class directory (no .class.yaml)", file=sys.stderr)
        return 1

    # --- Step 1: load-context.py --level class ---
    result = _run_script("load-context.py", ["--level", "class"])
    if result.returncode != 0:
        error_msg = result.stderr.strip() or "load-context.py failed"
        print(error_msg, file=sys.stderr)
        return 2

    context_output = result.stdout

    # --- Step 2: init-task.py <task-name> ---
    result = _run_script("init-task.py", [task_name])
    if result.returncode != 0:
        error_msg = result.stderr.strip() or "init-task.py failed"
        print(error_msg, file=sys.stderr)
        return result.returncode

    # Print context to stdout
    sys.stdout.write(context_output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
