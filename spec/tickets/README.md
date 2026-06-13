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

## Ticket index

| #  | Work order | Repo(s) | Depends on |
|----|-----------|---------|------------|
| 00 | Integration design (source of truth) | cadence | — |
| 01 | Runtime-portability decouple (un-pin from Claude Code) | cadence | 00 |
| 02 | pi-harness `cadence-start` preset + plugin mount | pi-harness | 00, 01 |
| 03 | `/start` procedure → Pi method-pin (autonomous happy path) | cadence | 01, 02 |
| 04 | Write-scope → gate enforce policy (**the load-bearing ticket**) | pi-harness | 02 |
| 05 | Stage-B verifier for a Cadence run (`verify-cadence.py`) | pi-harness + cadence | 02, 03 |
| 06 | End-to-end fixture + live-run acceptance | cadence + pi-harness | 03, 04, 05 |

## Dependency graph

```
00 ─┬─► 01 ─┬─► 03 ─┐
    │       │       ├─► 06  (milestone-1 gate: one live governed run)
    └─► 02 ─┼─► 04 ─┤
            └─► 05 ─┘
```

## Out of scope for milestone 1 (future tickets, not yet work-ordered)

- **Interactive `/onboard` + `/done`** inside the sandbox (needs human-in-the-loop over
  pi-harness `chat`/`serve`).
- **The multi-task orchestrator** (reading `.class.yaml` phases, launching a governed sub-run per
  task). pi-harness is single-session today; this is its own epic.
- **Workspace/commit-aware `approve`/promote** — pi-harness `approve` promotes a single output doc;
  a Cadence run's deliverable is a git commit over the whole engagement. See `00` §"Deliverable model".
