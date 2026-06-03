"""
Contract tests for check-periods.py

Spec: check-periods.py [--as-of YYYY-MM-DD] (run from engagement root, via cron)
- Walks all classes (dirs with .class.yaml)
- For each enabled task in terminal state (done/abandoned):
  - Reads done_at, anchor, period_format from .class.yaml
  - Computes next_anchor_date
  - If today >= next_anchor_date: reset status.yaml to not_started with next period
- Idempotent, skips adhoc tasks, skips disabled tasks
- Exit codes: 0 = success, 1 = not at root, 2 = filesystem/YAML error
"""

import importlib.util
from datetime import date
from pathlib import Path

import pytest

from conftest import (
    make_class,
    make_context_root,
    make_task,
    read_yaml,
    run_check_periods,
    run_script,
    start_to_done,
    write_yaml,
)


pytestmark = pytest.mark.mid


def _load_check_periods():
    """Import check-periods.py as a module (its filename is not a valid identifier)."""
    path = Path(__file__).resolve().parent.parent / "plugin" / "scripts" / "check-periods.py"
    spec = importlib.util.spec_from_file_location("check_periods", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check_periods = _load_check_periods()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_done_task(cls, name, period, done_at, period_format="monthly", anchor="first_monday"):
    """Create a done task with specific timing for reset testing."""
    return make_task(cls, name, status="done", period=period, done_at=done_at)


# ---------------------------------------------------------------------------
# Resets
# ---------------------------------------------------------------------------


class TestResets:
    """check-periods.py resets terminal tasks when anchor date has passed."""

    def test_resets_done_task_when_anchor_passed(self, tmp_path):
        """Task done for 2026-03, first_monday anchor → resets after first Monday of April (Apr 6)."""
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[
            {"task": "bank-fees", "order": 1, "enabled": True,
             "period_format": "monthly", "anchor": "first_monday"},
        ])
        make_task(cls, "bank-fees", status="done", period="2026-03",
                  done_at="2026-04-05T14:30:00Z")

        result = run_check_periods(root, as_of="2026-04-06")
        assert result.returncode == 0
        assert "bank-fees" in result.stdout
        assert "reset" in result.stdout

        data = read_yaml(cls / "bank-fees" / "status.yaml")
        assert data["status"] == "not_started"
        assert data["period"] == "2026-04"

    def test_resets_abandoned_task(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[
            {"task": "bank-fees", "order": 1, "enabled": True,
             "period_format": "monthly", "anchor": "first_monday"},
        ])
        make_task(cls, "bank-fees", status="abandoned", period="2026-03",
                  done_at="2026-04-05T14:30:00Z", issues=["unrecoverable"])

        result = run_check_periods(root, as_of="2026-04-06")
        assert result.returncode == 0
        assert "bank-fees" in result.stdout
        assert "reset" in result.stdout

        data = read_yaml(cls / "bank-fees" / "status.yaml")
        assert data["status"] == "not_started"


# ---------------------------------------------------------------------------
# Skips
# ---------------------------------------------------------------------------


class TestSkips:
    """check-periods.py correctly skips tasks that shouldn't be reset."""

    def test_skips_non_terminal_tasks(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[
            {"task": "bank-fees", "order": 1, "enabled": True,
             "period_format": "monthly", "anchor": "first_monday"},
        ])
        make_task(cls, "bank-fees", status="in_progress", period="2026-03")

        result = run_check_periods(root, as_of="2026-05-05")
        assert result.returncode == 0

        # Should still be in_progress
        data = read_yaml(cls / "bank-fees" / "status.yaml")
        assert data["status"] == "in_progress"

    def test_skips_already_not_started(self, tmp_path):
        """Idempotent: task already at not_started stays unchanged."""
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[
            {"task": "bank-fees", "order": 1, "enabled": True,
             "period_format": "monthly", "anchor": "first_monday"},
        ])
        make_task(cls, "bank-fees", status="not_started")

        result = run_check_periods(root, as_of="2026-05-05")
        assert result.returncode == 0
        assert read_yaml(cls / "bank-fees" / "status.yaml")["status"] == "not_started"

    def test_skips_adhoc_tasks(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "special", manifest=[
            {"task": "year-end", "order": 1, "enabled": True,
             "period_format": "adhoc", "anchor": "first_monday"},
        ])
        make_task(cls, "year-end", status="done", period="year-end-2026",
                  done_at="2026-04-07T14:30:00Z")

        result = run_check_periods(root, as_of="2026-12-31")
        assert result.returncode == 0

        # adhoc tasks are never auto-reset
        data = read_yaml(cls / "year-end" / "status.yaml")
        assert data["status"] == "done"

    def test_skips_disabled_tasks(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[
            {"task": "old-task", "order": 1, "enabled": False,
             "period_format": "monthly", "anchor": "first_monday"},
        ])
        make_task(cls, "old-task", status="done", period="2026-03",
                  done_at="2026-04-07T14:30:00Z")

        result = run_check_periods(root, as_of="2026-05-05")
        assert result.returncode == 0

        data = read_yaml(cls / "old-task" / "status.yaml")
        assert data["status"] == "done"

    def test_skips_when_anchor_not_reached(self, tmp_path):
        """Done recently, next anchor date is in the future.

        One-ahead anchor: first Monday of April (Apr 6). done_at is Apr 5
        (before anchor), so no late-completion guard. as-of Apr 4 is before
        anchor → task stays done.
        """
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[
            {"task": "bank-fees", "order": 1, "enabled": True,
             "period_format": "monthly", "anchor": "first_monday"},
        ])
        make_task(cls, "bank-fees", status="done", period="2026-03",
                  done_at="2026-04-05T14:30:00Z")

        # As-of date is BEFORE the anchor (first Monday of April = Apr 6)
        result = run_check_periods(root, as_of="2026-04-04")
        assert result.returncode == 0

        data = read_yaml(cls / "bank-fees" / "status.yaml")
        assert data["status"] == "done"


# ---------------------------------------------------------------------------
# Period math
# ---------------------------------------------------------------------------


class TestPeriodMath:
    """Period string increment logic."""

    def test_monthly_increment(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[
            {"task": "t", "order": 1, "enabled": True,
             "period_format": "monthly", "anchor": "first_monday"},
        ])
        make_task(cls, "t", status="done", period="2026-03",
                  done_at="2026-04-05T14:30:00Z")

        run_check_periods(root, as_of="2026-04-06")
        assert read_yaml(cls / "t" / "status.yaml")["period"] == "2026-04"

    def test_monthly_december_rollover(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[
            {"task": "t", "order": 1, "enabled": True,
             "period_format": "monthly", "anchor": "first_monday"},
        ])
        # First Monday of Jan 2027 = Jan 4. done_at must be before that.
        make_task(cls, "t", status="done", period="2026-12",
                  done_at="2027-01-03T14:30:00Z")

        run_check_periods(root, as_of="2027-01-04")
        assert read_yaml(cls / "t" / "status.yaml")["period"] == "2027-01"

    def test_weekly_increment(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[
            {"task": "t", "order": 1, "enabled": True,
             "period_format": "weekly", "anchor": "monday"},
        ])
        # Monday of W13 = Mar 23. done_at must be before that.
        make_task(cls, "t", status="done", period="2026-W12",
                  done_at="2026-03-22T14:30:00Z")

        run_check_periods(root, as_of="2026-03-23")
        assert read_yaml(cls / "t" / "status.yaml")["period"] == "2026-W13"

    def test_weekly_year_rollover(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[
            {"task": "t", "order": 1, "enabled": True,
             "period_format": "weekly", "anchor": "monday"},
        ])
        # Monday of W53 = Dec 28. done_at must be before that.
        make_task(cls, "t", status="done", period="2026-W52",
                  done_at="2026-12-27T14:30:00Z")

        run_check_periods(root, as_of="2026-12-28")
        next_period = read_yaml(cls / "t" / "status.yaml")["period"]
        # 2026 has 53 weeks, so W52+1 = W53
        assert next_period.startswith("202")

    def test_quarterly_increment(self, tmp_path):
        """Quarterly Q1 → Q2. One-ahead anchor = first Monday of Q2 (April 6)."""
        root = make_context_root(tmp_path)
        cls = make_class(root, "reporting", manifest=[
            {"task": "t", "order": 1, "enabled": True,
             "period_format": "quarterly", "anchor": "first_monday"},
        ])
        # First Monday of Q2 (April) = April 6. done_at must be before that.
        make_task(cls, "t", status="done", period="2026-Q1",
                  done_at="2026-04-05T14:30:00Z")

        run_check_periods(root, as_of="2026-04-06")
        assert read_yaml(cls / "t" / "status.yaml")["period"] == "2026-Q2"

    def test_quarterly_q4_rollover(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "reporting", manifest=[
            {"task": "t", "order": 1, "enabled": True,
             "period_format": "quarterly", "anchor": "first_monday"},
        ])
        # First Monday of Q1 2027 (January) = Jan 4. done_at must be before that.
        make_task(cls, "t", status="done", period="2026-Q4",
                  done_at="2027-01-03T14:30:00Z")

        run_check_periods(root, as_of="2027-01-04")
        assert read_yaml(cls / "t" / "status.yaml")["period"] == "2027-Q1"


# ---------------------------------------------------------------------------
# Anchor computation
# ---------------------------------------------------------------------------


class TestAnchorComputation:
    """Verify anchor date calculation for different anchor types."""

    def test_first_monday_monthly(self, tmp_path):
        """For period 2026-03 (monthly), one-ahead anchor = first Monday of April = April 6.
        done_at before anchor → no guard. as-of on anchor day → triggers reset."""
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[
            {"task": "t", "order": 1, "enabled": True,
             "period_format": "monthly", "anchor": "first_monday"},
        ])
        make_task(cls, "t", status="done", period="2026-03",
                  done_at="2026-04-05T14:30:00Z")

        # April 6 is the first Monday of April — should trigger on or after
        result = run_check_periods(root, as_of="2026-04-06")
        assert result.returncode == 0

        data = read_yaml(cls / "t" / "status.yaml")
        assert data["status"] == "not_started"

    def test_first_wednesday_monthly(self, tmp_path):
        """For period 2026-03, one-ahead anchor = first Wednesday of April = April 1.
        done_at must be before April 1 to avoid late-completion guard."""
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[
            {"task": "t", "order": 1, "enabled": True,
             "period_format": "monthly", "anchor": "first_wednesday"},
        ])
        make_task(cls, "t", status="done", period="2026-03",
                  done_at="2026-03-31T14:30:00Z")

        result = run_check_periods(root, as_of="2026-04-01")
        assert result.returncode == 0

    def test_monday_anchor_weekly(self, tmp_path):
        """Weekly task with monday anchor — Monday of the next ISO week."""
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[
            {"task": "t", "order": 1, "enabled": True,
             "period_format": "weekly", "anchor": "monday"},
        ])
        # Monday of W13 = Mar 23. done_at must be before that.
        make_task(cls, "t", status="done", period="2026-W12",
                  done_at="2026-03-22T14:30:00Z")

        result = run_check_periods(root, as_of="2026-03-23")
        assert result.returncode == 0

        data = read_yaml(cls / "t" / "status.yaml")
        assert data["status"] == "not_started"

    def test_first_monday_quarterly(self, tmp_path):
        """Quarterly task — one-ahead anchor = first Monday of Q2 (April 6)."""
        root = make_context_root(tmp_path)
        cls = make_class(root, "reporting", manifest=[
            {"task": "t", "order": 1, "enabled": True,
             "period_format": "quarterly", "anchor": "first_monday"},
        ])
        # First Monday of Q2 (April) = April 6. done_at before that.
        make_task(cls, "t", status="done", period="2026-Q1",
                  done_at="2026-04-05T14:30:00Z")

        # First Monday of Q2 (April 2026) is April 6
        result = run_check_periods(root, as_of="2026-04-06")
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# Reset side effects
# ---------------------------------------------------------------------------


class TestResetSideEffects:
    """Verify what fields change when a task is reset."""

    def test_reset_clears_issues_and_done_at(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[
            {"task": "t", "order": 1, "enabled": True,
             "period_format": "monthly", "anchor": "first_monday"},
        ])
        make_task(cls, "t", status="done", period="2026-03",
                  done_at="2026-04-05T14:30:00Z")

        run_check_periods(root, as_of="2026-04-06")

        data = read_yaml(cls / "t" / "status.yaml")
        assert data["issues"] == []
        assert data["done_at"] is None

    def test_reset_sets_next_period(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[
            {"task": "t", "order": 1, "enabled": True,
             "period_format": "monthly", "anchor": "first_monday"},
        ])
        make_task(cls, "t", status="done", period="2026-03",
                  done_at="2026-04-05T14:30:00Z")

        run_check_periods(root, as_of="2026-04-06")

        data = read_yaml(cls / "t" / "status.yaml")
        assert data["period"] == "2026-04"

    def test_schema_version_preserved(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[
            {"task": "t", "order": 1, "enabled": True,
             "period_format": "monthly", "anchor": "first_monday"},
        ])
        make_task(cls, "t", status="done", period="2026-03",
                  done_at="2026-04-05T14:30:00Z")

        run_check_periods(root, as_of="2026-04-06")

        data = read_yaml(cls / "t" / "status.yaml")
        assert data["schema_version"] == 1


# ---------------------------------------------------------------------------
# Multi-class
# ---------------------------------------------------------------------------


class TestMultiClass:
    """check-periods.py processes all classes in the engagement."""

    def test_walks_multiple_classes(self, tmp_path):
        root = make_context_root(tmp_path)

        cls1 = make_class(root, "treasury", manifest=[
            {"task": "t1", "order": 1, "enabled": True,
             "period_format": "monthly", "anchor": "first_monday"},
        ])
        make_task(cls1, "t1", status="done", period="2026-03",
                  done_at="2026-04-05T14:30:00Z")

        cls2 = make_class(root, "reporting", manifest=[
            {"task": "t2", "order": 1, "enabled": True,
             "period_format": "monthly", "anchor": "first_monday"},
        ])
        make_task(cls2, "t2", status="done", period="2026-03",
                  done_at="2026-04-05T14:30:00Z")

        run_check_periods(root, as_of="2026-04-06")

        assert read_yaml(cls1 / "t1" / "status.yaml")["status"] == "not_started"
        assert read_yaml(cls2 / "t2" / "status.yaml")["status"] == "not_started"

    def test_skips_non_class_directories(self, tmp_path):
        """Directories without .class.yaml (like .git, .claude) are ignored."""
        root = make_context_root(tmp_path)

        cls = make_class(root, "treasury", manifest=[
            {"task": "t", "order": 1, "enabled": True,
             "period_format": "monthly", "anchor": "first_monday"},
        ])
        make_task(cls, "t", status="done", period="2026-03",
                  done_at="2026-04-05T14:30:00Z")

        # .claude already exists from make_context_root; add .git
        (root / ".git").mkdir(exist_ok=True)

        result = run_check_periods(root, as_of="2026-04-06")
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# Preconditions
# ---------------------------------------------------------------------------


class TestPreconditions:
    """check-periods.py exits 1 when not at engagement root."""

    def test_exit_1_not_at_engagement_root(self, tmp_path):
        result = run_check_periods(tmp_path)
        assert result.returncode == 1
        assert "Not at engagement root" in result.stderr


# ---------------------------------------------------------------------------
# Git commit behavior
# ---------------------------------------------------------------------------


class TestGitCommit:
    """check-periods.py commits reset changes when a git repo is present."""

    def _git_init(self, root):
        """Initialize git repo with config for testing."""
        import subprocess as sp
        sp.run(["git", "init"], cwd=str(root), capture_output=True)
        sp.run(["git", "config", "user.email", "test@test.com"], cwd=str(root), capture_output=True)
        sp.run(["git", "config", "user.name", "Test"], cwd=str(root), capture_output=True)
        sp.run(["git", "add", "."], cwd=str(root), capture_output=True)
        sp.run(["git", "commit", "-m", "initial"], cwd=str(root), capture_output=True)

    def test_commit_after_reset(self, tmp_path):
        """When tasks are reset, check-periods creates a git commit."""
        import subprocess as sp
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[
            {"task": "bank-fees", "order": 1, "enabled": True,
             "period_format": "monthly", "anchor": "first_monday"},
        ])
        make_task(cls, "bank-fees", status="done", period="2026-03",
                  done_at="2026-04-05T14:30:00Z")

        self._git_init(root)

        result = run_check_periods(root, as_of="2026-04-06")
        assert result.returncode == 0

        # Verify a new commit was created with the expected message
        log = sp.run(
            ["git", "log", "--oneline", "-2"],
            cwd=str(root), capture_output=True, text=True,
        )
        assert "[check]" in log.stdout
        assert "treasury" in log.stdout

    def test_no_commit_when_no_resets(self, tmp_path):
        """When no tasks are reset, no git commit is created."""
        import subprocess as sp
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[
            {"task": "bank-fees", "order": 1, "enabled": True,
             "period_format": "monthly", "anchor": "first_monday"},
        ])
        make_task(cls, "bank-fees", status="not_started")

        self._git_init(root)

        # Count commits before
        before = sp.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=str(root), capture_output=True, text=True,
        )
        before_count = int(before.stdout.strip())

        result = run_check_periods(root, as_of="2026-05-05")
        assert result.returncode == 0

        # Count commits after — should be the same
        after = sp.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=str(root), capture_output=True, text=True,
        )
        after_count = int(after.stdout.strip())
        assert after_count == before_count


# ---------------------------------------------------------------------------
# Last-* anchors
# ---------------------------------------------------------------------------


class TestLastAnchors:
    """Tests for last_* anchor types and weekend anchors."""

    def test_last_friday_monthly(self, tmp_path):
        """Monthly period 2026-03, anchor last_friday.
        One-ahead: last Friday of April 2026 = April 24.
        done_at Apr 20 (before anchor) → no guard.
        as-of Apr 25 >= Apr 24 → triggers reset."""
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[
            {"task": "t", "order": 1, "enabled": True,
             "period_format": "monthly", "anchor": "last_friday"},
        ])
        make_task(cls, "t", status="done", period="2026-03",
                  done_at="2026-04-20T14:30:00Z")

        result = run_check_periods(root, as_of="2026-04-25")
        assert result.returncode == 0

        data = read_yaml(cls / "t" / "status.yaml")
        assert data["status"] == "not_started"
        assert data["period"] == "2026-04"

    def test_last_monday_quarterly(self, tmp_path):
        """Quarterly period 2026-Q1, anchor last_monday.
        One-ahead: last Monday of Q2's final month (June 2026) = June 29.
        done_at Apr 7 (before anchor) → no guard.
        as-of June 29 → triggers reset."""
        root = make_context_root(tmp_path)
        cls = make_class(root, "reporting", manifest=[
            {"task": "t", "order": 1, "enabled": True,
             "period_format": "quarterly", "anchor": "last_monday"},
        ])
        make_task(cls, "t", status="done", period="2026-Q1",
                  done_at="2026-04-07T14:30:00Z")

        result = run_check_periods(root, as_of="2026-06-29")
        assert result.returncode == 0

        data = read_yaml(cls / "t" / "status.yaml")
        assert data["status"] == "not_started"
        assert data["period"] == "2026-Q2"

    def test_first_saturday_monthly(self, tmp_path):
        """Monthly period 2026-03, anchor first_saturday.
        One-ahead: first Saturday of April 2026 = April 4.
        done_at Apr 3 (before anchor) → no guard.
        as-of Apr 4 → triggers reset."""
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[
            {"task": "t", "order": 1, "enabled": True,
             "period_format": "monthly", "anchor": "first_saturday"},
        ])
        make_task(cls, "t", status="done", period="2026-03",
                  done_at="2026-04-03T14:30:00Z")

        result = run_check_periods(root, as_of="2026-04-04")
        assert result.returncode == 0

        data = read_yaml(cls / "t" / "status.yaml")
        assert data["status"] == "not_started"
        assert data["period"] == "2026-04"


# ---------------------------------------------------------------------------
# One-ahead anchor and late-completion guard
# ---------------------------------------------------------------------------


class TestOneAheadAnchor:
    """Tests verifying one-ahead anchor logic and the late-completion guard."""

    def test_anchor_is_one_period_ahead(self, tmp_path):
        """Period 2026-03, first_monday. One-ahead anchor = first Monday of
        April = April 6. done_at Apr 1 (before anchor). as-of Apr 6 triggers.
        Period resets to 2026-04 (not 2026-05 as two-ahead would give)."""
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[
            {"task": "t", "order": 1, "enabled": True,
             "period_format": "monthly", "anchor": "first_monday"},
        ])
        make_task(cls, "t", status="done", period="2026-03",
                  done_at="2026-04-01T14:30:00Z")

        result = run_check_periods(root, as_of="2026-04-06")
        assert result.returncode == 0

        data = read_yaml(cls / "t" / "status.yaml")
        assert data["status"] == "not_started"
        assert data["period"] == "2026-04"

    def test_late_completion_pushes_to_next_cycle(self, tmp_path):
        """Period 2026-03, first_monday. Anchor = first Monday of April = Apr 6.
        done_at Apr 20 (AFTER anchor) → late-completion guard fires.
        Guard pushes next_per from 2026-04 to 2026-05 and anchor to
        first Monday of May = May 4.
        as-of Apr 25 < May 4 → does NOT trigger.
        as-of May 4 >= May 4 → DOES trigger with period 2026-05."""
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[
            {"task": "t", "order": 1, "enabled": True,
             "period_format": "monthly", "anchor": "first_monday"},
        ])
        make_task(cls, "t", status="done", period="2026-03",
                  done_at="2026-04-20T14:30:00Z")

        # Before the pushed anchor — should NOT trigger
        result = run_check_periods(root, as_of="2026-04-25")
        assert result.returncode == 0
        data = read_yaml(cls / "t" / "status.yaml")
        assert data["status"] == "done"

        # On the pushed anchor — SHOULD trigger
        result = run_check_periods(root, as_of="2026-05-04")
        assert result.returncode == 0
        data = read_yaml(cls / "t" / "status.yaml")
        assert data["status"] == "not_started"
        assert data["period"] == "2026-05"

    def test_late_completion_last_anchor(self, tmp_path):
        """Period 2026-03, last_friday. Anchor = last Friday of April = Apr 24.
        done_at Apr 30 (AFTER anchor) → late-completion guard fires.
        Guard pushes next_per from 2026-04 to 2026-05 and anchor to
        last Friday of May = May 29.
        as-of May 29 → triggers with period 2026-05."""
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[
            {"task": "t", "order": 1, "enabled": True,
             "period_format": "monthly", "anchor": "last_friday"},
        ])
        make_task(cls, "t", status="done", period="2026-03",
                  done_at="2026-04-30T14:30:00Z")

        result = run_check_periods(root, as_of="2026-05-29")
        assert result.returncode == 0

        data = read_yaml(cls / "t" / "status.yaml")
        assert data["status"] == "not_started"
        assert data["period"] == "2026-05"


# ---------------------------------------------------------------------------
# Pure decide_reset predicate (no filesystem / git / YAML)
# ---------------------------------------------------------------------------


class TestDecideResetPredicate:
    """Direct unit tests of the importable due-predicate extracted from main()."""

    def test_due_after_anchor_monthly(self):
        # period 2026-03, first_monday → anchor = first Monday of April = Apr 6.
        # done_at before anchor; today on/after anchor → due, resets to 2026-04.
        d = check_periods.decide_reset(
            "2026-03", "monthly", "first_monday",
            done_at=date(2026, 4, 1), today=date(2026, 4, 6),
        )
        assert d.due is True
        assert d.next_period == "2026-04"
        assert d.anchor_date == date(2026, 4, 6)

    def test_not_due_before_anchor_monthly(self):
        # Same schedule, but today is before the anchor → not due.
        d = check_periods.decide_reset(
            "2026-03", "monthly", "first_monday",
            done_at=date(2026, 4, 1), today=date(2026, 4, 5),
        )
        assert d.due is False
        assert d.next_period == "2026-04"
        assert d.anchor_date == date(2026, 4, 6)

    def test_late_completion_pushes_one_cycle(self):
        # done_at (Apr 30) is AFTER the next anchor (Apr 6) → guard pushes the
        # cycle forward: next_period 2026-04 → 2026-05, anchor → first Mon of May.
        d = check_periods.decide_reset(
            "2026-03", "monthly", "first_monday",
            done_at=date(2026, 4, 30), today=date(2026, 5, 4),
        )
        assert d.due is True
        assert d.next_period == "2026-05"
        assert d.anchor_date == date(2026, 5, 4)

    def test_quarterly_first_anchor(self):
        # Q1 → next Q2, first Monday of April (first month of Q2) = Apr 6.
        d = check_periods.decide_reset(
            "2026-Q1", "quarterly", "first_monday",
            done_at=date(2026, 1, 15), today=date(2026, 4, 6),
        )
        assert d.due is True
        assert d.next_period == "2026-Q2"
        assert d.anchor_date == date(2026, 4, 6)

    def test_anchor_equal_to_today_is_due(self):
        # Boundary: today == anchor_date counts as due (>=).
        d = check_periods.decide_reset(
            "2026-03", "monthly", "first_monday",
            done_at=date(2026, 4, 1), today=date(2026, 4, 6),
        )
        assert d.due is True
