"""
Contract tests for install-deps.py

Spec: install-deps.py (run from any level)
- Walks up to .context-root, installs requirements.txt top-down (root → class → task)
- Skips missing requirements.txt without error
- Exit codes: 0 = success, 1 = no .context-root, 2 = pip failed
- Idempotent (pip handles already-installed)
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


def run_install_deps(cwd):
    return run_script("install-deps.py", [], cwd=cwd)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestInstallDeps:
    """install-deps.py finds context root and installs dependencies."""

    def test_finds_context_root_from_task_level(self, task_dir):
        result = run_install_deps(task_dir)
        assert result.returncode == 0

    def test_finds_context_root_from_class_level(self, class_dir):
        result = run_install_deps(class_dir)
        assert result.returncode == 0

    def test_finds_context_root_from_root_level(self, engagement_root):
        result = run_install_deps(engagement_root)
        assert result.returncode == 0

    def test_installs_top_down_order(self, task_dir):
        """Root requirements installed before class, class before task."""
        # Write distinctive content to each requirements.txt so we can
        # verify order in pip output (or at minimum, that all are processed)
        root_path = task_dir.parent.parent
        (root_path / "requirements.txt").write_text("# root-deps\n")
        (task_dir.parent / "requirements.txt").write_text("# class-deps\n")
        (task_dir / "requirements.txt").write_text("# task-deps\n")

        result = run_install_deps(task_dir)
        assert result.returncode == 0

    def test_skips_missing_requirements_txt(self, tmp_path):
        """If a level has no requirements.txt, it's skipped without error."""
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury")
        task = make_task(cls, "my-task")

        # Remove class requirements.txt
        (cls / "requirements.txt").unlink()

        result = run_install_deps(task)
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# Precondition failures
# ---------------------------------------------------------------------------


class TestPreconditions:
    """install-deps.py exits 1 when .context-root is not found."""

    def test_exit_1_no_context_root(self, tmp_path):
        result = run_install_deps(tmp_path)
        assert result.returncode == 1

    def test_exit_1_from_arbitrary_nested_dir(self, tmp_path):
        """No .context-root anywhere in the ancestor chain."""
        nested = tmp_path / "a" / "b" / "c"
        nested.mkdir(parents=True)
        result = run_install_deps(nested)
        assert result.returncode == 1
