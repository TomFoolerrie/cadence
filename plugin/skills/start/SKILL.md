---
name: start
description: >
  This skill should be used when the user says "/start" or asks to
  "run a task," "execute the procedure," or "begin this period's work."
  Executes a task for the current period — scaffolds directories, loads
  context, runs the procedure, and commits.
version: 3.0.0
---

# /start — Execute Task for Current Period

## Step 1 — Determine Period

Ask the user: **"What period?"** (e.g., `2026-04` for monthly, `2026-Q1` for quarterly).

## Step 2 — Install Dependencies

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/install-deps.py
```

## Step 3 — Scaffold Period Directory

If `periods/<period>/` does **not** already exist, scaffold it:

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/init-period.py <period>
```

If the directory already exists, skip the scaffold.

## Step 4 — Load Context

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/load-context.py --level task
```

Read the output. This provides `SKILL.md`, `learned.md`, and other context files from the folder hierarchy.

## Step 5 — Execute Procedure

Follow the task's `SKILL.md` procedure from the loaded context. Use `learned.md` for patterns and known issues.

- Place source files in `periods/<period>/data/`.
- Place outputs in `periods/<period>/workpapers/`.
- If you need source data, ask the user to provide it.

## Step 6 — Git Commit

```bash
git add -A && git commit -m "[start] Execute <period>"
```

Tell the user: **"Execution complete. Review the output — when you're happy with it, run /done to close out the period."**

## Constraints

- **Fresh agent per execution.** All context comes from the folder hierarchy. No memory of prior conversations.
- **All context from folders.** `SKILL.md`, `learned.md`, `AGENT.md` in the hierarchy are the only inputs.
- **One commit per invocation.** Exactly one git commit at the end.
