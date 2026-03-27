"""
Contract tests for init-engagement.py

Spec: init-engagement.py <path> [--name <engagement-name>]
- Creates: .context-root, AGENT.md, .claude/tools/, .gitignore, requirements.txt
- Runs git init and creates initial commit
- If --name not provided, derives name from directory basename
- Exit codes: 0 = success, 1 = validation error, 2 = system error
- Not idempotent
"""

import json
import subprocess

import pytest

from conftest import read_yaml, run_script


pytestmark = pytest.mark.mid


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestCreatesEngagementDirectory:
    """init-engagement.py creates the correct directory structure."""

    def test_creates_all_expected_files_and_dirs(self, tmp_path):
        target = tmp_path / "acme-corp"
        result = run_script("init-engagement.py", [str(target)])
        assert result.returncode == 0

        assert target.is_dir()
        assert (target / ".context-root").is_file()
        assert (target / "AGENT.md").is_file()
        assert (target / ".claude" / "tools").is_dir()
        assert (target / ".gitignore").is_file()
        assert (target / "requirements.txt").is_file()

    def test_context_root_yaml_content(self, tmp_path):
        target = tmp_path / "acme-corp"
        run_script("init-engagement.py", [str(target)])

        data = read_yaml(target / ".context-root")
        assert data["engagement"] == "Acme Corp"
        assert data["schema_version"] == 1

    def test_context_root_with_name_flag(self, tmp_path):
        target = tmp_path / "acme"
        run_script("init-engagement.py", [str(target), "--name", "Acme Corporation"])

        data = read_yaml(target / ".context-root")
        assert data["engagement"] == "Acme Corporation"
        assert data["schema_version"] == 1

    def test_agent_md_content(self, tmp_path):
        target = tmp_path / "acme-corp"
        run_script("init-engagement.py", [str(target)])

        content = (target / "AGENT.md").read_text()
        assert "# Acme Corp" in content
        assert "## Entity Details" in content

    def test_agent_md_with_name_flag(self, tmp_path):
        target = tmp_path / "acme"
        run_script("init-engagement.py", [str(target), "--name", "Acme Corporation"])

        content = (target / "AGENT.md").read_text()
        assert "# Acme Corporation" in content

    def test_gitignore_content(self, tmp_path):
        target = tmp_path / "acme-corp"
        run_script("init-engagement.py", [str(target)])

        content = (target / ".gitignore").read_text()
        assert "**/periods/*/data/" in content
        assert "**/periods/*/workpapers/" in content
        assert ".context-cache/" in content
        assert ".DS_Store" in content

    def test_requirements_txt_is_empty(self, tmp_path):
        target = tmp_path / "acme-corp"
        run_script("init-engagement.py", [str(target)])

        content = (target / "requirements.txt").read_text()
        assert content.strip() == ""

    def test_claude_tools_directory_exists(self, tmp_path):
        target = tmp_path / "acme-corp"
        run_script("init-engagement.py", [str(target)])

        assert (target / ".claude" / "tools").is_dir()

    def test_claude_settings_json_exists(self, tmp_path):
        target = tmp_path / "acme-corp"
        run_script("init-engagement.py", [str(target)])

        assert (target / ".claude" / "settings.json").is_file()

    def test_claude_settings_json_content(self, tmp_path):
        target = tmp_path / "acme-corp"
        run_script("init-engagement.py", [str(target)])

        with open(target / ".claude" / "settings.json") as f:
            settings = json.load(f)

        assert settings == {
            "permissions": {
                "allow": ["Read", "Write(./**)"],
            }
        }


# ---------------------------------------------------------------------------
# Git initialization
# ---------------------------------------------------------------------------


class TestGitInitialization:
    """init-engagement.py initializes a git repo and creates an initial commit."""

    def test_git_repo_initialized(self, tmp_path):
        target = tmp_path / "acme-corp"
        run_script("init-engagement.py", [str(target)])

        assert (target / ".git").is_dir()

    def test_initial_commit_exists(self, tmp_path):
        target = tmp_path / "acme-corp"
        run_script("init-engagement.py", [str(target)])

        result = subprocess.run(
            ["git", "log", "--oneline"],
            cwd=str(target),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "[init] Acme Corp: engagement created" in result.stdout

    def test_initial_commit_message_with_name_flag(self, tmp_path):
        target = tmp_path / "acme"
        run_script("init-engagement.py", [str(target), "--name", "Acme Corporation"])

        result = subprocess.run(
            ["git", "log", "--oneline"],
            cwd=str(target),
            capture_output=True,
            text=True,
        )
        assert "[init] Acme Corporation: engagement created" in result.stdout

    def test_all_files_are_committed(self, tmp_path):
        target = tmp_path / "acme-corp"
        run_script("init-engagement.py", [str(target)])

        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(target),
            capture_output=True,
            text=True,
        )
        assert result.stdout.strip() == "", "Working tree should be clean after init"


# ---------------------------------------------------------------------------
# Name derivation
# ---------------------------------------------------------------------------


class TestNameDerivation:
    """Engagement name is derived from path basename when --name is not provided."""

    def test_hyphen_to_spaces_title_case(self, tmp_path):
        target = tmp_path / "acme-corp"
        run_script("init-engagement.py", [str(target)])

        data = read_yaml(target / ".context-root")
        assert data["engagement"] == "Acme Corp"

    def test_underscore_to_spaces_title_case(self, tmp_path):
        target = tmp_path / "acme_corp"
        run_script("init-engagement.py", [str(target)])

        data = read_yaml(target / ".context-root")
        assert data["engagement"] == "Acme Corp"

    def test_single_word(self, tmp_path):
        target = tmp_path / "acme"
        run_script("init-engagement.py", [str(target)])

        data = read_yaml(target / ".context-root")
        assert data["engagement"] == "Acme"

    def test_trailing_slash_handled(self, tmp_path):
        target = tmp_path / "acme-corp"
        result = run_script("init-engagement.py", [str(target) + "/"])
        assert result.returncode == 0

        data = read_yaml(target / ".context-root")
        assert data["engagement"] == "Acme Corp"

    def test_name_flag_overrides_derived(self, tmp_path):
        target = tmp_path / "acme-corp"
        run_script("init-engagement.py", [str(target), "--name", "ACME Corporation"])

        data = read_yaml(target / ".context-root")
        assert data["engagement"] == "ACME Corporation"


# ---------------------------------------------------------------------------
# Validation errors (exit 1)
# ---------------------------------------------------------------------------


class TestValidationErrors:
    """init-engagement.py exits 1 on validation errors."""

    def test_exit_1_path_already_exists(self, tmp_path):
        target = tmp_path / "acme-corp"
        target.mkdir()

        result = run_script("init-engagement.py", [str(target)])
        assert result.returncode == 1
        assert "already exists" in result.stderr.lower()

    def test_exit_1_no_path_argument(self):
        result = run_script("init-engagement.py", [])
        assert result.returncode == 2

    def test_not_idempotent(self, tmp_path):
        target = tmp_path / "acme-corp"
        result1 = run_script("init-engagement.py", [str(target)])
        assert result1.returncode == 0

        result2 = run_script("init-engagement.py", [str(target)])
        assert result2.returncode == 1


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases for init-engagement.py."""

    def test_path_with_spaces(self, tmp_path):
        target = tmp_path / "acme corp engagement"
        result = run_script("init-engagement.py", [str(target)])
        assert result.returncode == 0

        assert (target / ".context-root").is_file()
        data = read_yaml(target / ".context-root")
        assert data["engagement"] == "Acme Corp Engagement"

    def test_nested_path_creates_parents(self, tmp_path):
        target = tmp_path / "clients" / "acme-corp"
        result = run_script("init-engagement.py", [str(target)])
        assert result.returncode == 0

        assert (target / ".context-root").is_file()

    def test_no_partial_write_on_existing_path(self, tmp_path):
        """When path exists, nothing is modified inside it."""
        target = tmp_path / "acme-corp"
        target.mkdir()
        marker = target / "existing-file.txt"
        marker.write_text("original")

        run_script("init-engagement.py", [str(target)])

        assert marker.read_text() == "original"
        assert not (target / ".context-root").exists()
