# Complete Example: Month-End Close

A user installs an accounting plugin and selects `~/Documents/Accounting/`.

## After setup and onboarding several tasks:

```
~/Documents/Accounting/
├── .git/
├── .gitignore
├── .context-root                       ← YAML: engagement: "Acme Corp", schema_version: 1
├── AGENT.md                            ← entity: Acme Corp, FYE Dec 31, GAAP
├── .claude/
│   └── tools/
│       ├── je_formatter.py
│       └── pdf_parser.py
├── requirements.txt
├── treasury/
│   ├── .class.yaml                 ← orchestration manifest: 3 tasks, phase order
│   ├── AGENT.md                    ← treasury class context for task agents
│   ├── requirements.txt
│   ├── tools/
│   │   └── chase_parser.py         ← shared across treasury tasks
│   ├── monthly-bank-fees/
│   │   ├── SKILL.md                ← procedure for booking bank fees
│   │   ├── learned.md              ← 6 months of patterns
│   │   ├── status.yaml             ← last run: 2026-02, done
│   │   ├── tools/
│   │   │   └── fee_categorizer.py
│   │   ├── requirements.txt
│   │   └── periods/
│   │       ├── 2025-09/
│   │       ├── 2025-10/
│   │       ├── ...
│   │       └── 2026-02/
│   │           ├── data/
│   │           ├── workpapers/
│   │           └── review-notes/
│   ├── zba-entries/
│   │   ├── SKILL.md
│   │   ├── learned.md
│   │   └── ...
│   └── bank-reconciliation/
│       ├── SKILL.md
│       ├── learned.md
│       └── ...
├── reporting/
│   ├── .class.yaml                 ← manifest: financial statements, board package
│   ├── AGENT.md
│   └── ...
└── collections/
    ├── .class.yaml
    ├── AGENT.md
    └── ...
```

## A typical close cycle:

```
User:    "Work on monthly bank fees"
Agent:   Navigates to treasury/monthly-bank-fees/, runs load-context.py --level task
User:    /start
Agent:   Reads status.yaml → routes (not_started → normal execution)
Agent:   Sets in_progress via set-status.py
Agent:   Installs dependencies (install-deps.py)
Agent:   Scaffolds periods/2026-03/ (init-period.py)
Agent:   Loads context: root/AGENT.md → treasury/AGENT.md → SKILL.md + learned.md
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
