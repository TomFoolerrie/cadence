# Design: `init-engagement.py`

Script to replace manual template copying. Scaffolds a new engagement directory with git initialized.

## Usage

```
init-engagement.py <path> [--name <engagement-name>]
```

## What It Does

1. Creates the directory at `<path>`
2. Writes `.context-root` with engagement name and `schema_version: 1`
3. Writes template `AGENT.md` with entity detail fields
4. Creates `.claude/tools/` directory
5. Writes `.gitignore` (excludes `**/periods/*/data/`, `**/periods/*/workpapers/`, `.context-cache/`, `.DS_Store`)
6. Writes empty `requirements.txt`
7. Runs `git init`
8. Creates initial commit: `[init] <engagement-name>: engagement created`

## Why

Every skill ends with `git add` + `git commit`. Without a git repo, all commits fail silently. This was the #1 issue in the dry run — the agent couldn't commit anything.
