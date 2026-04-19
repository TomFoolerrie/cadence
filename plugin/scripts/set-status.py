#!/usr/bin/env python3
"""Agent/skill gateway for task-level status.yaml transitions.

Usage: set-status.py <status> [reason] [--period <period>]

Validates that the requested transition is legal before writing.
Exit codes: 0=success, 1=invalid transition/missing reason/missing file, 2=corrupt YAML
"""

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

PERIOD_PATTERNS = [
    re.compile(r"^\d{4}-\d{2}$"),         # monthly: 2026-03
    re.compile(r"^\d{4}-Q[1-4]$"),         # quarterly: 2026-Q1
    re.compile(r"^\d{4}$"),                # annual: 2026
    re.compile(r"^\d{4}-\d{2}-\d{2}$"),   # adhoc: 2026-03-15
    re.compile(r"^\d{4}-W\d{2}$"),         # weekly: 2026-W12
]

# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

VALID_TRANSITIONS = {
    ("not_started", "in_progress"),
    ("in_progress", "in_progress"),
    ("in_progress", "review_ready"),
    ("in_progress", "blocked"),
    ("review_ready", "in_progress"),
    ("review_ready", "done"),
    ("blocked", "not_started"),
    ("blocked", "abandoned"),
}

REQUIRES_REASON = {"blocked", "abandoned"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Set task status")
    parser.add_argument("status", help="Target status")
    parser.add_argument("reason", nargs="?", default=None, help="Reason (required for blocked/abandoned)")
    parser.add_argument("--period", default=None, help="Period string (only on not_started -> in_progress)")
    args = parser.parse_args()

    new_status = args.status
    reason = args.reason
    period = args.period

    # --- Precondition: status.yaml exists ---
    status_path = Path.cwd() / "status.yaml"
    if not status_path.exists():
        print("No status.yaml in current directory", file=sys.stderr)
        return 1

    # --- Precondition: valid YAML ---
    try:
        with open(status_path) as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            print("Corrupt status.yaml", file=sys.stderr)
            return 2
    except yaml.YAMLError:
        print("Corrupt status.yaml", file=sys.stderr)
        return 2

    current_status = data.get("status")

    # --- Precondition: reason required for blocked/abandoned ---
    if new_status in REQUIRES_REASON and not reason:
        print("Reason required for blocked/abandoned status", file=sys.stderr)
        return 1

    # --- Precondition: --period only valid on not_started -> in_progress ---
    if period is not None and not (current_status == "not_started" and new_status == "in_progress"):
        print("--period is only valid on not_started \u2192 in_progress", file=sys.stderr)
        return 1

    # --- Precondition: period must match a known format ---
    if period is not None and not any(p.match(period) for p in PERIOD_PATTERNS):
        print(f"Invalid period format: {period!r}", file=sys.stderr)
        return 1

    # --- Precondition: legal transition ---
    if (current_status, new_status) not in VALID_TRANSITIONS:
        print(f"Invalid transition: {current_status} \u2192 {new_status}", file=sys.stderr)
        return 1

    # --- in_progress -> in_progress is a no-op ---
    if current_status == "in_progress" and new_status == "in_progress":
        return 0

    # --- Apply transition ---
    if new_status == "in_progress" and current_status == "not_started":
        data["status"] = "in_progress"
        if period is not None:
            data["period"] = period

    elif new_status == "in_progress" and current_status == "review_ready":
        data["status"] = "in_progress"
        data["issues"] = []

    elif new_status == "review_ready":
        data["status"] = "review_ready"
        data["issues"] = []

    elif new_status == "blocked":
        data["status"] = "blocked"
        data["issues"] = [reason]

    elif new_status == "done":
        data["status"] = "done"
        data["issues"] = []
        data["done_at"] = datetime.now(timezone.utc).isoformat()

    elif new_status == "abandoned":
        data["status"] = "abandoned"
        data["issues"] = [reason]
        data["done_at"] = datetime.now(timezone.utc).isoformat()

    elif new_status == "not_started" and current_status == "blocked":
        data["status"] = "not_started"
        data["issues"] = []
        data["done_at"] = None

    # --- Write ---
    try:
        with open(status_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    except OSError as e:
        print(f"Filesystem error: {e}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
