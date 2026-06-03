# Complete Example: Month-End Close

A user installs an accounting plugin and selects `~/Documents/Accounting/`.

## After setup and onboarding several tasks:

The hierarchy after setup looks like the tree in Section 1 of `02-architecture.md`. Here is a populated example after onboarding three treasury tasks, a reporting class, and a collections class:

## A typical close cycle:

```
User:    "Work on monthly bank fees"
Agent:   Navigates to treasury/monthly-bank-fees/, runs load-context.py --level task
User:    /start
Agent:   Reads status.yaml → routes (not_started → normal execution)
Agent:   Sets in_progress via set-status.py
Agent:   Installs dependencies (install-deps.py)
Agent:   Scaffolds periods/2026-03/ (init-period.py)
Agent:   Loads context: root/AGENTS.md → treasury/AGENTS.md → SKILL.md + learned.md
Agent:   Pulls Chase statement from data/
Agent:   Runs chase_parser.py → fee_categorizer.py → je_formatter.py
Agent:   Writes draft JE to workpapers/
Agent:   "March bank fees prepared: $11,850 across 12 lines.
          Slightly below the $12,000-13,000 range from learned.md —
          one fewer international wire this month. Draft is in workpapers/."

Agent:   Sets review_ready via set-status.py

User:    Reviews the draft, looks good
User:    /done
Agent:   Sets status to done via set-status.py
Agent:   Updates learned.md: confirmed, $11,850 — updates range to $11,800-13,000
Agent:   git commit -m "[done] monthly-bank-fees 2026-03: confirmed, updated learned.md"
Agent:   archive-period.py uploads workpapers/ and data/ to Google Drive
Agent:   "Captured. Range updated. Ready for the next task."
```

> **Note on the range update:** The `$11,800-13,000` change lives in `learned.md` — an amount pattern that `/done` updates autonomously based on observed data. If a review instead revealed that a *validation threshold* in `SKILL.md` needed changing (e.g., a materiality limit or an expected-total check), `/done` would **propose** that change and wait for human approval before editing `SKILL.md`. This is the key boundary: `learned.md` patterns are agent-managed; `SKILL.md` procedure changes require human sign-off.
