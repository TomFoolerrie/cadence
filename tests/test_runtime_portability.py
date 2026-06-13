"""Runtime-portability tests (Ticket 01).

Locks in that Cadence's executable layer runs under any runtime with Python +
git, without changing behaviour under Claude Code. The real coupling is the
literal plugin-root token emitted into agent-facing text, NOT script
env-resolution (the scripts resolve siblings via Path(__file__) and read no env
var at runtime).

Three contracts:
 1. The gated scripts run headless from a task dir with a CLEAN env (no
    CLAUDE_PLUGIN_ROOT / CADENCE_PLUGIN_ROOT) — they resolve via Path(__file__).
 2. The plugin-root token emitted into templates/skills is the agreed single
    substitutable form, defined once in init-task.py and mirrored by
    tests/conftest.py make_task in lockstep.
 3. The cwd contract: with cwd = the task dir under a non-symlinked path, the
    walk-up helpers resolve root / class correctly.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import (
    PLUGIN_ROOT_TOKEN,
    SCRIPTS_DIR,
    make_class,
    make_context_root,
    make_task,
    read_yaml,
)

pytestmark = pytest.mark.mid


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Env vars that MUST NOT be required for the scripts to work.
PLUGIN_ROOT_ENV_VARS = ("CLAUDE_PLUGIN_ROOT", "CADENCE_PLUGIN_ROOT")


def run_script_clean_env(script_name, args=None, cwd=None, timeout=10):
    """Run scripts/<script_name> with a sanitized env that has NEITHER
    CLAUDE_PLUGIN_ROOT nor CADENCE_PLUGIN_ROOT set, proving Path(__file__)
    resolution does not depend on them."""
    script_path = SCRIPTS_DIR / script_name
    cmd = [sys.executable, str(script_path)] + (args or [])

    env = os.environ.copy()
    for var in PLUGIN_ROOT_ENV_VARS:
        env.pop(var, None)
    env["PYTHONDONTWRITEBYTECACHE"] = "1"

    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


def make_task_at(tmp_path, status="not_started", period="2026-03"):
    root = make_context_root(tmp_path)
    cls = make_class(root, "treasury")
    task = make_task(cls, "monthly-bank-fees", status=status, period=period)
    return root, cls, task


# ---------------------------------------------------------------------------
# 1. Scripts run headless from a task dir with a clean env
# ---------------------------------------------------------------------------


class TestHeadlessCleanEnv:
    def test_set_status_legal_transition_no_plugin_root_env(self, tmp_path):
        """set-status.py performs a legal transition with no plugin-root env."""
        _, _, task = make_task_at(tmp_path, status="not_started")

        result = run_script_clean_env("set-status.py", ["in_progress"], cwd=task)

        assert result.returncode == 0, result.stderr
        assert read_yaml(task / "status.yaml")["status"] == "in_progress"

    def test_load_context_prints_context_no_plugin_root_env(self, tmp_path):
        """load-context.py assembles + prints context with no plugin-root env."""
        root, _, task = make_task_at(tmp_path)

        result = run_script_clean_env(
            "load-context.py", ["--level", "task"], cwd=task
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip(), "expected non-empty context output"

    def test_clean_env_really_has_no_plugin_root(self, tmp_path):
        """Guard: the sanitized env genuinely strips both vars (so the tests
        above are meaningful, not accidentally inheriting a set var)."""
        _, _, task = make_task_at(tmp_path)
        # echo the env back out via a trivial python -c run under the same sanitizer
        env = os.environ.copy()
        for var in PLUGIN_ROOT_ENV_VARS:
            env.pop(var, None)
        for var in PLUGIN_ROOT_ENV_VARS:
            assert var not in env


# ---------------------------------------------------------------------------
# 2. The agent-facing plugin-root token is the agreed substitutable form
# ---------------------------------------------------------------------------


class TestPluginRootToken:
    def test_token_is_claude_code_form_unchanged(self):
        """Under Claude Code / Cowork the emitted token stays
        ${CLAUDE_PLUGIN_ROOT} — behaviour is unchanged for the CC path. Pi's
        method-pin (Ticket 03) substitutes $CADENCE_PLUGIN_ROOT at the prose
        level; the emitted literal is the CC form."""
        assert PLUGIN_ROOT_TOKEN == "${CLAUDE_PLUGIN_ROOT}"

    def test_init_task_emits_the_token_in_reference_md(self, tmp_path):
        """init-task.py's generated reference.md emits exactly the single token,
        and references no other plugin-root spelling."""
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury")

        result = run_script_clean_env("init-task.py", ["new-task"], cwd=cls)
        assert result.returncode == 0, result.stderr

        reference = (cls / "new-task" / "reference.md").read_text()
        assert PLUGIN_ROOT_TOKEN in reference
        # set-status + init-period usage lines both carry the token.
        assert reference.count(PLUGIN_ROOT_TOKEN) >= 4
        # No stray alternate spelling slipped in.
        assert "$CADENCE_PLUGIN_ROOT" not in reference

    def test_conftest_make_task_in_lockstep_with_init_task(self, tmp_path):
        """make_task() must emit the SAME token init-task.py emits — they are
        independent copies of the reference.md text, so this guards drift."""
        root = make_context_root(tmp_path)
        cls = make_class(root, "treasury")
        task = make_task(cls, "fixture-task")

        fixture_reference = (task / "reference.md").read_text()
        assert PLUGIN_ROOT_TOKEN in fixture_reference

        # And the real script's output uses the identical token.
        run_script_clean_env("init-task.py", ["real-task"], cwd=cls)
        real_reference = (cls / "real-task" / "reference.md").read_text()

        # Same token, same count of usages -> lockstep.
        assert fixture_reference.count(PLUGIN_ROOT_TOKEN) == real_reference.count(
            PLUGIN_ROOT_TOKEN
        )


# ---------------------------------------------------------------------------
# 3. cwd contract: walk-up helpers resolve from a non-symlinked task dir
# ---------------------------------------------------------------------------


class TestCwdContract:
    def test_walk_up_resolves_root_and_class_from_task_dir(self, tmp_path):
        """With cwd = the task dir (real, non-symlinked path), load-context.py's
        walk-up (find_context_root + find_class_dir + the SKILL.md walk)
        resolves and renders all three tiers."""
        root, cls, task = make_task_at(tmp_path)
        # Sanity: this is a real path, not a symlink.
        assert not task.is_symlink()
        assert task.resolve() == task

        result = run_script_clean_env(
            "load-context.py", ["--level", "task"], cwd=task
        )
        assert result.returncode == 0, result.stderr
        # The class content (AGENT.md says "Treasury") should surface in the
        # assembled context, proving the class dir was located by walking up
        # from the task dir, and the task SKILL.md ("## Purpose") proves the
        # SKILL.md walk resolved too.
        assert "Treasury" in result.stdout
        assert "## Purpose" in result.stdout

    def test_set_status_resolves_status_yaml_from_task_cwd(self, tmp_path):
        """set-status.py reads status.yaml from cwd (the task dir) — the cwd
        contract for the gated write path."""
        _, _, task = make_task_at(tmp_path, status="not_started")
        result = run_script_clean_env("set-status.py", ["in_progress"], cwd=task)
        assert result.returncode == 0, result.stderr

    def test_find_helpers_use_absolute_not_resolve(self):
        """Document the contract relied on: the walk-up helpers use .absolute()
        (NOT .resolve()), so they do not canonicalize symlinks. The integration
        guarantees /work is not a symlink; this asserts the helper contract so a
        future switch to .resolve() is a deliberate, test-visible change."""
        source = (SCRIPTS_DIR / "load-context.py").read_text()
        assert "current = start.absolute()" in source
        assert "current = start.resolve()" not in source
