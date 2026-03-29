---
name: done
description: >
  Trigger when the user says "/done" after approving the output.
  Captures learnings from the conversation, updates learned.md,
  and closes the period with a commit.
version: 3.1.0
---

# /done

The user has accepted the output. Capture what was learned and close the period.

**Constraint:** runs in the same conversation as `/start` or `/onboard` — you already have full context.

## Step 1 — Update learned.md

Review the conversation for what happened this period. Add a row to the **Review History** table:

| Period | Outcome | Key Number | Note |
|--------|---------|------------|------|

Also update:
- **Patterns** — confirm existing or add new patterns worth remembering.
- **What Didn't Work** — if anything went wrong before the user approved, record it.

Write concisely — a fresh agent reads this next period.

## Step 2 — Propose SKILL.md Changes (if needed)

If the conversation revealed a problem with the **procedure itself** (missing step, bad threshold, wrong data source), show a diff and get **explicit user approval** before editing. If rejected, note it in learned.md.

If no changes needed, skip this step.

## Step 3 — Git Commit

```bash
git add -A && git commit -m "[done] Complete <period>"
```

Tell the user: **"Period complete. Run /start when ready for next cycle."**
