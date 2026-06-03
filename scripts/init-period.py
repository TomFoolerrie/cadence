#!/usr/bin/env python3
"""
init-period.py <period>

Scaffolds a period directory within a task.

Exit codes: 0 = success, 1 = precondition failed, 2 = filesystem error
"""

import re
import sys
from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# Period format regexes
# ---------------------------------------------------------------------------

FORMAT_PATTERNS = {
    "monthly": re.compile(r"^[0-9]{4}-(0[1-9]|1[0-2])$"),
    "weekly": re.compile(r"^[0-9]{4}-W(0[1-9]|[1-4][0-9]|5[0-3])$"),
    "quarterly": re.compile(r"^[0-9]{4}-Q[1-4]$"),
}


def read_yaml(path: Path) -> dict:
    with open(path) as f:
        data = yaml.safe_load(f)
    return data if data is not None else {}


def get_period_format(task_dir: Path) -> str:
    """Determine period_format from parent .class.yaml manifest. Defaults to monthly."""
    class_yaml = task_dir.parent / ".class.yaml"
    if not class_yaml.exists():
        return "monthly"

    data = read_yaml(class_yaml)
    manifest = data.get("manifest", [])
    task_name = task_dir.name

    for entry in manifest:
        if entry.get("task") == task_name:
            return entry.get("period_format", "monthly")

    return "monthly"


def validate_period(period: str, fmt: str) -> bool:
    """Return True if period matches the given format."""
    if fmt == "adhoc":
        return True
    pattern = FORMAT_PATTERNS.get(fmt)
    if pattern is None:
        return True
    return pattern.match(period) is not None


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: init-period.py <period>", file=sys.stderr)
        return 1

    period = sys.argv[1]
    cwd = Path.cwd()

    # Precondition: SKILL.md exists
    if not (cwd / "SKILL.md").exists():
        print("Not in a task directory (no SKILL.md)", file=sys.stderr)
        return 1

    # Precondition: status is in_progress
    status_path = cwd / "status.yaml"
    if not status_path.exists():
        print("Not in a task directory (no status.yaml)", file=sys.stderr)
        return 1

    status_data = read_yaml(status_path)
    current_status = status_data.get("status", "")
    if current_status != "in_progress":
        print(f"Status must be in_progress (current: {current_status})", file=sys.stderr)
        return 1

    # Determine and validate period format
    fmt = get_period_format(cwd)
    if not validate_period(period, fmt):
        print(f"Period '{period}' does not match format {fmt}", file=sys.stderr)
        return 1

    # Precondition: period directory does not exist
    period_dir = cwd / "periods" / period
    if period_dir.exists():
        print(f"Period directory periods/{period}/ already exists", file=sys.stderr)
        return 1

    # Create directories
    try:
        (period_dir / "data").mkdir(parents=True, exist_ok=True)
        (period_dir / "workpapers").mkdir(parents=True, exist_ok=True)
        (period_dir / "review-notes").mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"Filesystem error: {e}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
