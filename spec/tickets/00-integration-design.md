# Ticket 00: Integration design — Cadence on pi-harness (source of truth)

**Status:** DESIGN (revised 2026-06-13 after ticket review). Authoritative design; tickets 01–07
implement against it. Update it when a decision changes.
**Source of truth (external):** pi-harness `CLAUDE.md`, `spec/pi-skill-harness.md` (§4 driving Pi,
§7 image, §9 governance), `harness/project-config.ts`, `harness/cli.ts`, `harness/gate/policy.ts`,
repo-root `projects/README.md`.
**Source of truth (this repo):** `spec/02-architecture.md`, `spec/06-separation-of-concerns.md`,
`spec/skill-start.md`, `plugin/skills/start/SKILL.md`, `notes/open-items.md` (esp. item 18).

## Motivation

Cadence captures recurring professional procedures and re-runs them each period with a fresh agent.
Today it runs as a **Claude Code plugin on the user's Cowork filesystem** — unsandboxed, no formal
compute isolation, no tamper-evident audit (`spec/08-open-questions.md` item 7). pi-harness is the
inverse: a proven **containment + audit + least-privilege gate** substrate. Running Cadence inside it
gives Cadence what it lacks and gives pi-harness a second non-document, stateful generality proof.

## The decision and why

**Runtime: Pi-driven, general mode.** Cadence's hierarchy + 14 Python scripts are pure Python + git +
stdlib (no Claude Code import — confirmed by review). The Claude-Code-specific surface and its
pi-harness equivalent:

| Claude Code mechanism (today) | What it does | pi-harness equivalent (this build) |
|---|---|---|
| Skills fired by `/start`, `/onboard`, … | Inject a procedure | A **method-pin** + default task on a `project-config.ts` row (Ticket 03) |
| `${CLAUDE_PLUGIN_ROOT}/scripts/*.py` **token in skill/template text** | Tells the agent where the scripts are | Mount `plugin/` ro; the pin tells the agent to use `$CADENCE_PLUGIN_ROOT` (Tickets 01, 02) |
| `.claude/settings.json` write-scope (`deny Write(../**)`, `Write(./status.yaml)`, `Write(./.class.yaml)`) | **Hard** boundary so the agent can't bypass the gated scripts | The pi-harness **gate in enforce mode** with a **net-new** Cadence policy layer (Ticket 04) |

> **Correction from review:** the scripts do **not** read `CLAUDE_PLUGIN_ROOT` at runtime — they
> resolve siblings via `Path(__file__)`. The coupling is the literal `${CLAUDE_PLUGIN_ROOT}` *token in
> agent-facing skill/template prose*, not script env-resolution. Ticket 01 is re-scoped accordingly.

**Rejected alternatives** (don't relitigate): *Claude Code in the container* (install CC, re-point the
gate to `PreToolUse` hooks — much more work, changes pi-harness's runtime assumption); *substrate
concepts only* (Cadence-native orchestrator — most new code, throws away the tested session core).

## Two hard truths surfaced by review (read before implementing)

1. **Cadence is the first project that breaks pi-harness's "a project is a config row, not a fork."**
   `ProjectConfig` is a closed interface with no field for an extra mount or extra env, the gate has
   **no sub-`/work` granularity**, and `run.ps1` never adopted `project-config.ts` resolution. So this
   integration genuinely requires entrypoint + policy *code*, not just a data row. **Ticket 02a** owns
   the minimal generic extension (`extraMounts`/`extraEnv` + a task-scoped cwd) so the breach is made
   *once*, reusably, instead of as Cadence-specific branches. **Scope to `cli.ts` only; defer `run.ps1`**
   (Cadence targets Linux/CI).

2. **Cadence's hard boundary degrades to advice unless the gate gains task-subtree scope.** pi-harness's
   gate today classifies *any* write inside `/work` as `record`/allow — a write one level above the task
   dir but still under `/work` is **not** denied. Cadence's reliability rests on `.claude/settings.json`
   making write-scope a *hard* boundary (the dry runs proved instructions alone fail). So Ticket 04 is
   not "turn on enforce mode" — it must **add real task-subtree + protected-file denial to `policy.ts`**
   and the gate must resolve paths against `cwd = /work/$CADENCE_TASK`. This is the security core of the
   whole integration; treat it as such.

## Scope — milestone 1: autonomous `/start`

```
./run --project cadence-start --cadence-root <cadence> --cadence-task <class>/<task> --work <engagement-root>
   → Pi (cwd = /work/<class>/<task>) reads root→class→task context, routes on status,
     runs $CADENCE_PLUGIN_ROOT/scripts/start-setup.py, uses the venv by ABSOLUTE path,
     executes the task procedure, produces workpapers, sets review_ready (or blocked),
     makes exactly one git commit
   → gate (enforce, task-scoped) denies every out-of-task write; audit/manifest land in /runs
```

Autonomous = non-interactive happy path: period already set (or computable for non-adhoc — see
Ticket 03), source data already in `data/`, no human prompt. Branches that *would* ask a human become
**set `blocked` + stop** — **except** `done`/`abandoned` routes, which make **no** commit and **no**
status write (review correction).

## Deliverable model (resolved: git is the deliverable)

General mode treats the `--work` folder as the deliverable; there's no single output doc, so
`--task approve` reports "nothing to approve" (correct — verified). Cadence's deliverable is **one git
commit** over the engagement (= the `--work` mount). Milestone 1 accepts **two complementary audit
layers** and does not extend `approve`:

1. **Cadence's git commit** — the human-meaningful deliverable.
2. **pi-harness `audit.jsonl` + `manifest.json`** (redirected to `/runs` via `AUDIT_ROOT`) — the
   tamper-evident tool-call record + the gate's per-call classification.

The verifier (Ticket 05) cross-checks them. A workspace/commit-aware `approve` is deferred.

> **Audit coverage caveat (review):** `audit.jsonl` records `file.path` only for the `edit`/`write`
> tools. Mutations done via `bash` (redirection, `cp`, a script) are **not** path-recorded. The gate
> still classifies the `bash` command, but the verifier's "no out-of-scope write" scan can only see
> `edit`/`write`. Ticket 04's enforce-mode denial is what actually contains `bash`-driven escapes.

## Dependency / environment notes (carry into every ticket)

- `--work` is a **host-writable mount** = the engagement git repo; the gate (Ticket 04) keeps the agent
  inside the active task subtree.
- **Git runs in the container** against `/work`; commits land on the host. The `base` image **does not
  ship git or pyyaml** (review) — Tickets 02/05 must add them. A deterministic git identity is required
  (Ticket 02), with a baked fallback because identity-via-pin depends on model compliance.
- **The venv** lives at `<root>/venv/`. Good news (review): `install-deps.py` **no-ops when
  `requirements.txt` is empty**, so an empty-deps fixture needs no network. Make **"all requirements.txt
  empty"** an explicit milestone-1 invariant (Ticket 06) — a stray dep silently reaches PyPI.
- **Pi's bash tool is non-persistent** (review): `source venv/bin/activate` does not survive to the next
  call. The pin must use the venv interpreter by absolute path (Ticket 03).

## Non-goals (milestone 1)

No interactive `/onboard`/`/done`, no `/status`, no multi-task orchestration. No new pi-harness
invocation mode (reuse `run-once`). Skills/scripts used as-is wherever possible — parametrize, never
fork. `run.ps1` support is out of scope.

## Acceptance for the epic (= Ticket 06)

One live, governed run of autonomous `/start` over a committed fixture engagement: verifier passes, the
audit confirms the gate denied every out-of-task escape and blocked nothing legitimate. Plus a
deterministic **bad-seed** run proving the gate actually blocks. Until that live run exists, the epic
stays open (pi-harness's own "one live run" discipline).
