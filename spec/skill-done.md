# Skill: `/done`

## Frontmatter

```yaml
---
name: done
description: >
  Processes human review feedback after /start or /onboard.
  Updates learned.md, may propose SKILL.md changes,
  fixes output if needed, and archives to Google Drive.
version: 1.0.0
---
```

## Purpose

Capture what was learned this period so next period is smarter. `/done` is the post-review skill — it runs after the human has reviewed the draft produced by `/start`.

---

## Constraints

- **Same conversation.** `/done` always runs in the same conversation as the preceding `/start` or `/onboard`. It does **not** load context independently — the active conversation provides all context. For the first period, the user runs `/done` after `/onboard` reaches `review_ready`.
- **Only from `review_ready`.** `/done` can only be called when `status.yaml` is `review_ready`. Any other state is rejected.

---

## Procedure

### Step 1 — Confirm Review Status

Check `status.yaml`. If status is not `review_ready`, tell the user and stop. `/done` only runs after `/start` has set `review_ready`.

### Step 2 — Capture the Review

Ask the user for their review feedback. Three outcomes:

| Outcome | Meaning | Next steps |
|---------|---------|------------|
| **Approved** | Output is correct as-is | → Step 3 (learnings only) |
| **Corrected** | Output has issues the agent should fix | → Step 4 (fix), then Step 3 |
| **Rejected** | Output is fundamentally wrong, needs full re-execution | → Do not proceed with `/done`. Tell the user to run `/start` again, which will transition `review_ready → in_progress` for re-execution. |

If the human gives verbal feedback, write it to `periods/{period}/review-notes/review-notes.md` as a permanent record. Review notes are git-tracked — they feed the audit trail.

### Step 3 — Update learned.md

This is the core job. Write concisely — learned.md is read by a fresh instance next period and costs tokens.

**What to write:**

- **Review History** — Add one row: period, outcome (approved/corrected), key number, one-line note.
- **Patterns** — Update if this cycle confirms or contradicts an existing pattern. Add new patterns only if they're worth remembering (expected ranges, recurring amounts, timing patterns). Counters (Confirmed/Contradicted) are optional metadata — use them if the pattern benefits from tracking confidence.
- **What Didn't Work** — If corrected: record what you tried, what happened, and what to do instead. Be specific enough that a fresh instance won't repeat the mistake.
- **Open Questions** — Add anything unresolved that should be investigated next period.

**What NOT to write:**

- Don't repeat what's already in SKILL.md
- Don't log routine operations that went as expected
- Don't write paragraphs — use tables and bullet points
- Don't duplicate the review notes — just reference the period
- Don't write "everything worked" — that's zero information

**Consolidation.** If learned.md is getting long (~150 lines), consolidate during this update: merge related entries, remove low-value patterns, summarize verbose notes. The file should stay focused and useful, not grow unboundedly.

### Step 4 — Fix Output (if corrected)

If the human found issues with the draft:

1. Fix the output in `periods/{period}/workpapers/`.
2. If the root cause is in a tool, fix it at the appropriate tier:
   - Task-specific logic → `{task}/tools/`
   - Shared across class → `{class}/tools/`
   - Global utility → `.claude/tools/`
3. If the fix changes validation thresholds or expected values, note the change in learned.md.

### Step 5 — Propose SKILL.md Updates (if needed)

If the review revealed the **procedure itself was wrong** — a missing step, bad threshold, unclear instruction, wrong data source — this is a SKILL.md issue, not a learned.md issue.

**Do not edit SKILL.md silently.** Present the proposed change to the user:

```
I'd like to update SKILL.md:

  ## Procedure
  - Step 3: Changed threshold from $500 to $1,000
    (the $500 threshold flagged too many false positives)

Approve this change?
```

Wait for the user's approval before writing. This is a convention enforced by this skill's instructions — SKILL.md changes are high-stakes because they affect every future execution.

### Step 6 — Set Done

```bash
set-status.py done
```

This clears `issues[]` and sets `done_at` to the current timestamp.

### Step 7 — Commit

```bash
git add .
git commit -m "[done] <task-name> <period>: <summary>"
```

The summary should note what changed (e.g., "approved, updated learned.md" or "corrected fee categorization, fixed tool, updated learned.md").

### Step 8 — Archive to Google Drive

```bash
archive-period.py
```

Uploads the completed period's `workpapers/` and `data/` to Google Drive, mirroring the hierarchy structure. If the upload fails, report the failure but do not change task status — the task is already `done`.

Tell the user: *"Captured. Ready for the next task."*

---

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| Status is not `review_ready` | Inform the user, stop. `/done` only runs from `review_ready`. |
| Human rejects the draft entirely | Do not proceed with `/done`. Tell the user to run `/start` again for re-execution. |
| SKILL.md change proposed but rejected | Record the rejection context in learned.md so a future `/done` cycle can re-evaluate. |
| `archive-period.py` fails | Report the failure. Task remains `done`. User can retry the upload manually. |
| No feedback from human | Still set `done` — an approved review with no notes is valid. Add a row to Review History with "approved, no corrections." |
| Multiple corrections in one review | Fix all issues, record each in learned.md, propose any SKILL.md changes as a batch. |

---

## Script Composition

| Script | When called | Purpose |
|--------|------------|---------|
| `set-status.py done` | Step 6 | Transition to terminal state |
| `archive-period.py` | Step 8 | Upload period to Google Drive |
