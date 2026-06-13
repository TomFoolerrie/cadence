# Tickets — Cadence on pi-harness

Work orders for running **Cadence inside the [pi-harness](https://github.com/tomfoolerrie/pi-harness)
sandbox**: a Pi agent in a Docker container, with a tamper-evident audit and an enforcing
least-privilege gate, executing a Cadence engagement as a governed, headless run.

**Read `00-integration-design.md` first** — it is the source of truth for the architecture decision,
the Claude-Code→pi-harness mapping, and the milestone plan. Every other ticket depends on it.

## Architecture decision (locked 2026-06-13)

- **Runtime: Pi-driven, general mode.** Cadence's hierarchy + scripts run under Pi via pi-harness
  `--kind general`. We do **not** install Claude Code in the container. The slash-command UX is
  replaced by a method-pin; `.claude/settings.json` write-scoping is replaced by the gate in
  **enforce mode**. (See `00` for the two rejected alternatives.)
- **First milestone: autonomous `/start`.** Prove one recurring period execution (route on status →
  run procedure → produce draft → `review_ready`) runs governed in the container. Interactive
  `/onboard`, `/done`, and the multi-task orchestrator are explicitly deferred.

> **Revised 2026-06-13 after a per-ticket review pass.** Review confirmed the core architecture but
> surfaced that **Cadence is the first project that breaks pi-harness's "a project is a config row, not
> a fork"** — it needs a generic entrypoint extension (**new Ticket 02a**) and **net-new gate policy**
> (Ticket 04), because the stock gate has no sub-`/work` granularity. Every ticket carries its
> review corrections inline. `run.ps1` is out of scope — Cadence is `cli.ts` (Linux/CI) only.

## Ticket index

| #   | Work order | Repo(s) | Depends on |
|-----|-----------|---------|------------|
| 00  | Integration design (source of truth) | cadence | — |
| 01  | Runtime-portability decouple (the coupling is template *text*, not script env) | cadence | 00 |
| 02a | **pi-harness foundational extension** — generic `extraMounts`/`extraEnv` + task-scoped cwd | pi-harness | 00 |
| 02  | pi-harness `cadence-start` preset (row + plugin mount + git in base) | pi-harness | 00, 01, 02a |
| 03  | `/start` procedure → Pi method-pin (autonomous happy path) | cadence | 01, 02, 02a |
| 04  | Write-scope → **net-new** gate task-subtree policy, enforce mode (**load-bearing**) | pi-harness | 02, 02a |
| 05  | Stage-B verifier (`verify-cadence.py`) + base-image git/pyyaml + pre-run baseline | pi-harness + cadence | 02, 02a, 03 |
| 06  | End-to-end fixture + live-run acceptance (**milestone-1 gate**) | cadence + pi-harness | 02, 02a, 03, 04, 05 |
| 07  | Human-in-the-loop `/start`→review→`/done` over chat/serve (**milestone 2**) | cadence + pi-harness | 03, 04, 05, 06 |

## Milestones

- **Milestone 1 — autonomous `/start`** (tickets 00–06): one headless, governed period execution via
  pi-harness `run-once`. No human in the loop.
- **Milestone 2 — human-in-the-loop** (ticket 07): `/start` → human review → `/done` as **one
  persistent chat/serve session** (one `run_id`, one accumulating audit). This is where inline `/done`
  lives — it inherently needs the review step, so it cannot run under milestone 1's `run-once`.

## Dependency graph

```
00 ─┬─► 01 ───────────► 03 ─┐
    ├─► 02a ─► 02 ─┬─► 04 ──┼─► 06  (milestone-1 gate: one live governed run) ─► 07  (milestone 2)
    │              └─► 05 ──┤
    └──────────────────────┘
```

**02a is the new critical-path foundation** — 02/03/04/05/06 all assume its generic mount/env/cwd seam.

## The three foundational findings (settle these first)

1. **Config-row promise breaks.** `ProjectConfig` can't carry an extra mount/env; the gate has no
   sub-`/work` scope; `run.ps1` never adopted the registry. → **02a** makes the breach once, generically
   (`extraMounts`/`extraEnv`/`cwdSubdirEnv`), `cli.ts`-only.
2. **cwd mismatch.** pi-harness runs the agent at `/work`; Cadence scripts walk up from the *task* dir.
   → forward **`cwd=/work/$CADENCE_TASK`** (02a) for both the session and the gate's path resolution.
3. **Hard boundary → advice.** Cadence's reliability needs a *hard* write-scope; the stock gate allows
   any write inside `/work`. → **04 adds real task-subtree + protected-file denial** to `policy.ts` and
   runs enforce mode. This is the security core of the integration, not a config flip.

## Out of scope for milestones 1–2 (future, not yet work-ordered)

- **Interactive `/onboard`** (the knowledge-transfer interview) — same chat/serve substrate as 07, but
  its own ticket; it's the richest interactive flow and deserves dedicated scoping.
- **The multi-task orchestrator** (reading `.class.yaml` phases, launching a governed sub-run per
  task). pi-harness is single-session today; this is its own epic.
- **Workspace/commit-aware `approve`/promote** — pi-harness `approve` promotes a single output doc;
  a Cadence run's deliverable is a git commit over the whole engagement. See `00` §"Deliverable model".
