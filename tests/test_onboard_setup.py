"""
Contract tests for onboard-setup.py

Spec: onboard-setup.py <task-name> (run from class directory)
- Runs load-context --level class, then init-task <task-name>
- Exit codes: 0 = success, 1 = precondition error, 2 = system error
"""

import pytest

from conftest import (
    make_class,
    make_context_root,
    make_task,
    read_yaml,
    run_script,
)

pytestmark = pytest.mark.mid


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run_onboard_setup(cwd, task_name=None):
    args = [task_name] if task_name else []
    return run_script("onboard-setup.py", args, cwd=cwd, timeout=30)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestHappyPath:
    def test_creates_task_and_returns_context(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[])

        result = run_onboard_setup(cls, "monthly-bank-fees")
        assert result.returncode == 0

        # Task directory was created
        task_dir = cls / "monthly-bank-fees"
        assert task_dir.is_dir()
        assert (task_dir / "SKILL.md").is_file()
        assert (task_dir / "status.yaml").is_file()
        assert (task_dir / "learned.md").is_file()
        assert (task_dir / "tools").is_dir()
        assert (task_dir / "periods").is_dir()

    def test_stdout_contains_context_sections(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[])

        result = run_onboard_setup(cls, "monthly-bank-fees")
        assert result.returncode == 0

        # load-context --level class prints root and class AGENT.md
        assert "root/AGENT.md" in result.stdout
        assert "class/AGENT.md" in result.stdout

    def test_status_yaml_is_not_started(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[])

        run_onboard_setup(cls, "monthly-bank-fees")

        data = read_yaml(cls / "monthly-bank-fees" / "status.yaml")
        assert data["status"] == "not_started"


# ---------------------------------------------------------------------------
# Precondition failures (exit 1)
# ---------------------------------------------------------------------------


class TestPreconditionFailures:
    def test_no_class_yaml(self, tmp_path):
        """Exit 1 if not in a class directory."""
        result = run_onboard_setup(tmp_path, "some-task")
        assert result.returncode == 1
        assert "class" in result.stderr.lower()

    def test_task_already_exists(self, tmp_path):
        """Exit 1 if task directory already exists."""
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[])
        make_task(cls, "monthly-bank-fees")

        result = run_onboard_setup(cls, "monthly-bank-fees")
        assert result.returncode == 1
        assert "already exists" in result.stderr.lower()

    def test_no_args(self, tmp_path):
        """Exit 1 if no task name provided."""
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[])

        result = run_onboard_setup(cls)
        assert result.returncode == 1

    def test_no_context_root_in_ancestors(self, tmp_path):
        """Exit 2 if no .context-root found (load-context fails)."""
        # Create a class dir without a context root ancestor
        cls = tmp_path / "orphan-class"
        cls.mkdir()
        (cls / ".class.yaml").write_text(
            "schema_version: 1\nname: Orphan\ndescription: ''\nmanifest: []\n"
        )
        (cls / "AGENT.md").write_text("# Orphan\n")

        result = run_onboard_setup(cls, "some-task")
        assert result.returncode == 2
        assert "context-root" in result.stderr.lower()


# ---------------------------------------------------------------------------
# No partial state on failure
# ---------------------------------------------------------------------------


class TestNoPartialState:
    def test_no_task_dir_on_context_failure(self, tmp_path):
        """If load-context fails, init-task should not run."""
        cls = tmp_path / "orphan-class"
        cls.mkdir()
        (cls / ".class.yaml").write_text(
            "schema_version: 1\nname: Orphan\ndescription: ''\nmanifest: []\n"
        )
        (cls / "AGENT.md").write_text("# Orphan\n")

        run_onboard_setup(cls, "some-task")

        # Task directory should NOT have been created
        assert not (cls / "some-task").exists()
