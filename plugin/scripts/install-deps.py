#!/usr/bin/env python3
"""Install Python dependencies from requirements.txt files, top-down through the hierarchy."""

import subprocess
import sys
from pathlib import Path
from typing import Optional


def find_context_root(start: Path) -> Optional[Path]:
    """Walk up from start to find the directory containing .context-root."""
    current = start.resolve()
    while True:
        if (current / ".context-root").exists():
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent


def detect_level(cwd: Path):
    """Determine the current level and return (level, root, class_dir, task_dir)."""
    if (cwd / "SKILL.md").exists():
        return "task"
    elif (cwd / ".class.yaml").exists():
        return "class"
    elif (cwd / ".context-root").exists():
        return "root"
    return "root"


def should_install(req_path: Path) -> bool:
    """Return True if requirements.txt exists and is non-empty."""
    if not req_path.exists():
        return False
    content = req_path.read_text().strip()
    return len(content) > 0


def install_requirements(req_path: Path) -> int:
    """Run pip install -r for the given requirements.txt. Returns the return code."""
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(req_path)],
        capture_output=False,
    )
    return result.returncode


def main():
    cwd = Path.cwd()

    # Find context root
    root = find_context_root(cwd)
    if root is None:
        print("No .context-root found in any ancestor directory", file=sys.stderr)
        sys.exit(1)

    # Determine level
    level = detect_level(cwd)

    # Build list of requirements.txt paths to install, top-down
    req_paths = []

    # Always include root
    req_paths.append(root / "requirements.txt")

    if level == "class":
        req_paths.append(cwd / "requirements.txt")
    elif level == "task":
        class_dir = cwd.parent
        req_paths.append(class_dir / "requirements.txt")
        req_paths.append(cwd / "requirements.txt")

    # Install sequentially, skipping missing/empty
    for req_path in req_paths:
        if not should_install(req_path):
            continue
        rc = install_requirements(req_path)
        if rc != 0:
            print(f"pip install failed for {req_path}", file=sys.stderr)
            sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
