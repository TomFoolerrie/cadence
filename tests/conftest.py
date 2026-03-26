"""
Shared fixtures and helpers for Context Engineer tests.

Provides:
- Builder helpers to construct temporary hierarchy trees (root/class/task)
- run_script() to invoke scripts via subprocess as black-box tests
- YAML read/write helpers
- Pre-built fixtures for common test scenarios
"""

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import pytest
import yaml

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "plugin" / "scripts"

DEFAULT_ENGAGEMENT = "Test Corp"
DEFAULT_SCHEMA_VERSION = 1

SKILL_MD_TEMPLATE = """\
# {name}

## Purpose
<!-- What does this task produce? -->

## Data Sources
<!-- Where does the input come from? -->

## Procedure
<!-- Step-by-step instructions -->

## Validation
<!-- How to verify the output -->

## Completion Criteria
<!-- What artifacts must exist when done? -->

## Contacts
<!-- Who to call when something breaks -->
"""

LEARNED_MD_TEMPLATE = """\
## Review History

| Period | Outcome | Key Number | Note |
|--------|---------|------------|------|

## Patterns

## What Didn't Work

| Period | Attempted | Result | Fix |
|--------|-----------|--------|-----|

## Open Questions
"""

AGENT_MD_ROOT_TEMPLATE = """\
# {engagement}

## Entity Details
<!-- Legal name, fiscal year, materiality, systems, contacts -->
"""

AGENT_MD_CLASS_TEMPLATE = """\
# {name}

## What This Class Covers
<!-- Domain description -->

## Key Concepts
<!-- Shared conventions for task agents -->
"""


# ---------------------------------------------------------------------------
# YAML helpers
# ---------------------------------------------------------------------------


def read_yaml(path: Path) -> dict:
    """Read and parse a YAML file. Returns {} on empty files."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return data if data is not None else {}


def write_yaml(path: Path, data: dict) -> None:
    """Write a dict as YAML to path."""
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


# ---------------------------------------------------------------------------
# Script runner
# ---------------------------------------------------------------------------


def run_script(
    script_name: str,
    args: Optional[List[str]] = None,
    cwd: Optional[Path] = None,
    timeout: int = 10,
) -> subprocess.CompletedProcess:
    """
    Run scripts/<script_name> via the current Python interpreter.

    Returns subprocess.CompletedProcess with stdout, stderr, returncode.
    """
    script_path = SCRIPTS_DIR / script_name
    cmd = [sys.executable, str(script_path)] + (args or [])
    env = {"PYTHONDONTWRITEBYTECACHE": "1"}

    full_env = os.environ.copy()
    full_env.update(env)

    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=full_env,
    )


# ---------------------------------------------------------------------------
# Hierarchy builders
# ---------------------------------------------------------------------------


def make_context_root(
    path: Path,
    engagement: str = DEFAULT_ENGAGEMENT,
    schema_version: int = DEFAULT_SCHEMA_VERSION,
) -> Path:
    """Create .context-root and root-level files at path. Returns path."""
    path.mkdir(parents=True, exist_ok=True)

    # .context-root
    write_yaml(path / ".context-root", {
        "engagement": engagement,
        "schema_version": schema_version,
    })

    # AGENT.md
    (path / "AGENT.md").write_text(
        AGENT_MD_ROOT_TEMPLATE.format(engagement=engagement)
    )

    # requirements.txt (empty)
    (path / "requirements.txt").write_text("")

    # .claude/tools/
    (path / ".claude" / "tools").mkdir(parents=True, exist_ok=True)

    # .gitignore
    (path / ".gitignore").write_text(
        "**/periods/*/data/\n**/periods/*/workpapers/\n.context-cache/\n.DS_Store\n"
    )

    return path


def make_class(
    root: Path,
    name: str = "treasury",
    manifest: Optional[List[Dict]] = None,
) -> Path:
    """
    Create a class directory under root with .class.yaml, AGENT.md, tools/, requirements.txt.
    Returns path to the class directory.
    """
    if manifest is None:
        manifest = [
            {
                "task": "monthly-bank-fees",
                "order": 1,
                "enabled": True,
                "period_format": "monthly",
                "anchor": "first_monday",
            }
        ]

    class_dir = root / name
    class_dir.mkdir(parents=True, exist_ok=True)

    # .class.yaml
    write_yaml(class_dir / ".class.yaml", {
        "schema_version": DEFAULT_SCHEMA_VERSION,
        "name": name.replace("-", " ").title(),
        "description": "",
        "manifest": manifest,
    })

    # AGENT.md
    class_name = name.replace("-", " ").title()
    (class_dir / "AGENT.md").write_text(
        AGENT_MD_CLASS_TEMPLATE.format(name=class_name)
    )

    # tools/
    (class_dir / "tools").mkdir(exist_ok=True)

    # requirements.txt
    (class_dir / "requirements.txt").write_text("")

    return class_dir


def make_task(
    class_path: Path,
    name: str = "monthly-bank-fees",
    status: str = "not_started",
    period: str = "",
    done_at: Optional[str] = None,
    issues: Optional[List[str]] = None,
) -> Path:
    """
    Create a task directory under class_path with all required files.
    Returns path to the task directory.
    """
    task_dir = class_path / name
    task_dir.mkdir(parents=True, exist_ok=True)

    # SKILL.md
    (task_dir / "SKILL.md").write_text(SKILL_MD_TEMPLATE.format(name=name))

    # learned.md
    (task_dir / "learned.md").write_text(LEARNED_MD_TEMPLATE)

    # status.yaml
    write_yaml(task_dir / "status.yaml", {
        "schema_version": DEFAULT_SCHEMA_VERSION,
        "period": period,
        "status": status,
        "issues": issues or [],
        "done_at": done_at,
    })

    # tools/
    (task_dir / "tools").mkdir(exist_ok=True)

    # periods/
    (task_dir / "periods").mkdir(exist_ok=True)

    # requirements.txt
    (task_dir / "requirements.txt").write_text("")

    return task_dir


def make_period(task_path: Path, period: str) -> Path:
    """
    Create period subdirectories under task_path/periods/<period>/.
    Returns path to the period directory.
    """
    period_dir = task_path / "periods" / period
    (period_dir / "data").mkdir(parents=True, exist_ok=True)
    (period_dir / "workpapers").mkdir(parents=True, exist_ok=True)
    (period_dir / "review-notes").mkdir(parents=True, exist_ok=True)
    return period_dir


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def engagement_root(tmp_path):
    """Minimal engagement root with .context-root, AGENT.md, requirements.txt, .claude/tools/."""
    return make_context_root(tmp_path)


@pytest.fixture
def class_dir(engagement_root):
    """
    Class directory (treasury/) under engagement root.
    .class.yaml has one monthly task entry in manifest.
    """
    return make_class(engagement_root, "treasury")


@pytest.fixture
def task_dir(class_dir):
    """Task directory (monthly-bank-fees/) under class dir. Status: not_started."""
    return make_task(class_dir, "monthly-bank-fees")


@pytest.fixture
def task_dir_in_progress(class_dir):
    """Task directory with status: in_progress, period: 2026-03."""
    return make_task(
        class_dir,
        "monthly-bank-fees",
        status="in_progress",
        period="2026-03",
    )


@pytest.fixture
def task_dir_done(class_dir):
    """Task directory with status: done, done_at set, period: 2026-03."""
    return make_task(
        class_dir,
        "monthly-bank-fees",
        status="done",
        period="2026-03",
        done_at=datetime.now(timezone.utc).isoformat(),
    )


@pytest.fixture
def task_dir_blocked(class_dir):
    """Task directory with status: blocked, issues populated."""
    return make_task(
        class_dir,
        "monthly-bank-fees",
        status="blocked",
        period="2026-03",
        issues=["Chase API returned 401 — token expired"],
    )
