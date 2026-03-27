"""
Tests for computed class-level status rollup.

Spec: Class-level status is computed on the fly from task-level status.yaml files.
It is NEVER stored. The /status skill (or any consumer) computes it by reading all
enabled tasks in a class.

Rules:
- All enabled tasks not_started → class not_started
- Any enabled task beyond not_started (but not all terminal) → class in_progress
- All enabled tasks done or abandoned → class done

This may be tested via a utility function, load-context --orchestrator,
or the /status skill. Tests here validate the rollup logic itself.
"""

import pytest

from conftest import make_class, make_context_root, make_task, read_yaml


pytestmark = pytest.mark.mid


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def compute_class_status(class_path):
    """Reference implementation of class-level status rollup (spec test oracle).

    This function implements the spec's derivation rules (Section 02-three-levels.md).
    It is defined here as a test oracle — production code should eventually
    match this behavior. See also: load-context.py --orchestrator.
    """
    class_yaml = read_yaml(class_path / ".class.yaml")
    manifest = class_yaml.get("manifest", [])
    enabled_tasks = [t for t in manifest if t.get("enabled", True)]

    if not enabled_tasks:
        return "not_started"

    statuses = []
    for task_entry in enabled_tasks:
        task_name = task_entry["task"]
        task_status_path = class_path / task_name / "status.yaml"
        if task_status_path.exists():
            data = read_yaml(task_status_path)
            statuses.append(data.get("status", "not_started"))
        else:
            statuses.append("not_started")

    terminal = {"done", "abandoned"}

    if all(s == "not_started" for s in statuses):
        return "not_started"
    elif all(s in terminal for s in statuses):
        return "done"
    else:
        return "in_progress"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestClassStatusRollup:
    """Computed class-level status follows spec derivation rules."""

    def test_all_not_started_yields_class_not_started(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[
            {"task": "task-a", "order": 1, "enabled": True, "period_format": "monthly", "anchor": "first_monday"},
            {"task": "task-b", "order": 2, "enabled": True, "period_format": "monthly", "anchor": "first_monday"},
        ])
        make_task(cls, "task-a", status="not_started")
        make_task(cls, "task-b", status="not_started")

        assert compute_class_status(cls) == "not_started"

    def test_any_beyond_not_started_yields_in_progress(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[
            {"task": "task-a", "order": 1, "enabled": True, "period_format": "monthly", "anchor": "first_monday"},
            {"task": "task-b", "order": 2, "enabled": True, "period_format": "monthly", "anchor": "first_monday"},
        ])
        make_task(cls, "task-a", status="in_progress", period="2026-03")
        make_task(cls, "task-b", status="not_started")

        assert compute_class_status(cls) == "in_progress"

    def test_all_done_yields_class_done(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[
            {"task": "task-a", "order": 1, "enabled": True, "period_format": "monthly", "anchor": "first_monday"},
            {"task": "task-b", "order": 2, "enabled": True, "period_format": "monthly", "anchor": "first_monday"},
        ])
        make_task(cls, "task-a", status="done", period="2026-03", done_at="2026-04-07T14:30:00Z")
        make_task(cls, "task-b", status="done", period="2026-03", done_at="2026-04-07T14:30:00Z")

        assert compute_class_status(cls) == "done"

    def test_mixed_done_and_abandoned_yields_class_done(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[
            {"task": "task-a", "order": 1, "enabled": True, "period_format": "monthly", "anchor": "first_monday"},
            {"task": "task-b", "order": 2, "enabled": True, "period_format": "monthly", "anchor": "first_monday"},
        ])
        make_task(cls, "task-a", status="done", period="2026-03", done_at="2026-04-07T14:30:00Z")
        make_task(cls, "task-b", status="abandoned", period="2026-03",
                  done_at="2026-04-07T14:30:00Z", issues=["unrecoverable"])

        assert compute_class_status(cls) == "done"

    def test_disabled_tasks_excluded(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[
            {"task": "task-a", "order": 1, "enabled": True, "period_format": "monthly", "anchor": "first_monday"},
            {"task": "task-b", "order": 2, "enabled": False, "period_format": "monthly", "anchor": "first_monday"},
        ])
        make_task(cls, "task-a", status="done", period="2026-03", done_at="2026-04-07T14:30:00Z")
        make_task(cls, "task-b", status="not_started")  # disabled, should be ignored

        assert compute_class_status(cls) == "done"

    def test_single_task_follows_task_status(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[
            {"task": "only-task", "order": 1, "enabled": True, "period_format": "monthly", "anchor": "first_monday"},
        ])
        make_task(cls, "only-task", status="review_ready", period="2026-03")

        assert compute_class_status(cls) == "in_progress"
