"""
Shared fixtures and helpers for Cadence tests.

Provides:
- Builder helpers to construct temporary hierarchy trees (root/class/task)
- run_script() to invoke scripts via subprocess as black-box tests
- YAML read/write helpers
- Pre-built fixtures for common test scenarios
"""

import json
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
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

DEFAULT_ENGAGEMENT = "Test Corp"
DEFAULT_SCHEMA_VERSION = 1

SKILL_MD_TEMPLATE = """\
---
name: {name}
description: >
  TODO — describe what this folder produces.
---

# {name}

## Purpose

<!-- What does this produce? Which accounts does it touch? -->

## Data Sources

<!-- Where does the data come from? Format? What if it's missing? -->

## Procedure

<!-- Step-by-step processing logic. Reference shared tools by path. -->

## Validation

<!-- How to verify the output is correct. -->

## Contacts

<!-- Who to ask when something goes wrong. -->

## Completion Criteria

<!-- What does a completed task look like? What artifacts must exist? -->
"""

LEARNED_MD_TEMPLATE = """\
# Learned Patterns

## Review History

| Period | Outcome | Key Number | Note |
|--------|---------|------------|------|

## Patterns

<!-- Entries use structured delta format:
- **Pattern description**
  Confirmed: N | Contradicted: N | First seen: YYYY-MM
  Used for: how this pattern informs execution
-->

## What Didn't Work

<!-- Entries use structured delta format:
- **What was attempted**
  Confirmed: N | Contradicted: N | First seen: YYYY-MM
  Result: what happened | Fix: how it was resolved
-->

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
    env: Optional[Dict[str, str]] = None,
) -> subprocess.CompletedProcess:
    """
    Run scripts/<script_name> via the current Python interpreter.

    Pass ``env`` to set/override environment variables for the child (e.g.
    ``{"CADENCE_TRACK": "pi"}``); it is layered over the inherited environment.

    Returns subprocess.CompletedProcess with stdout, stderr, returncode.
    """
    script_path = SCRIPTS_DIR / script_name
    cmd = [sys.executable, str(script_path)] + (args or [])
    overrides = {"PYTHONDONTWRITEBYTECACHE": "1"}
    if env:
        overrides.update(env)

    full_env = os.environ.copy()
    full_env.update(overrides)

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

    # AGENTS.md
    (path / "AGENTS.md").write_text(
        AGENT_MD_ROOT_TEMPLATE.format(engagement=engagement)
    )

    # requirements.txt (empty)
    (path / "requirements.txt").write_text("")

    # tools/ — track-neutral global shared tools (re-homed from .claude/tools/)
    (path / "tools").mkdir(parents=True, exist_ok=True)

    # .claude/settings.json — default (claude) track enforcement
    import json
    settings = {"permissions": {"allow": ["Read", "Write(./**)"]}}
    (path / ".claude").mkdir(parents=True, exist_ok=True)
    with open(path / ".claude" / "settings.json", "w") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")

    # .gitignore
    (path / ".gitignore").write_text(
        "**/periods/*/data/\n**/periods/*/workpapers/\n.context-cache/\n.DS_Store\nvenv/\n"
    )

    return path


def make_class(
    root: Path,
    name: str = "treasury",
    manifest: Optional[List[Dict]] = None,
) -> Path:
    """
    Create a class directory under root with .class.yaml, AGENTS.md, tools/, requirements.txt.
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

    # AGENTS.md
    class_name = name.replace("-", " ").title()
    (class_dir / "AGENTS.md").write_text(
        AGENT_MD_CLASS_TEMPLATE.format(name=class_name)
    )

    # tools/
    (class_dir / "tools").mkdir(exist_ok=True)

    # .claude/settings.json
    (class_dir / ".claude").mkdir(parents=True, exist_ok=True)
    settings = {
        "permissions": {
            "allow": ["Read", "Write(./**)"],
            "deny": ["Write(../**)", "Write(./.class.yaml)"]
        }
    }
    with open(class_dir / ".claude" / "settings.json", "w") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")

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

    # reference.md
    reference_content = (
        f"# reference — {name}\n\n"
        "## Write Restrictions\n"
        "- `status.yaml` — Do not edit directly. Use: `python ${CLAUDE_PLUGIN_ROOT}/scripts/set-status.py <status>`\n"
        "- Do not create directories with mkdir. Use: `python ${CLAUDE_PLUGIN_ROOT}/scripts/init-period.py <period>`\n\n"
        "## Plugin Scripts\n"
        "| Script | Purpose | Usage |\n"
        "|--------|---------|-------|\n"
        "| `set-status.py` | Change task status | `python ${CLAUDE_PLUGIN_ROOT}/scripts/set-status.py <status>` |\n"
        "| `init-period.py` | Scaffold a new period directory | `python ${CLAUDE_PLUGIN_ROOT}/scripts/init-period.py <period>` |\n"
    )
    (task_dir / "reference.md").write_text(reference_content)

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

    # .claude/settings.json
    (task_dir / ".claude").mkdir(parents=True, exist_ok=True)
    settings = {
        "permissions": {
            "allow": ["Read", "Write(./**)"],
            "deny": ["Write(../**)", "Write(./status.yaml)"]
        }
    }
    with open(task_dir / ".claude" / "settings.json", "w") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")

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


def make_venv(root: Path) -> Path:
    """Create a mock venv structure for testing (avoids real python -m venv)."""
    venv_dir = root / "venv" / "bin"
    venv_dir.mkdir(parents=True, exist_ok=True)
    # Mock pip as a shell script that succeeds
    pip_path = venv_dir / "pip"
    pip_path.write_text("#!/bin/sh\nexit 0\n")
    pip_path.chmod(0o755)
    # Mock python
    python_path = venv_dir / "python"
    python_path.write_text("#!/bin/sh\nexit 0\n")
    python_path.chmod(0o755)
    return root / "venv"


def start_to_done(task_dir, period):
    """Run a task through the full start-to-done cycle with assertions."""
    result = run_script("set-status.py", ["in_progress", "--period", period], cwd=task_dir)
    assert result.returncode == 0
    result = run_script("init-period.py", [period], cwd=task_dir)
    assert result.returncode == 0
    result = run_script("set-status.py", ["review_ready"], cwd=task_dir)
    assert result.returncode == 0
    result = run_script("set-status.py", ["done"], cwd=task_dir)
    assert result.returncode == 0


def run_check_periods(cwd, as_of=None):
    """Run check-periods.py with optional --as-of flag."""
    args = []
    if as_of:
        args.extend(["--as-of", as_of])
    return run_script("check-periods.py", args, cwd=cwd)


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def engagement_root(tmp_path):
    """Minimal engagement root with .context-root, AGENTS.md, requirements.txt, tools/."""
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
