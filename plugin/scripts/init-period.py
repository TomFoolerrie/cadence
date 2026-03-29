#!/usr/bin/env python3
"""
init-period.py <period>

Scaffolds a period directory within a task.

Exit codes: 0 = success, 1 = precondition failed, 2 = filesystem error
"""

import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: init-period.py <period>", file=sys.stderr)
        return 1

    period = sys.argv[1]
    cwd = Path.cwd()

    # Precondition: SKILL.md exists (must be in a task directory)
    if not (cwd / "SKILL.md").exists():
        print("Not in a task directory (no SKILL.md)", file=sys.stderr)
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
