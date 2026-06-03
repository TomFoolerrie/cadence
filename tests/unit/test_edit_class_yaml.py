"""
Contract tests for edit-class-yaml.py

Spec: edit-class-yaml.py <subcommand> (run from class directory)
- Subcommands: set-description, add-task, update-task, remove-task
- Preconditions: .class.yaml exists in cwd, valid YAML with manifest list
- Exit codes: 0 = success, 1 = validation error, 2 = system error
"""

import pytest

from conftest import (
    make_context_root,
    make_class,
    make_task,
    read_yaml,
    run_script,
    write_yaml,
)


pytestmark = pytest.mark.mid

SCRIPT = "edit-class-yaml.py"


# ===========================================================================
# set-description
# ===========================================================================


class TestSetDescription:
    """set-description subcommand."""

    def test_sets_description(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[])

        result = run_script(SCRIPT, ["set-description", "Cash management tasks"], cwd=cls)
        assert result.returncode == 0

        data = read_yaml(cls / ".class.yaml")
        assert data["description"] == "Cash management tasks"

    def test_overwrites_existing_description(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[])
        # Set initial description
        d = read_yaml(cls / ".class.yaml")
        d["description"] = "Old description"
        write_yaml(cls / ".class.yaml", d)

        result = run_script(SCRIPT, ["set-description", "New description"], cwd=cls)
        assert result.returncode == 0

        data = read_yaml(cls / ".class.yaml")
        assert data["description"] == "New description"

    def test_set_description_preserves_manifest(self, tmp_path):
        """Setting description does not modify manifest entries."""
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[
            {"task": "bank-fees", "order": 1, "enabled": True,
             "period_format": "monthly", "anchor": "first_monday"},
        ])
        result = run_script(SCRIPT, ["set-description", "Cash management"], cwd=cls)
        assert result.returncode == 0
        data = read_yaml(cls / ".class.yaml")
        assert data["description"] == "Cash management"
        assert len(data["manifest"]) == 1
        assert data["manifest"][0]["task"] == "bank-fees"
        assert data["manifest"][0]["order"] == 1
        assert data["schema_version"] == 1

    def test_set_description_empty_string(self, tmp_path):
        """Empty string description is valid."""
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[])
        result = run_script(SCRIPT, ["set-description", ""], cwd=cls)
        assert result.returncode == 0
        data = read_yaml(cls / ".class.yaml")
        assert data["description"] == ""

    def test_exit_1_no_class_yaml(self, tmp_path):
        result = run_script(SCRIPT, ["set-description", "Something"], cwd=tmp_path)
        assert result.returncode == 1


# ===========================================================================
# add-task
# ===========================================================================


class TestAddTask:
    """add-task subcommand."""

    def test_happy_path_adds_task_with_all_fields(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[])
        make_task(cls, "monthly-bank-fees")

        result = run_script(
            SCRIPT,
            ["add-task", "monthly-bank-fees", "--order", "1",
             "--period-format", "monthly", "--anchor", "first_monday"],
            cwd=cls,
        )
        assert result.returncode == 0

        data = read_yaml(cls / ".class.yaml")
        assert len(data["manifest"]) == 1
        entry = data["manifest"][0]
        assert entry["task"] == "monthly-bank-fees"
        assert entry["order"] == 1
        assert entry["enabled"] is True
        assert entry["period_format"] == "monthly"
        assert entry["anchor"] == "first_monday"

    def test_defaults_enabled_true_monthly_first_monday(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[])
        make_task(cls, "monthly-bank-fees")

        result = run_script(
            SCRIPT,
            ["add-task", "monthly-bank-fees", "--order", "1"],
            cwd=cls,
        )
        assert result.returncode == 0

        entry = read_yaml(cls / ".class.yaml")["manifest"][0]
        assert entry["enabled"] is True
        assert entry["period_format"] == "monthly"
        assert entry["anchor"] == "first_monday"

    def test_custom_values_all_flags(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[])
        make_task(cls, "quarterly-review")

        result = run_script(
            SCRIPT,
            ["add-task", "quarterly-review", "--order", "5",
             "--no-enabled", "--period-format", "quarterly", "--anchor", "last_friday"],
            cwd=cls,
        )
        assert result.returncode == 0

        entry = read_yaml(cls / ".class.yaml")["manifest"][0]
        assert entry["task"] == "quarterly-review"
        assert entry["order"] == 5
        assert entry["enabled"] is False
        assert entry["period_format"] == "quarterly"
        assert entry["anchor"] == "last_friday"

    def test_exit_1_task_already_in_manifest(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[
            {"task": "monthly-bank-fees", "order": 1, "enabled": True,
             "period_format": "monthly", "anchor": "first_monday"},
        ])
        make_task(cls, "monthly-bank-fees")

        result = run_script(
            SCRIPT,
            ["add-task", "monthly-bank-fees", "--order", "2"],
            cwd=cls,
        )
        assert result.returncode == 1
        assert "already in manifest" in result.stderr.lower()

    def test_exit_1_task_directory_missing(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[])

        result = run_script(
            SCRIPT,
            ["add-task", "nonexistent-task", "--order", "1"],
            cwd=cls,
        )
        assert result.returncode == 1
        assert "does not exist" in result.stderr.lower()

    def test_exit_1_task_directory_no_skill_md(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[])
        # Create directory without SKILL.md
        (cls / "bad-task").mkdir()

        result = run_script(
            SCRIPT,
            ["add-task", "bad-task", "--order", "1"],
            cwd=cls,
        )
        assert result.returncode == 1
        assert "skill.md" in result.stderr.lower()

    def test_exit_1_invalid_period_format(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[])
        make_task(cls, "my-task")

        result = run_script(
            SCRIPT,
            ["add-task", "my-task", "--order", "1", "--period-format", "biweekly"],
            cwd=cls,
        )
        assert result.returncode == 1
        assert "period-format" in result.stderr.lower() or "biweekly" in result.stderr.lower()

    def test_exit_1_invalid_anchor(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[])
        make_task(cls, "my-task")

        result = run_script(
            SCRIPT,
            ["add-task", "my-task", "--order", "1", "--anchor", "second_monday"],
            cwd=cls,
        )
        assert result.returncode == 1
        assert "anchor" in result.stderr.lower() or "second_monday" in result.stderr.lower()

    def test_exit_1_nonpositive_order(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[])
        make_task(cls, "my-task")

        result = run_script(
            SCRIPT,
            ["add-task", "my-task", "--order", "0"],
            cwd=cls,
        )
        assert result.returncode == 1

    def test_exit_1_negative_order(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[])
        make_task(cls, "my-task")

        result = run_script(
            SCRIPT,
            ["add-task", "my-task", "--order", "-1"],
            cwd=cls,
        )
        assert result.returncode == 1

    def test_no_enabled_sets_false(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[])
        make_task(cls, "my-task")

        result = run_script(
            SCRIPT,
            ["add-task", "my-task", "--order", "1", "--no-enabled"],
            cwd=cls,
        )
        assert result.returncode == 0

        entry = read_yaml(cls / ".class.yaml")["manifest"][0]
        assert entry["enabled"] is False


# ===========================================================================
# update-task
# ===========================================================================


class TestUpdateTask:
    """update-task subcommand."""

    def _manifest_with_task(self):
        return [
            {"task": "monthly-bank-fees", "order": 1, "enabled": True,
             "period_format": "monthly", "anchor": "first_monday"},
        ]

    def test_update_order(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=self._manifest_with_task())

        result = run_script(
            SCRIPT,
            ["update-task", "monthly-bank-fees", "--order", "3"],
            cwd=cls,
        )
        assert result.returncode == 0

        entry = read_yaml(cls / ".class.yaml")["manifest"][0]
        assert entry["order"] == 3
        # Other fields unchanged
        assert entry["enabled"] is True
        assert entry["period_format"] == "monthly"
        assert entry["anchor"] == "first_monday"

    def test_update_enabled(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=self._manifest_with_task())

        result = run_script(
            SCRIPT,
            ["update-task", "monthly-bank-fees", "--no-enabled"],
            cwd=cls,
        )
        assert result.returncode == 0

        entry = read_yaml(cls / ".class.yaml")["manifest"][0]
        assert entry["enabled"] is False

    def test_update_period_format(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=self._manifest_with_task())

        result = run_script(
            SCRIPT,
            ["update-task", "monthly-bank-fees", "--period-format", "weekly"],
            cwd=cls,
        )
        assert result.returncode == 0

        entry = read_yaml(cls / ".class.yaml")["manifest"][0]
        assert entry["period_format"] == "weekly"

    def test_update_anchor(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=self._manifest_with_task())

        result = run_script(
            SCRIPT,
            ["update-task", "monthly-bank-fees", "--anchor", "last_friday"],
            cwd=cls,
        )
        assert result.returncode == 0

        entry = read_yaml(cls / ".class.yaml")["manifest"][0]
        assert entry["anchor"] == "last_friday"

    def test_update_multiple_fields(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=self._manifest_with_task())

        result = run_script(
            SCRIPT,
            ["update-task", "monthly-bank-fees",
             "--order", "5", "--no-enabled", "--period-format", "quarterly", "--anchor", "last_thursday"],
            cwd=cls,
        )
        assert result.returncode == 0

        entry = read_yaml(cls / ".class.yaml")["manifest"][0]
        assert entry["order"] == 5
        assert entry["enabled"] is False
        assert entry["period_format"] == "quarterly"
        assert entry["anchor"] == "last_thursday"

    def test_exit_1_task_not_in_manifest(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[])

        result = run_script(
            SCRIPT,
            ["update-task", "nonexistent", "--order", "1"],
            cwd=cls,
        )
        assert result.returncode == 1
        assert "not in manifest" in result.stderr.lower()

    def test_exit_1_no_fields_provided(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=self._manifest_with_task())

        result = run_script(
            SCRIPT,
            ["update-task", "monthly-bank-fees"],
            cwd=cls,
        )
        assert result.returncode == 1
        assert "no fields" in result.stderr.lower()

    def test_exit_1_invalid_period_format(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=self._manifest_with_task())

        result = run_script(
            SCRIPT,
            ["update-task", "monthly-bank-fees", "--period-format", "biweekly"],
            cwd=cls,
        )
        assert result.returncode == 1

    def test_exit_1_invalid_anchor(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=self._manifest_with_task())

        result = run_script(
            SCRIPT,
            ["update-task", "monthly-bank-fees", "--anchor", "second_monday"],
            cwd=cls,
        )
        assert result.returncode == 1

    def test_exit_1_nonpositive_order(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=self._manifest_with_task())

        result = run_script(
            SCRIPT,
            ["update-task", "monthly-bank-fees", "--order", "0"],
            cwd=cls,
        )
        assert result.returncode == 1


# ===========================================================================
# remove-task
# ===========================================================================


class TestRemoveTask:
    """remove-task subcommand."""

    def test_happy_path_removes_task(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[
            {"task": "monthly-bank-fees", "order": 1, "enabled": True,
             "period_format": "monthly", "anchor": "first_monday"},
        ])

        result = run_script(SCRIPT, ["remove-task", "monthly-bank-fees"], cwd=cls)
        assert result.returncode == 0

        data = read_yaml(cls / ".class.yaml")
        assert len(data["manifest"]) == 0

    def test_exit_1_task_not_in_manifest(self, tmp_path):
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury", manifest=[])

        result = run_script(SCRIPT, ["remove-task", "nonexistent"], cwd=cls)
        assert result.returncode == 1
        assert "not in manifest" in result.stderr.lower()


# ===========================================================================
# Edge cases
# ===========================================================================


class TestEdgeCases:
    """Edge cases: corrupt YAML, missing manifest."""

    def test_corrupt_yaml_exit_2(self, tmp_path):
        (tmp_path / ".class.yaml").write_text("not: valid: yaml: [[[")

        result = run_script(SCRIPT, ["set-description", "test"], cwd=tmp_path)
        assert result.returncode == 2

    def test_missing_manifest_key_exit_2(self, tmp_path):
        (tmp_path / ".class.yaml").write_text("schema_version: 1\nname: Test\n")

        result = run_script(SCRIPT, ["set-description", "test"], cwd=tmp_path)
        assert result.returncode == 2

    def test_manifest_not_a_list_exit_2(self, tmp_path):
        (tmp_path / ".class.yaml").write_text(
            "schema_version: 1\nname: Test\nmanifest: not-a-list\n"
        )

        result = run_script(SCRIPT, ["add-task", "foo", "--order", "1"], cwd=tmp_path)
        assert result.returncode == 2

    def test_no_traceback_on_corrupt_yaml(self, tmp_path):
        (tmp_path / ".class.yaml").write_text("{{invalid")

        result = run_script(SCRIPT, ["set-description", "test"], cwd=tmp_path)
        assert result.returncode == 2
        assert "Traceback" not in result.stderr
