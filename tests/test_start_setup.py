"""
Contract tests for start-setup.py

Spec: start-setup.py [--period <period>] (run from task directory)
- Runs set-status, install-deps, init-period, load-context in sequence
- On failure at steps 2-4: sets blocked and exits 2
- Exit codes: 0 = success, 1 = precondition error, 2 = system error
"""

import pytest

from conftest import (
    make_class,
    make_context_root,
    make_period,
    make_task,
    read_yaml,
    run_script,
)

pytestmark = pytest.mark.mid


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run_setup(cwd, period=None):
    args = []
    if period:
        args.extend(["--period", period])
    return run_script("start-setup.py", args, cwd=cwd, timeout=30)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestHappyPath:
    def test_not_started_with_period_arg(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury")
        task = make_task(cls, "monthly-bank-fees")

        result = run_setup(task, period="2026-03")
        assert result.returncode == 0

        data = read_yaml(task / "status.yaml")
        assert data["status"] == "in_progress"
        assert data["period"] == "2026-03"

    def test_not_started_with_period_in_status(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury")
        task = make_task(cls, "monthly-bank-fees", period="2026-03")

        result = run_setup(task)
        assert result.returncode == 0

        data = read_yaml(task / "status.yaml")
        assert data["status"] == "in_progress"
        assert data["period"] == "2026-03"

    def test_period_arg_ignored_when_status_has_period(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury")
        task = make_task(cls, "monthly-bank-fees", period="2026-03")

        result = run_setup(task, period="2026-04")
        assert result.returncode == 0

        data = read_yaml(task / "status.yaml")
        assert data["period"] == "2026-03"  # not overwritten

    def test_crash_recovery_in_progress(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury")
        task = make_task(
            cls, "monthly-bank-fees", status="in_progress", period="2026-03"
        )
        make_period(task, "2026-03")

        result = run_setup(task)
        assert result.returncode == 0

        data = read_yaml(task / "status.yaml")
        assert data["status"] == "in_progress"
        assert data["period"] == "2026-03"

    def test_review_ready_reentry(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury")
        task = make_task(
            cls, "monthly-bank-fees", status="review_ready", period="2026-03"
        )
        make_period(task, "2026-03")

        result = run_setup(task)
        assert result.returncode == 0

        data = read_yaml(task / "status.yaml")
        assert data["status"] == "in_progress"
        assert data["period"] == "2026-03"  # preserved


# ---------------------------------------------------------------------------
# Period directory
# ---------------------------------------------------------------------------


class TestPeriodDir:
    def test_creates_period_dir(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury")
        task = make_task(cls, "monthly-bank-fees")

        run_setup(task, period="2026-03")

        period_dir = task / "periods" / "2026-03"
        assert (period_dir / "data").is_dir()
        assert (period_dir / "workpapers").is_dir()
        assert (period_dir / "review-notes").is_dir()

    def test_skips_existing_period_dir(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury")
        task = make_task(
            cls, "monthly-bank-fees", status="in_progress", period="2026-03"
        )
        make_period(task, "2026-03")

        # Should not fail even though period dir exists
        result = run_setup(task)
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# Context output
# ---------------------------------------------------------------------------


class TestContextOutput:
    def test_stdout_contains_context_sections(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury")
        task = make_task(cls, "monthly-bank-fees")

        result = run_setup(task, period="2026-03")
        assert result.returncode == 0

        # load-context.py prints section headers
        assert "root/AGENT.md" in result.stdout
        assert "SKILL.md" in result.stdout
        assert "status.yaml" in result.stdout

    def test_no_context_on_failure(self, tmp_path):
        """If setup fails, stdout should be empty (no partial context)."""
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury")
        task = make_task(cls, "monthly-bank-fees")

        # No period available -> exit 1, no context output
        result = run_setup(task)
        assert result.returncode == 1
        assert result.stdout.strip() == ""


# ---------------------------------------------------------------------------
# Precondition failures (exit 1, no blocked)
# ---------------------------------------------------------------------------


class TestFailures:
    def test_no_period_available(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury")
        task = make_task(cls, "monthly-bank-fees")

        result = run_setup(task)  # no --period, no period in status.yaml
        assert result.returncode == 1
        assert "No period available" in result.stderr

    def test_no_status_yaml(self, tmp_path):
        result = run_setup(tmp_path, period="2026-03")
        assert result.returncode == 1
        assert "No status.yaml" in result.stderr

    def test_invalid_transition_does_not_set_blocked(self, tmp_path):
        """done -> in_progress is invalid; should exit 1 without setting blocked."""
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury")
        task = make_task(
            cls, "monthly-bank-fees", status="done", period="2026-03"
        )

        result = run_setup(task)
        assert result.returncode == 1

        data = read_yaml(task / "status.yaml")
        assert data["status"] == "done"  # unchanged, not blocked


# ---------------------------------------------------------------------------
# Blocked on failure (exit 2, blocked set)
# ---------------------------------------------------------------------------


class TestPreconditionEdgeCases:
    def test_corrupt_status_yaml(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury")
        task = make_task(cls, "monthly-bank-fees")

        # Corrupt the status.yaml
        (task / "status.yaml").write_text(":\n  :\n")

        result = run_setup(task, period="2026-03")
        assert result.returncode == 1
        assert "Corrupt" in result.stderr


class TestBlockedOnFailure:
    def test_install_deps_failure_sets_blocked(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury")
        task = make_task(cls, "monthly-bank-fees")

        # Write invalid requirements to trigger pip failure
        (task / "requirements.txt").write_text("===invalid===\n")

        result = run_setup(task, period="2026-03")
        assert result.returncode == 2

        data = read_yaml(task / "status.yaml")
        assert data["status"] == "blocked"
        assert len(data["issues"]) > 0

    def test_load_context_failure_sets_blocked(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury")
        task = make_task(cls, "monthly-bank-fees")

        # Remove .context-root so load-context.py fails
        (root / ".context-root").unlink()

        result = run_setup(task, period="2026-03")
        assert result.returncode == 2

        data = read_yaml(task / "status.yaml")
        assert data["status"] == "blocked"
        assert len(data["issues"]) > 0

    def test_init_period_failure_sets_blocked(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury")
        task = make_task(cls, "monthly-bank-fees")

        # Pass an invalid period format for a monthly task
        result = run_setup(task, period="bad-period")
        assert result.returncode == 2

        data = read_yaml(task / "status.yaml")
        assert data["status"] == "blocked"
        assert len(data["issues"]) > 0

    def test_blocked_reason_contains_error_text(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury")
        task = make_task(cls, "monthly-bank-fees")

        (root / ".context-root").unlink()

        run_setup(task, period="2026-03")

        data = read_yaml(task / "status.yaml")
        # The blocked reason should contain the error from load-context.py
        assert any("context-root" in issue.lower() for issue in data["issues"])
