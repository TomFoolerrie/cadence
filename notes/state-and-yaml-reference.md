# State Machine & YAML Reference

Cross-reference of how `status.yaml` and `.class.yaml` are created, mutated, and by whom. Verified against spec, scripts, and skills (2026-03-28).

## Status Transitions

| From → To | Triggered by | Notes |
|-----------|-------------|-------|
| `not_started → in_progress` | `/start` (via `start-setup.py`), `/onboard` Step 9a | `--period` required | *We can collapse **'/onboard' into a couple commands like '/start'.**
| `in_progress → in_progress` | `/start` (crash recovery) | Idempotent no-op |
| `in_progress → review_ready` | `/start` Step 3, `/onboard` Step 9d | Success path |
| `in_progress → blocked` | `/start` Step 3, `start-setup.py` on failure | Requires `reason` |
| `review_ready → in_progress` | `/start` Step 0 (human rejection) | Re-execute |
| `review_ready → done` | `/done` Step 6 | Sets `done_at`, clears `issues` |
| `blocked → not_started` | `/start` Step 0a (human retry) | Clears `issues` |
| `blocked → abandoned` | `/start` Step 0a (human abandon) | Requires `reason`, sets `done_at` |
| `done → not_started` | `check-periods.py` only | Direct YAML write, bypasses `set-status.py` |
| `abandoned → not_started` | `check-periods.py` only | Direct YAML write, bypasses `set-status.py` |

### Transition rules

- **`REQUIRES_REASON`**: `blocked`, `abandoned` — must pass reason string
- **`--period` flag**: only valid on `not_started → in_progress`
- **Terminal states**: `done` and `abandoned` — only `check-periods.py` can exit them
- **Idempotent**: `in_progress → in_progress` exits 0 without writing

## status.yaml Schema

```yaml
schema_version: 1         # int, preserved across resets
period: "2026-03"          # string, empty until first execution
status: "not_started"      # enum: not_started|in_progress|review_ready|blocked|done|abandoned
issues: []                 # list[string], reasons for blocked/abandoned
done_at: null              # null | ISO8601 string
```

### Field mutations by transition

| Transition | Fields modified |
|-----------|-----------------|
| `not_started → in_progress` | `status`, optionally `period` (via `--period`) |
| `in_progress → in_progress` | none (no-op) |
| `in_progress → review_ready` | `status`, `issues = []` |
| `in_progress → blocked` | `status`, `issues = [reason]` |
| `review_ready → in_progress` | `status`, `issues = []` |
| `review_ready → done` | `status`, `issues = []`, `done_at = now()` |
| `blocked → not_started` | `status`, `issues = []`, `done_at = None` |
| `blocked → abandoned` | `status`, `issues = [reason]`, `done_at = now()` |

## .class.yaml Schema

```yaml
schema_version: 1
name: "Treasury"            # title-cased from directory name
description: ""             # set via edit-class-yaml.py set-description
manifest:
  - task: "monthly-bank-fees"   # kebab-case, must match directory name
    order: 1                    # positive int, execution phase
    enabled: true               # membership flag
    period_format: "monthly"    # monthly|weekly|quarterly|adhoc
    anchor: "first_monday"      # day-of-week anchor for period triggering
```

### .class.yaml Mutations

| Operation | Command | Who triggers | When |
|-----------|---------|-------------|------|
| Create | `init-class.py <name>` | `/onboard` (class-level) | Step 3 |
| Set description | `edit-class-yaml.py set-description` | `/onboard` Step 8 | After interview |
| Add task | `edit-class-yaml.py add-task` | `/onboard` Step 8 | After interview |
| Update task | `edit-class-yaml.py update-task` | Agent (conversation) | User requests change |
| Remove task | `edit-class-yaml.py remove-task` | Agent (conversation) | User retires task |

**Read-only consumers**: `/start`, `/done`, `/status` never write to `.class.yaml`.

### Write protection

`.claude/settings.json` at the class level denies `Write(./.class.yaml)` — all mutations must go through `edit-class-yaml.py`.

## Who Writes What

| File | Writers | Protection |
|------|---------|-----------|
| `status.yaml` | `set-status.py`, `check-periods.py` | `settings.json` denies `Write(./status.yaml)` |
| `.class.yaml` | `init-class.py`, `edit-class-yaml.py` | `settings.json` denies `Write(./.class.yaml)` |
| `SKILL.md` | `/onboard` (create), `/done` (human-approved edits) | None — content file |
| `learned.md` | `/done` (append review history + patterns) | None — content file |

## Known Documentation Gap

`schema_version` in `status.yaml` is used and preserved by all code paths but not documented in `spec/03-status-machine.md`.
