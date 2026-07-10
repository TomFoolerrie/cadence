"""Ticket 06 — milestone-1 end-to-end fixture: generator + host pre-flight.

Two layers, both fully offline (no Docker, no model, no network):

1. Structural: run the generator into a tmp dir and assert the produced tree is
   well-formed — all expected files exist, git is initialized with a base commit,
   every requirements.txt is empty, the seeded data IS tracked despite .gitignore,
   status.yaml is seeded correctly, SKILL.md has Procedure + Completion Criteria.

2. Host offline dry-run: run start-setup.py over the GOOD fixture in this repo's
   interpreter and assert exit 0, status -> in_progress, context loads, and no
   pip/network occurred (empty requirements => install-deps no-op). Then exercise
   the pure-stdlib task tool directly and assert it produces the balanced
   workpaper. This is the pre-flight that catches a non-empty-requirements
   regression BEFORE any billed run. It does NOT simulate the agent/LLM.
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import SCRIPTS_DIR, read_yaml, run_script


def _load_generator():
    path = Path(__file__).resolve().parent / "fixtures" / "generate_fixture.py"
    spec = importlib.util.spec_from_file_location("generate_fixture", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GEN = _load_generator()
TASK_REL = f"{GEN.CLASS_NAME}/{GEN.TASK_NAME}"


def _git(args, cwd):
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True
    )


# ---------------------------------------------------------------------------
# Structural tests
# ---------------------------------------------------------------------------


@pytest.fixture
def good_fixture(tmp_path):
    target = tmp_path / "engagement"
    task_dir = GEN.generate(target, seed="good")
    return target, task_dir


@pytest.fixture
def bad_fixture(tmp_path):
    target = tmp_path / "engagement"
    task_dir = GEN.generate(target, seed="bad")
    return target, task_dir


def test_expected_tree_exists(good_fixture):
    root, task_dir = good_fixture
    # root-level scaffolding
    for rel in (
        ".context-root",
        "AGENT.md",
        ".claude/settings.json",
        ".claude/tools",
        "requirements.txt",
        ".gitignore",
    ):
        assert (root / rel).exists(), f"missing root/{rel}"
    # class scaffolding
    cls = root / GEN.CLASS_NAME
    for rel in (".class.yaml", "AGENT.md", ".claude/settings.json", "requirements.txt"):
        assert (cls / rel).exists(), f"missing class/{rel}"
    # task scaffolding
    for rel in (
        "SKILL.md",
        "learned.md",
        "status.yaml",
        "reference.md",
        ".claude/settings.json",
        "requirements.txt",
        "tools/summarize.py",
        f"periods/{GEN.DEFAULT_PERIOD}/data/{GEN.DATA_CSV_NAME}",
    ):
        assert (task_dir / rel).exists(), f"missing task/{rel}"


def test_git_initialized_with_base_commit(good_fixture):
    root, _ = good_fixture
    assert (root / ".git").is_dir()
    log = _git(["log", "--oneline"], root)
    assert log.returncode == 0
    lines = [l for l in log.stdout.splitlines() if l.strip()]
    # init-engagement makes the [init] commit; the generator adds a [fixture] commit.
    assert len(lines) >= 1
    assert any("[fixture] good seed" in l for l in lines)
    # working tree clean except the (gitignored) period artifacts
    status = _git(["status", "--porcelain"], root)
    assert status.stdout.strip() == "", f"unexpected dirty tree: {status.stdout!r}"


def test_all_requirements_empty(good_fixture):
    root, task_dir = good_fixture
    for req in (
        root / "requirements.txt",
        root / GEN.CLASS_NAME / "requirements.txt",
        task_dir / "requirements.txt",
    ):
        assert req.read_text().strip() == "", f"{req} is not empty (offline invariant)"


def test_seeded_data_is_tracked_despite_gitignore(good_fixture):
    root, _ = good_fixture
    # .gitignore must contain the data/ rule (proving the collision is real).
    assert "**/periods/*/data/" in (root / ".gitignore").read_text()
    tracked = _git(["ls-files"], root).stdout.splitlines()
    data_rel = f"{TASK_REL}/periods/{GEN.DEFAULT_PERIOD}/data/{GEN.DATA_CSV_NAME}"
    assert data_rel in tracked, "seeded data was not force-added into the commit"


def test_workpaper_not_committed(good_fixture):
    # The workpaper is a working-tree artifact, not a committed file.
    root, _ = good_fixture
    tracked = _git(["ls-files"], root).stdout
    assert GEN.WORKPAPER_NAME not in tracked


def test_no_host_venv_shipped(good_fixture):
    """Ticket 08 (a): the generator must NOT ship a host-built venv at the root
    (its interpreter symlinks point at the host Python and are unusable in the
    container)."""
    root, _ = good_fixture
    assert not (root / "venv").exists(), "fixture must not ship a host-built venv/"


def test_status_seeded_correctly(good_fixture):
    _, task_dir = good_fixture
    data = read_yaml(task_dir / "status.yaml")
    assert data["status"] == "not_started"
    assert data["period"] == GEN.DEFAULT_PERIOD
    assert data["issues"] == []
    assert data["done_at"] is None


def test_period_unset_variant(tmp_path):
    target = tmp_path / "engagement"
    task_dir = GEN.generate(target, seed="good", period_unset=True)
    data = read_yaml(task_dir / "status.yaml")
    assert data["status"] == "not_started"
    assert data["period"] == ""
    # the class manifest must carry a non-adhoc period_format for computation
    cdata = read_yaml(target / GEN.CLASS_NAME / ".class.yaml")
    entry = next(e for e in cdata["manifest"] if e["task"] == GEN.TASK_NAME)
    assert entry["period_format"] == "monthly"


def test_skill_md_has_procedure_and_completion(good_fixture):
    _, task_dir = good_fixture
    skill = (task_dir / "SKILL.md").read_text()
    assert "## Procedure" in skill
    assert "## Completion Criteria" in skill
    # Procedure names the task tool; Completion Criteria names the workpaper.
    assert "summarize.py" in skill
    assert GEN.WORKPAPER_NAME in skill


def test_bad_seed_shape(bad_fixture):
    root, task_dir = bad_fixture
    # escape tool exists and writes to a read-only rootfs path outside /work
    # unconditionally (deterministic OS-mount containment, model-independent).
    escape = task_dir / "tools" / "escape.py"
    assert escape.exists()
    assert "/etc/escape.txt" in escape.read_text()
    # SKILL.md tells the agent to run it.
    skill = (task_dir / "SKILL.md").read_text()
    assert "## Procedure" in skill
    assert "escape.py" in skill
    # no GOOD task tool present
    assert not (task_dir / "tools" / "summarize.py").exists()
    # still git-committed
    assert any("[fixture] bad seed" in l for l in _git(["log", "--oneline"], root).stdout.splitlines())


def test_bad_seed_skill_drives_write_tool_escape(bad_fixture):
    """Ticket 09 (c): the BAD SKILL Procedure must drive a write/edit-tool write to
    an out-of-/work path so the gate's `write.outside-task-scope` deny is
    deterministic and unambiguously the escape (not a venv-remediation write)."""
    _, task_dir = bad_fixture
    skill = (task_dir / "SKILL.md").read_text()
    # names the mediated write/edit tool (not just bash) ...
    assert "write" in skill.lower()
    assert "edit" in skill.lower()
    # ... targeting the out-of-/work path
    assert "/tmp/escape.txt" in skill
    assert "OUTSIDE" in skill
    # and it still cites the enforce-gate rule it is meant to trigger
    assert "write.outside-task-scope" in skill


# ---------------------------------------------------------------------------
# Host offline dry-run (pre-flight)
# ---------------------------------------------------------------------------


def test_install_deps_noops_on_empty_requirements(good_fixture):
    """Direct proof of the offline invariant: install-deps must NOT call pip."""
    _, task_dir = good_fixture
    # install-deps prints "Installing <req> ..." only when it shells pip.
    result = run_script("install-deps.py", [], cwd=task_dir)
    assert result.returncode == 0, result.stderr
    assert "Installing" not in result.stdout
    assert "pip install" not in (result.stdout + result.stderr)


def test_start_setup_offline_dry_run(good_fixture):
    """start-setup over the GOOD fixture: exit 0, in_progress, context loads, offline."""
    _, task_dir = good_fixture
    result = run_script("start-setup.py", [], cwd=task_dir, timeout=60)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    # status reached in_progress
    data = read_yaml(task_dir / "status.yaml")
    assert data["status"] == "in_progress"
    # context loaded (load-context prints the SKILL.md among the chain)
    assert "SKILL.md" in result.stdout
    assert "## Procedure" in result.stdout
    # offline proof: no pip install happened
    assert "Installing" not in result.stdout
    assert "pip install" not in (result.stdout + result.stderr)


def test_task_tool_produces_balanced_workpaper(good_fixture):
    """Exercise the pure-stdlib task tool directly (no agent/LLM)."""
    _, task_dir = good_fixture
    tool = task_dir / "tools" / "summarize.py"
    result = subprocess.run(
        [sys.executable, str(tool), GEN.DEFAULT_PERIOD],
        cwd=str(task_dir),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    wp = task_dir / "periods" / GEN.DEFAULT_PERIOD / "workpapers" / GEN.WORKPAPER_NAME
    assert wp.exists()
    content = wp.read_text()
    assert f"total: {GEN.EXPECTED_TOTAL}" in content
    assert "rows: 3" in content


def test_generate_rejects_existing_target(tmp_path):
    target = tmp_path / "engagement"
    GEN.generate(target, seed="good")
    with pytest.raises(RuntimeError):
        GEN.generate(target, seed="good")
