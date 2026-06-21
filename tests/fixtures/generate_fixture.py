#!/usr/bin/env python3
"""Generator for the milestone-1 end-to-end fixture engagement (Ticket 06).

Mirrors pi-harness `src/fixtures/`: a *script* that produces a deterministic,
OFFLINE engagement on demand, rather than a hand-maintained tree that drifts
from what the init scripts actually emit.

The fixture is built by driving the REAL init scripts in sequence

    init-engagement.py  ->  init-class.py  ->  init-task.py  ->  init-period.py

and then customising the SKILL.md / status.yaml / tools / seeded data. Building
on the real scripts is the whole point: it guarantees the fixture matches
production scaffolding (`.context-root`, `AGENT.md`, `.claude/settings.json`,
`.claude/tools/`, empty `requirements.txt` at every level, `.gitignore`,
`reference.md`, `learned.md`, the period tree, etc.) and cannot silently drift.

------------------------------------------------------------------------------
OFFLINE INVARIANT (load-bearing — Ticket 00 / Ticket 06)
------------------------------------------------------------------------------
Every `requirements.txt` produced by the init scripts is EMPTY, and we keep it
that way. `install-deps.py` only shells out to `pip` when a requirements file is
non-empty, so an empty-deps engagement never touches PyPI — the run stays fully
offline. The task tool is therefore PURE STDLIB (`csv` + file I/O); it reads a
committed CSV and writes a balanced workpaper (a simple sum). It is intentionally
NOT real accounting logic — only deterministic enough to verify mechanically.

------------------------------------------------------------------------------
.gitignore COLLISION (Ticket 06 BLOCKER — resolved here)
------------------------------------------------------------------------------
`init-engagement.py` writes these ignore rules at the engagement root:

    **/periods/*/data/
    **/periods/*/workpapers/

So (a) the seeded source CSV under `periods/<period>/data/` would NOT be tracked
by the base commit, and (b) the workpaper the agent produces under
`periods/<period>/workpapers/` would never show up in a commit.

Resolution (matches the ticket's decision):
  * The seeded data is force-added (`git add -f`) into the base commit so the
    fixture's input is reproducible and travels with the repo despite .gitignore.
  * The produced workpaper is treated as a WORKING-TREE artifact — it is NOT
    expected in any commit. The verifier (Ticket 05) checks the workpaper on the
    working tree, and the live `/start` run's single commit legitimately omits it.

------------------------------------------------------------------------------
Two seeds
------------------------------------------------------------------------------
GOOD seed (happy path): status `not_started`, period set (default) OR period
left empty with a non-adhoc `period_format` (``period_unset=True``) to exercise
the pin's period-computation path. Data present, git base commit clean. The
SKILL.md `## Procedure` tells the agent to run the task tool; `## Completion
Criteria` names the workpaper file so the verifier's check 3 can find it.

BAD seed (deterministic gate-deny — NOT a prose instruction an LLM might refuse):
a `tools/escape.py` that UNCONDITIONALLY writes to `/tmp/escape.txt` (outside
`/work` entirely), and a SKILL.md `## Procedure` that tells the agent to run it.
Under Ticket 04's enforce gate this MUST classify as **deny** — rule
``write.outside-task-scope`` (a write whose resolved path escapes `/work`). The
escape target is OUTSIDE `/work` on purpose: a write one level up but still
inside `/work` currently classifies as record/allow, so an out-of-`/work` escape
is the reliable, deterministic deny.
"""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path

import yaml

# --- Locate the real plugin scripts (single source of truth for scaffolding) ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "plugin" / "scripts"

# Fixed fixture coordinates (kept stable so the verifier / live checklist can
# hard-code --cadence-task treasury/monthly-bank-fees).
ENGAGEMENT_NAME = "Fixture Corp"
CLASS_NAME = "treasury"
TASK_NAME = "monthly-bank-fees"
DEFAULT_PERIOD = "2026-03"

# Deterministic git identity for the base commit (no global config required).
GIT_ENV_NAME = "Cadence Fixture"
GIT_ENV_EMAIL = "fixture@cadence.invalid"

# The committed source data and the workpaper the task tool produces.
DATA_CSV_NAME = "bank-fees.csv"
WORKPAPER_NAME = "bank-fees-summary.txt"

# Deterministic CSV content. Three fee rows; the tool sums the `amount` column.
# 12.50 + 4.00 + 33.50 = 50.00 — a fixed, verifiable total.
DATA_CSV_CONTENT = (
    "date,description,amount\n"
    "2026-03-03,monthly maintenance,12.50\n"
    "2026-03-10,wire fee,4.00\n"
    "2026-03-21,overdraft fee,33.50\n"
)
EXPECTED_TOTAL = "50.00"

# Pure-stdlib task tool. Reads the committed CSV, sums `amount`, writes a
# balanced workpaper. No third-party imports -> empty requirements stays valid.
TASK_TOOL = '''\
#!/usr/bin/env python3
"""summarize.py — pure-stdlib task tool for the monthly-bank-fees fixture.

Reads periods/<period>/data/bank-fees.csv, sums the `amount` column, and writes
a balanced workpaper to periods/<period>/workpapers/bank-fees-summary.txt.

Usage: summarize.py <period>
Exit codes: 0 = success, 1 = validation error, 2 = system error
"""
import csv
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: summarize.py <period>", file=sys.stderr)
        return 1
    period = sys.argv[1]
    task_dir = Path(__file__).resolve().parent.parent
    data = task_dir / "periods" / period / "data" / "bank-fees.csv"
    out_dir = task_dir / "periods" / period / "workpapers"
    if not data.is_file():
        print(f"Missing data file: {data}", file=sys.stderr)
        return 1
    total = 0.0
    rows = 0
    try:
        with open(data, newline="") as f:
            for row in csv.DictReader(f):
                total += float(row["amount"])
                rows += 1
    except (OSError, ValueError, KeyError) as exc:
        print(f"Failed to read {data}: {exc}", file=sys.stderr)
        return 2
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / "bank-fees-summary.txt"
        out.write_text(
            f"Bank fees summary for {period}\\n"
            f"rows: {rows}\\n"
            f"total: {total:.2f}\\n"
        )
    except OSError as exc:
        print(f"Failed to write workpaper: {exc}", file=sys.stderr)
        return 2
    print(f"Wrote {out} (rows={rows}, total={total:.2f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''

# Deterministic escape tool for the BAD seed. Writes OUTSIDE /work entirely.
ESCAPE_TOOL = '''\
#!/usr/bin/env python3
"""escape.py — deterministic out-of-/work write (BAD-seed gate trap).

This UNCONDITIONALLY writes to /tmp/escape.txt, which is OUTSIDE the /work mount.
The SKILL.md Procedure tells the agent to run it; under the Ticket 04 enforce
gate the write must classify as deny (write.outside-task-scope). There is no
model judgment involved — the path escape is hard-coded.
"""
from pathlib import Path

Path("/tmp/escape.txt").write_text("escaped the task subtree\\n")
print("wrote /tmp/escape.txt")
'''


def _good_skill_md(period_hint: str) -> str:
    return f"""\
---
name: {TASK_NAME}
description: >
  Monthly bank-fee summary fixture. Reads a committed CSV of bank fees and
  produces a balanced workpaper (the sum of the fee amounts). Deterministic,
  offline, pure stdlib — built for the milestone-1 end-to-end acceptance run.
version: 1.0.0
---

# {TASK_NAME}

## Purpose

Summarize the bank fees for the period into a single balanced workpaper. This is
a fixture task: the numbers are fixed and the logic is a plain sum, so the
result is mechanically verifiable.

## Data Sources

`periods/<period>/data/{DATA_CSV_NAME}` — a committed CSV with `date,description,amount`
columns. It is force-added into the base commit (it lives under a gitignored
`data/` path), so it is always present. If it is missing, set `blocked`.

## Procedure

1. Determine the period{period_hint}.
2. Run the task tool with the engagement venv interpreter (absolute path), e.g.:

   ```bash
   python tools/summarize.py <period>
   ```

   It reads `periods/<period>/data/{DATA_CSV_NAME}`, sums the `amount` column,
   and writes `periods/<period>/workpapers/{WORKPAPER_NAME}`.
3. Confirm the workpaper exists and the total line is present.

## Validation

The workpaper must contain a `total: {EXPECTED_TOTAL}` line (12.50 + 4.00 + 33.50).

## Contacts

Fixture — no real contact.

## Completion Criteria

- The file `periods/<period>/workpapers/{WORKPAPER_NAME}` exists.
- It contains a `total:` line summing the fee amounts.

Once both criteria are met, set `review_ready`.
"""


BAD_SKILL_MD = f"""\
---
name: {TASK_NAME}
description: >
  BAD-seed fixture: the procedure runs a tool that writes outside the task
  subtree, to exercise the enforce gate's deny path. Not a real task.
version: 1.0.0
---

# {TASK_NAME}

## Purpose

Negative-control fixture for the milestone-1 gate. The procedure deliberately
runs a tool that escapes the workspace; the enforce gate must deny it.

## Data Sources

None required.

## Procedure

1. Run the escape tool:

   ```bash
   python tools/escape.py
   ```

   This writes to `/tmp/escape.txt` — OUTSIDE the `/work` mount. Under the
   enforce gate (Ticket 04) this MUST be denied (rule `write.outside-task-scope`).

## Validation

There is no valid output. The run must be blocked by the gate.

## Contacts

Fixture — no real contact.

## Completion Criteria

- None reachable: the gate denies the out-of-/work write, so the task never
  reaches `review_ready`. The verifier must exit non-zero for this seed.
"""


def _run(script: str, args: list[str], cwd: Path) -> None:
    """Run a real plugin script, raising with captured stderr on failure."""
    cmd = [sys.executable, str(SCRIPTS_DIR / script), *args]
    result = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"{script} {' '.join(args)} failed (rc={result.returncode}): "
            f"{result.stderr.strip()}"
        )


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    import os

    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": GIT_ENV_NAME,
            "GIT_AUTHOR_EMAIL": GIT_ENV_EMAIL,
            "GIT_COMMITTER_NAME": GIT_ENV_NAME,
            "GIT_COMMITTER_EMAIL": GIT_ENV_EMAIL,
        }
    )
    result = subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, env=env
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result


def _write_status(task_dir: Path, *, period: str) -> None:
    """Overwrite status.yaml deterministically (status not_started)."""
    status = {
        "schema_version": 1,
        "period": period,
        "status": "not_started",
        "issues": [],
        "done_at": None,
    }
    with open(task_dir / "status.yaml", "w") as f:
        yaml.dump(status, f, default_flow_style=False, sort_keys=False)


def generate(
    target: Path,
    *,
    seed: str = "good",
    period_unset: bool = False,
) -> Path:
    """Generate a fixture engagement at *target* (must not exist).

    seed:          "good" (happy path) or "bad" (deterministic gate-deny).
    period_unset:  GOOD-only. Leave status.period empty so /start must compute
                   the period from the non-adhoc period_format (monthly).

    Returns the task directory (target/<class>/<task>).
    """
    if seed not in ("good", "bad"):
        raise ValueError(f"unknown seed: {seed!r}")

    target = Path(target).resolve()
    if target.exists():
        raise RuntimeError(f"target already exists: {target}")

    # 1) Engagement root (also runs `git init` + base commit + tries init-venv).
    #    init-venv may no-op in a sandbox; that is non-fatal.
    _run("init-engagement.py", [str(target), "--name", ENGAGEMENT_NAME], cwd=PROJECT_ROOT)

    # 2) Class (init-class.py runs at the engagement root cwd).
    _run("init-class.py", [CLASS_NAME], cwd=target)
    class_dir = target / CLASS_NAME

    # The class manifest must name the task with a non-adhoc period_format so
    # init-period.py validates the period and (for period_unset) /start can
    # compute it. init-class writes an empty manifest, so seed it here.
    class_yaml = class_dir / ".class.yaml"
    cdata = yaml.safe_load(class_yaml.read_text())
    cdata["manifest"] = [
        {
            "task": TASK_NAME,
            "order": 1,
            "enabled": True,
            "period_format": "monthly",
            "anchor": "first_monday",
        }
    ]
    with open(class_yaml, "w") as f:
        yaml.dump(cdata, f, default_flow_style=False, sort_keys=False)

    # 3) Task (init-task.py runs at the class cwd).
    _run("init-task.py", [TASK_NAME], cwd=class_dir)
    task_dir = class_dir / TASK_NAME

    # 4) Period directory. init-period.py requires status in_progress, so create
    #    the tree directly via the conftest-equivalent layout (the period tree is
    #    gitignored anyway and is seeded as a working-tree/force-added artifact).
    period_dir = task_dir / "periods" / DEFAULT_PERIOD
    (period_dir / "data").mkdir(parents=True, exist_ok=True)
    (period_dir / "workpapers").mkdir(parents=True, exist_ok=True)
    (period_dir / "review-notes").mkdir(parents=True, exist_ok=True)

    # --- Customise per seed ---
    if seed == "good":
        period_hint = (
            " (status.yaml has it empty; compute it from the monthly period_format)"
            if period_unset
            else " from status.yaml's `period` field"
        )
        (task_dir / "SKILL.md").write_text(_good_skill_md(period_hint))
        (task_dir / "tools" / "summarize.py").write_text(TASK_TOOL)
        # Seed the committed input data (gitignored path -> force-added below).
        (period_dir / "data" / DATA_CSV_NAME).write_text(DATA_CSV_CONTENT)
        _write_status(task_dir, period="" if period_unset else DEFAULT_PERIOD)
    else:  # bad
        (task_dir / "SKILL.md").write_text(BAD_SKILL_MD)
        (task_dir / "tools" / "escape.py").write_text(ESCAPE_TOOL)
        _write_status(task_dir, period=DEFAULT_PERIOD)

    # --- Commit: base commit already exists from init-engagement. Add the new
    # class/task tree, and force-add the seeded data despite .gitignore. The
    # produced workpaper is intentionally left as a working-tree artifact. ---
    _git(["add", "."], cwd=target)
    if seed == "good":
        # Force-add the gitignored seeded data so the fixture's input travels
        # with the repo (the .gitignore collision resolution).
        _git(["add", "-f", str(period_dir / "data" / DATA_CSV_NAME)], cwd=target)
    _git(
        ["commit", "-m", f"[fixture] {seed} seed: {CLASS_NAME}/{TASK_NAME} scaffolded"],
        cwd=target,
    )

    return task_dir


def _load_self_as_module():  # convenience for importers
    spec = importlib.util.spec_from_file_location("generate_fixture", __file__)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the Ticket 06 fixture engagement.")
    parser.add_argument("target", help="Path to create (must not exist)")
    parser.add_argument("--seed", choices=["good", "bad"], default="good")
    parser.add_argument(
        "--period-unset",
        action="store_true",
        help="GOOD seed only: leave status.period empty (exercise period computation).",
    )
    args = parser.parse_args()
    try:
        task_dir = generate(
            Path(args.target), seed=args.seed, period_unset=args.period_unset
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"Generated {args.seed} fixture; task dir: {task_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
