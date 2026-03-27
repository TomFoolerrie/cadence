"""
End-to-end tests for the done → check-periods → next cycle flow.

Tests that completed tasks are automatically reset and can start fresh periods.
"""

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


pytestmark = pytest.mark.e2e


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPeriodResetWorkflow:
    """Done → cron reset → next cycle."""

    def test_done_then_check_periods_resets(self, tmp_path):
        """Complete a task, run check-periods past anchor, verify reset."""
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[
            {"task": "bank-fees", "order": 1, "enabled": True,
             "period_format": "monthly", "anchor": "first_monday"},
        ])
        task = make_task(cls, "bank-fees")

        # Complete the task
        start_to_done(task, "2026-03")

        # Run check-periods past the anchor date
        result = run_check_periods(root, as_of="2026-05-05")
        assert result.returncode == 0

        data = read_yaml(task / "status.yaml")
        assert data["status"] == "not_started"
        assert data["period"] == "2026-04"
        assert data["done_at"] is None
        assert data["issues"] == []

    def test_reset_then_start_new_period(self, tmp_path):
        """After check-periods reset, run full start cycle for next period."""
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[
            {"task": "bank-fees", "order": 1, "enabled": True,
             "period_format": "monthly", "anchor": "first_monday"},
        ])
        task = make_task(cls, "bank-fees")

        # First period
        start_to_done(task, "2026-03")

        # Reset via cron
        run_check_periods(root, as_of="2026-05-05")

        # Second period
        start_to_done(task, "2026-04")

        data = read_yaml(task / "status.yaml")
        assert data["status"] == "done"
        assert data["period"] == "2026-04"

        # Both period directories should exist
        assert (task / "periods" / "2026-03" / "data").is_dir()
        assert (task / "periods" / "2026-04" / "data").is_dir()

    def test_mixed_tasks_some_reset(self, tmp_path):
        """Two tasks: one past anchor (resets), one not (stays done)."""
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[
            {"task": "task-a", "order": 1, "enabled": True,
             "period_format": "monthly", "anchor": "first_monday"},
            {"task": "task-b", "order": 2, "enabled": True,
             "period_format": "monthly", "anchor": "first_monday"},
        ])

        task_a = make_task(cls, "task-a")
        task_b = make_task(cls, "task-b")

        # Task A: done for March (early April)
        start_to_done(task_a, "2026-03")

        # Task B: done for April (early May) — more recent
        write_yaml(task_b / "status.yaml", {
            "schema_version": 1,
            "period": "2026-04",
            "status": "done",
            "issues": [],
            "done_at": "2026-05-05T14:30:00Z",
        })

        # Run check-periods on May 5 — task A should reset, task B should not
        # (Task A's next anchor for April would be first Monday of May = May 4)
        result = run_check_periods(root, as_of="2026-05-05")
        assert result.returncode == 0

        data_a = read_yaml(task_a / "status.yaml")
        assert data_a["status"] == "not_started"

        data_b = read_yaml(task_b / "status.yaml")
        assert data_b["status"] == "done"

    def test_abandoned_task_also_resets(self, tmp_path):
        """Abandoned task gets reset by check-periods."""
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[
            {"task": "bank-fees", "order": 1, "enabled": True,
             "period_format": "monthly", "anchor": "first_monday"},
        ])
        task = make_task(cls, "bank-fees", status="in_progress", period="2026-03")

        # Block then abandon
        run_script("set-status.py", ["blocked", "API failure"], cwd=task)
        run_script("set-status.py", ["abandoned", "Cannot recover"], cwd=task)

        # Run check-periods past anchor
        result = run_check_periods(root, as_of="2026-05-05")
        assert result.returncode == 0

        data = read_yaml(task / "status.yaml")
        assert data["status"] == "not_started"
