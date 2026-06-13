# Ticket 00: Integration design — Cadence on pi-harness (source of truth)

**Status:** DESIGN. This ticket is the authoritative design for the integration; tickets 01–06
implement against it. Update it when a decision changes; don't let the implementation drift from it.
**Source of truth (external):** pi-harness `CLAUDE.md`, `spec/pi-skill-harness.md` (§4 driving Pi,
§7 image, §9 governance), `harness/project-config.ts`, `projects/README.md`.
**Source of truth (this repo):** `spec/02-architecture.md`, `spec/06-separation-of-concerns.md`,
`spec/skill-start.md`, `plugin/skills/start/SKILL.md`.

## Motivation

Cadence captures recurring professional procedures and re-runs them each period with a fresh agent.
Today it runs as a **Claude Code plugin on the user's Cowork filesystem** — unsandboxed, with no
formal compute isolation and no tamper-evident audit (see `notes/open-items.md` and
`spec/08-open-questions.md` item 7). pi-harness is the inverse: a proven **containment + audit +
least-privilege gate** substrate whose explicit bet is "a new project is a config row, not a fork."

Running Cadence inside pi-harness gives Cadence exactly what it lacks (kernel isolation, a bounded
writable mount, a per-run JSONL+manifest audit, an enforcing gate) and gives pi-harness a second
non-document, stateful proof of its generality bet.

## The decision and why

**Runtime: Pi-driven, general mode.** Cadence's hierarchy + 14 Python scripts are already
runtime-agnostic — pure Python + git, no Claude Code import (confirmed: scripts follow the exit-code
contract and are invoked via `Bash`). Only three things are Claude-Code-specific, and each has a
clean pi-harness equivalent:

| Claude Code mechanism (today) | What it does | pi-harness equivalent (this build) |
|---|---|---|
| Skills are **prompt injections** fired by `/start`, `/onboard`, … | Inject a procedure into the session | A **method-pin** + default task on a `project-config.ts` row (Ticket 03) |
| `${CLAUDE_PLUGIN_ROOT}/scripts/*.py` | Locate the gated scripts | Mount `plugin/` into the container; export `CADENCE_PLUGIN_ROOT` (Tickets 01, 02) |
| `.claude/settings.json` write-scope (`deny Write(../**)`, `Write(./status.yaml)`, `Write(./.class.yaml)`) | **Hard** boundary so the agent can't bypass the gated scripts | The pi-harness **gate in enforce mode** with a Cadence policy (Ticket 04) |

**Rejected alternatives** (recorded so we don't relitigate):

- *Claude Code hosted in the container.* Preserves Cadence's UX verbatim but means installing Claude
  Code in the image and re-pointing pi-harness's gate from Pi's `tool_call` hooks to Claude Code's
  `PreToolUse` hooks — substantially more work, and it changes pi-harness's core runtime assumption.
- *Substrate concepts only* (reuse the ideas, build a Cadence-native orchestrator). Most control,
  most new code, and it throws away the proven, tested session core for no milestone-1 benefit.

Pi-driven general mode is the least new code and aligns with where Cadence already says it is going
(`spec/02-architecture.md`: a future headless orchestrator that launches a sub-agent per task).

## Scope — milestone 1: autonomous `/start`

Prove this, governed, in the container:

```
./run --project cadence-start --work <engagement-root>   # + CADENCE_TASK=<class>/<task>
   → Pi reads root/AGENT.md → class/AGENT.md → task SKILL.md + learned.md + status.yaml
   → routes on status, runs start-setup.py, activates the venv, executes the task procedure
   → produces workpapers, sets review_ready (or blocked), makes exactly one git commit
   → gate (enforce) blocked every out-of-scope write; audit/manifest written to /runs
```

The autonomous run assumes the non-interactive happy path: the period is already set (by
`check-periods.py`), source data is already present in `periods/<period>/data/`, and no human prompt
is required. Any branch that *would* require a human in Cadence today (blocked-recovery menu, empty
period prompt, "ask the user to upload data") becomes **set `blocked` with a reason and stop** —
headless v1 has no human to ask. (Ticket 03 enumerates each.)

## Deliverable model (a real tension — resolve in milestone 1 as "git is the deliverable")

pi-harness `general` mode treats the **mounted `--work` folder as the deliverable** (changes persist
to the host); there is no single output doc, so `--task approve` reports "nothing to approve". Cadence
already has its own deliverable contract: **exactly one git commit per `/start` invocation** over the
engagement repo, which is the host-side `--work` mount.

For milestone 1 we accept **two complementary audit layers** and do **not** extend `approve`:

1. **Cadence's git commit** — the human-meaningful deliverable (the draft + status transition).
2. **pi-harness's `audit.jsonl` + `manifest.json`** (redirected to `/runs` via `AUDIT_ROOT` so they
   don't litter the engagement folder) — the tamper-evident record of every tool call and the gate's
   classification of each.

The Stage-B verifier (Ticket 05) cross-checks the two: the git commit happened, the status reached a
valid terminal-for-the-run state, and the audit shows no denied/out-of-scope writes. A
workspace/commit-aware `approve` is a **deferred** pi-harness enhancement, noted in `README.md`.

## Boundary / blast-radius notes (carry into every ticket)

- `--work` is a **host-writable mount** = the engagement git repo. Containment is still the container,
  but the blast radius is that folder. The gate (Ticket 04) is what keeps the agent inside the active
  task subtree.
- **Git runs in the container** against `/work`; commits land on the host. The container needs a git
  identity (`user.name`/`user.email`) — set it deterministically (Ticket 02/06), don't rely on host
  config leaking in.
- **The venv lives in the engagement** (`<root>/venv/`) and is built by `init-venv.py`/`install-deps.py`.
  Dependency install needs network egress, which is governed by the environment's network policy —
  flag as a milestone-1 risk for the fixture (Ticket 06): keep the fixture task's deps minimal/none.

## Non-goals (milestone 1)

- No interactive `/onboard` / `/done`, no `/status` dashboard, no multi-task orchestration.
- No change to Cadence's scripts' contracts or to pi-harness's gate *classifier engine* beyond adding
  a Cadence policy layer and running enforce mode (both already supported).
- No new pi-harness invocation mode; reuse `run-once` (general).
- Skills/scripts are used **as-is wherever possible** — mirror pi-harness's "ride the wave"
  discipline. Where a script genuinely can't run headless, parametrize (env var), never fork.

## Acceptance for the epic (= Ticket 06)

One live, governed run of autonomous `/start` over a committed fixture engagement, where the Stage-B
verifier passes and the audit confirms the gate blocked nothing legitimate and denied every
out-of-scope write. Until that single live run exists, this epic stays open (same discipline as
pi-harness's own open base-build ticket).
