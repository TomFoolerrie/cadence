# `.class.yaml` v2 — Planning Doc

**Status:** planning
**Date:** 2026-05-09
**Sibling to:** [`pi-migration-plan.md`](./pi-migration-plan.md). Orthogonal in implementation; shares Symphony as a downstream beneficiary.

This is a planning doc. A detailed spec follows once the shape is agreed.

---

## 1. Goals

1. **Richer dependency graph.** Replace coarse phase-based `order: N` with explicit `blocked_by:` edges per Linear's blocks/blocked-by model. Better parallelism, more accurate semantics.
2. **First-class cycle.** Hoist period cadence from per-task fields up to a class-level `cycle:` block — replaces today's per-task `period_format` and `anchor` sprawl.
3. **Stay disciplined.** Borrow *logic* from Linear, not its surface area. Keep Cadence's strict state machine, three-level hierarchy, and "folder is the memory" principles intact. Resist speculative metadata (priority, estimate, reviewer, labels) until a real downstream consumer demonstrates a need that the existing schema can't satisfy — and prefer specific typed fields over polymorphic tagging.

## 2. Schema v2

```yaml
# treasury/.class.yaml
schema_version: 2
name: Treasury
description: Cash management, banking relationships, and financing activities.

cycle:
  cadence: monthly                       # monthly | weekly | quarterly | adhoc
  rollover_anchor: first_business_day    # when the class period rolls forward (class-level only)

manifest:
  - task: monthly-bank-fees
    enabled: true

  - task: zba-entries
    enabled: true

  - task: bank-reconciliation
    enabled: true
    blocked_by:
      - monthly-bank-fees                # task gate (bare string)
      - zba-entries                      # task gate
      - { calendar: first_wednesday }    # calendar gate (dict)
```

**Two distinct gating concepts in v2.** v1's `anchor` played two roles (period rollover *and* within-period eligibility floor). v2 separates them:

1. *Period rollover* — `cycle.rollover_anchor` at the class level drives when the class period rolls forward. `check-periods.py` resets all class tasks to `not_started` when the next period's `rollover_anchor` passes. Class-level only — there is no per-task rollover anchor.
2. *Within-period eligibility* — folded entirely into `blocked_by` (see §3a). A task encodes "wait until day_25 in the current period" as `blocked_by: [{calendar: day_25}]`. No separate `anchor:` field on tasks.

This collapses the eligibility predicate to one polymorphic loop and removes the v1 awkwardness of one field doing two unrelated jobs.

**Calendar / anchor whitelist.** The anchor namespace is finite and shared between `cycle.rollover_anchor` and calendar gates inside `blocked_by`. Validated at write time by `init-task.py` and `edit-class-yaml.py`:

| Cadence | Anchor whitelist |
|---|---|
| `daily` | `business_day`, `every_day` |
| `weekly` | `monday` … `sunday`, `business_day` |
| `monthly` | `first_business_day`, `last_business_day`, `first_<weekday>`, `second_<weekday>`, `third_<weekday>`, `fourth_<weekday>`, `last_<weekday>`, `day_<N>` |
| `quarterly` | Same shape as monthly, scoped to quarter boundaries |
| `annual` | `<month>_<day>`, `<month>_first_<weekday>` |

Calendar gates inside `blocked_by` resolve against the consumer task's *current* period via `current_period_for(task)` (§3a). Time-of-day is intentionally out of scope (see §7) — it's a Symphony scheduler concern, not a schema concern.

**Class cadence is the floor of frequency.** A task may override `cadence:` to a *slower* rhythm than the class default (e.g., quarterly forecast in a monthly class) but never a faster one. The class cadence represents the shortest cycle any task in the class operates on. This keeps the cycle ledger (§3b) keyed cleanly to the class period and keeps `check-periods.py` driven solely by class-period boundaries. It's also a useful cohesion test — a task with a fundamentally faster rhythm belongs in a separate class (daily cash watch isn't a stowaway in monthly close).

`init-task.py` and `edit-class-yaml.py` validate this at write time, rejecting faster-than-class overrides with: *"task `<name>` cadence is more frequent than class cadence — split into a separate class."*

What disappears from v1:
- `order: N` — replaced by `blocked_by: [...]`. Tasks with no `blocked_by` are phase-1-equivalent.
- Per-task `period_format` — moves up to `cycle.cadence` (overridable per-task if truly heterogeneous, subject to the floor rule above).
- Per-task `anchor` field — eliminated. Calendar-keyed start floors fold into `blocked_by` as `{calendar: <name>}` entries. Class-level `cycle.anchor` is renamed `cycle.rollover_anchor` to make its single remaining role (period rollover) unambiguous.

## 3. Logic Borrowed from Linear (with Cadence Adaptations)

This is the section that matters. Schema is the easy part — the *behavior* derived from the schema is where Linear's design is load-bearing.

### 3a. Dependency-graph resolution (blocks / blocked_by)

**Linear:** Issues form a directed graph via `blocks` edges. An issue is *eligible* (can be picked up) iff all its blockers are in a terminal state (`Done` or `Cancelled`). Cycles are detected and rejected at write time.

**Cadence adaptation:**
- A new helper, `class-graph.py` (library + CLI), parses `.class.yaml`, validates the DAG (rejects cycles), and exposes `eligible_tasks(class_dir) -> [task_name]`. A task is eligible iff every entry in `blocked_by` is *satisfied* under a polymorphic predicate:
  - **Task gate** (bare string, e.g. `monthly-bank-fees`) — satisfied when that task's `status.yaml.status` is in `{done, abandoned}`.
  - **Calendar gate** (dict, e.g. `{calendar: first_wednesday}`) — satisfied when `today >= resolve_calendar(name, current_period_for(task))`. Calendar names come from the anchor whitelist (§2).

  v2 supports exactly these two gate types; the validator rejects any other shape. Cycles are rejected at write time. The `current_period_for(task)` helper threads through `class-rollup.py` and the cycle ledger writer (§3b); cross-cadence task gates are out of scope under V1 (a). Cross-class blockers are out of scope under V2.
- `/start` invoked at the class level uses this to know what to fire. Today the user picks a task by walking into its folder; tomorrow `/start` from the class dir auto-selects the next eligible one.
- Symphony reads the same function to drive its dispatch loop. (See `pi-migration-plan.md` §8 — the Symphony trigger bridge consumes both `check-periods.py` for "due" and `class-graph.py` for "eligible.")
- Lives in the top-level shared `scripts/` (the layout from `pi-migration-plan.md` §2), next to `check-periods.py` — both are "compute eligibility from filesystem state."

**What we don't borrow:** Linear's UI affordances around dependency visualization. That's `/status`'s job, and it can render the graph however we like.

### 3b. Cycle as a container

**Linear:** A cycle is a time-bounded container. Issues belong to cycles. When a cycle closes, incomplete issues optionally roll forward.

**Cadence adaptation:**
- The class-level `cycle:` block declares the rhythm once. Per-task `cadence:` overrides only when a task is genuinely slower than the class (subject to §2's floor rule); calendar-keyed start floors live in `blocked_by` (§3a), not in `cycle:`.
- `check-periods.py` writes a per-cycle **open/close ledger** at `<class>/cycles/<period>.yaml`. `opened_at` fires when the class period rolls forward (`cycle.rollover_anchor` for the new period passes); `closed_at` and terminal task statuses are written on the next roll-forward. This gives every cycle a clean historical record even though `status.yaml` files reset on roll-forward. Tasks with slower per-task `cadence:` overrides participate only in the cycles where their own period actually rolls.
- Start with a minimal payload — `{period, opened_at, closed_at, task_statuses}` — and grow it (estimates remaining, aggregated abandonment reasons, etc) as Symphony needs more.
- `cycles/` is script-written; agents must not edit it directly. The pi gate extension (`pi-migration-plan.md` §3a) denies writes there. The Claude track relies on settings.json scope rules.
- The ledger is what Symphony surfaces back to Linear (or the firm dashboard) as a parent-issue rollup.

**What we don't borrow:** Linear's auto-rollover-with-velocity logic. Cadence periods are deterministic (driven by anchors), not capacity-bound.

### 3c. Dispatch ordering

**Linear:** When several issues are simultaneously eligible, the cycle view orders by priority then estimate, with overrides via manual rank.

**Cadence adaptation:**
- `class-graph.py` returns eligible tasks in **manifest order** — the human-controllable, deterministic ordering. Reorder the manifest to change priority; no separate `priority:` field.
- For Symphony with concurrency caps (`max_concurrent_runs: 3`), this is the dispatch queue. Symphony can layer additional sort logic on top once it has signal worth using; v2 doesn't pre-emptively encode it.
- For interactive `/start` from a class dir, this is the "next thing to do" the skill suggests.

**What we don't borrow:** scheduler-aware metadata (`priority`, `estimate`, manual rank) for v2. The manifest is already an ordered list — reorder declaratively to re-rank, no drift between a `priority:` field and the order on disk. Promote individual fields back when Symphony demonstrates a concrete need that manifest order can't satisfy (see §7).

### 3d. Sub-issue rollup → class status

**Linear:** Parent issue state is *derived* from its sub-issues' states (% done, blocked count, etc).

**Cadence adaptation:**
- `/status` already does this — reads task `status.yaml` files and computes a class-level rollup on the fly. Formalize the logic into `class-rollup.py` (library function), used by `/status`, by the cycle ledger writer in §3b, and by Symphony when it updates a Linear parent issue.
- The rollup gains v2's new dimensions: % done and count blocked.

**What we don't borrow:** Storing the rollup. It's always computed, never persisted (except in cycle summaries — see §3b).

### 3e. Cancellation with reason

**Linear:** Issues can be `Cancelled` with a free-text reason captured in the activity log.

**Cadence adaptation:**
- `set-status.py` already supports `abandoned`. Extend `status.yaml` schema to include an optional `abandoned_reason:` string when transitioning to abandoned. Required, not optional — forces the human to articulate why.
- The cycle ledger in §3b surfaces abandoned reasons so they're visible at the firm/portfolio level.

**What we don't borrow:** Generic comment threads. `learned.md` and `review-notes/` already cover the use case.

### 3f. SLA-style escalation (deferred)

**Linear:** SLAs auto-bump priority as deadlines approach.

**Cadence adaptation:** *Defer.* Worth thinking about — "if a monthly close task is still `not_started` 5 days past anchor, flag it" — but this needs a separate "deadlines" feature design and isn't load-bearing for v2. Note in §6 as a future affordance.

### 3g. Data flow between tasks (net-new — Linear has no concept here)

The dependency graph (`blocked_by`) guarantees *temporal* readiness, but says nothing about *what file* a downstream task should read. v2 keeps data flow as filesystem convention rather than schema:

- A consuming task's `SKILL.md` prescribes the relative path: `read ../monthly-bank-fees/periods/<period>/workpapers/fees-summary.xlsx`.
- `blocked_by` guarantees the file exists by the time the consumer runs.
- Cross-class data flow uses a longer relative path: `../../reporting/balance-sheet-roll/periods/<period>/workpapers/...`. No new mechanism — same convention, scoped one directory level higher.
- **No `inputs:` or `outputs:` schema fields in v2.** Declarative I/O would invite drift between manifest and SKILL.md; the human reads SKILL.md anyway, so the path lives there.

This composes cleanly with the eligibility predicate (§3a): a task isn't surfaced as eligible until its blockers are `done`, which is exactly when the workpaper paths it'll read are guaranteed to exist.

### What we explicitly DO NOT borrow

| Linear primitive | Why we skip |
|---|---|
| Custom workflow states | Strict state machine is a Cadence *feature*; custom states defeat script-gating |
| Comment threads on issues | `learned.md` + `review-notes/` + git history cover this |
| Triage state | Conflicts with `not_started → in_progress → ...` rigor |
| Subtasks / subclasses (4th level) | Three levels (root → class → task) is load-bearing — keeps filesystem shallow, scope rules unambiguous, context inheritance flat, and skills attached to specific levels. Use multi-cycle for cadence variety within a class, or **separate classes** with class-class deps (v3) for genuine hierarchy |
| Workspace-level workflow customization | One opinionated workflow is the point |
| Manual rank within a cycle | Manifest order is the rank — declarative, no drift between a separate `priority:` field and the on-disk order |
| `priority`, `estimate`, `reviewer` fields | Speculative scheduler metadata for a Symphony that doesn't exist yet. Manifest order covers dispatch; reviewer routing belongs in Linear/GitHub. Promote when a real consumer demonstrates need (see §7) |

## 4. Migration from v1

Two-version coexistence is the cleanest path:

1. **Reader scripts handle both.** `init-class.py`, `load-context.py`, `set-status.py`, `check-periods.py`, `/status` all branch on `schema_version`. v1 keeps working until every engagement is upgraded.
2. **One-shot upgrade script.** `upgrade-class-yaml.py` converts v1 → v2 in place:
   - `order: 1` tasks get `blocked_by: []`.
   - `order: N>1` tasks get `blocked_by: [<every order: N-1 task as task gates>]` (preserves phase-equivalent semantics; user can refine to true edges later).
   - `period_format` hoists to `cycle.cadence` if uniform across the class; otherwise per-task `cadence:` overrides (subject to §2's floor rule — upgrade script raises if any task is faster than the inferred class cadence).
   - Class-level v1 `anchor` (if present) renames to `cycle.rollover_anchor`. Per-task v1 `anchor` becomes a calendar gate appended to that task's `blocked_by`: `{calendar: <name>}`. Per-task `anchor` field is removed.
   - Bumps `schema_version` to 2.
   - Idempotent — safe to re-run.
3. **Deprecation timeline.** v1 readers stay for two release cycles, then v1 throws an error and points at the upgrade script.

## 5. Migration Steps

Each step ends with all existing tests passing, plus new tests for the v2 surface area introduced in that step.

1. **Library refactor of read paths.** Promote rollup and eligibility logic out of `/status` and into `class-rollup.py` + `class-graph.py`. *Pure refactor — no schema change yet*; the libraries start with v1's `order: N` eligibility logic and step 3 evolves them to `blocked_by`. Wire `/status` and `check-periods.py` to call the libraries. Builds on the `check-periods.py` library refactor from `pi-migration-plan.md` §5 step 1.
2. **Define v2 schema and the version branching.** Add `schema_version` reading to all consumer scripts. v1 path unchanged; v2 path stub raises `NotImplementedError` until step 4.
3. **Implement v2 readers.** `class-graph.py` understands `blocked_by`; `class-rollup.py` aggregates v2 task statuses; `init-class.py` writes v2 by default for new classes.
4. **Cycle ledger writer.** `check-periods.py` writes `cycles/<period>.yaml` with `opened_at` on roll-in and `closed_at` + terminal task statuses on roll-out. Pure addition; no behavioral change to existing flows.
5. **Cancellation reason.** `set-status.py` requires `abandoned_reason` on `→ abandoned`. Tests for the new requirement.
6. **`upgrade-class-yaml.py`.** With round-trip tests against the existing `engagement-template/.class.yaml` files.
7. **Documentation + spec update.** `spec/02-architecture.md` schema section; `spec/04-scaffolding.md`; `notes/open-items.md` queue updates.

## 6. Open Questions

- **V1 — Cycle granularity.** Does every class fit a single `cycle.cadence`? Reporting often has both monthly *and* quarterly tasks. Two paths: (a) per-task `cadence:` overrides, (b) multiple cycles per class with a `cycle_id:` field on each task. (a) is simpler, (b) is closer to Linear's reality. **Lean (a) for v2** with two clarifications: (i) under (a), "current period" is task-scoped — a `current_period_for(task)` helper threads through the eligibility predicate (§3a), `class-rollup.py`, and the cycle ledger writer (§3b); (ii) cross-cadence task gates inside `blocked_by` are explicitly out of scope under (a) — same-cadence task dependencies only. Calendar gates are unaffected since they always resolve against the consumer task's own current period. Promotion trigger from (a) → (b) is **the appearance of cross-cadence task dependencies in a real engagement**, not just multi-cadence within a class.
- **V2 — `blocked_by` scope.** Cross-class dependencies (e.g., reporting blocked by treasury close)? **Lean no for v2** — keep `blocked_by` intra-class only. Cross-class dependencies push us toward a fourth level (engagement-level orchestration), which we don't want yet.
- **V3 — SLA / deadlines.** Add a `due_offset:` field per task ("5 business days past anchor")? Defer to a separate design — it's its own feature.

## 7. Out of Scope

- Cross-class dependencies (see V2).
- Deadlines / SLAs (see V3).
- Speculative task metadata (`priority`, `estimate`, `reviewer`, `labels`). Manifest order covers dispatch ordering today; reviewer routing belongs in Linear/GitHub assignee fields; categorical filtering doesn't have a load-bearing consumer yet. Promote when a real downstream consumer (Symphony, dashboard, audit query, etc.) demonstrates a concrete need — and prefer a specific typed field (e.g., `requires_senior_review: bool`) over a polymorphic tagging system. The schema is additive — adding an optional field later is cheap and doesn't break v2 readers.
- Additional `blocked_by` gate types beyond `task` and `calendar` (e.g., external file appearing on disk, API readiness, human approval signal, scheduler ping). The polymorphic shape leaves the door open and validators reject unknown types in v2. Promote a specific type only when a real engagement demonstrates the need — adding speculative types repeats the priority/estimate mistake.
- Subclasses or nested class groupings (see "What we explicitly DO NOT borrow" — three-level hierarchy is load-bearing).
- Schema-declared task inputs/outputs (`inputs:` / `outputs:` fields). Data flow is filesystem convention — see §3g.
- Time-of-day anchoring within a daily cadence. That's a Symphony scheduling concern (when to poll), not a Cadence schema concern (which date is "today's" period).
- Auto-generated Linear projection (covered in `pi-migration-plan.md` §8 as future Symphony work).
- Velocity/throughput tracking across cycles. The cycle ledger file is the substrate; analytics on top is a future affordance.
- Removing v1 reader code — stays for two release cycles minimum.

## 8. Relationship to Other Plans

### vs. pi migration

Orthogonal. v2 is harness-agnostic — it's pure schema + Python script work. Neither plan blocks the other. Sequencing: **pi migration first, then v2.** Reasons:

- The pi migration touches more of the repo's structure (new top-level dirs, TS extension, test split). Doing v2 inside that churn invites merge pain.
- v2 benefits from the §5 step 1 of the pi plan (`check-periods.py` library refactor) — that's already on the pi-track sequence and v2 step 1 builds on it.
- v2 introduces no harness-specific code, so it lands cleanly *after* the harness restructure stabilizes.

If pi migration slips, v2 can ship independently against the existing `plugin/` structure — it doesn't require the new layout.

### vs. Symphony

v2 is what makes Symphony *good*, not what makes Symphony *possible*. Symphony could run on v1, but:

- v2's `blocked_by` graph is the dispatch DAG Symphony needs.
- v2's `cycle.cadence` + `cycle.rollover_anchor` give Symphony a deterministic period model.
- v2's cycle ledgers are the natural payload for Linear parent-issue rollups.
- v2's heterogeneous `blocked_by` (task + calendar gates) means Symphony's eligibility check is one polymorphic predicate, not two.

Net: build v2 *before* Symphony, regardless of when Symphony itself lands. The two plans together describe the full destination.

### Test infrastructure interaction

Both plans touch `tests/`. Sequencing matters:
- Pi migration creates `tests/unit/`+`claude/`+`pi/` split.
- v2 lands inside that split: schema tests in `tests/unit/`, e2e tests duplicated across `tests/claude/` and `tests/pi/` (since both harnesses run the same scripts).
- Don't try to do both at once. Pi first, then v2.

---

## Next

Resolve V1 (cycle granularity) — promote "lean (a)" to a decision and remove from open questions. Then promote to detailed spec with field validators, transition matrix for the upgrade script, and the test matrix.
