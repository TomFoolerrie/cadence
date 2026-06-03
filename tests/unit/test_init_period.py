"""
Contract tests for init-period.py

Spec: init-period.py <period> (run from task directory)
- Creates: periods/{period}/data/, workpapers/, review-notes/
- Preconditions: SKILL.md exists in cwd, status is in_progress,
  period format valid per .class.yaml, period directory does not exist
- Does NOT modify status.yaml
- Exit codes: 0 = success, 1 = precondition failed, 2 = filesystem error
- Not idempotent
"""

import pytest

from conftest import (
    make_class,
    make_context_root,
    make_task,
    read_yaml,
    run_script,
    write_yaml,
)


pytestmark = pytest.mark.mid


# ---------------------------------------------------------------------------
# Helpers for period format variants
# ---------------------------------------------------------------------------


@pytest.fixture
def weekly_task(tmp_path):
    """Task in a class with period_format: weekly."""
    root = make_context_root(tmp_path)
    cls = make_class(root, "treasury", manifest=[
        {"task": "weekly-report", "order": 1, "enabled": True,
         "period_format": "weekly", "anchor": "monday"},
    ])
    return make_task(cls, "weekly-report", status="in_progress", period="2026-W12")


@pytest.fixture
def quarterly_task(tmp_path):
    """Task in a class with period_format: quarterly."""
    root = make_context_root(tmp_path)
    cls = make_class(root, "reporting", manifest=[
        {"task": "quarterly-close", "order": 1, "enabled": True,
         "period_format": "quarterly", "anchor": "first_monday"},
    ])
    return make_task(cls, "quarterly-close", status="in_progress", period="2026-Q1")


@pytest.fixture
def adhoc_task(tmp_path):
    """Task in a class with period_format: adhoc."""
    root = make_context_root(tmp_path)
    cls = make_class(root, "special", manifest=[
        {"task": "year-end-adj", "order": 1, "enabled": True,
         "period_format": "adhoc", "anchor": "first_monday"},
    ])
    return make_task(cls, "year-end-adj", status="in_progress", period="year-end-true-up")


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

    def test_does_not_modify_status_yaml(self, task_dir_in_progress):
        """status.yaml must be byte-identical before and after."""
        status_path = task_dir_in_progress / "status.yaml"
        before = status_path.read_bytes()

        run_script("init-period.py", ["2026-03"], cwd=task_dir_in_progress)

        after = status_path.read_bytes()
        assert before == after


# ---------------------------------------------------------------------------
# Period format validation — monthly (default)
# ---------------------------------------------------------------------------


class TestMonthlyFormat:
    """Period format validation for monthly (YYYY-MM)."""

    def test_valid_monthly_format(self, task_dir_in_progress):
        result = run_script("init-period.py", ["2026-03"], cwd=task_dir_in_progress)
        assert result.returncode == 0

    @pytest.mark.parametrize("bad_period", [
        "2026-3",      # single digit month
        "2026-13",     # month > 12
        "2026-00",     # month 00
        "03-2026",     # reversed
        "202603",      # no separator
        "2026/03",     # wrong separator
    ])
    def test_invalid_monthly_format(self, task_dir_in_progress, bad_period):
        result = run_script("init-period.py", [bad_period], cwd=task_dir_in_progress)
        assert result.returncode == 1

    def test_monthly_rejects_quarterly_string(self, task_dir_in_progress):
        """Monthly format should reject a quarterly period string."""
        result = run_script("init-period.py", ["2026-Q1"], cwd=task_dir_in_progress)
        assert result.returncode == 1


# ---------------------------------------------------------------------------
# Period format validation — weekly
# ---------------------------------------------------------------------------


class TestWeeklyFormat:
    """Period format validation for weekly (YYYY-WNN)."""

    def test_valid_weekly_format(self, weekly_task):
        result = run_script("init-period.py", ["2026-W12"], cwd=weekly_task)
        assert result.returncode == 0

    @pytest.mark.parametrize("bad_period", [
        "2026-W54",    # week > 53
        "2026-W0",     # single digit
        "2026-W00",    # week 00
        "2026W12",     # no dash
    ])
    def test_invalid_weekly_format(self, weekly_task, bad_period):
        result = run_script("init-period.py", [bad_period], cwd=weekly_task)
        assert result.returncode == 1


# ---------------------------------------------------------------------------
# Period format validation — quarterly
# ---------------------------------------------------------------------------


class TestQuarterlyFormat:
    """Period format validation for quarterly (YYYY-QN)."""

    def test_valid_quarterly_format(self, quarterly_task):
        result = run_script("init-period.py", ["2026-Q1"], cwd=quarterly_task)
        assert result.returncode == 0

    @pytest.mark.parametrize("bad_period", [
        "2026-Q5",     # quarter > 4
        "2026-Q0",     # quarter 0
    ])
    def test_invalid_quarterly_format(self, quarterly_task, bad_period):
        result = run_script("init-period.py", [bad_period], cwd=quarterly_task)
        assert result.returncode == 1


# ---------------------------------------------------------------------------
# Period format validation — adhoc
# ---------------------------------------------------------------------------


class TestAdhocFormat:
    """Period format validation for adhoc (any string)."""

    def test_adhoc_accepts_any_string(self, adhoc_task):
        result = run_script("init-period.py", ["year-end-true-up"], cwd=adhoc_task)
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# Default behavior
# ---------------------------------------------------------------------------


class TestDefaults:
    """Behavior when period_format is missing or task not in manifest."""

    def test_defaults_to_monthly_when_no_manifest_entry(self, tmp_path):
        """When task is not listed in .class.yaml manifest, defaults to monthly validation."""
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[])  # empty manifest
        task = make_task(cls, "unlisted-task", status="in_progress", period="2026-03")

        # Valid monthly format should pass
        result = run_script("init-period.py", ["2026-03"], cwd=task)
        assert result.returncode == 0

    def test_defaults_reject_non_monthly_when_no_manifest_entry(self, tmp_path):
        """When defaulting to monthly, non-monthly strings are rejected."""
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[])
        task = make_task(cls, "unlisted-task", status="in_progress", period="2026-W12")

        result = run_script("init-period.py", ["2026-W12"], cwd=task)
        assert result.returncode == 1


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

    def test_exit_1_status_not_started(self, task_dir):
        """Fails when status is not_started (must be in_progress)."""
        result = run_script("init-period.py", ["2026-03"], cwd=task_dir)
        assert result.returncode == 1
        assert "Status must be in_progress" in result.stderr

    def test_exit_1_status_done(self, task_dir_done):
        """Fails when status is done."""
        result = run_script("init-period.py", ["2026-03"], cwd=task_dir_done)
        assert result.returncode == 1
        assert "Status must be in_progress" in result.stderr

    def test_exit_1_status_blocked(self, task_dir_blocked):
        """Fails when status is blocked."""
        result = run_script("init-period.py", ["2026-03"], cwd=task_dir_blocked)
        assert result.returncode == 1
        assert "Status must be in_progress" in result.stderr

    def test_exit_1_period_dir_already_exists(self, task_dir_in_progress):
        """Fails when period directory already exists."""
        (task_dir_in_progress / "periods" / "2026-03").mkdir(parents=True)
        result = run_script("init-period.py", ["2026-03"], cwd=task_dir_in_progress)
        assert result.returncode == 1
        assert "already exists" in result.stderr
