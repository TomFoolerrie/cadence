---
name: done
description: >
  This skill should be used when the user says "/done" or indicates
  they have "reviewed the output" or "approved the draft." Processes
  human review feedback after /start or /onboard. Updates learned.md,
  may propose SKILL.md changes, fixes output if corrected, sets done,
  and archives to Google Drive.
version: 1.0.0
---

# /done

Process the human review, capture learnings, and close out the period.

**Constraint:** `/done` always runs in the same conversation as the preceding `/start` or `/onboard`. It does not load context independently.

## Step 1 — Confirm Review Status

Read `status.yaml` in the current task directory.

- If status is `review_ready`, proceed to Step 2.
- If status is anything else, tell the user: "This task is not ready for review (current status: {status}). Run /start first to produce a draft." Stop.

## Step 2 — Capture the Review

Ask the user for their review feedback. Present the three options:

1. **Approved** — Output is correct as-is.
2. **Corrected** — Output has specific issues to fix.
3. **Rejected** — Output is fundamentally wrong and needs full re-execution.

Handle each outcome:

| Outcome | Action |
|---------|--------|
| Approved | Proceed to Step 3. |
| Corrected | Proceed to Step 4 (fix output), then Step 3. |
| Rejected | Do NOT proceed with /done. Tell the user: "Run /start again to re-execute this task." Stop. |

If the user provides verbal feedback (any commentary beyond a simple approval), write it to `periods/{period}/review-notes/review-notes.md` as a permanent record. This file is git-tracked and feeds the audit trail.

If the user gives no feedback at all, treat it as approved with no corrections. Still proceed — an approved review with no notes is valid.

## Step 3 — Update learned.md

Open the task's `learned.md` and update it. Write concisely — a fresh Claude instance reads this file next period and every token costs.

Update these sections:

### Review History

Add one row to the table:

| Period | Outcome | Key Number | Note |
|--------|---------|------------|------|

- Period: the current period string from `status.yaml`.
- Outcome: `approved` or `corrected`.
- Key Number: the most important number from this period's output (a total, a variance, a count — whatever best characterizes the result).
- Note: one line summarizing what happened. If corrected, summarize what was wrong.

### Patterns

- If this cycle confirms an existing pattern, update it (increment the confirmed counter if one exists).
- If this cycle contradicts an existing pattern, note the contradiction.
- Add a new pattern only if it is worth remembering for future periods: expected ranges, recurring amounts, timing patterns, data source quirks.
- Do not add patterns for routine operations that went as expected.

### What Didn't Work

If the outcome was corrected:

- Record what you tried.
- Record what actually happened (the incorrect result).
- Record what to do instead next time.
- Be specific enough that a fresh instance will not repeat the mistake.

If the outcome was approved, do not add entries here. "Everything worked" is zero information.

### Open Questions

Add anything unresolved that should be investigated next period. Remove questions that have been answered.

### What NOT to Write

- Do not repeat information already in SKILL.md.
- Do not log routine operations that went as expected.
- Do not write paragraphs — use tables and bullet points.
- Do not duplicate the review notes — reference the period instead.

### Consolidation

If learned.md exceeds approximately 150 lines, consolidate during this update:

- Merge related entries in the patterns table.
- Remove low-value patterns that have not been useful.
- Summarize verbose notes into concise bullets.
- Keep the file focused and useful. It must not grow unboundedly.

## Step 4 — Fix Output (if corrected)

If the human found issues with the draft:

1. Fix the output files in `periods/{period}/workpapers/`. Apply the corrections the user described.
2. If the root cause is in a tool (not just the output), fix the tool at the appropriate tier:
   - Task-specific logic: fix in `{task}/tools/`.
   - Shared across the class: fix in `{class}/tools/`.
   - Global utility: fix in `.claude/tools/`.
3. If the fix changes validation thresholds or expected values, note the change in learned.md under Patterns or What Didn't Work.

After fixing, return to Step 3 to record the learnings.

## Step 5 — Propose SKILL.md Updates

Evaluate whether the review revealed a problem with the **procedure itself** — a missing step, a bad threshold, an unclear instruction, a wrong data source. These are SKILL.md issues, not learned.md issues.

If no SKILL.md changes are needed, skip to Step 6.

If changes are needed, present each proposed change to the user:

```
I'd like to update SKILL.md:

  ## Procedure
  - Step 3: Changed threshold from $500 to $1,000
    (the $500 threshold flagged too many false positives)

Approve this change?
```

Wait for the user's explicit approval before writing any change to SKILL.md. Never edit SKILL.md silently. This is a hard rule — SKILL.md changes are high-stakes because they affect every future execution.

If the user rejects a proposed SKILL.md change, record the rejection context in learned.md under Open Questions so a future /done cycle can re-evaluate.

## Step 6 — Set Done

Run the status transition:

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/set-status.py done
```

This clears `issues[]` and sets `done_at` to the current timestamp.

## Step 7 — Git Commit

Stage and commit all changes:

```bash
git add .
git commit -m "[done] <task-name> <period>: <summary>"
```

The summary should describe what changed. Examples:

- `[done] monthly-bank-fees 2026-03: approved, updated learned.md`
- `[done] monthly-bank-fees 2026-03: corrected fee categorization, fixed tool, updated learned.md`

## Step 8 — Archive to Google Drive

Run the archive script:

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/archive-period.py
```

This uploads the completed period's `workpapers/` and `data/` to Google Drive, mirroring the hierarchy structure.

If the archive succeeds, tell the user: "Captured. Ready for the next task."

If the archive fails, report the failure to the user but do NOT change the task status. The task remains `done`. The user can retry the upload manually later.

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| Status is not `review_ready` | Inform the user and stop. /done only runs from `review_ready`. |
| Human rejects the draft | Do not proceed. Tell the user to run /start again. |
| SKILL.md change proposed but rejected | Record the rejection context in learned.md under Open Questions. |
| `archive-period.py` fails | Report failure. Task remains `done`. |
| No feedback from human | Treat as approved. Add Review History row with "approved, no corrections." |
| Multiple corrections in one review | Fix all issues, record each in learned.md, propose any SKILL.md changes as a batch. |
