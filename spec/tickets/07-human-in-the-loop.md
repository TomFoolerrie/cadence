# Ticket 07: Human-in-the-loop — `/start` → review → `/done` over chat/serve (milestone 2)

**Status:** TODO (milestone 2 — depends on milestone 1 landing)
**Repo:** cadence (method-pin authoring + tests) + pi-harness (run-mode wiring)
**Depends on:** 03, 04, 05, 06 (milestone 1 must work headless first)
**Source of truth:** `plugin/skills/done/SKILL.md`, `spec/skill-done.md`, `spec/skill-start.md`,
`spec/03-status-machine.md`, `spec/06-separation-of-concerns.md`; pi-harness `run-chat.ts`,
`run-serve.ts`, `serve/`, `CLAUDE.md` (the "one run_id, one accumulating audit.jsonl per session" +
"drive serve headless" notes); `00-integration-design.md`.

## Motivation

`/done` must run **inline in the same instance** as the preceding `/start`/`/onboard` — it does not load
context independently; it captures the human's review of the draft, updates `learned.md`, proposes
`SKILL.md` changes for approval, sets `done`, and archives (`spec/skill-done.md`,
`plugin/skills/done/SKILL.md`). Milestone 1 (`run-once`, autonomous) structurally **cannot** do this:
the instance exits after `/start` and there is no human in the loop. The inline review→`/done` flow is
exactly what pi-harness's **multi-turn modes** (`chat`, `serve`) are for: one persistent Pi session,
one accumulating `audit.jsonl`, a human driving turns.

## Goal

Run the full **`/start` → human review → `/done`** cycle as a single governed pi-harness **chat (or
serve) session**: one `run_id`, one audit trail spanning both turns, the gate enforcing the same
Cadence write-scope, ending in `status: done` + the archive + exactly the commits Cadence's contract
specifies.

## Design

### Mode

Use pi-harness **chat** for the interactive human path (REPL, TTY) and/or **serve** for a front-end/API
path. Both keep **one session across turns with one accumulating audit** — the structural match for
"`/done` runs in the same conversation." A new `cadence` (vs `cadence-start`) project preset, or a
`--task chat`/`--task serve` over the existing row, selects multi-turn mode.

### One method-pin, two procedures, routed by the human turn

The pin (extends Ticket 03's) describes **both** behaviours and routes on the human's instruction:

- **Turn(s) for `/start`:** the Ticket 03 procedure — but the *interactive* branches that Ticket 03
  forced to "blocked + stop" (blocked-recovery menu, empty-period prompt, "provide source data") are
  now **re-enabled as questions to the human**, since there is one. Produce the draft, set
  `review_ready`, commit, and **wait** for the human's review (the next turn) rather than exiting.
- **Turn(s) for `/done`:** capture the verbal review feedback into `review-notes/`, update `learned.md`,
  **propose** `SKILL.md`/tool changes for the human's approval (don't apply unilaterally), `set-status.py
  done`, run `archive-period.py` (non-blocking stub today, per open-item #13), and commit.

`/done` relies on the `/start` turn's context being present — which it is, because it's the **same
persistent session**. Make the pin explicit about what's expected to carry over.

### The state-model wrinkle to resolve

Cadence today assumes a **fresh, stateless agent per `/start`** ("everything it needs is in the
folder"). The inline `/start`→`/done` flow instead *wants* in-session persistence so `/done` has the
`/start` context. These aren't in conflict — the on-disk files remain the source of truth (a crash mid-
session can still resume from disk) — but the pin must state the rule clearly: **disk is authoritative;
in-session memory is a convenience for the inline `/done`, not a second source of truth.** Decide and
document; add a test asserting `/done` re-reads `status.yaml`/`learned.md` from disk rather than trusting
session memory for state-machine decisions.

### Governance over a multi-turn session

- Gate stays **enforce** (Ticket 04) for every turn; the write-scope rules are unchanged.
- The pin adds `/done`'s protected-write expectations: `learned.md` and `review-notes/` are **in-scope**
  (task-dir writes — allowed); `status.yaml` still only via `set-status.py`; `SKILL.md` changes are
  *proposed*, applied only after the human's in-session approval.
- One `run_id` / one `audit.jsonl` spans `/start`+review+`/done` — the tamper-evident record of the
  whole cycle. Confirm the audit cleanly attributes turns.

## Work items

- [ ] Extend the method-pin (Ticket 03's source) with the `/done` procedure + the routing logic +
      the re-enabled interactive `/start` branches. Single source; freeze the new invariants in a test.
- [ ] Choose + wire the mode: a `cadence` multi-turn preset (or `--task chat`/`serve` on `cadence-start`)
      in `project-config.ts`. Confirm pi-harness's chat-needs-TTY / serve-binds-0.0.0.0 / launch-node-with-
      `--init`-not-npm gotchas are respected for a Cadence session.
- [ ] Resolve + document the disk-authoritative-vs-session-memory rule; add the `/done`-re-reads-disk test.
- [ ] Extend the verifier (Ticket 05) for the `/done` end-state: `status: done`, review-notes present,
      learned.md updated, archive attempted, commit messages match, audit spans the cycle with no denies.
- [ ] Headless drive recipe for CI/test (per pi-harness's "drive `-Task chat` by piping into `docker run
      -i`" and "drive serve headless" notes): script `/start` → a canned review → `/done` to stdin / over
      HTTP, ending in `/exit` so the audit flushes.

## Acceptance

- One governed multi-turn session over the Ticket 06 fixture: `/start` → (scripted) human review →
  `/done`, ending in `status: done`, archive attempted, the contract's commits, and a single
  `audit.jsonl` spanning both turns with zero denies and no out-of-scope writes.
- A negative case: `/done` makes its state decision from disk even when fed misleading session text.
- Verifier (extended) exits `0` on the good cycle, non-zero on a tampered one. Written up in
  `notes/dry-runs/`.

## Out of scope (still later)

- Interactive **`/onboard`** (the knowledge-transfer interview) — same chat/serve substrate, but its own
  ticket; it's the richest interactive flow and deserves dedicated scoping.
- The **multi-task orchestrator** (`.class.yaml` phases, a governed sub-run per task) — a separate epic;
  pi-harness is single-session today.
