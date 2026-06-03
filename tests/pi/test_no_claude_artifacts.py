"""
Pi-track scaffolding tests.

On `CADENCE_TRACK=pi` the init scripts emit NO `.claude/` directory at any level
— write-scope enforcement comes from the in-process tool_call gate instead (see
pi/extension/). The global-tools convention must still survive, now in the
track-neutral `root/tools/` (re-homed from `.claude/tools/`).

These cover the §5 parity rows: "CADENCE_TRACK=pi → no .claude/ dir" and
"global-tools loading works under both tracks".
"""

import pytest

from conftest import run_script


pytestmark = pytest.mark.mid


PI = {"CADENCE_TRACK": "pi"}


def _pi_engagement(tmp_path):
    """Scaffold a Pi-track engagement root (no .claude/) and return its path."""
    target = tmp_path / "acme"
    result = run_script("init-engagement.py", [str(target)], env=PI)
    assert result.returncode == 0, result.stderr
    return target


class TestNoClaudeArtifacts:
    """No .claude/ is emitted on the Pi track at root, class, or task level."""

    def test_engagement_root_has_no_claude(self, tmp_path):
        root = _pi_engagement(tmp_path)
        assert not (root / ".claude").exists()
        # The shared, track-neutral scaffold is still there.
        assert (root / ".context-root").is_file()
        assert (root / "AGENTS.md").is_file()

    def test_class_has_no_claude(self, tmp_path):
        root = _pi_engagement(tmp_path)
        assert run_script("init-class.py", ["treasury"], cwd=root, env=PI).returncode == 0
        class_dir = root / "treasury"
        assert class_dir.is_dir()
        assert not (class_dir / ".claude").exists()

    def test_task_has_no_claude(self, tmp_path):
        root = _pi_engagement(tmp_path)
        run_script("init-class.py", ["treasury"], cwd=root, env=PI)
        class_dir = root / "treasury"
        assert run_script("init-task.py", ["bank-fees"], cwd=class_dir, env=PI).returncode == 0
        task_dir = class_dir / "bank-fees"
        assert task_dir.is_dir()
        assert not (task_dir / ".claude").exists()


class TestGlobalToolsSurvive:
    """The global-tools dir is track-neutral root/tools/ — present without .claude."""

    def test_global_tools_dir_present_on_pi(self, tmp_path):
        root = _pi_engagement(tmp_path)
        assert (root / "tools").is_dir()
        assert not (root / ".claude").exists()

    def test_load_context_reads_global_tools_on_pi(self, tmp_path):
        root = _pi_engagement(tmp_path)
        run_script("init-class.py", ["treasury"], cwd=root, env=PI)
        class_dir = root / "treasury"
        run_script("init-task.py", ["bank-fees"], cwd=class_dir, env=PI)
        task_dir = class_dir / "bank-fees"

        # A global tool in the re-homed location must show up in context.
        (root / "tools" / "format.py").write_text("# global tool")

        result = run_script("load-context.py", ["--level", "task"], cwd=task_dir, env=PI)
        assert result.returncode == 0
        assert "format.py" in result.stdout
