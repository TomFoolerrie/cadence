"""
Contract tests for init-period.py

Spec: init-period.py <period> (run from task directory)
- Creates: periods/{period}/data/, workpapers/, review-notes/
- Preconditions: SKILL.md exists in cwd, period directory does not exist
- Exit codes: 0 = success, 1 = precondition failed, 2 = filesystem error
- Not idempotent
"""

import pytest

from conftest import (
    run_script,
)


pytestmark = pytest.mark.mid


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestCreatesPeriodDirectory:
    """init-period.py creates the correct subdirectory structure."""

    def test_creates_data_workpapers_review_notes(self, task_dir_in_progress):
        result = run_script("init-period.py", ["2026-03"], cwd=task_dir_in_progress)
        assert result.returncode == 0

        period_dir = task_dir_in_progress / "periods" / "2026-03"
        assert (period_dir / "data").is_dir()
        assert (period_dir / "workpapers").is_dir()
        assert (period_dir / "review-notes").is_dir()

    def test_accepts_any_period_string(self, task_dir_in_progress):
        """Any period string is accepted as long as preconditions are met."""
        result = run_script("init-period.py", ["year-end-true-up"], cwd=task_dir_in_progress)
        assert result.returncode == 0
        assert (task_dir_in_progress / "periods" / "year-end-true-up" / "data").is_dir()


# ---------------------------------------------------------------------------
# Precondition failures
# ---------------------------------------------------------------------------


class TestPreconditions:
    """init-period.py exits 1 when preconditions are not met."""

    def test_exit_1_no_skill_md(self, tmp_path):
        """Fails when SKILL.md is missing (not in a task directory)."""
        result = run_script("init-period.py", ["2026-03"], cwd=tmp_path)
        assert result.returncode == 1
        assert "Not in a task directory" in result.stderr

    def test_exit_1_period_dir_already_exists(self, task_dir_in_progress):
        """Fails when period directory already exists."""
        (task_dir_in_progress / "periods" / "2026-03").mkdir(parents=True)
        result = run_script("init-period.py", ["2026-03"], cwd=task_dir_in_progress)
        assert result.returncode == 1
        assert "already exists" in result.stderr

    def test_works_regardless_of_status(self, task_dir):
        """Works even when status is not in_progress."""
        result = run_script("init-period.py", ["2026-03"], cwd=task_dir)
        assert result.returncode == 0
        assert (task_dir / "periods" / "2026-03" / "data").is_dir()
