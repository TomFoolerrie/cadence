"""
Contract tests for init-task.py

Spec: init-task.py <name> (run from class directory)
- Creates: SKILL.md, learned.md, status.yaml, tools/, periods/, requirements.txt
- Preconditions: .class.yaml exists in cwd, target directory does not exist
- Exit codes: 0 = success, 1 = precondition failed, 2 = filesystem error
- Not idempotent
"""

import json

import pytest

from conftest import make_class, make_context_root, read_yaml, run_script


pytestmark = pytest.mark.mid


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestCreatesTaskDirectory:
    """init-task.py creates the correct directory structure."""

    def test_creates_all_expected_files_and_dirs(self, class_dir):
        result = run_script("init-task.py", ["monthly-bank-fees"], cwd=class_dir)
        assert result.returncode == 0

        task_dir = class_dir / "monthly-bank-fees"
        assert task_dir.is_dir()
        assert (task_dir / "SKILL.md").is_file()
        assert (task_dir / "learned.md").is_file()
        assert (task_dir / "status.yaml").is_file()
        assert (task_dir / "tools").is_dir()
        assert (task_dir / "periods").is_dir()
        assert (task_dir / "requirements.txt").is_file()
        assert (task_dir / "reference.md").is_file()

    def test_reference_md_contains_task_name(self, class_dir):
        run_script("init-task.py", ["monthly-bank-fees"], cwd=class_dir)

        content = (class_dir / "monthly-bank-fees" / "reference.md").read_text()
        assert "# reference — monthly-bank-fees" in content

    def test_reference_md_contains_plugin_scripts_table(self, class_dir):
        run_script("init-task.py", ["monthly-bank-fees"], cwd=class_dir)

        content = (class_dir / "monthly-bank-fees" / "reference.md").read_text()
        assert "## Plugin Scripts" in content
        assert "| Script | Purpose | Usage |" in content
        assert "init-period.py" in content

    def test_status_yaml_initial_values(self, class_dir):
        run_script("init-task.py", ["monthly-bank-fees"], cwd=class_dir)

        data = read_yaml(class_dir / "monthly-bank-fees" / "status.yaml")
        assert data["schema_version"] == 1
        assert data["period"] == ""
        assert data["status"] == "not_started"
        assert data["issues"] == []
        assert data["done_at"] is None

    def test_skill_md_contains_required_sections(self, class_dir):
        run_script("init-task.py", ["monthly-bank-fees"], cwd=class_dir)

        content = (class_dir / "monthly-bank-fees" / "SKILL.md").read_text()
        assert "## Purpose" in content
        assert "## Data Sources" in content
        assert "## Procedure" in content
        assert "## Validation" in content
        assert "## Contacts" in content
        assert "## Completion Criteria" in content

    def test_skill_md_name_in_heading(self, class_dir):
        run_script("init-task.py", ["monthly-bank-fees"], cwd=class_dir)

        content = (class_dir / "monthly-bank-fees" / "SKILL.md").read_text()
        assert "# monthly-bank-fees" in content

    def test_learned_md_template_sections(self, class_dir):
        run_script("init-task.py", ["monthly-bank-fees"], cwd=class_dir)

        content = (class_dir / "monthly-bank-fees" / "learned.md").read_text()
        assert "## Review History" in content
        assert "| Period" in content  # table header
        assert "## Patterns" in content
        assert "## What Didn't Work" in content
        assert "## Open Questions" in content

    def test_requirements_txt_is_empty(self, class_dir):
        run_script("init-task.py", ["monthly-bank-fees"], cwd=class_dir)

        content = (class_dir / "monthly-bank-fees" / "requirements.txt").read_text()
        assert content.strip() == ""

    def test_claude_settings_json_exists(self, class_dir):
        run_script("init-task.py", ["monthly-bank-fees"], cwd=class_dir)
        assert (class_dir / "monthly-bank-fees" / ".claude" / "settings.json").is_file()

    def test_claude_settings_json_content(self, class_dir):
        run_script("init-task.py", ["monthly-bank-fees"], cwd=class_dir)

        with open(class_dir / "monthly-bank-fees" / ".claude" / "settings.json") as f:
            settings = json.load(f)

        assert settings == {
            "permissions": {
                "allow": ["Read", "Write(./**)"],
                "deny": ["Write(../**)"],
            }
        }

    def test_claude_settings_json_deny_rules(self, class_dir):
        run_script("init-task.py", ["monthly-bank-fees"], cwd=class_dir)

        with open(class_dir / "monthly-bank-fees" / ".claude" / "settings.json") as f:
            settings = json.load(f)

        deny = settings["permissions"]["deny"]
        assert "Write(../**)" in deny


# ---------------------------------------------------------------------------
# Precondition failures
# ---------------------------------------------------------------------------


class TestPreconditions:
    """init-task.py exits 1 when preconditions are not met."""

    def test_exit_1_no_class_yaml(self, tmp_path):
        """Fails when .class.yaml is missing from cwd."""
        result = run_script("init-task.py", ["my-task"], cwd=tmp_path)
        assert result.returncode == 1
        assert not (tmp_path / "my-task").exists()

    def test_exit_1_directory_already_exists(self, class_dir):
        """Fails when target directory already exists."""
        (class_dir / "monthly-bank-fees").mkdir()
        result = run_script("init-task.py", ["monthly-bank-fees"], cwd=class_dir)
        assert result.returncode == 1
        assert "already exists" in result.stderr.lower() or "already exists" in result.stdout.lower()

    def test_not_idempotent(self, class_dir):
        """Running twice with same name fails on second run."""
        result1 = run_script("init-task.py", ["monthly-bank-fees"], cwd=class_dir)
        assert result1.returncode == 0

        result2 = run_script("init-task.py", ["monthly-bank-fees"], cwd=class_dir)
        assert result2.returncode == 1

    def test_malformed_class_yaml_exits_cleanly(self, tmp_path):
        """Malformed .class.yaml exits with error, not a Python traceback."""
        (tmp_path / ".class.yaml").write_text("not: valid: yaml: [[[")
        result = run_script("init-task.py", ["my-task"], cwd=tmp_path)
        assert result.returncode != 0
        assert "Traceback" not in result.stderr
