---
name: done
description: >
  This skill should be used when the user says "/done" or indicates
  they have "reviewed the output" or "approved the draft." Processes
  human review feedback after /start or /onboard. Updates learned.md,
  may propose SKILL.md changes, fixes output if corrected, sets done,
  and commits.
version: 2.0.0
---

# /done

Process the human review, capture learnings, and close out the period.

**Constraint:** `/done` runs in the same conversation as `/start` or `/onboard`. You already have full context.

## Step 1 — Confirm Review Status

Read `status.yaml` from the current task directory.

- If status is `review_ready`, proceed to Step 2.
- If status is anything else, tell the user: "This task is not ready for review (current status: {status})." Stop.

## Step 2 — Capture the Review

Ask the user for their review. Present three options:

1. **Approved** — output is correct, no changes needed.
2. **Corrected** — output has minor issues; user describes what to fix.
3. **Rejected** — output is wrong, needs full re-execution.

| Outcome | Action |
|---------|--------|
| Approved | Proceed to Step 3. |
| Corrected | Proceed to Step 3, then Step 4. |
| Rejected | Tell the user: "Run /start again to re-execute." Do NOT change status. Stop. |

## Step 3 — Update learned.md

Open `learned.md` and append to the relevant sections. Write concisely — a fresh Claude instance reads this file next period.

### Review History

Add one row:

| Period | Outcome | Key Number | Note |
|--------|---------|------------|------|

- **Period:** current period from `status.yaml`.
- **Outcome:** `approved` or `corrected`.
- **Key Number:** the most important number from this period's output.
- **Note:** one line. If corrected, summarize what was wrong.

### Patterns

- Confirm or update existing patterns.
- Add new patterns only if worth remembering for future periods.
- Note contradictions to existing patterns.

### What Didn't Work

If corrected:

- What you tried.
- What actually happened.
- What to do instead next time.

If approved, do not add entries.

### Open Questions

- Add anything unresolved for next period.
- Remove questions that have been answered.

## Step 4 — Fix Output (if corrected)

Apply the user's corrections to files in `periods/<period>/workpapers/`.

## Step 5 — Propose SKILL.md Updates

If the review revealed a problem with the **procedure itself** (missing step, bad threshold, wrong data source), propose changes. Show the diff to the user:

```
I'd like to update SKILL.md:

  ## Procedure
  - Step 3: Changed threshold from $500 to $1,000
    (the $500 threshold flagged too many false positives)

Approve this change?
```

**Never edit SKILL.md without explicit user approval.** If rejected, record the context in learned.md under Open Questions.

If no changes are needed, skip this step.

## Step 6 — Write status.yaml

Write `status.yaml` directly:

```yaml
schema_version: 1
status: done
period: "<period>"
issues: []
done_at: "<ISO 8601 timestamp>"
```

## Step 7 — Git Commit

```bash
git add -A && git commit -m "[done] Complete <period>"
```

Tell the user: "Period complete. Run /start when ready for the next cycle."

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| Status is not `review_ready` | Inform the user and stop. |
| Human rejects the draft | Do not change status. Tell user to run /start again. Stop. |
| SKILL.md change proposed but rejected | Record rejection in learned.md under Open Questions. |
| No feedback from human | Treat as approved. Add Review History row noting "approved, no corrections." |
| Multiple corrections | Fix all issues, record each in learned.md, propose any SKILL.md changes as a batch. |
