#!/usr/bin/env python3
"""
check-periods.py — Scheduled infrastructure script.

Walks the engagement hierarchy and resets terminal tasks whose next anchor
date has arrived.

Usage:
    python check-periods.py [--as-of YYYY-MM-DD]

Exit codes:
    0 — success
    1 — not at engagement root (no .context-root)
    2 — filesystem / YAML error
"""

import argparse
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# Period increment helpers
# ---------------------------------------------------------------------------

def next_period_string(current_period: str, period_format: str) -> str:
    """Compute the next period string given the current one."""
    if period_format == "monthly":
        # YYYY-MM
        year, month = int(current_period[:4]), int(current_period[5:7])
        month += 1
        if month > 12:
            month = 1
            year += 1
        return f"{year:04d}-{month:02d}"

    elif period_format == "weekly":
        # YYYY-WNN
        year = int(current_period[:4])
        week = int(current_period[6:])
        week += 1
        # Check if the incremented week is valid for that ISO year
        # by seeing how many ISO weeks the year has.
        max_week = date(year, 12, 28).isocalendar()[1]  # always in last week
        if week > max_week:
            week = 1
            year += 1
        return f"{year:04d}-W{week:02d}"

    elif period_format == "quarterly":
        # YYYY-QN
        year = int(current_period[:4])
        quarter = int(current_period[6])
        quarter += 1
        if quarter > 4:
            quarter = 1
            year += 1
        return f"{year:04d}-Q{quarter}"

    return current_period


# ---------------------------------------------------------------------------
# Anchor date computation
# ---------------------------------------------------------------------------

WEEKDAY_MAP = {
    "monday": 0, "tuesday": 1, "wednesday": 2,
    "thursday": 3, "friday": 4,
}


def first_weekday_of_month(year: int, month: int, weekday: int) -> date:
    """Return the first occurrence of *weekday* (0=Mon) in the given month."""
    first = date(year, month, 1)
    diff = (weekday - first.weekday()) % 7
    return first + timedelta(days=diff)


def compute_anchor_date(
    current_period: str,
    period_format: str,
    anchor: str,
    done_at_str: str,
) -> date:
    """
    Compute the next anchor date after which the task should be reset.

    For monthly with "first_<weekday>": first occurrence of that weekday
    in the month after the next period (two months ahead of current).

    For quarterly with "first_<weekday>": first occurrence of that weekday
    in the first month of the quarter after the next quarter.

    For weekly with bare weekday: that weekday of the next ISO week.
    """
    next_per = next_period_string(current_period, period_format)

    if period_format == "monthly" and anchor.startswith("first_"):
        # Anchor is the first <weekday> of the month AFTER the next period.
        # e.g. current=2026-03, next=2026-04, anchor month=May 2026
        anchor_period = next_period_string(next_per, period_format)
        day_name = anchor[len("first_"):]
        weekday = WEEKDAY_MAP[day_name]
        year = int(anchor_period[:4])
        month = int(anchor_period[5:7])
        return first_weekday_of_month(year, month, weekday)

    elif period_format == "quarterly" and anchor.startswith("first_"):
        # Anchor is the first <weekday> of the first month of the quarter
        # AFTER the next period's quarter.
        # e.g. current=Q1, next=Q2, anchor quarter=Q3
        anchor_period = next_period_string(next_per, period_format)
        year = int(anchor_period[:4])
        quarter = int(anchor_period[6])
        month = (quarter - 1) * 3 + 1
        day_name = anchor[len("first_"):]
        weekday = WEEKDAY_MAP[day_name]
        return first_weekday_of_month(year, month, weekday)

    elif period_format == "weekly":
        # Bare weekday anchor: the weekday of the next ISO week
        # next_per is YYYY-WNN
        year = int(next_per[:4])
        week = int(next_per[6:])
        weekday = WEEKDAY_MAP.get(anchor, 0)
        # ISO weekday: Monday=1 .. Sunday=7
        return date.fromisocalendar(year, week, weekday + 1)

    # Fallback: tomorrow (should not happen with well-formed data)
    done_at = datetime.fromisoformat(done_at_str.replace("Z", "+00:00")).date()
    return done_at + timedelta(days=1)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Check and reset period tasks.")
    parser.add_argument("--as-of", dest="as_of", default=None,
                        help="Override today's date (YYYY-MM-DD)")
    args = parser.parse_args()

    # Determine "today"
    if args.as_of:
        today = date.fromisoformat(args.as_of)
    else:
        today = date.today()

    root = Path.cwd()

    # Precondition: must be at engagement root
    if not (root / ".context-root").exists():
        print("Not at engagement root (no .context-root)", file=sys.stderr)
        return 1

    try:
        # Walk immediate subdirectories looking for .class.yaml
        for entry in sorted(root.iterdir()):
            if not entry.is_dir():
                continue
            class_yaml_path = entry / ".class.yaml"
            if not class_yaml_path.exists():
                continue

            # Read class manifest
            with open(class_yaml_path) as f:
                class_data = yaml.safe_load(f)

            manifest = class_data.get("manifest", [])
            class_name = entry.name
            reset_count = 0

            reset_details = []
            skip_details = []

            for task_entry in manifest:
                task_name = task_entry.get("task", "")
                enabled = task_entry.get("enabled", True)
                period_format = task_entry.get("period_format", "monthly")
                anchor = task_entry.get("anchor", "first_monday")

                if not enabled:
                    continue
                if period_format == "adhoc":
                    continue

                # Read task status.yaml
                status_path = entry / task_name / "status.yaml"
                if not status_path.exists():
                    continue

                with open(status_path) as f:
                    status_data = yaml.safe_load(f)

                status = status_data.get("status", "")
                if status not in ("done", "abandoned"):
                    continue

                done_at_str = status_data.get("done_at")
                if not done_at_str:
                    continue

                current_period = status_data.get("period", "")

                # Compute anchor date
                anchor_date = compute_anchor_date(
                    current_period, period_format, anchor, done_at_str,
                )

                if today >= anchor_date:
                    next_per = next_period_string(current_period, period_format)
                    schema_version = status_data.get("schema_version", 1)

                    new_status = {
                        "schema_version": schema_version,
                        "period": next_per,
                        "status": "not_started",
                        "issues": [],
                        "done_at": None,
                    }

                    with open(status_path, "w") as f:
                        yaml.dump(new_status, f, default_flow_style=False, sort_keys=False)

                    reset_count += 1
                    reset_details.append(
                        f"reset {task_name} ({current_period} \u2192 {next_per})"
                    )
                else:
                    skip_details.append(
                        f"skipped {task_name} (next anchor: {anchor_date.isoformat()})"
                    )

            # Stdout summary
            if reset_details:
                print(f"{class_name}: {', '.join(reset_details)}")
                for skip in skip_details:
                    print(f"{class_name}: {skip}")
            elif skip_details:
                for skip in skip_details:
                    print(f"{class_name}: {skip}")
            else:
                print(f"{class_name}: no resets needed")

            # Git commit per class (if any resets)
            if reset_count > 0:
                try:
                    subprocess.run(
                        ["git", "add", str(entry) + "/"],
                        cwd=str(root), capture_output=True,
                    )
                    subprocess.run(
                        ["git", "commit", "-m",
                         f"[check] {class_name}: reset {reset_count} tasks for new period"],
                        cwd=str(root), capture_output=True,
                    )
                except FileNotFoundError:
                    pass  # git not available

    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
