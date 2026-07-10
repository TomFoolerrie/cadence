#!/usr/bin/env python3
"""Install Python dependencies from requirements.txt files, top-down through the hierarchy."""

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


def install_requirements(req_path: Path, venv_pip: Path) -> int:
    """Run pip install -r for the given requirements.txt. Returns the return code."""
    print(f"Installing {req_path} ...")
    result = subprocess.run(
        [str(venv_pip), "install", "-q", "-r", str(req_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stdout, file=sys.stderr)
        print(result.stderr, file=sys.stderr)
    return result.returncode


def main() -> int:
    cwd = Path.cwd()

    # Find context root
    root = find_context_root(cwd)
    if root is None:
        print("No .context-root found in any ancestor directory", file=sys.stderr)
        return 1

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

    # Short-circuit: if nothing is installable (all requirements empty/absent),
    # succeed without ever requiring a pip binary. This keeps the
    # "empty requirements ⇒ install-deps is a no-op" invariant honestly true
    # for offline engagements that ship no venv.
    installable = [p for p in req_paths if should_install(p)]
    if not installable:
        return 0

    # Resolve pip — prefer venv, fall back to system pip. Only reached when
    # there is at least one non-empty requirements file to install.
    venv_pip = root / "venv" / "bin" / "pip"
    if not venv_pip.exists():
        # No venv available (e.g., sandbox environment) — fall back to system pip
        import shutil
        system_pip = shutil.which("pip") or shutil.which("pip3")
        if system_pip:
            venv_pip = Path(system_pip)
            print(f"No venv found — using system pip: {system_pip}", file=sys.stderr)
        else:
            print(f"No venv found at {root}/venv/ and no system pip available", file=sys.stderr)
            return 2

    # Install sequentially (paths already filtered to non-empty)
    for req_path in installable:
        rc = install_requirements(req_path, venv_pip)
        if rc != 0:
            print(f"pip install failed for {req_path}", file=sys.stderr)
            return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
