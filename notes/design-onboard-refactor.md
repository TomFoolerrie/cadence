# Design: Onboard Skill Refactor

Context: The first dry run (2026-03-25) revealed a mode-switching problem in onboard Step 8. After 30 minutes of direct file creation during the interview/builder phases, the agent could not reliably switch to "use scripts for everything" mode. See `dry-run-2026-03-25.md` for the full root cause analysis.

## Constraints Block

Add a hard constraint block near the top of the onboard SKILL.md (both class and task flows):

```markdown
## Constraints

- **Scripts are mandatory.** Never create directories with mkdir or modify YAML files directly.
  All scaffolding goes through `init-*.py` scripts. All YAML state changes go through
  `set-status.py` or `edit-class-yaml.py`. The scripts validate inputs and enforce the schema.
- **Markdown files are the exception.** SKILL.md, learned.md, and AGENT.md are written directly
  by the agent — these are content files, not state files.
```

## Decision: Step 8 should invoke `/start`

The dry run proved that reimplementing `/start` inline is a mistake. By Step 8 the agent has been in "builder" mode for 30 minutes — it's been writing files, installing deps, building tools. Asking it to also remember status transitions, period scaffolding via `init-period.py`, and validation rules from earlier in the document is too much. It just freestyles.

`/start` already handles all of this correctly — status transitions, `init-period.py`, execution, validation. Step 8 should delegate to it instead of reimplementing it. This:
- Removes ~40% of the onboard skill's execution complexity
- Ensures the dry run follows the exact same path as every future period
- Means fixes to `/start` automatically apply to onboarding too

**Action:** Replace Step 8's inline procedure with a single instruction: "Invoke `/start` to execute the first period." Remove all the inlined status/scaffolding/validation steps from onboard.

**Note (post-review):** Verify that `/start`'s period-detection logic handles the first-period case cleanly. After `init-task.py`, `status.yaml` has `period: ''` and `status: not_started` — this is the normal `/start` entry point. Step 1 of `/start` says "If status.yaml period is empty or a new period is needed" it prompts the user. This should work, but needs explicit testing during implementation.
