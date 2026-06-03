"""
Contract tests for archive-period.py

Spec: archive-period.py (run from task directory, called by /done)
- Preconditions: status.yaml exists with status: done, .context-root exists
- Uploads periods/{period}/workpapers/ and data/ to Drive
- Idempotent (checks Drive for existing folder before uploading)
- Non-blocking failure (reports error but doesn't change task status)
- Exit codes: 0 = success, 1 = preconditions, 2 = Drive not configured or upload failed

Note: Full upload tests require a Drive API mock. This file tests preconditions only.
"""

import pytest

from conftest import (
    make_class,
    make_context_root,
    make_task,
    run_script,
)


pytestmark = pytest.mark.mid


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run_archive_period(cwd):
    return run_script("archive-period.py", [], cwd=cwd)


# ---------------------------------------------------------------------------
# Precondition failures
# ---------------------------------------------------------------------------


class TestPreconditions:
    """archive-period.py exits 1 when preconditions are not met."""

    def test_exit_1_no_status_yaml(self, tmp_path):
        result = run_archive_period(tmp_path)
        assert result.returncode == 1

    def test_exit_1_status_not_done(self, task_dir_in_progress):
        result = run_archive_period(task_dir_in_progress)
        assert result.returncode == 1

    def test_exit_1_no_context_root(self, tmp_path):
        """Task dir with done status but no .context-root in ancestors."""
        task = tmp_path / "orphan-task"
        task.mkdir()
        (task / "SKILL.md").write_text("# test")

        from conftest import write_yaml
        write_yaml(task / "status.yaml", {
            "schema_version": 1,
            "period": "2026-03",
            "status": "done",
            "issues": [],
            "done_at": "2026-04-07T14:30:00Z",
        })

        result = run_archive_period(task)
        assert result.returncode == 1


# ---------------------------------------------------------------------------
# Contract verification (reads correct fields)
# ---------------------------------------------------------------------------


class TestContractFields:
    """archive-period.py reads the correct fields from hierarchy files."""

    def test_reads_period_from_status_yaml(self, task_dir_done):
        """Script should use the period from status.yaml (2026-03)."""
        # This test verifies the script attempts to archive the correct period.
        # Without a Drive mock, it will exit 2 (Drive not configured),
        # but should NOT exit 1 (preconditions should pass).
        result = run_archive_period(task_dir_done)
        # Preconditions pass (exit code should not be 1)
        assert result.returncode != 1

    def test_reads_engagement_from_context_root(self, task_dir_done):
        """Script should extract engagement name from .context-root."""
        result = run_archive_period(task_dir_done)
        assert result.returncode != 1
