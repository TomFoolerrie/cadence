"""
Contract tests for init-venv.py

Spec: init-venv.py (run from anywhere within an engagement hierarchy)
- Walks up to .context-root, creates venv at engagement root
- Idempotent: exits 0 if venv/bin/python already exists
- Exit codes: 0 = success/exists, 1 = no .context-root, 2 = creation failed
"""

import pytest

from conftest import (
    make_class,
    make_context_root,
    make_task,
    make_venv,
    run_script,
)


pytestmark = pytest.mark.mid


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run_init_venv(cwd):
    return run_script("init-venv.py", [], cwd=cwd, timeout=30)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestInitVenv:
    """init-venv.py creates a venv at the engagement root."""

    def test_creates_venv_at_root(self, tmp_path):
        root = make_context_root(tmp_path)

        result = run_init_venv(root)
        assert result.returncode == 0
        assert (root / "venv" / "bin" / "python").exists()

    def test_idempotent_when_venv_exists(self, tmp_path):
        root = make_context_root(tmp_path)
        make_venv(root)

        result = run_init_venv(root)
        assert result.returncode == 0

    def test_finds_root_from_task_dir(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury")
        task = make_task(cls, "monthly-bank-fees")

        result = run_init_venv(task)
        assert result.returncode == 0
        assert (root / "venv" / "bin" / "python").exists()

    def test_finds_root_from_class_dir(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury")

        result = run_init_venv(cls)
        assert result.returncode == 0
        assert (root / "venv" / "bin" / "python").exists()


# ---------------------------------------------------------------------------
# Precondition failures
# ---------------------------------------------------------------------------


class TestPreconditions:
    """init-venv.py exits 1 when .context-root is not found."""

    def test_exit_1_no_context_root(self, tmp_path):
        result = run_init_venv(tmp_path)
        assert result.returncode == 1
        assert "No .context-root found" in result.stderr

    def test_exit_1_from_arbitrary_nested_dir(self, tmp_path):
        nested = tmp_path / "a" / "b" / "c"
        nested.mkdir(parents=True)
        result = run_init_venv(nested)
        assert result.returncode == 1
        assert "No .context-root found" in result.stderr
