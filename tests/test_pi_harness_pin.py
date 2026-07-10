"""
Cross-repo fixture test (Ticket 03, decision A).

The canonical autonomous /start method-pin lives in pi-harness's
`harness/project-config.ts` (CADENCE_START_METHOD_PIN) -- it cannot be imported
from this repo because project-config.ts is a pure, self-contained TS module.
This repo keeps a guard: read pi-harness's copy and assert it still encodes
Cadence's load-bearing /start invariants, so the two repos cannot silently drift.

The two repos are separate in CI, so this test SKIPS gracefully when pi-harness
is not present at the expected sibling path.
"""

import os
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.mid

# Candidate locations for the pi-harness checkout (env override first).
_CANDIDATES = [
    os.environ.get("PI_HARNESS_ROOT", ""),
    "/home/user/pi-harness",
    str(Path(__file__).resolve().parents[2] / "pi-harness"),
]


def _find_project_config() -> Path | None:
    for c in _CANDIDATES:
        if not c:
            continue
        p = Path(c) / "harness" / "project-config.ts"
        if p.exists():
            return p
    return None


@pytest.fixture(scope="module")
def pin_text() -> str:
    cfg = _find_project_config()
    if cfg is None:
        pytest.skip("pi-harness checkout not found; cross-repo pin fixture skipped")
    src = cfg.read_text(encoding="utf-8")
    m = re.search(r"const CADENCE_START_METHOD_PIN = \[(.*?)\]\.join", src, re.DOTALL)
    assert m, "CADENCE_START_METHOD_PIN array not found in project-config.ts"
    # Join the quoted string fragments into one body (good enough for substring checks).
    return "\n".join(re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(1)))


def test_pin_routes_status_through_set_status_py(pin_text):
    assert "set-status.py" in pin_text
    assert "status.yaml" in pin_text and ".class.yaml" in pin_text


def test_pin_respects_transition_legality(pin_text):
    # blocked is legal only from in_progress (set-status.py VALID_TRANSITIONS), so the
    # adhoc-empty-period block must route through in_progress first; never auto-emit abandoned.
    assert "in_progress" in pin_text
    assert re.search(r"blocked.*only.*in_progress", pin_text, re.IGNORECASE)
    assert re.search(r"never emit\s+`?abandoned", pin_text, re.IGNORECASE)


def test_pin_period_handling(pin_text):
    assert re.search(r"COMPUTE the prior period", pin_text, re.IGNORECASE)
    assert "adhoc" in pin_text


def test_pin_uses_absolute_venv_interpreter(pin_text):
    assert "/venv/bin/python" in pin_text
    assert ".context-root" in pin_text


def test_pin_reads_runtime_env(pin_text):
    assert "$CADENCE_PLUGIN_ROOT" in pin_text
    assert "$CADENCE_TASK" in pin_text


def test_pin_write_scope_and_commit_discipline(pin_text):
    assert "periods/<period>/data/" in pin_text
    assert "periods/<period>/workpapers/" in pin_text
    assert re.search(r"EXACTLY ONE commit", pin_text, re.IGNORECASE)
    assert "done" in pin_text and "abandoned" in pin_text
