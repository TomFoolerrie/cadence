#!/usr/bin/env python3
"""Agent/skill gateway for .class.yaml mutations.

Usage:
    edit-class-yaml.py set-description <description>
    edit-class-yaml.py add-task <task> --order <N> [--enabled] [--no-enabled] [--period-format <fmt>] [--anchor <anchor>]
    edit-class-yaml.py update-task <task> [--order <N>] [--enabled] [--no-enabled] [--period-format <fmt>] [--anchor <anchor>]
    edit-class-yaml.py remove-task <task>

Exit codes: 0=success, 1=validation error, 2=system error (corrupt YAML, filesystem)
"""

import argparse
import sys
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Valid enums
# ---------------------------------------------------------------------------

VALID_PERIOD_FORMATS = {"monthly", "weekly", "quarterly", "adhoc"}

VALID_ANCHORS = {
    "first_monday", "first_tuesday", "first_wednesday", "first_thursday", "first_friday",
    "last_monday", "last_tuesday", "last_wednesday", "last_thursday", "last_friday",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_class_yaml():
    """Load and validate .class.yaml from cwd. Exits on failure."""
    class_path = Path.cwd() / ".class.yaml"

    if not class_path.exists():
        print("No .class.yaml in current directory", file=sys.stderr)
        sys.exit(1)

    try:
        with open(class_path) as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            print("Corrupt .class.yaml", file=sys.stderr)
            sys.exit(2)
        if "manifest" not in data or not isinstance(data["manifest"], list):
            print("Corrupt .class.yaml: missing manifest", file=sys.stderr)
            sys.exit(2)
    except yaml.YAMLError:
        print("Corrupt .class.yaml", file=sys.stderr)
        sys.exit(2)

    return class_path, data


def save_class_yaml(class_path, data):
    """Write data back to .class.yaml."""
    try:
        with open(class_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    except OSError as e:
        print(f"Filesystem error: {e}", file=sys.stderr)
        sys.exit(2)


def find_task_index(manifest, task_name):
    """Return index of task in manifest, or -1 if not found."""
    for i, entry in enumerate(manifest):
        if entry.get("task") == task_name:
            return i
    return -1


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


def cmd_set_description(args):
    class_path, data = load_class_yaml()
    data["description"] = args.description
    save_class_yaml(class_path, data)


def cmd_add_task(args):
    class_path, data = load_class_yaml()
    manifest = data["manifest"]

    # Validate task not already in manifest
    if find_task_index(manifest, args.task) != -1:
        print(f"Task '{args.task}' already in manifest", file=sys.stderr)
        sys.exit(1)

    # Validate task directory exists with SKILL.md
    task_dir = Path.cwd() / args.task
    if not task_dir.is_dir():
        print(f"Task directory '{args.task}' does not exist", file=sys.stderr)
        sys.exit(1)
    if not (task_dir / "SKILL.md").is_file():
        print(f"Task directory '{args.task}' has no SKILL.md", file=sys.stderr)
        sys.exit(1)

    # Validate order
    if args.order <= 0:
        print("--order must be a positive integer", file=sys.stderr)
        sys.exit(1)

    # Validate enums
    if args.period_format not in VALID_PERIOD_FORMATS:
        print(f"Invalid period-format: '{args.period_format}'", file=sys.stderr)
        sys.exit(1)
    if args.anchor not in VALID_ANCHORS:
        print(f"Invalid anchor: '{args.anchor}'", file=sys.stderr)
        sys.exit(1)

    # Build entry with all fields explicit
    entry = {
        "task": args.task,
        "order": args.order,
        "enabled": args.enabled,
        "period_format": args.period_format,
        "anchor": args.anchor,
    }
    manifest.append(entry)
    save_class_yaml(class_path, data)


def cmd_update_task(args):
    class_path, data = load_class_yaml()
    manifest = data["manifest"]

    idx = find_task_index(manifest, args.task)
    if idx == -1:
        print(f"Task '{args.task}' not in manifest", file=sys.stderr)
        sys.exit(1)

    # Check at least one field provided
    has_update = False
    if args.order is not None:
        has_update = True
    if args.enabled is not None:
        has_update = True
    if args.period_format is not None:
        has_update = True
    if args.anchor is not None:
        has_update = True

    if not has_update:
        print("No fields provided to update", file=sys.stderr)
        sys.exit(1)

    entry = manifest[idx]

    if args.order is not None:
        if args.order <= 0:
            print("--order must be a positive integer", file=sys.stderr)
            sys.exit(1)
        entry["order"] = args.order

    if args.enabled is not None:
        entry["enabled"] = args.enabled

    if args.period_format is not None:
        if args.period_format not in VALID_PERIOD_FORMATS:
            print(f"Invalid period-format: '{args.period_format}'", file=sys.stderr)
            sys.exit(1)
        entry["period_format"] = args.period_format

    if args.anchor is not None:
        if args.anchor not in VALID_ANCHORS:
            print(f"Invalid anchor: '{args.anchor}'", file=sys.stderr)
            sys.exit(1)
        entry["anchor"] = args.anchor

    save_class_yaml(class_path, data)


def cmd_remove_task(args):
    class_path, data = load_class_yaml()
    manifest = data["manifest"]

    idx = find_task_index(manifest, args.task)
    if idx == -1:
        print(f"Task '{args.task}' not in manifest", file=sys.stderr)
        sys.exit(1)

    manifest.pop(idx)
    save_class_yaml(class_path, data)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Edit .class.yaml")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # set-description
    sp_desc = subparsers.add_parser("set-description", help="Set class description")
    sp_desc.add_argument("description", help="Description text")

    # add-task
    sp_add = subparsers.add_parser("add-task", help="Add task to manifest")
    sp_add.add_argument("task", help="Task name (directory name)")
    sp_add.add_argument("--order", type=int, required=True, help="Execution order (positive integer)")
    sp_add.add_argument(
        "--enabled", "--no-enabled",
        dest="enabled",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Whether task is enabled (default: true)",
    )
    sp_add.add_argument("--period-format", default="monthly", help="Period format (default: monthly)")
    sp_add.add_argument("--anchor", default="first_monday", help="Anchor day (default: first_monday)")

    # update-task
    sp_upd = subparsers.add_parser("update-task", help="Update task in manifest")
    sp_upd.add_argument("task", help="Task name (directory name)")
    sp_upd.add_argument("--order", type=int, default=None, help="Execution order")
    sp_upd.add_argument(
        "--enabled", "--no-enabled",
        dest="enabled",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Whether task is enabled",
    )
    sp_upd.add_argument("--period-format", default=None, help="Period format")
    sp_upd.add_argument("--anchor", default=None, help="Anchor day")

    # remove-task
    sp_rm = subparsers.add_parser("remove-task", help="Remove task from manifest")
    sp_rm.add_argument("task", help="Task name (directory name)")

    args = parser.parse_args()

    if args.command == "set-description":
        cmd_set_description(args)
    elif args.command == "add-task":
        cmd_add_task(args)
    elif args.command == "update-task":
        cmd_update_task(args)
    elif args.command == "remove-task":
        cmd_remove_task(args)


if __name__ == "__main__":
    main()
