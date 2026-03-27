"""
Contract tests for init-class.py

Spec: init-class.py <name> (run from engagement root)
- Creates: .class.yaml, AGENT.md, tools/, requirements.txt
- Preconditions: .context-root exists in cwd, target directory does not exist
- Exit codes: 0 = success, 1 = precondition failed, 2 = filesystem error
- Not idempotent
"""

import json

import pytest

from conftest import make_context_root, read_yaml, run_script


pytestmark = pytest.mark.mid


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestCreatesClassDirectory:
    """init-class.py creates the correct directory structure."""

    def test_creates_all_expected_files_and_dirs(self, engagement_root):
        result = run_script("init-class.py", ["treasury"], cwd=engagement_root)
        assert result.returncode == 0

        class_dir = engagement_root / "treasury"
        assert class_dir.is_dir()
        assert (class_dir / ".class.yaml").is_file()
        assert (class_dir / "AGENT.md").is_file()
        assert (class_dir / "tools").is_dir()
        assert (class_dir / "requirements.txt").is_file()

    def test_class_yaml_content(self, engagement_root):
        run_script("init-class.py", ["treasury"], cwd=engagement_root)

        data = read_yaml(engagement_root / "treasury" / ".class.yaml")
        assert data["schema_version"] == 1
        assert data["name"] == "Treasury"
        assert data["description"] == ""
        assert data["manifest"] == []

    def test_agent_md_contains_template_sections(self, engagement_root):
        run_script("init-class.py", ["treasury"], cwd=engagement_root)

        content = (engagement_root / "treasury" / "AGENT.md").read_text()
        assert "## What This Class Covers" in content
        assert "## Key Concepts" in content

    def test_agent_md_name_interpolation(self, engagement_root):
        run_script("init-class.py", ["order-to-cash"], cwd=engagement_root)

        content = (engagement_root / "order-to-cash" / "AGENT.md").read_text()
        assert "# Order To Cash" in content

    def test_requirements_txt_is_empty(self, engagement_root):
        run_script("init-class.py", ["treasury"], cwd=engagement_root)

        content = (engagement_root / "treasury" / "requirements.txt").read_text()
        assert content.strip() == ""

    def test_tools_directory_exists(self, engagement_root):
        run_script("init-class.py", ["treasury"], cwd=engagement_root)
        assert (engagement_root / "treasury" / "tools").is_dir()

    def test_claude_settings_json_exists(self, engagement_root):
        run_script("init-class.py", ["treasury"], cwd=engagement_root)
        assert (engagement_root / "treasury" / ".claude" / "settings.json").is_file()

    def test_claude_settings_json_content(self, engagement_root):
        run_script("init-class.py", ["treasury"], cwd=engagement_root)

        with open(engagement_root / "treasury" / ".claude" / "settings.json") as f:
            settings = json.load(f)

        assert settings == {
            "permissions": {
                "allow": ["Read", "Write(./**)"],
                "deny": ["Write(../**)", "Write(./.class.yaml)"],
            }
        }

    def test_claude_settings_json_deny_rules(self, engagement_root):
        run_script("init-class.py", ["treasury"], cwd=engagement_root)

        with open(engagement_root / "treasury" / ".claude" / "settings.json") as f:
            settings = json.load(f)

        deny = settings["permissions"]["deny"]
        assert "Write(../**)" in deny
        assert "Write(./.class.yaml)" in deny


# ---------------------------------------------------------------------------
# Precondition failures
# ---------------------------------------------------------------------------


class TestPreconditions:
    """init-class.py exits 1 when preconditions are not met."""

    def test_exit_1_no_context_root(self, tmp_path):
        """Fails when .context-root is missing from cwd."""
        result = run_script("init-class.py", ["treasury"], cwd=tmp_path)
        assert result.returncode == 1
        # No directory should be created
        assert not (tmp_path / "treasury").exists()

    def test_exit_1_directory_already_exists(self, engagement_root):
        """Fails when target directory already exists."""
        (engagement_root / "treasury").mkdir()
        result = run_script("init-class.py", ["treasury"], cwd=engagement_root)
        assert result.returncode == 1
        assert "already exists" in result.stderr.lower() or "already exists" in result.stdout.lower()

    def test_not_idempotent(self, engagement_root):
        """Running twice with same name fails on second run."""
        result1 = run_script("init-class.py", ["treasury"], cwd=engagement_root)
        assert result1.returncode == 0

        result2 = run_script("init-class.py", ["treasury"], cwd=engagement_root)
        assert result2.returncode == 1


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases for init-class.py."""

    def test_kebab_case_name(self, engagement_root):
        """Kebab-case names create correct directory and title-case .class.yaml name."""
        result = run_script("init-class.py", ["order-to-cash"], cwd=engagement_root)
        assert result.returncode == 0
        assert (engagement_root / "order-to-cash").is_dir()

        data = read_yaml(engagement_root / "order-to-cash" / ".class.yaml")
        assert data["name"] == "Order To Cash"

    def test_no_partial_write_on_failure(self, engagement_root):
        """When target exists, no files are modified inside it."""
        target = engagement_root / "treasury"
        target.mkdir()
        marker = target / "existing-file.txt"
        marker.write_text("original")

        run_script("init-class.py", ["treasury"], cwd=engagement_root)

        # Original file untouched, no new files created
        assert marker.read_text() == "original"
        assert not (target / ".class.yaml").exists()

    def test_malformed_context_root_exits_cleanly(self, tmp_path):
        """Malformed .context-root exits with error, not a Python traceback."""
        (tmp_path / ".context-root").write_text("not: valid: yaml: [[[")
        result = run_script("init-class.py", ["treasury"], cwd=tmp_path)
        assert result.returncode != 0
        # Should not contain Python traceback
        assert "Traceback" not in result.stderr
