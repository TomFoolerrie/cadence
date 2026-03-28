#!/usr/bin/env python3
"""Create a Python virtual environment at the engagement root.

Usage: init-venv.py  (run from anywhere within an engagement hierarchy)

Idempotent: exits 0 if venv already exists.
Exit codes: 0=success/exists, 1=no .context-root, 2=creation failed
"""

import subprocess
import sys
from pathlib import Path
from typing import Optional


def find_context_root(start: Path) -> Optional[Path]:
    """Walk up from start to find the directory containing .context-root."""
    current = start.absolute()
    while True:
        if (current / ".context-root").exists():
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent


def main() -> int:
    cwd = Path.cwd()

    # Find context root
    root = find_context_root(cwd)
    if root is None:
        print("No .context-root found in any ancestor directory", file=sys.stderr)
        return 1

    # Unix-only paths (venv/bin/). Windows would use venv/Scripts/.
    venv_python = root / "venv" / "bin" / "python"
    if venv_python.exists():
        return 0  # already exists, idempotent

    # Create venv
    try:
        result = subprocess.run(
            [sys.executable, "-m", "venv", str(root / "venv")],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"venv creation failed: {result.stderr.strip()}", file=sys.stderr)
            return 2
    except OSError as exc:
        print(f"venv creation failed: {exc}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
