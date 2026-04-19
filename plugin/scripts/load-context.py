#!/usr/bin/env python3
"""
load-context.py — Pure context assembly.

Reads hierarchy files (root / class / task) and prints them to stdout.
No side effects (pure read).

Usage:
    load-context.py --level root|class|task [--orchestrator]
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

import yaml


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def find_context_root(start: Path) -> Optional[Path]:
    """Walk up from *start* looking for a directory containing .context-root."""
    current = start.absolute()
    while True:
        if (current / ".context-root").exists():
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent


def find_class_dir(start: Path, root: Path) -> Optional[Path]:
    """Walk up from *start* (inclusive) looking for a directory with .class.yaml,
    stopping at (and including) *root*."""
    current = start.absolute()
    root = root.absolute()
    while True:
        if (current / ".class.yaml").exists():
            return current
        if current == root:
            return None
        parent = current.parent
        if parent == current:
            return None
        current = parent


def section(title: str, content: str) -> str:
    """Format a section with ── header ── delimiters."""
    return f"── {title} ──\n{content}\n"


def read_file(path: Path) -> str:
    """Read a file and return its contents, or empty string if missing."""
    if path.exists():
        return path.read_text()
    return ""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Assemble context from hierarchy.")
    parser.add_argument(
        "--level",
        required=True,
        choices=["root", "class", "task"],
        help="Hierarchy level to load.",
    )
    parser.add_argument(
        "--orchestrator",
        action="store_true",
        help="Include .class.yaml (only valid with --level class).",
    )
    args = parser.parse_args()

    # --orchestrator only valid with --level class
    if args.orchestrator and args.level != "class":
        print("--orchestrator is only valid with --level class", file=sys.stderr)
        return 1

    cwd = Path.cwd()

    # Find .context-root
    root = find_context_root(cwd)
    if root is None:
        print("No .context-root found in any ancestor directory", file=sys.stderr)
        return 1

    # Validate .context-root YAML
    try:
        with open(root / ".context-root") as f:
            cr_data = yaml.safe_load(f)
        if not isinstance(cr_data, dict) or "engagement" not in cr_data:
            print("Invalid .context-root: missing engagement key", file=sys.stderr)
            return 1
    except yaml.YAMLError:
        print("Invalid .context-root: missing engagement key", file=sys.stderr)
        return 1

    output_parts: list[str] = []

    # --- Root AGENT.md (always included) ---
    root_agent = read_file(root / "AGENT.md")
    output_parts.append(section("root/AGENT.md", root_agent))

    if args.level == "root":
        print("\n".join(output_parts).rstrip())
        return 0

    # --- Class level ---
    class_dir = find_class_dir(cwd, root)
    if class_dir is None:
        print("Not in a class directory", file=sys.stderr)
        return 1

    class_agent = read_file(class_dir / "AGENT.md")
    output_parts.append(section("class/AGENT.md", class_agent))

    if args.level == "class":
        if args.orchestrator:
            class_yaml_content = read_file(class_dir / ".class.yaml")
            output_parts.append(section(".class.yaml", class_yaml_content))
        print("\n".join(output_parts).rstrip())
        return 0

    # --- Task level ---
    # For task level, cwd must contain SKILL.md (or we walk up to find it,
    # but the spec says "cwd has SKILL.md").
    # We also need to find the task dir — walk up from cwd looking for SKILL.md
    task_dir = None
    search = cwd.absolute()
    while True:
        if (search / "SKILL.md").exists():
            task_dir = search
            break
        if search == root:
            break
        parent = search.parent
        if parent == search:
            break
        search = parent

    if task_dir is None:
        print("Not in a task directory (no SKILL.md found)", file=sys.stderr)
        return 1

    # SKILL.md
    skill_content = read_file(task_dir / "SKILL.md")
    output_parts.append(section("SKILL.md", skill_content))

    # learned.md
    learned_content = read_file(task_dir / "learned.md")
    output_parts.append(section("learned.md", learned_content))

    # status.yaml — read once; derive both display content and blocked hint
    status_raw = read_file(task_dir / "status.yaml")
    output_parts.append(section("status.yaml", status_raw))
    try:
        status_data = yaml.safe_load(status_raw) if status_raw else None
        if isinstance(status_data, dict) and status_data.get("status") == "blocked":
            output_parts.append(
                "\u26a0 Recovery: This task is blocked. Review issues[] and decide "
                "\u2014 retry (resets to not_started) or investigate further."
            )
    except yaml.YAMLError:
        pass

    # reference.md (write restrictions and script docs)
    reference_content = read_file(task_dir / "reference.md")
    if reference_content:
        output_parts.append(section("reference.md", reference_content))

    # Tools section
    task_tools = task_dir / "tools"
    class_tools = class_dir / "tools"
    global_tools = root / ".claude" / "tools"

    tool_lines: list[str] = []

    if task_tools.is_dir() and any(task_tools.iterdir()):
        rel = os.path.relpath(task_tools, root)
        tool_lines.append(f"task:   {rel}")
        # List individual tools
        for t in sorted(task_tools.iterdir()):
            if t.is_file():
                tool_lines.append(f"  {os.path.relpath(t, root)}")

    if class_tools.is_dir() and any(class_tools.iterdir()):
        rel = os.path.relpath(class_tools, root)
        tool_lines.append(f"class:  {rel}")
        for t in sorted(class_tools.iterdir()):
            if t.is_file():
                tool_lines.append(f"  {os.path.relpath(t, root)}")

    if global_tools.is_dir() and any(global_tools.iterdir()):
        rel = os.path.relpath(global_tools, root)
        tool_lines.append(f"global: {rel}")
        for t in sorted(global_tools.iterdir()):
            if t.is_file():
                tool_lines.append(f"  {os.path.relpath(t, root)}")

    if tool_lines:
        output_parts.append(section("tools", "\n".join(tool_lines)))

    print("\n".join(output_parts).rstrip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
