# Ticket 06: End-to-end fixture + live-run acceptance (milestone-1 gate)

**Status:** TODO
**Repo:** cadence (the fixture engagement) + pi-harness (the live run)
**Depends on:** 03, 04, 05 (and transitively 00–02)
**Source of truth:** all of `00`–`05`; pi-harness `CLAUDE.md` (the "one live run" discipline, the
headless serve/run notes), `tests/conftest.py` (cadence fixture conventions).

## Goal

Close the milestone: **one live, governed run** of autonomous `/start` over a committed fixture
engagement, inside the pi-harness container, where the Stage-B verifier passes and the audit proves the
gate contained the run. This is the epic's acceptance gate (Ticket 00 §Acceptance). Until it exists,
the integration stays open — the same discipline pi-harness applies to its own base-build ticket.

## Design — the fixture engagement

A **minimal, deterministic** engagement committed under e.g. `tests/fixtures/engagement-fixture/` (or a
generator that builds it, mirroring `src/fixtures/` in pi-harness — prefer a generator so the binary/
state isn't hand-maintained). It must be:

- A real engagement root: `.context-root`, root `AGENT.md`, one class (e.g. `treasury/`) with
  `.class.yaml` + `AGENT.md`, one task (e.g. `monthly-bank-fees/`) with `SKILL.md`, `learned.md`,
  `status.yaml`, and a `tools/` script.
- **Self-contained and offline.** The task's procedure must run with **no network and no third-party
  deps** (the milestone-1 risk from `00`): pre-place deterministic source data in
  `periods/<period>/data/`, and make the tool pure-stdlib Python so `install-deps.py` has nothing to
  fetch. (A trivially-deterministic task — e.g. sum a committed CSV into a balanced workpaper — is
  ideal; it doesn't need to be the real bank-fees logic.)
- Seeded so `/start` takes the **happy path**: `status: not_started` (or `review_ready` to exercise the
  rejected-draft re-run), `period` already set, data present. Git-initialized with a clean base commit.
- A **second, "bad" seed** (or a post-run tamper) to prove the verifier and gate *fail* correctly:
  e.g. a task whose procedure tries to write outside its dir (gate must deny + verifier must catch).

## Work items

- [ ] Build the fixture engagement (or its generator) + commit it. Document how to regenerate.
- [ ] **Pre-flight on the host** (no billed run), per pi-harness discipline:
      - pi-harness typecheck clean (CI list) and `npm test` green (incl. Tickets 02/04/05 additions);
      - cadence `python -m pytest tests/` green (incl. Ticket 01 additions);
      - the generated `docker` argv confirmed via a stub for `--project cadence-start` (mounts, env,
        `GATE_MODE=enforce`, `AUDIT_ROOT=/runs`).
- [ ] **The live run** (needs Docker + a model key + the network policy that allows the image pull):
      `./run --project cadence-start --work <fixture-engagement> --cadence-task treasury/monthly-bank-fees`
      then `./run --project cadence-start --task verify --work <same>`.
- [ ] Capture the evidence: the git commit on the host, `status.yaml` = `review_ready`, the workpaper,
      `/runs/audit/<run_id>/{audit.jsonl,manifest.json}`, and the verifier exit `0`.
- [ ] Run the **bad seed** and confirm: the gate **denies** the out-of-scope write (audit shows a
      `deny` entry, the enforce block actually fired) and the verifier exits non-zero.
- [ ] Write up the result as a dry-run note under `notes/dry-runs/` (matching Cadence's existing
      dry-run-findings convention) and flip `00`/`README.md` status to "milestone 1 done".

## Acceptance (the milestone)

- A green live run: autonomous `/start` over the fixture → `review_ready`, one commit, workpaper
  present, verifier exit `0`, audit + manifest written.
- A red live run on the bad seed: gate enforce **blocked** the over-reach (recorded in the audit),
  verifier exit non-zero — proving the boundary is real, not decorative.
- Both written up in `notes/dry-runs/`.

## Notes / risks

- **Environment gating.** Like pi-harness's open base-build ticket, the live run may be blocked in a
  given sandbox by (a) no Docker-registry egress for the image pull and (b) no API key. If so, complete
  every host-verifiable item, record the exact 2-command live checklist here, and keep the ticket open
  pending an environment with both — do not claim the milestone on host checks alone.
- Never pipe a live run through `2>&1` (pi-harness PowerShell gotcha); run it once (it's billed).
- For a headless `chat`/`serve` variant later, see pi-harness's "drive serve headless" notes — out of
  scope here; milestone 1 is `run-once`.
