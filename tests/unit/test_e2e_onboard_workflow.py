"""
End-to-end tests for the /onboard workflow.

Tests cross-script state — not re-testing individual scripts, but verifying
that the full onboard chain produces a valid, usable hierarchy.
"""

import subprocess

import pytest

from conftest import (
    make_context_root,
    read_yaml,
    run_script,
)


pytestmark = pytest.mark.e2e


def init_engagement(tmp_path, name="Test Corp"):
    """Create engagement via init-engagement.py. Returns the engagement root path."""
    eng_path = tmp_path / name.lower().replace(" ", "-")
    result = run_script("init-engagement.py", [str(eng_path), "--name", name])
    assert result.returncode == 0
    return eng_path


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

    def test_full_engagement_to_task_lifecycle(self, tmp_path):
        """
        Complete chain using init-engagement.py through full status lifecycle.

        init-engagement → init-class → init-task → edit-class-yaml add-task →
        set-status in_progress → init-period → set-status review_ready →
        set-status done.
        """
        root = init_engagement(tmp_path)

        # Create class
        result = run_script("init-class.py", ["treasury"], cwd=root)
        assert result.returncode == 0
        class_dir = root / "treasury"

        # Create task
        result = run_script("init-task.py", ["monthly-bank-fees"], cwd=class_dir)
        assert result.returncode == 0
        task_dir = class_dir / "monthly-bank-fees"

        # Register task in class manifest
        result = run_script(
            "edit-class-yaml.py",
            ["add-task", "monthly-bank-fees", "--order", "1",
             "--period-format", "monthly", "--anchor", "first_monday"],
            cwd=class_dir,
        )
        assert result.returncode == 0

        # Start work
        result = run_script(
            "set-status.py", ["in_progress", "--period", "2026-03"], cwd=task_dir
        )
        assert result.returncode == 0

        # Create period
        result = run_script("init-period.py", ["2026-03"], cwd=task_dir)
        assert result.returncode == 0

        # Mark review ready
        result = run_script("set-status.py", ["review_ready"], cwd=task_dir)
        assert result.returncode == 0

        # Complete
        result = run_script("set-status.py", ["done"], cwd=task_dir)
        assert result.returncode == 0

        # Verify final status
        data = read_yaml(task_dir / "status.yaml")
        assert data["status"] == "done"
        assert data["period"] == "2026-03"

        # Verify class manifest has the task
        class_data = read_yaml(class_dir / ".class.yaml")
        manifest = class_data["manifest"]
        task_names = [entry["task"] for entry in manifest]
        assert "monthly-bank-fees" in task_names

        # Verify reference.md and learned.md exist
        assert (task_dir / "reference.md").is_file()
        assert (task_dir / "learned.md").is_file()

        # Verify git log has initial commit
        git_result = subprocess.run(
            ["git", "log", "--oneline"],
            cwd=str(root),
            capture_output=True,
            text=True,
        )
        assert git_result.returncode == 0
        assert "[init]" in git_result.stdout

    def test_edit_class_yaml_set_description_in_onboard_flow(self, tmp_path):
        """
        Verify set-description subcommand works in context of a freshly
        scaffolded engagement.
        """
        root = init_engagement(tmp_path)

        # Create class
        result = run_script("init-class.py", ["treasury"], cwd=root)
        assert result.returncode == 0
        class_dir = root / "treasury"

        # Set description
        result = run_script(
            "edit-class-yaml.py",
            ["set-description", "Cash management and banking"],
            cwd=class_dir,
        )
        assert result.returncode == 0

        # Verify description is set and manifest is intact
        class_data = read_yaml(class_dir / ".class.yaml")
        assert class_data["description"] == "Cash management and banking"
        assert isinstance(class_data["manifest"], list)

    # Note: write-scope enforcement (.claude/settings.json) is the Claude
    # track's mechanism — its multi-level assertions live in
    # tests/claude/test_settings_enforcement.py (harness-specific).

    def test_second_task_onboard_adds_to_existing_manifest(self, tmp_path):
        """
        Verify onboarding a second task into an existing class produces
        a manifest with both entries at the correct order values.
        """
        root = init_engagement(tmp_path)

        # Create class
        result = run_script("init-class.py", ["treasury"], cwd=root)
        assert result.returncode == 0
        class_dir = root / "treasury"

        # Create and register first task
        result = run_script("init-task.py", ["task1"], cwd=class_dir)
        assert result.returncode == 0
        result = run_script(
            "edit-class-yaml.py", ["add-task", "task1", "--order", "1"], cwd=class_dir
        )
        assert result.returncode == 0

        # Create and register second task
        result = run_script("init-task.py", ["task2"], cwd=class_dir)
        assert result.returncode == 0
        result = run_script(
            "edit-class-yaml.py", ["add-task", "task2", "--order", "2"], cwd=class_dir
        )
        assert result.returncode == 0

        # Verify manifest has both entries
        class_data = read_yaml(class_dir / ".class.yaml")
        manifest = class_data["manifest"]
        assert len(manifest) == 2

        by_name = {entry["task"]: entry for entry in manifest}
        assert by_name["task1"]["order"] == 1
        assert by_name["task1"]["enabled"] is True
        assert by_name["task2"]["order"] == 2
        assert by_name["task2"]["enabled"] is True

    def test_init_task_leaves_correct_state_for_start_delegation(self, tmp_path):
        """
        Verify that init-task.py leaves status.yaml in the exact state
        that /start expects: status not_started with empty period.
        """
        root = init_engagement(tmp_path)

        # Create class and task
        result = run_script("init-class.py", ["treasury"], cwd=root)
        assert result.returncode == 0
        class_dir = root / "treasury"

        result = run_script("init-task.py", ["monthly-bank-fees"], cwd=class_dir)
        assert result.returncode == 0
        task_dir = class_dir / "monthly-bank-fees"

        # Verify precondition state for /start delegation
        data = read_yaml(task_dir / "status.yaml")
        assert data["status"] == "not_started"
        assert data["period"] == ""
