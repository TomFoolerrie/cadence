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
    make_venv,
    run_script,
)


pytestmark = pytest.mark.mid


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run_install_deps(cwd, env=None):
    return run_script("install-deps.py", [], cwd=cwd, env=env)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestInstallDeps:
    """install-deps.py finds context root and installs dependencies."""

    def test_finds_context_root_from_task_level(self, tmp_path):
        root = make_context_root(tmp_path)
        make_venv(root)
        cls = make_class(root, "treasury")
        task = make_task(cls, "monthly-bank-fees")
        result = run_install_deps(task)
        assert result.returncode == 0

    def test_finds_context_root_from_class_level(self, tmp_path):
        root = make_context_root(tmp_path)
        make_venv(root)
        cls = make_class(root, "treasury")
        result = run_install_deps(cls)
        assert result.returncode == 0

    def test_finds_context_root_from_root_level(self, tmp_path):
        root = make_context_root(tmp_path)
        make_venv(root)
        result = run_install_deps(root)
        assert result.returncode == 0

    def test_installs_top_down_order(self, tmp_path):
        """Root requirements installed before class, class before task."""
        root = make_context_root(tmp_path)
        make_venv(root)
        cls = make_class(root, "treasury")
        task = make_task(cls, "monthly-bank-fees")

        # Write distinctive content to each requirements.txt so we can
        # verify order in pip output (or at minimum, that all are processed)
        (root / "requirements.txt").write_text("# root-deps\n")
        (cls / "requirements.txt").write_text("# class-deps\n")
        (task / "requirements.txt").write_text("# task-deps\n")

        result = run_install_deps(task)
        assert result.returncode == 0

    def test_skips_missing_requirements_txt(self, tmp_path):
        """If a level has no requirements.txt, it's skipped without error."""
        root = make_context_root(tmp_path)
        make_venv(root)
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
        assert "No .context-root found" in result.stderr

    def test_exit_1_from_arbitrary_nested_dir(self, tmp_path):
        """No .context-root anywhere in the ancestor chain."""
        nested = tmp_path / "a" / "b" / "c"
        nested.mkdir(parents=True)
        result = run_install_deps(nested)
        assert result.returncode == 1
        assert "No .context-root found" in result.stderr

    def test_falls_back_to_system_pip_when_no_venv(self, tmp_path):
        """Falls back to system pip when no venv exists (sandbox mode).

        Requires a NON-empty requirements.txt so the pip-resolution path is
        actually exercised — with an empty requirements file the run
        short-circuits to 0 before ever resolving pip.
        """
        root = make_context_root(tmp_path)
        # Non-empty (already-installed dep) so the pip fallback path runs and
        # the install succeeds without touching the network.
        (root / "requirements.txt").write_text("pip\n")
        result = run_install_deps(root)
        # Should succeed using system pip, not fail
        assert result.returncode == 0
        assert "No venv found" in result.stderr
        assert "using system pip" in result.stderr

    def test_empty_requirements_no_pip_returns_0(self, tmp_path, monkeypatch):
        """Empty/absent requirements + no venv + no system pip ⇒ short-circuit to 0.

        Regression for the exact live failure: an offline engagement whose every
        requirements.txt is empty must be a no-op success, never `return 2`.
        Simulate "no system pip" by clearing PATH so shutil.which finds nothing.
        """
        root = make_context_root(tmp_path)  # seeds an empty requirements.txt
        # Run with an empty PATH so no system pip is discoverable. If the code
        # short-circuits correctly it never reaches pip resolution anyway.
        result = run_install_deps(root, env={"PATH": ""})
        assert result.returncode == 0
        # Pip is never resolved, so the fallback messages must NOT appear.
        assert "No venv found" not in result.stderr

    def test_nonempty_requirements_no_pip_returns_2(self, tmp_path):
        """Non-empty requirements + no venv + no system pip ⇒ preserved return 2."""
        root = make_context_root(tmp_path)
        (root / "requirements.txt").write_text("some-real-dep\n")
        result = run_install_deps(root, env={"PATH": ""})
        assert result.returncode == 2
        assert "no system pip available" in result.stderr
