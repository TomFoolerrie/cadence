"""
Claude-track write-scope enforcement tests.

These assert the harness-specific `.claude/settings.json` artifacts — the Claude
track's enforcement mechanism (the Pi track replaces them with the in-process
tool_call gate; see tests/pi/). Relocated here from the shared unit suite as part
of the two-track split, and extended to cover settings-gen.py directly and the
explicit `CADENCE_TRACK=claude` contract.
"""

import json

import pytest

from conftest import make_context_root, run_script


pytestmark = pytest.mark.mid


CLAUDE = {"CADENCE_TRACK": "claude"}


# ---------------------------------------------------------------------------
# settings.json emitted by the init scripts on the Claude track
# ---------------------------------------------------------------------------


class TestInitScriptsEmitSettings:
    """init-engagement/class/task emit the right per-level settings.json."""

    def test_root_settings_allow_only(self, tmp_path):
        target = tmp_path / "acme"
        assert run_script("init-engagement.py", [str(target)], env=CLAUDE).returncode == 0

        with open(target / ".claude" / "settings.json") as f:
            settings = json.load(f)
        assert settings == {"permissions": {"allow": ["Read", "Write(./**)"]}}
        assert "deny" not in settings["permissions"]

    def test_class_settings_deny_rules(self, tmp_path):
        root = make_context_root(tmp_path)
        assert run_script("init-class.py", ["treasury"], cwd=root, env=CLAUDE).returncode == 0

        with open(root / "treasury" / ".claude" / "settings.json") as f:
            settings = json.load(f)
        assert settings == {
            "permissions": {
                "allow": ["Read", "Write(./**)"],
                "deny": ["Write(../**)", "Write(./.class.yaml)"],
            }
        }

    def test_task_settings_deny_rules(self, tmp_path):
        root = make_context_root(tmp_path)
        run_script("init-class.py", ["treasury"], cwd=root, env=CLAUDE)
        class_dir = root / "treasury"
        assert run_script("init-task.py", ["bank-fees"], cwd=class_dir, env=CLAUDE).returncode == 0

        with open(class_dir / "bank-fees" / ".claude" / "settings.json") as f:
            settings = json.load(f)
        assert settings == {
            "permissions": {
                "allow": ["Read", "Write(./**)"],
                "deny": ["Write(../**)", "Write(./status.yaml)"],
            }
        }

    def test_default_track_is_claude(self, tmp_path):
        """Unset CADENCE_TRACK defaults to claude → settings.json still emitted."""
        root = make_context_root(tmp_path)
        # No env override at all.
        assert run_script("init-class.py", ["treasury"], cwd=root).returncode == 0
        assert (root / "treasury" / ".claude" / "settings.json").is_file()


# ---------------------------------------------------------------------------
# settings-gen.py directly
# ---------------------------------------------------------------------------


class TestSettingsGen:
    """settings-gen.py <dir> <level> writes the canonical block, idempotently."""

    @pytest.mark.parametrize("level,expected", [
        ("root", {"allow": ["Read", "Write(./**)"]}),
        ("class", {"allow": ["Read", "Write(./**)"],
                   "deny": ["Write(../**)", "Write(./.class.yaml)"]}),
        ("task", {"allow": ["Read", "Write(./**)"],
                  "deny": ["Write(../**)", "Write(./status.yaml)"]}),
    ])
    def test_per_level_content(self, tmp_path, level, expected):
        assert run_script("settings-gen.py", [str(tmp_path), level]).returncode == 0
        with open(tmp_path / ".claude" / "settings.json") as f:
            settings = json.load(f)
        assert settings == {"permissions": expected}

    def test_idempotent(self, tmp_path):
        first = run_script("settings-gen.py", [str(tmp_path), "task"])
        assert first.returncode == 0
        content1 = (tmp_path / ".claude" / "settings.json").read_text()

        second = run_script("settings-gen.py", [str(tmp_path), "task"])
        assert second.returncode == 0
        content2 = (tmp_path / ".claude" / "settings.json").read_text()

        assert content1 == content2

    def test_unknown_level_is_validation_error(self, tmp_path):
        result = run_script("settings-gen.py", [str(tmp_path), "bogus"])
        assert result.returncode != 0
        assert not (tmp_path / ".claude").exists()

    def test_missing_dir_is_validation_error(self, tmp_path):
        result = run_script("settings-gen.py", [str(tmp_path / "nope"), "root"])
        assert result.returncode == 1
