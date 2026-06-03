#!/usr/bin/env python3
"""Atomic setup phase for /start skill.

Runs set-status, install-deps, init-period, and load-context in sequence.
On failure at steps 2-4, sets status to blocked and exits 2.

Usage: start-setup.py [--period <period>]

Run from a task directory (must contain status.yaml).

Exit codes:
    0 — setup complete, context printed to stdout
    1 — precondition error (no period available, not in task dir, invalid transition)
    2 — system error (script failure; status set to blocked)
"""

import argparse
import subprocess
import sys
from pathlib import Path

import yaml

SCRIPTS_DIR = Path(__file__).resolve().parent


def _run_script(name: str, args: list):
    """Run a sibling script. Returns CompletedProcess with captured stdout/stderr."""
    cmd = [sys.executable, str(SCRIPTS_DIR / name)] + args
    return subprocess.run(cmd, capture_output=True, text=True)


def _set_blocked(reason: str) -> None:
    """Attempt to set status to blocked. Warns on failure but does not raise."""
    result = _run_script("set-status.py", ["blocked", reason])
    if result.returncode != 0:
        print(
            f"Warning: could not set blocked status: {result.stderr.strip()}",
            file=sys.stderr,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Atomic setup for /start")
    parser.add_argument("--period", default=None, help="Period string")
    args = parser.parse_args()

    # --- Read status.yaml ---
    status_path = Path.cwd() / "status.yaml"
    if not status_path.exists():
        print("No status.yaml in current directory", file=sys.stderr)
        return 1

    try:
        with open(status_path) as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            print("Corrupt status.yaml", file=sys.stderr)
            return 1
    except yaml.YAMLError:
        print("Corrupt status.yaml", file=sys.stderr)
        return 1

    current_status = data.get("status", "")
    existing_period = data.get("period") or ""

    # --- Resolve period ---
    if existing_period:
        period = existing_period
    elif args.period:
        period = args.period
    else:
        print(
            "No period available — pass --period or ensure status.yaml has a period set",
            file=sys.stderr,
        )
        return 1

    # --- Step 1: set-status.py in_progress ---
    status_args = ["in_progress"]
    if current_status == "not_started" and not existing_period and args.period:
        status_args.extend(["--period", period])

    result = _run_script("set-status.py", status_args)
    if result.returncode != 0:
        print(result.stderr.strip(), file=sys.stderr)
        return result.returncode

    # --- Step 1.5: init-venv.py (idempotent, non-fatal in sandbox environments) ---
    result = _run_script("init-venv.py", [])
    if result.returncode != 0:
        warning = result.stderr.strip() or "init-venv.py failed"
        print(f"Warning: venv init skipped: {warning}", file=sys.stderr)
        # Non-fatal — install-deps will fall back to system pip

    # --- Step 2: install-deps.py ---
    result = _run_script("install-deps.py", [])
    if result.returncode != 0:
        error_msg = result.stderr.strip() or "install-deps.py failed"
        _set_blocked(error_msg)
        print(error_msg, file=sys.stderr)
        return 2

    # --- Step 3: init-period.py (skip if dir exists) ---
    period_dir = Path.cwd() / "periods" / period
    if not period_dir.exists():
        result = _run_script("init-period.py", [period])
        if result.returncode != 0:
            error_msg = result.stderr.strip() or "init-period.py failed"
            _set_blocked(error_msg)
            print(error_msg, file=sys.stderr)
            return 2

    # --- Step 4: load-context.py --level task ---
    result = _run_script("load-context.py", ["--level", "task"])
    if result.returncode != 0:
        error_msg = result.stderr.strip() or "load-context.py failed"
        _set_blocked(error_msg)
        print(error_msg, file=sys.stderr)
        return 2

    # Print context to stdout (the payload for the agent)
    sys.stdout.write(result.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
