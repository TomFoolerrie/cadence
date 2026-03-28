#!/usr/bin/env python3
"""Upload a completed period's workpapers and data to Google Drive.

Usage: archive-period.py  (run from a task directory)

Preconditions:
- cwd contains status.yaml with status: done
- .context-root exists in an ancestor directory

Exit codes: 0=success/already uploaded, 1=precondition failed, 2=Drive not configured or upload failed
"""

import sys
from pathlib import Path
from typing import Optional

import yaml

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def find_context_root(start: Path) -> Optional[Path]:
    """Walk up from start to find a directory containing .context-root."""
    current = start.resolve()
    while True:
        if (current / ".context-root").exists():
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent


def main() -> int:
    cwd = Path.cwd()

    # --- Precondition: status.yaml exists ---
    status_path = cwd / "status.yaml"
    if not status_path.exists():
        print("No status.yaml in current directory", file=sys.stderr)
        return 1

    # --- Read status.yaml ---
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
    period = data.get("period", "")

    # --- Precondition: status must be done ---
    if current_status != "done":
        print(f"Status must be done (current: {current_status})", file=sys.stderr)
        return 1

    # --- Precondition: .context-root exists ---
    root = find_context_root(cwd)
    if root is None:
        print("No .context-root found", file=sys.stderr)
        return 1

    # --- Read engagement name ---
    with open(root / ".context-root") as f:
        root_data = yaml.safe_load(f)
    engagement = root_data.get("engagement", "")

    # --- Determine class and task names from path ---
    # Structure: root / class / task (cwd)
    task_name = cwd.name
    class_name = cwd.parent.name

    # --- Build Drive path ---
    drive_path = f"{engagement}/{class_name}/{task_name}/{period}/"
    print(f"Archive target: {drive_path}")

    # --- Check for Google Drive credentials ---
    # Look for service account or OAuth credentials in common locations
    credential_paths = [
        root / ".google-credentials.json",
        root / "service-account.json",
        cwd / ".google-credentials.json",
        Path.home() / ".config" / "cadence" / "google-credentials.json",
    ]

    drive_configured = any(p.exists() for p in credential_paths)

    if not drive_configured:
        print("No Google Drive connected", file=sys.stderr)
        return 2

    # --- Upload not yet implemented ---
    print("Archive not yet implemented \u2014 skipping upload", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
