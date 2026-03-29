---
name: done
description: >
  Trigger when the user says "/done" or indicates they have reviewed
  the output. Captures human feedback, updates learned.md, and closes
  the period.
version: 3.0.0
---

# /done

Capture review feedback, update learnings, close the period.

**Constraint:** runs in the same conversation as `/start` or `/onboard` — you already have full context.

## Step 1 — Ask for Feedback

Ask: **"How did it go?"** Present three options:

1. **Approved** — output is correct.
2. **Corrected** — user describes what to fix.
3. **Rejected** — tell the user "Run /start again." **Stop.**

## Step 2 — Update learned.md

Add a row to the **Review History** table:

| Period | Outcome | Key Number | Note |
|--------|---------|------------|------|

If corrected, also:
- Add/update **Patterns** if applicable.
- Add entry to **What Didn't Work** (what went wrong, what to do instead).

## Step 3 — Fix Output (if corrected)

Apply the user's corrections to files in `periods/<period>/workpapers/`.

## Step 4 — Propose SKILL.md Changes (if needed)

If the procedure itself needs updating, show a diff and get **explicit user approval** before editing. If rejected, note it in learned.md.

## Step 5 — Write status.yaml

```yaml
schema_version: 1
status: done
period: "<period>"
done_at: "<ISO 8601 timestamp>"
```

## Step 6 — Git Commit

```bash
git add -A && git commit -m "[done] Complete <period>"
```

Tell the user: **"Period complete. Run /start when ready for next cycle."**
