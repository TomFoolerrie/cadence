"""
End-to-end tests for error recovery paths.

Tests blocked → retry/abandon, crash recovery, and review rejection workflows.
"""

import pytest

from conftest import (
    make_class,
    make_context_root,
    make_task,
    read_yaml,
    run_script,
)


pytestmark = pytest.mark.e2e


class TestErrorRecovery:
    """Error recovery paths through the state machine."""

    def test_blocked_then_retry(self, tmp_path):
        """blocked → not_started → in_progress. Issues cleared on retry."""
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury")
        task = make_task(cls, "monthly-bank-fees")

        # Start and get blocked
        run_script("set-status.py", ["in_progress", "--period", "2026-03"], cwd=task)
        run_script("set-status.py", ["blocked", "Chase API 401"], cwd=task)

        data = read_yaml(task / "status.yaml")
        assert data["status"] == "blocked"
        assert "Chase API 401" in data["issues"]

        # Retry
        run_script("set-status.py", ["not_started"], cwd=task)

        data = read_yaml(task / "status.yaml")
        assert data["status"] == "not_started"
        assert data["issues"] == []

        # Re-start
        result = run_script("set-status.py", ["in_progress"], cwd=task)
        assert result.returncode == 0
        assert read_yaml(task / "status.yaml")["status"] == "in_progress"

    def test_blocked_then_abandon(self, tmp_path):
        """blocked → abandoned. Issues and done_at set."""
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury")
        task = make_task(cls, "monthly-bank-fees")

        # Start and get blocked
        run_script("set-status.py", ["in_progress", "--period", "2026-03"], cwd=task)
        run_script("set-status.py", ["blocked", "Unrecoverable error"], cwd=task)

        # Abandon
        run_script("set-status.py", ["abandoned", "Cannot recover this period"], cwd=task)

        data = read_yaml(task / "status.yaml")
        assert data["status"] == "abandoned"
        assert "Cannot recover this period" in data["issues"]
        assert data["done_at"] is not None

    def test_blocked_context_shows_recovery_hint(self, tmp_path):
        """When blocked, load-context --level task shows recovery guidance."""
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury")
        task = make_task(cls, "monthly-bank-fees")

        run_script("set-status.py", ["in_progress", "--period", "2026-03"], cwd=task)
        run_script("set-status.py", ["blocked", "API failure"], cwd=task)

        result = run_script("load-context.py", ["--level", "task"], cwd=task)
        assert result.returncode == 0

        stdout_lower = result.stdout.lower()
        assert "recovery" in stdout_lower or "blocked" in stdout_lower

    def test_crash_recovery_idempotent_in_progress(self, tmp_path):
        """in_progress → in_progress is a no-op (crash recovery)."""
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury")
        task = make_task(cls, "monthly-bank-fees")

        run_script("set-status.py", ["in_progress", "--period", "2026-03"], cwd=task)
        before = (task / "status.yaml").read_bytes()

        # Simulate crash recovery — agent calls in_progress again
        result = run_script("set-status.py", ["in_progress"], cwd=task)
        assert result.returncode == 0

        after = (task / "status.yaml").read_bytes()
        assert before == after

    def test_review_rejection_and_redo(self, tmp_path):
        """review_ready → in_progress → review_ready → done. Full rejection cycle."""
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury")
        task = make_task(cls, "monthly-bank-fees")

        # First attempt
        run_script("set-status.py", ["in_progress", "--period", "2026-03"], cwd=task)
        run_script("init-period.py", ["2026-03"], cwd=task)
        run_script("set-status.py", ["review_ready"], cwd=task)

        # Human rejects — go back to in_progress
        result = run_script("set-status.py", ["in_progress"], cwd=task)
        assert result.returncode == 0
        assert read_yaml(task / "status.yaml")["status"] == "in_progress"

        # Fix and re-submit
        result = run_script("set-status.py", ["review_ready"], cwd=task)
        assert result.returncode == 0

        # Approve
        result = run_script("set-status.py", ["done"], cwd=task)
        assert result.returncode == 0

        data = read_yaml(task / "status.yaml")
        assert data["status"] == "done"
        assert data["done_at"] is not None
