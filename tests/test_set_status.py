"""
Contract tests for set-status.py

Spec: set-status.py <status> [reason] [--period <period>]
- Preconditions: status.yaml exists in cwd, transition is legal
- Valid transitions defined by state machine (see VALID_TRANSITIONS)
- Side effects: done/abandoned set done_at, blocked populates issues, retry clears issues
- Exit codes: 0 = success, 1 = invalid transition, 2 = filesystem error
- Idempotent only for in_progress → in_progress
"""

from datetime import datetime

import pytest

from conftest import make_class, make_context_root, make_task, read_yaml, run_script, write_yaml


pytestmark = pytest.mark.mid


# ---------------------------------------------------------------------------
# State machine definition (source of truth for parametrized tests)
# ---------------------------------------------------------------------------

ALL_STATUSES = ["not_started", "in_progress", "review_ready", "blocked", "done", "abandoned"]

VALID_TRANSITIONS = {
    ("not_started", "in_progress"),
    ("in_progress", "in_progress"),      # idempotent no-op
    ("in_progress", "review_ready"),
    ("in_progress", "blocked"),
    ("review_ready", "in_progress"),
    ("review_ready", "done"),
    ("blocked", "not_started"),
    ("blocked", "abandoned"),
}

# Transitions that require a reason argument
REQUIRES_REASON = {"blocked", "abandoned"}

INVALID_TRANSITIONS = [
    (frm, to)
    for frm in ALL_STATUSES
    for to in ALL_STATUSES
    if (frm, to) not in VALID_TRANSITIONS
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_task_with_status(tmp_path, status, period="2026-03", issues=None, done_at=None):
    """Create a full hierarchy with a task at the given status."""
    root = make_context_root(tmp_path)
    cls = make_class(root, "treasury")
    return make_task(cls, "monthly-bank-fees", status=status,
                     period=period, issues=issues, done_at=done_at)


def run_set_status(cwd, new_status, reason=None, period=None):
    """Run set-status.py with the given arguments."""
    args = [new_status]
    if reason:
        args.append(reason)
    if period:
        args.extend(["--period", period])
    return run_script("set-status.py", args, cwd=cwd)


# ---------------------------------------------------------------------------
# Valid transitions
# ---------------------------------------------------------------------------


class TestValidTransitions:
    """Each valid state machine transition succeeds."""

    def test_not_started_to_in_progress(self, tmp_path):
        task = make_task_with_status(tmp_path, "not_started")
        result = run_set_status(task, "in_progress")
        assert result.returncode == 0

        data = read_yaml(task / "status.yaml")
        assert data["status"] == "in_progress"

    def test_not_started_to_in_progress_with_period(self, tmp_path):
        task = make_task_with_status(tmp_path, "not_started", period="")
        result = run_set_status(task, "in_progress", period="2026-03")
        assert result.returncode == 0

        data = read_yaml(task / "status.yaml")
        assert data["status"] == "in_progress"
        assert data["period"] == "2026-03"

    def test_in_progress_to_in_progress_is_noop(self, tmp_path):
        """Idempotent: file should be byte-identical after no-op transition."""
        task = make_task_with_status(tmp_path, "in_progress")
        before = (task / "status.yaml").read_bytes()

        result = run_set_status(task, "in_progress")
        assert result.returncode == 0

        after = (task / "status.yaml").read_bytes()
        assert before == after

    def test_in_progress_to_review_ready(self, tmp_path):
        task = make_task_with_status(tmp_path, "in_progress")
        result = run_set_status(task, "review_ready")
        assert result.returncode == 0

        data = read_yaml(task / "status.yaml")
        assert data["status"] == "review_ready"

    def test_in_progress_to_blocked(self, tmp_path):
        task = make_task_with_status(tmp_path, "in_progress")
        result = run_set_status(task, "blocked", reason="Chase API 401")
        assert result.returncode == 0

        data = read_yaml(task / "status.yaml")
        assert data["status"] == "blocked"
        assert "Chase API 401" in data["issues"]

    def test_review_ready_to_in_progress(self, tmp_path):
        task = make_task_with_status(tmp_path, "review_ready",
                                     issues=["minor formatting issue"])
        result = run_set_status(task, "in_progress")
        assert result.returncode == 0

        data = read_yaml(task / "status.yaml")
        assert data["status"] == "in_progress"
        assert data["issues"] == []

    def test_review_ready_to_done(self, tmp_path):
        task = make_task_with_status(tmp_path, "review_ready")
        result = run_set_status(task, "done")
        assert result.returncode == 0

        data = read_yaml(task / "status.yaml")
        assert data["status"] == "done"
        assert data["issues"] == []
        assert data["done_at"] is not None

    def test_blocked_to_not_started(self, tmp_path):
        task = make_task_with_status(tmp_path, "blocked",
                                     issues=["API failure"])
        result = run_set_status(task, "not_started")
        assert result.returncode == 0

        data = read_yaml(task / "status.yaml")
        assert data["status"] == "not_started"
        assert data["issues"] == []
        assert data["done_at"] is None

    def test_blocked_to_abandoned(self, tmp_path):
        task = make_task_with_status(tmp_path, "blocked",
                                     issues=["API failure"])
        result = run_set_status(task, "abandoned", reason="Cannot recover this period")
        assert result.returncode == 0

        data = read_yaml(task / "status.yaml")
        assert data["status"] == "abandoned"
        assert "Cannot recover this period" in data["issues"]
        assert data["done_at"] is not None


# ---------------------------------------------------------------------------
# Invalid transitions (parametrized)
# ---------------------------------------------------------------------------


class TestInvalidTransitions:
    """All illegal state transitions are rejected with exit code 1."""

    @pytest.mark.parametrize("from_status,to_status", INVALID_TRANSITIONS,
                             ids=[f"{f}->{t}" for f, t in INVALID_TRANSITIONS])
    def test_invalid_transition_exits_1(self, tmp_path, from_status, to_status):
        # For terminal states, set done_at so status.yaml is valid
        done_at = "2026-04-07T14:30:00Z" if from_status in ("done", "abandoned") else None
        issues = ["reason"] if from_status in ("blocked",) else None
        task = make_task_with_status(tmp_path, from_status, done_at=done_at, issues=issues)

        # Provide reason for transitions that require it
        reason = "test reason" if to_status in REQUIRES_REASON else None
        result = run_set_status(task, to_status, reason=reason)
        assert result.returncode == 1


# ---------------------------------------------------------------------------
# Side effects
# ---------------------------------------------------------------------------


class TestSideEffects:
    """Verify side effects of transitions on status.yaml fields."""

    def test_done_sets_done_at_iso8601(self, tmp_path):
        """done_at must be a valid ISO 8601 timestamp."""
        task = make_task_with_status(tmp_path, "review_ready")
        run_set_status(task, "done")

        data = read_yaml(task / "status.yaml")
        # Should be parseable as ISO 8601
        dt = datetime.fromisoformat(data["done_at"])
        assert dt.year >= 2026

    def test_done_clears_issues(self, tmp_path):
        task = make_task_with_status(tmp_path, "review_ready",
                                     issues=["leftover issue"])
        run_set_status(task, "done")

        data = read_yaml(task / "status.yaml")
        assert data["issues"] == []

    def test_abandoned_sets_done_at(self, tmp_path):
        task = make_task_with_status(tmp_path, "blocked", issues=["failure"])
        run_set_status(task, "abandoned", reason="giving up")

        data = read_yaml(task / "status.yaml")
        assert data["done_at"] is not None
        dt = datetime.fromisoformat(data["done_at"])
        assert dt.year >= 2026

    def test_abandoned_keeps_reason_in_issues(self, tmp_path):
        task = make_task_with_status(tmp_path, "blocked", issues=["original failure"])
        run_set_status(task, "abandoned", reason="giving up")

        data = read_yaml(task / "status.yaml")
        assert "giving up" in data["issues"]

    def test_blocked_populates_issues(self, tmp_path):
        task = make_task_with_status(tmp_path, "in_progress")
        run_set_status(task, "blocked", reason="Chase API 401")

        data = read_yaml(task / "status.yaml")
        assert "Chase API 401" in data["issues"]

    def test_blocked_to_not_started_clears_issues_and_done_at(self, tmp_path):
        task = make_task_with_status(tmp_path, "blocked",
                                     issues=["failure"], done_at=None)
        run_set_status(task, "not_started")

        data = read_yaml(task / "status.yaml")
        assert data["issues"] == []
        assert data["done_at"] is None

    def test_review_ready_to_in_progress_clears_issues(self, tmp_path):
        task = make_task_with_status(tmp_path, "review_ready",
                                     issues=["reviewer notes"])
        run_set_status(task, "in_progress")

        data = read_yaml(task / "status.yaml")
        assert data["issues"] == []

    def test_done_at_not_set_on_non_terminal_transitions(self, tmp_path):
        """done_at should remain None for non-terminal transitions."""
        task = make_task_with_status(tmp_path, "not_started")
        run_set_status(task, "in_progress")

        data = read_yaml(task / "status.yaml")
        assert data["done_at"] is None

    def test_schema_version_never_modified(self, tmp_path):
        """schema_version must stay 1 across all transitions."""
        task = make_task_with_status(tmp_path, "not_started")

        # Walk through several transitions
        run_set_status(task, "in_progress")
        assert read_yaml(task / "status.yaml")["schema_version"] == 1

        run_set_status(task, "review_ready")
        assert read_yaml(task / "status.yaml")["schema_version"] == 1

        run_set_status(task, "done")
        assert read_yaml(task / "status.yaml")["schema_version"] == 1

    def test_period_preserved_across_transitions(self, tmp_path):
        """Once period is set, subsequent transitions preserve it."""
        task = make_task_with_status(tmp_path, "not_started", period="")
        run_set_status(task, "in_progress", period="2026-03")

        assert read_yaml(task / "status.yaml")["period"] == "2026-03"

        run_set_status(task, "review_ready")
        assert read_yaml(task / "status.yaml")["period"] == "2026-03"

        run_set_status(task, "done")
        assert read_yaml(task / "status.yaml")["period"] == "2026-03"


# ---------------------------------------------------------------------------
# Precondition failures
# ---------------------------------------------------------------------------


class TestPreconditions:
    """Precondition checks for set-status.py."""

    def test_exit_1_no_status_yaml(self, tmp_path):
        result = run_set_status(tmp_path, "in_progress")
        assert result.returncode == 1

    def test_exit_1_reason_required_for_blocked(self, tmp_path):
        task = make_task_with_status(tmp_path, "in_progress")
        result = run_set_status(task, "blocked")  # no reason
        assert result.returncode == 1

    def test_exit_1_reason_required_for_abandoned(self, tmp_path):
        task = make_task_with_status(tmp_path, "blocked", issues=["failure"])
        result = run_set_status(task, "abandoned")  # no reason
        assert result.returncode == 1

    def test_malformed_status_yaml_exits_2(self, tmp_path):
        """Malformed YAML exits with code 2 (filesystem error)."""
        (tmp_path / "status.yaml").write_text("not: valid: yaml: [[[")
        result = run_set_status(tmp_path, "in_progress")
        assert result.returncode == 2
        assert "Traceback" not in result.stderr


# ---------------------------------------------------------------------------
# --period flag
# ---------------------------------------------------------------------------


class TestPeriodFlag:
    """Tests for the --period flag behavior."""

    def test_period_flag_sets_period_on_not_started_to_in_progress(self, tmp_path):
        task = make_task_with_status(tmp_path, "not_started", period="")
        result = run_set_status(task, "in_progress", period="2026-04")
        assert result.returncode == 0
        assert read_yaml(task / "status.yaml")["period"] == "2026-04"

    def test_period_flag_only_valid_on_not_started_to_in_progress(self, tmp_path):
        """--period on other transitions should be rejected."""
        task = make_task_with_status(tmp_path, "in_progress")
        result = run_set_status(task, "review_ready", period="2026-03")
        assert result.returncode == 1

    def test_invalid_period_format_rejected(self, tmp_path):
        """--period with invalid format exits 1."""
        task = make_task_with_status(tmp_path, "not_started", period="")
        result = run_set_status(task, "in_progress", period="not-a-period")
        assert result.returncode == 1
        assert "Traceback" not in result.stderr

    def test_path_traversal_period_rejected(self, tmp_path):
        """--period with path traversal string exits 1."""
        task = make_task_with_status(tmp_path, "not_started", period="")
        result = run_set_status(task, "in_progress", period="../../etc")
        assert result.returncode == 1
        assert "Traceback" not in result.stderr
