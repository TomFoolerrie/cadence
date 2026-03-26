"""
End-to-end tests for the /onboard workflow.

Tests cross-script state — not re-testing individual scripts, but verifying
that the full onboard chain produces a valid, usable hierarchy.
"""

import pytest

from conftest import (
    make_context_root,
    read_yaml,
    run_script,
)


pytestmark = pytest.mark.e2e


class TestOnboardWorkflow:
    """Full onboard: init-class → init-task → start lifecycle."""

    def test_full_onboard_lifecycle(self, tmp_path):
        """
        Complete onboard flow:
        1. Create engagement root
        2. init-class treasury
        3. init-task monthly-bank-fees (from class dir)
        4. set-status in_progress --period 2026-03
        5. init-period 2026-03
        6. set-status review_ready
        7. set-status done

        Verify final hierarchy and status.
        """
        root = make_context_root(tmp_path)

        # Step 1: Create class
        result = run_script("init-class.py", ["treasury"], cwd=root)
        assert result.returncode == 0
        class_dir = root / "treasury"

        # Step 2: Create task
        result = run_script("init-task.py", ["monthly-bank-fees"], cwd=class_dir)
        assert result.returncode == 0
        task_dir = class_dir / "monthly-bank-fees"

        # Step 3: Start work
        result = run_script("set-status.py", ["in_progress", "--period", "2026-03"], cwd=task_dir)
        assert result.returncode == 0

        # Step 4: Create period
        result = run_script("init-period.py", ["2026-03"], cwd=task_dir)
        assert result.returncode == 0

        # Verify period structure
        assert (task_dir / "periods" / "2026-03" / "data").is_dir()
        assert (task_dir / "periods" / "2026-03" / "workpapers").is_dir()
        assert (task_dir / "periods" / "2026-03" / "review-notes").is_dir()

        # Step 5: Mark review ready
        result = run_script("set-status.py", ["review_ready"], cwd=task_dir)
        assert result.returncode == 0

        # Step 6: Complete
        result = run_script("set-status.py", ["done"], cwd=task_dir)
        assert result.returncode == 0

        # Final verification
        data = read_yaml(task_dir / "status.yaml")
        assert data["status"] == "done"
        assert data["period"] == "2026-03"
        assert data["done_at"] is not None
        assert data["issues"] == []

    def test_context_loading_at_each_onboard_stage(self, tmp_path):
        """
        After class creation, load-context --level class works.
        After task creation, load-context --level task works.
        """
        root = make_context_root(tmp_path)

        # Create class
        run_script("init-class.py", ["treasury"], cwd=root)
        class_dir = root / "treasury"

        # Verify class-level context loads
        result = run_script("load-context.py", ["--level", "class"], cwd=class_dir)
        assert result.returncode == 0
        assert "Test Corp" in result.stdout  # root context
        assert "Treasury" in result.stdout   # class context

        # Create task
        run_script("init-task.py", ["monthly-bank-fees"], cwd=class_dir)
        task_dir = class_dir / "monthly-bank-fees"

        # Verify task-level context loads
        result = run_script("load-context.py", ["--level", "task"], cwd=task_dir)
        assert result.returncode == 0
        assert "Test Corp" in result.stdout
        assert "Treasury" in result.stdout
        assert "## Purpose" in result.stdout
