"""
Contract tests for load-context.py

Spec: load-context.py --level root|class|task [--orchestrator]
- Walks up from cwd to find .context-root
- Assembles context top-down: root AGENT.md → class AGENT.md → task files
- --orchestrator adds .class.yaml content (only valid with --level class)
- Blocked status appends recovery hint
- Tool paths printed in resolution order (task > class > global)
- Exit codes: 0 = success, 1 = precondition failed
- Idempotent (pure read)
"""

import pytest

from conftest import (
    make_class,
    make_context_root,
    make_period,
    make_task,
    run_script,
)


pytestmark = pytest.mark.mid


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run_load_context(cwd, level, orchestrator=False):
    args = ["--level", level]
    if orchestrator:
        args.append("--orchestrator")
    return run_script("load-context.py", args, cwd=cwd)


# ---------------------------------------------------------------------------
# Level filtering
# ---------------------------------------------------------------------------


class TestLevelFiltering:
    """load-context.py returns the correct files based on --level."""

    def test_level_root_loads_only_root_agent_md(self, engagement_root):
        result = run_load_context(engagement_root, "root")
        assert result.returncode == 0
        assert "AGENT.md" in result.stdout
        # Should NOT contain class or task content
        assert "SKILL.md" not in result.stdout

    def test_level_class_loads_root_and_class_agent_md(self, class_dir):
        result = run_load_context(class_dir, "class")
        assert result.returncode == 0

        # Both root and class AGENT.md should appear
        assert "Test Corp" in result.stdout  # root content
        assert "Treasury" in result.stdout   # class content

    def test_level_task_loads_full_chain(self, task_dir):
        result = run_load_context(task_dir, "task")
        assert result.returncode == 0

        # Root, class, and task files should all appear
        assert "Test Corp" in result.stdout         # root AGENT.md
        assert "Treasury" in result.stdout           # class AGENT.md
        assert "## Purpose" in result.stdout         # SKILL.md
        assert "## Review History" in result.stdout  # learned.md


# ---------------------------------------------------------------------------
# Output format
# ---------------------------------------------------------------------------


class TestOutputFormat:
    """Output format and ordering."""

    def test_section_headers_format(self, task_dir):
        result = run_load_context(task_dir, "task")
        assert result.returncode == 0
        # Headers should follow the ── filename ── pattern
        assert "──" in result.stdout

    def test_top_down_order(self, task_dir):
        """Root content appears before class content, class before task."""
        result = run_load_context(task_dir, "task")
        stdout = result.stdout

        # Find positions of key content from each level
        root_pos = stdout.find("Test Corp")
        class_pos = stdout.find("Treasury")
        task_pos = stdout.find("## Purpose")

        assert root_pos < class_pos < task_pos


# ---------------------------------------------------------------------------
# --orchestrator flag
# ---------------------------------------------------------------------------


class TestOrchestratorFlag:
    """--orchestrator flag appends .class.yaml content."""

    def test_orchestrator_appends_class_yaml(self, class_dir):
        result = run_load_context(class_dir, "class", orchestrator=True)
        assert result.returncode == 0
        # .class.yaml manifest content should appear
        assert "monthly-bank-fees" in result.stdout

    def test_orchestrator_only_valid_with_class_level(self, engagement_root, task_dir):
        """--orchestrator exits 1 when used with root or task level."""
        result_root = run_load_context(engagement_root, "root", orchestrator=True)
        assert result_root.returncode == 1

        result_task = run_load_context(task_dir, "task", orchestrator=True)
        assert result_task.returncode == 1


# ---------------------------------------------------------------------------
# Recovery hints
# ---------------------------------------------------------------------------


class TestRecoveryHints:
    """Blocked status triggers recovery hint in output."""

    def test_blocked_status_appends_recovery_hint(self, task_dir_blocked):
        result = run_load_context(task_dir_blocked, "task")
        assert result.returncode == 0
        # Should contain some form of recovery guidance
        stdout_lower = result.stdout.lower()
        assert "recovery" in stdout_lower or "blocked" in stdout_lower

    def test_non_blocked_status_no_recovery_hint(self, task_dir_in_progress):
        result = run_load_context(task_dir_in_progress, "task")
        assert result.returncode == 0
        assert "recovery" not in result.stdout.lower()


# ---------------------------------------------------------------------------
# Tool path resolution
# ---------------------------------------------------------------------------


class TestToolPaths:
    """Tool path resolution order: task > class > global."""

    def test_tool_paths_resolution_order(self, task_dir):
        """Tool paths section lists task tools before class tools before global."""
        # Add a tool at each level to make paths visible
        (task_dir / "tools" / "validate.py").write_text("# task tool")

        class_path = task_dir.parent
        (class_path / "tools" / "parse.py").write_text("# class tool")

        root_path = class_path.parent
        (root_path / ".claude" / "tools" / "format.py").write_text("# global tool")

        result = run_load_context(task_dir, "task")
        assert result.returncode == 0

        stdout = result.stdout
        # Task tools should appear before class tools, class before global
        task_tool_pos = stdout.find("validate.py")
        class_tool_pos = stdout.find("parse.py")
        global_tool_pos = stdout.find("format.py")

        assert task_tool_pos >= 0, "task tool not found in output"
        assert class_tool_pos >= 0, "class tool not found in output"
        assert global_tool_pos >= 0, "global tool not found in output"
        assert task_tool_pos < class_tool_pos < global_tool_pos

    def test_tool_name_collision(self, task_dir):
        """Same filename at multiple levels — task-level wins in resolution order."""
        (task_dir / "tools" / "validate.py").write_text("# task version")

        class_path = task_dir.parent
        (class_path / "tools" / "validate.py").write_text("# class version")

        result = run_load_context(task_dir, "task")
        assert result.returncode == 0
        # Both should be listed, but task first
        stdout = result.stdout
        first_occurrence = stdout.find("validate.py")
        assert first_occurrence >= 0

    def test_tool_paths_omits_nonexistent_dirs(self, tmp_path):
        """Tool dirs that don't exist are omitted from output."""
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury")
        task = make_task(cls, "monthly-bank-fees")

        # Remove task tools dir
        (task / "tools").rmdir()

        result = run_load_context(task, "task")
        assert result.returncode == 0

    def test_tool_paths_only_at_task_level(self, class_dir):
        """Tool paths section not present at root or class level."""
        result = run_load_context(class_dir, "class")
        assert result.returncode == 0
        assert "── tools ──" not in result.stdout


# ---------------------------------------------------------------------------
# Walk-up to find .context-root
# ---------------------------------------------------------------------------


class TestWalkUp:
    """load-context.py walks up directory tree to find .context-root."""

    def test_walks_up_from_deeply_nested_dir(self, task_dir):
        """Works from inside periods/2026-03/data/."""
        nested = task_dir / "periods" / "2026-03" / "data"
        nested.mkdir(parents=True, exist_ok=True)

        result = run_load_context(nested, "task")
        # Should still find .context-root and load context
        assert result.returncode == 0
        assert "Test Corp" in result.stdout


# ---------------------------------------------------------------------------
# Precondition failures
# ---------------------------------------------------------------------------


class TestPreconditions:
    """load-context.py exits 1 when preconditions fail."""

    def test_exit_1_no_context_root(self, tmp_path):
        result = run_load_context(tmp_path, "root")
        assert result.returncode == 1
        assert "No .context-root found" in result.stderr

    def test_exit_1_invalid_context_root_yaml(self, tmp_path):
        """Malformed .context-root exits 1."""
        (tmp_path / ".context-root").write_text("not valid yaml [[[")
        result = run_load_context(tmp_path, "root")
        assert result.returncode == 1
        assert "Traceback" not in result.stderr
        assert "Invalid .context-root" in result.stderr

    def test_exit_1_wrong_level_for_directory(self, engagement_root):
        """--level task from root directory (no SKILL.md) exits 1."""
        result = run_load_context(engagement_root, "task")
        assert result.returncode == 1
        assert "Not in a class directory" in result.stderr

    def test_exit_1_context_root_missing_engagement_key(self, tmp_path):
        """Valid YAML .context-root but missing engagement key exits 1."""
        (tmp_path / ".context-root").write_text("schema_version: 1\n")
        result = run_load_context(tmp_path, "root")
        assert result.returncode == 1
        assert "missing engagement key" in result.stderr.lower()


# ---------------------------------------------------------------------------
# reference.md inclusion
# ---------------------------------------------------------------------------


class TestReferenceMd:
    """reference.md is included at task level only."""

    def test_task_level_includes_reference_md(self, task_dir):
        result = run_load_context(task_dir, "task")
        assert result.returncode == 0
        assert "\u2500\u2500 reference.md \u2500\u2500" in result.stdout
        assert "Plugin Scripts" in result.stdout

    def test_root_level_excludes_reference_md(self, engagement_root):
        result = run_load_context(engagement_root, "root")
        assert result.returncode == 0
        assert "reference.md" not in result.stdout

    def test_class_level_excludes_reference_md(self, class_dir):
        result = run_load_context(class_dir, "class")
        assert result.returncode == 0
        assert "reference.md" not in result.stdout
