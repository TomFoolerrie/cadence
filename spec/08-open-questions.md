# Open Questions (v2)

1. **Orchestrator implementation.** `.class.yaml` declares task order, but the orchestrator agent itself isn't specified. Key decisions: how does the orchestrator launch sub-agents? How does it collect results? The error protocol (`03-status-machine.md`) defines status transitions and recovery rules — the orchestrator needs to follow these, potentially with added retry policies.

2. **Task/class configuration.** `period_format` is configurable per task in `.class.yaml` (`02-architecture.md` Section 3). Remaining question: should other structural elements be configurable (e.g., a task that doesn't need `periods/`, a class that needs additional files)?

3. **Hierarchy templates.** Should plugins define reusable templates that can be instantiated multiple times? ("Create a new client workspace" → scaffolds a fresh hierarchy from a template.) Useful for firms managing multiple engagements.

4. **Cross-hierarchy references.** Can a task in one hierarchy reference a file from another? (e.g., your accounting workspace referencing a contract from your legal workspace.)

5. **Real-time file watching.** Should the runtime watch for new files mid-session, or only scan at session start? Acknowledged as a future concern — current design loads context at session start only.

6. **Token budget coordination.** How do context loading costs scale as the hierarchy grows? Partially mitigated: `learned.md` is agent-managed and consolidates when the file gets long (~150 lines guideline). This limits unbounded growth but doesn't address the broader question of a formal token budget system. Remaining question: should there be a hard budget system that limits how much context each level contributes to `load-context.py` output?

7. **Multi-user and remote collaboration.** MVP is single-user, local-only. Future state may support pushing the hierarchy to a git remote for team collaboration, which would require write-scope enforcement, period locking, conflict resolution, and governance controls.

8. **Orchestrator review of non-trivial work product.** The orchestrator (`02-architecture.md` Section 8) is described as reviewing workpapers against learned.md patterns. But workpapers may be spreadsheets, PDFs, or JE drafts — not trivially parseable. The tools layer may need to produce machine-readable validation output alongside human-readable workpapers.

9. **Adhoc task lifecycle.** In MVP, adhoc tasks are single-use — once they reach a terminal state (`done` or `abandoned`), they stay there. `check-periods.py` skips adhoc tasks (cannot auto-compute next period), and `/start` refuses to execute terminal tasks. To run an adhoc task again, the user must `/onboard` a new task. Future state may add a manual reset mechanism (e.g., `/start` prompting for a new period string when the task is adhoc + terminal).
