"""
End-to-end tests for the /start → /done execution cycle.

Tests the recurring workflow: start a period, produce work, review, complete.
"""

import pytest

from conftest import (
    make_class,
    make_context_root,
    make_task,
    read_yaml,
    run_script,
    start_to_done,
    write_yaml,
)


pytestmark = pytest.mark.e2e


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestExecutionWorkflow:
    """Recurring /start → /done cycle."""

    def test_start_to_done_happy_path(self, tmp_path):
        """Full cycle: not_started → in_progress → review_ready → done."""
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury")
        task = make_task(cls, "monthly-bank-fees")

        start_to_done(task, "2026-03")

        data = read_yaml(task / "status.yaml")
        assert data["status"] == "done"
        assert data["period"] == "2026-03"
        assert data["done_at"] is not None
        assert data["issues"] == []
        assert (task / "periods" / "2026-03" / "data").is_dir()

    def test_context_available_throughout_execution(self, tmp_path):
        """load-context succeeds at each step of execution."""
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury")
        task = make_task(cls, "monthly-bank-fees")

        # Before start
        result = run_script("load-context.py", ["--level", "task"], cwd=task)
        assert result.returncode == 0

        # During execution
        run_script("set-status.py", ["in_progress", "--period", "2026-03"], cwd=task)
        result = run_script("load-context.py", ["--level", "task"], cwd=task)
        assert result.returncode == 0

        # At review
        run_script("set-status.py", ["review_ready"], cwd=task)
        result = run_script("load-context.py", ["--level", "task"], cwd=task)
        assert result.returncode == 0

    def test_second_period_after_manual_reset(self, tmp_path):
        """After completing one period, manually reset and run a second."""
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury")
        task = make_task(cls, "monthly-bank-fees")

        # First period
        start_to_done(task, "2026-03")

        # Manual reset (simulating what check-periods.py does)
        write_yaml(task / "status.yaml", {
            "schema_version": 1,
            "period": "2026-04",
            "status": "not_started",
            "issues": [],
            "done_at": None,
        })

        # Second period
        start_to_done(task, "2026-04")

        # Both period directories should exist
        assert (task / "periods" / "2026-03" / "data").is_dir()
        assert (task / "periods" / "2026-04" / "data").is_dir()

        data = read_yaml(task / "status.yaml")
        assert data["status"] == "done"
        assert data["period"] == "2026-04"

    def test_multiple_tasks_in_class(self, tmp_path):
        """Two tasks in same class, both through full lifecycle."""
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[
            {"task": "bank-fees", "order": 1, "enabled": True,
             "period_format": "monthly", "anchor": "first_monday"},
            {"task": "zba-entries", "order": 1, "enabled": True,
             "period_format": "monthly", "anchor": "first_monday"},
        ])
        task1 = make_task(cls, "bank-fees")
        task2 = make_task(cls, "zba-entries")

        start_to_done(task1, "2026-03")
        start_to_done(task2, "2026-03")

        assert read_yaml(task1 / "status.yaml")["status"] == "done"
        assert read_yaml(task2 / "status.yaml")["status"] == "done"
