# Ticket 06: End-to-end fixture + live-run acceptance (milestone-1 gate)

**Status:** TODO (revised 2026-06-13 after review)
**Repo:** cadence (fixture) + pi-harness (live run)
**Depends on:** 02, 02a, 03, 04, 05 (transitively 00–01)
**Source of truth:** all of `00`–`05`; cadence `tests/conftest.py`, `plugin/scripts/init-engagement.py`,
`init-task.py`, `spec/04-scaffolding.md`; pi-harness `harness/CLAUDE.md` (the "one live run" discipline +
environment-gating caveats), `src/fixtures/` (generator pattern).

## Goal

Close milestone 1: **one live, governed run** of autonomous `/start` over a committed fixture engagement
where the verifier passes and the audit proves the gate contained the run — plus a **deterministic
bad-seed** run proving the gate actually blocks.

## The fixture engagement (review-corrected)

Minimal, deterministic, **offline**, committed under e.g. `tests/fixtures/engagement-fixture/` (prefer a
**generator**, like pi-harness `src/fixtures/`). It must include **everything the init scripts produce**
(review found the inventory was incomplete):

- root: `.context-root`, `AGENT.md`, **`.claude/settings.json`**, **`.claude/tools/`**,
  **`requirements.txt` (empty)**, **`.gitignore`**, git-initialized with a clean base commit.
- class (`treasury/`): `.class.yaml`, `AGENT.md`, `.claude/settings.json`, `requirements.txt` (empty).
- task (`monthly-bank-fees/`): `SKILL.md`, `learned.md`, `status.yaml`, **`reference.md`**,
  **`.claude/settings.json`** (the real deny rules), `requirements.txt` (empty), `tools/<tool>.py`,
  `periods/<period>/data/` (seeded).

**Offline invariant (explicit):** *every* `requirements.txt` is empty so `install-deps.py` no-ops (it
only shells `pip` when requirements is non-empty — review-confirmed). A stray dep would hit PyPI and
hang/fail. The task tool is **pure stdlib** (e.g. sum a committed CSV into a balanced workpaper — it
need not be the real bank-fees logic).

**`.gitignore` collision (review BLOCKER):** `init-engagement.py` writes ignore rules for
`**/periods/*/data/` and `**/periods/*/workpapers/`. So seeded data won't be tracked and the produced
workpaper won't appear in the commit. **Resolve:** the fixture overrides those ignore rules (or seeds
data with `git add -f`), and acceptance treats the **workpaper as a working-tree artifact**, not a
committed file. Decide and document in the fixture.

Seed for the **happy path**: `status: not_started` (or `review_ready` to exercise the rejected-draft
re-run), `period` set (or left empty for a non-adhoc format to exercise period-computation), data present.

**Bad seed (deterministic — review correction):** an LLM may refuse a "write outside your dir"
*instruction*, so the negative case must be a **`tools/` script the SKILL.md tells the agent to run that
unconditionally writes outside `/work` entirely** (e.g. `/tmp/escape.txt` or `/etc/...`) — **not** one
level up but still inside `/work` (that currently classifies as record/allow until Ticket 04, and even
after, the reliable deny is an escape from `/work`). This makes the deny deterministic and tied to the
gate, not model judgment.

## Work items

- [x] **Build the fixture engagement (or generator) + commit; document regeneration and the `.gitignore`
      override decision.** BUILT (2026-06-21): generator at `tests/fixtures/generate_fixture.py`
      (mirrors pi-harness `src/fixtures/`) + `tests/fixtures/README.md`. It drives the REAL init scripts
      (`init-engagement.py` -> `init-class.py` -> `init-task.py`, then the period tree + customisation),
      so it cannot drift from production scaffolding. GOOD seed (`--seed good`, plus `--period-unset` for
      the period-computation path) and BAD seed (`--seed bad`). The `.gitignore` collision is resolved by
      force-adding the seeded CSV (`git add -f`) and treating the workpaper as a working-tree artifact
      (documented in the generator docstring + README).
- [x] **Host pre-flight** (no billed run) — the cadence-side items:
      - [x] cadence `python -m pytest tests/` green: **326 passed, 1 failed** — the single failure is the
        pre-existing date-sensitive `test_e2e_period_reset.py::...test_done_then_check_periods_resets`
        (unrelated to this ticket); everything else (incl. the 11 new fixture tests) passes.
      - [x] **offline dry-run `start-setup.py` over the GOOD fixture on the host**
        (`test_e2e_fixture.py::test_start_setup_offline_dry_run`): asserts exit 0, status -> `in_progress`,
        context loads, and NO pip/network (empty requirements => `install-deps.py` no-op). Plus a direct
        `install-deps` no-op assertion and an end-to-end task-tool run producing the balanced workpaper
        (`total: 50.00`). This is the regression catch before any billed run.
      - [ ] pi-harness typecheck (CI list) + `npm test` green (incl. 02/02a/04/05 additions) — pi-harness
        repo, not done in this cadence-fixture change.
      - [ ] `docker`-argv stub for `--project cadence-start` (mounts, env, `cwd=/work/<task>`,
        `GATE_MODE=enforce`, `AUDIT_ROOT=/runs`) — pi-harness repo.
- [ ] **Live run** — BLOCKED in this sandbox (no Docker-registry egress + no key); follows the
      pi-harness "one live run" discipline. Exact 2-command checklist once a Docker host + key are
      available (run from pi-harness `harness/`; `<fixture>` = a freshly generated GOOD fixture, `<cadence>`
      = a clone of this repo):
      ```bash
      # 0) generate a fresh GOOD fixture engagement (offline):
      python <cadence>/tests/fixtures/generate_fixture.py /tmp/fx-good --seed good
      # 1) autonomous /start (one billed run; never 2>&1):
      ./run --project cadence-start --cadence-root <cadence> \
            --cadence-task treasury/monthly-bank-fees --work /tmp/fx-good
      # 2) verify the result (Stage B):
      ./run --project cadence-start --task verify --work /tmp/fx-good
      ```
      Bad-seed deny run: regenerate with `--seed bad` into `/tmp/fx-bad` and repeat step 1; the gate
      must emit a `deny` entry (`write.outside-task-scope`) in `audit.jsonl`, leave the engagement
      unmodified/uncommitted, and the verifier (step 2) must exit non-zero.
- [ ] **Capture evidence:** the git commit on the host (assert **exactly one**, message
      `[start] monthly-bank-fees <period>: …`); `status.yaml` = `review_ready` with `issues: []`; the
      workpaper (working-tree); `/runs/audit/<run_id>/{audit.jsonl,manifest.json}`; **absence of any
      pip/network tool call in the audit** (positive offline proof); verifier exit `0`.
- [ ] **Bad-seed run:** confirm the gate **denies** the escape (a `deny` entry in `audit.jsonl`, the
      enforce block fired), the engagement is **left uncommitted/unmodified** for the escape, and the
      verifier exits non-zero.
- [ ] Write up both as a dry-run note under `notes/dry-runs/`; flip `00`/`README.md` to "milestone 1 done".

## Acceptance (the milestone)

- Green live run: `review_ready`, exactly one correctly-messaged commit, workpaper present, no
  pip/network in the audit, verifier `0`, audit+manifest written.
- Red live run: gate enforce **blocked** the out-of-`/work` escape (in the audit), no partial state
  committed, verifier non-zero.
- Both written up in `notes/dry-runs/`.

## Notes / risks

- **Unbuilt prerequisites:** `--project cadence-start` / `--cadence-root` / `--cadence-task` don't exist
  until Tickets 02/02a — this ticket strictly follows them.
- **Environment gating:** like pi-harness's base-build ticket, the live run may be blocked by no
  registry egress + no key. If so, complete every host-verifiable item, record the exact commands here,
  and keep the ticket open — don't claim the milestone on host checks alone.
- Never `2>&1` a live run; run it once (billed).
