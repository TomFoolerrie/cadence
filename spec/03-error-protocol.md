# Error Protocol

## 4.1 Task-Level Status Transitions

```
not_started  ──→ in_progress       (/start begins executing)

in_progress  ──→ in_progress       (idempotent — crash recovery, /start re-enters)
in_progress  ──→ review_ready      (/start completes successfully — draft ready for human review)
in_progress  ──→ blocked           (/start fails)

review_ready ──→ in_progress       (human rejects draft — /start re-executes)
review_ready ──→ done              (/done after human review confirms)

blocked      ──→ not_started       (human says "retry" — resets for fresh attempt)
blocked      ──→ abandoned         (human says "abandon" — unrecoverable for this period)
```

**Infrastructure transitions** (direct writes by `check-periods.py`, not through `set-status.py`):

```
done         ──→ not_started       (check-periods.py — next anchor date arrived)
abandoned    ──→ not_started       (check-periods.py — next anchor date arrived)
```

**Rules:**

- **On `in_progress`:** The `/start` skill sets this immediately when execution begins. Indicates work is actively happening. **Idempotent:** if the task is already `in_progress` (e.g., from a crashed session), `/start` re-enters `in_progress` as a no-op. Also valid from `review_ready` — if the human rejects a draft, `/start` moves the task back to `in_progress` for re-execution.
- **On `review_ready`:** The task agent completed its work and produced a draft. The output is in `workpapers/` and awaits human review. Set by the `/start` skill on successful completion. In future state, the orchestrator reviews at this stage before setting `done`.
- **On `done`:** The task completed for this period. `/done` sets `done` after human review and clears `issues[]`. `done` is terminal.
- **On `blocked`:** The agent reports what failed and why in `issues[]`. The human investigates and decides whether to retry (→ `not_started`) or abandon (→ `abandoned`). Set by `/start` on failure.
- **On `abandoned`:** The human determined this period's issue is unrecoverable (e.g., data was never available, engagement was paused). The agent records the reason in `issues[]`. `abandoned` is terminal for this period — the prior-period guard treats it equivalently to `done`, so a new period can begin. Set via `set-status.py` during the `/start` conversation.
- **No automatic retries.** Human-in-the-loop for all recovery decisions in MVP.
- **All tasks must reach a terminal state.** Every enabled task must reach `done` or `abandoned` before the class is considered done.
- **Period advancement resets terminal states automatically.** `check-periods.py` runs on a schedule, reads each terminal task's `done_at` timestamp and `anchor` field, and resets tasks whose next period is due. This is the only mechanism that transitions out of a terminal state — it is a lifecycle event, not a within-period recovery. See Section 6.6.

## 4.2 Class-Level Status Protocol

Class status is **always derived** from task statuses — never set independently. The `/status` skill computes the class rollup on the fly by reading all task-level `status.yaml` files within the class. There is no `class-status.yaml` file.

```
not_started  ──→ in_progress   (any task moves beyond not_started)
in_progress  ──→ done          (all enabled tasks done or abandoned)
```

**Rules:**

- A task in `blocked` or `in_progress` keeps the class `in_progress`. The human investigates and unblocks.
- The class reaches `done` when every enabled task is `done` or `abandoned`.
- Class status is computed on demand by `/status` — it is never stored in a file.

**Derivation rules (what `/status` computes):**

All derivation rules apply only to **enabled** tasks (where `enabled: true` in `.class.yaml`). Disabled tasks are excluded from `tasks_total` and all rollup counts.

| Condition | `class_status` |
|-----------|---------------|
| All enabled tasks are `not_started` | `not_started` |
| Any enabled task is beyond `not_started` (but not all terminal) | `in_progress` |
| All enabled tasks are `done` or `abandoned` | `done` |
