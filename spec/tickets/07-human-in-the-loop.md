# Ticket 07: Human-in-the-loop — `/start` → review → `/done` over chat/serve (milestone 2)

**Status:** TODO (milestone 2 — after milestone 1; revised 2026-06-13 after review)
**Repo:** cadence (pin authoring + tests) + pi-harness (run-mode wiring)
**Depends on:** 03, 04, 05, 06
**Source of truth:** `plugin/skills/done/SKILL.md`, `spec/skill-done.md`, `spec/skill-start.md`,
`spec/03-status-machine.md`, `spec/06-separation-of-concerns.md`, `plugin/scripts/archive-period.py`
(stub — open-item #13); pi-harness `run-chat.ts`, `run-serve.ts`, `serve/`, `session-setup.ts`
(`SessionManager.inMemory()`, one `Audit(runId)` + single `flush()`), `gate/policy.ts`, `CLAUDE.md`;
`00`, `04`.

## Motivation

`/done` must run **inline in the same instance** as `/start` — it doesn't load context independently; it
captures the human's review, updates `learned.md`, *proposes* `SKILL.md` changes for approval, sets
`done`, archives. Milestone 1 (`run-once`, autonomous) can't: the instance exits and there's no human.
pi-harness's **chat/serve** modes are the fit — review **verified** they are one persistent
`createAgentSession` (`SessionManager.inMemory()`) with **one accumulating `audit.jsonl`** and a single
`flush()` on exit. So `/start`→review→`/done` maps to one governed multi-turn session, one `run_id`.

## Goal

Run `/start` → human review → `/done` as a single governed chat (or serve) session: one `run_id`, one
audit across turns, the same enforcing Cadence gate, ending in `status: done` + archive-attempted + the
contract's commits.

## What review changed (read before building)

1. **"Same conversation" is delivered by a *different substrate*.** In Cadence today, `/done` is a
   separate skill loaded by progressive disclosure in one CC conversation. Here there are no skill loads
   — **one method-pin holds both procedures** and the human types `/start`/`/done` as routing strings.
   This means the pin must **reproduce the full `/done` procedure** (all of `done/SKILL.md`) inline →
   real **drift risk** vs the skill file that is the spec's source of truth. Decide how to keep the pin
   and `done/SKILL.md` in sync (a shared-text fixture test, per Ticket 03's string-home choice).
2. **The enforced boundaries degrade to advisory unless Ticket 04's policy covers them.** pi-harness's
   stock gate is flat `/work` containment: a silent `SKILL.md` edit or a direct `status.yaml` edit is
   `record`/allowed. Cadence's "propose `SKILL.md` changes, don't apply" and "only `set-status.py` writes
   status" are **pin-advice only** unless Ticket 04's task-scoped policy (status.yaml/`.class.yaml`
   denial) is in force here too. **Run this session under the same Ticket-04 enforce policy**, and state
   plainly that `SKILL.md`-approval remains pin-advisory (the gate has no "propose vs apply" notion) —
   or scope a further policy rule if we want it enforced.
3. **`archive-period.py` always exits 2** (stub). `done/SKILL.md` treats archive failure as non-blocking
   (status stays `done`). So acceptance must assert the **failure path** (status `done`, failure
   reported) — **not** a "Captured. Ready for the next task" success string that can never appear today.
4. **Disk authoritative, session memory convenience** — sound and already what the skills do
   (`done/SKILL.md` Step 1 re-reads `status.yaml`). Keep it; the test must actively inject misleading
   *session* text and confirm `/done` still decides from disk.
5. **Routing is model-judgment, and `/start`'s re-enabled questions complicate it.** With the
   interactive `/start` branches back on (the human answers period/blocked prompts), the pin must
   disambiguate "a `/start`-clarification answer" from "a `/done` invocation." Headless test drives feed
   stdin **in strict order** (`run-chat.ts` consumes lines sequentially) — an unanticipated model
   question **desyncs** the whole scripted conversation. Design the canned drive defensively.

## Design

- **Mode:** chat (interactive/TTY) and/or serve (front-end/API). A new `cadence` multi-turn preset or
  `--task chat`/`serve` over the row. Respect pi-harness's chat-needs-TTY / serve-binds-`0.0.0.0` /
  launch-`node --init`-not-npm gotchas.
- **One pin, two procedures, routed by the human turn:** the Ticket-03 `/start` procedure (with the
  interactive branches **re-enabled as questions**, since a human is present) + the full `/done`
  procedure. `/start` produces the draft, sets `review_ready`, commits, and **waits** for the next turn.
- **`/done` turn:** capture review → `review-notes/`, update `learned.md`, **propose** `SKILL.md`/tool
  changes (apply only on in-session approval — pin-advisory, see #2), `set-status.py done`,
  `archive-period.py` (failure-path expected), commit.
- **Disk authoritative** (#4): on-disk files are the source of truth; in-session memory is convenience.

## Work items

- [ ] Extend the pin (Ticket 03's source) with the full `/done` procedure + routing + re-enabled
      `/start` questions; freeze the new invariants and a **pin↔`done/SKILL.md` sync test** (#1).
- [ ] Wire the mode (`cadence` multi-turn preset or `--task chat`/`serve`); honor the chat/serve gotchas.
- [ ] Run under Ticket-04 enforce policy; **document that `SKILL.md`-approval and status-protection are
      pin-advisory** under the current gate, or scope the extra rule (#2).
- [ ] Add the disk-authoritative test (`/done` decides from disk despite misleading session text) (#4).
- [ ] Extend the verifier (Ticket 05) for the `/done` end-state: `status: done`, review-notes present,
      `learned.md` updated, **archive attempted with failure tolerated**, commit messages match, audit
      spans the cycle with no denies/out-of-task writes.
- [ ] Defensive headless drive (#5): script `/start` → canned review → `/done` → `/exit`; handle the
      model asking an unplanned question without desyncing (e.g. tolerant/keyed input, or a serve driver
      that reads each turn's events before sending the next).
- [ ] **Confirm the Cadence command surface doesn't trip a `deny` in enforce** (`git`, `python3 script`,
      `archive-period.py`) via a dry-run against `policy.ts` before asserting "zero denies."

## Acceptance

- One governed multi-turn session over the Ticket-06 fixture: `/start` → scripted review → `/done` →
  `status: done`, archive **attempted (failure tolerated)**, contract commits, **one** `audit.jsonl`
  spanning both turns with zero denies and no out-of-task writes.
- Negative: `/done` decides state from disk even when fed misleading session text.
- Verifier (extended) `0` on the good cycle, non-zero on a tampered one. Written up in `notes/dry-runs/`.

## Out of scope (still later)

- Interactive **`/onboard`** (the richest interactive flow — its own ticket).
- The **multi-task orchestrator** (`.class.yaml` phases, a governed sub-run per task) — pi-harness is
  single-session today; separate epic.
