# Ticket 03: `/start` procedure → Pi method-pin (autonomous happy path)

**Status:** TODO (revised 2026-06-13 after review)
**Repo:** cadence (authoring + freeze test) → string lands in pi-harness's `cadence-start` row (Ticket 02)
**Depends on:** 01, 02, 02a
**Source of truth:** `plugin/skills/start/SKILL.md`, `spec/skill-start.md`, `spec/03-status-machine.md`,
`plugin/scripts/set-status.py` (the transition guard); pi-harness `session-setup.ts`
(`appendSystemPromptOverride`), `project-config.ts` (the pin-as-frozen-const pattern), `CLAUDE.md`
(bash non-persistence); `00`.

## Goal

Translate the `/start` skill (a Claude Code prompt injection) into a **method-pin** (appended to Pi's
system prompt) + a **default task**, reproducing `/start` Steps 0–4 for the non-interactive path.

## Faithful map of `/start` Steps 0–4 (review-corrected)

cwd = `/work/$CADENCE_TASK` (Ticket 02a); scripts at `$CADENCE_PLUGIN_ROOT/scripts`.

| `/start` step | Headless behaviour |
|---|---|
| **Step 0** route on `status.yaml` | `done`/`abandoned` → report + **stop with NO commit and NO status write**. `not_started`/`in_progress`/`review_ready` → proceed. |
| **Step 0a** blocked-recovery menu | No human → report issues + **stop** (no auto-retry/abandon, **no commit**). |
| **Step 1** period | If `period` set → use it. If empty AND `period_format != adhoc` → **compute** it from the current date (prev month/quarter/week) per `skill-start.md:79` — do **not** block. If empty AND `adhoc` → **set `blocked`** (no human to ask). Then run `start-setup.py` (→ `in_progress`, deps, period scaffold, context). Exit 1 → report+stop; exit 2 → already `blocked`, commit, stop. |
| **Step 2** execute | Use the venv **by absolute path** `<root>/venv/bin/python` (see "bash non-persistence" below) — `<root>` = the dir containing `.context-root`, found by walking up from cwd. Read SKILL.md + learned.md. Follow `## Procedure`. Source → `periods/<period>/data/` only; outputs → `periods/<period>/workpapers/` only. Resolve tools task→class→global. Missing required data → **set `blocked`** (don't ask for upload). Check `## Completion Criteria` before any `review_ready`. |
| **Step 3** outcome | Success → `set-status.py review_ready`. Failure → `set-status.py blocked "<reason>"`. |
| **Step 4** commit | Exactly **one** commit on the `review_ready`/`blocked` paths; **zero** commits on `done`/`abandoned`/Step-0a routes. Messages: `[start] <task> <period>: draft ready for review` / `... blocked — <reason>`. |

All status writes go through `set-status.py`; all scaffolding through init scripts — never direct YAML
edits (Ticket 04's gate makes this a hard boundary).

### Review corrections folded in

- **Non-adhoc empty period is computable, not a block** (`skill-start.md:79`). `SKILL.md:77` says "ask
  the user" — that's the Cowork path; **resolve to the spec (compute) for headless**, and note the
  SKILL.md/spec divergence so it's fixed deliberately, not silently.
- **`done`/`abandoned` and Step-0a routes produce zero commits and zero status writes** (`SKILL.md:27`).
  The earlier "every interactive branch → blocked + one commit" rule was wrong for terminal routes.
- **Transition legality:** `blocked` is legal only **from `in_progress`** (`03-status-machine.md`).
  `not_started → blocked` is **not** in the table — so the adhoc-empty-period block must either route
  through `in_progress` first or `set-status.py` must permit it. **Verify `set-status.py`'s guard and
  pick one before authoring the pin** (don't emit an illegal transition).
- **Bash non-persistence:** `source venv/bin/activate` does not survive to the next Pi `bash` call. The
  pin must call `<root>/venv/bin/python …` by absolute path every time (or `source … && …` inline), and
  define `<root>` discovery (walk up for `.context-root`) since cwd is the task dir.

### Interactive branches → headless policy

Every human-wait becomes **set `blocked` + stop** (one commit) — **except** terminal routes
(`done`/`abandoned`, Step 0a) which stop with **no** commit/write. Enumerate each explicitly in the pin.

## Where the pin string lives (review-corrected)

The "author in cadence, `import` into pi-harness" plan is **not viable**: `project-config.ts` pins are
**pure frozen TS `const` literals** in the self-contained pi-harness package — it can't `import` from
cadence (not in its module graph, not mounted at build) and can't `fs`-read a cadence `.md` (purity
contract). Choose one:

- **(A, recommended)** The canonical pin lives **in pi-harness** (`CADENCE_START_METHOD_PIN` in
  `project-config.ts`, frozen by `test:project`). Cadence keeps a **cross-repo fixture test** that reads
  pi-harness's copy and asserts it still contains Cadence's load-bearing invariants.
- **(B)** A build step copies a cadence `.md` into the row; a test asserts byte-equality both sides.

Pick (A) unless there's a reason; record the choice here.

## Work items

- [ ] Author `CADENCE_START_METHOD_PIN` (the "how" above + the no-human policy + the script-gating
      mandate + the write-scope expectations matching Ticket 04) and `CADENCE_START_TASK` (the "what":
      execute `$CADENCE_TASK` for its current period). Instruct the agent to **read** `$CADENCE_PLUGIN_ROOT`
      / `$CADENCE_TASK` (the pin can't interpolate them).
- [ ] Implement the chosen string-home (A or B) with the freeze/fixture test.
- [ ] **Verify `set-status.py`'s transition guard** for the adhoc-empty-period block path; route legally.
- [ ] Cross-check every emittable transition against `03-status-machine.md` (`in_progress`,
      `review_ready`, `blocked` — the pin does **not** auto-emit `abandoned`).

## Acceptance

- The pin reproduces Steps 0–4 for the non-interactive path with each interactive/terminal branch
  explicit and correctly differentiated (block+commit vs stop+no-commit).
- Freeze/fixture test green; single source, no drift. No illegal transition emittable.
- Behavioural acceptance (agent actually following the pin) is proven by the live run in Ticket 06.

## Notes

- The pin is **appended** to Pi's prompt (verified) — write it as additive guidance.
- No task-specific accounting logic in the pin — that's the task's own `SKILL.md`, read at runtime.
