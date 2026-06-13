# Ticket 03: `/start` procedure → Pi method-pin (autonomous happy path)

**Status:** TODO
**Repo:** cadence (authoring the pin text + its test) → consumed by pi-harness's `cadence-start` row (Ticket 02)
**Depends on:** 01, 02
**Source of truth:** `plugin/skills/start/SKILL.md`, `spec/skill-start.md`, `spec/03-status-machine.md`;
`00-integration-design.md`.

## Goal

Translate the `/start` skill — today a Claude Code prompt injection — into a **method-pin** (appended
to Pi's system prompt) plus a **default task** (the per-run instruction). This is the behaviour-fidelity
ticket: the Pi run must follow the same Step 0→4 procedure and produce the same artifacts as a Claude
Code `/start`, minus the interactive branches (which have no human in headless v1).

## Design — faithful map of `/start` Steps 0–4 to a headless pin

The pin instructs the agent (cwd = `/work/<CADENCE_TASK>`, scripts at `$CADENCE_PLUGIN_ROOT/scripts`):

| `/start` step | Headless behaviour in the pin |
|---|---|
| **Step 0** route on `status.yaml` | `done`/`abandoned` → report + stop, no commit. `not_started`/`in_progress`(crash)/`review_ready`(rejected) → proceed. |
| **Step 0a** blocked-recovery menu | **No human to ask** → report the issues and stop (do **not** auto-retry/abandon). |
| **Step 1** setup | If `period` empty → **set `blocked` "period not set; run check-periods.py"** and stop (headless has no one to prompt). Else run `start-setup.py` (sets `in_progress`, installs deps, scaffolds period, loads context). Exit 1 → report+stop; exit 2 → already `blocked`, commit, stop. |
| **Step 2** execute | Activate `<root>/venv`. Read SKILL.md + learned.md from loaded context. Follow `## Procedure`. Write source only under `periods/<period>/data/`, outputs only under `periods/<period>/workpapers/`. Resolve tools task→class→global. If required source data is **missing** → set `blocked` (don't ask for an upload). Check `## Completion Criteria` before any `review_ready`. |
| **Step 3** outcome | Success → `set-status.py review_ready`. Failure → `set-status.py blocked "<reason>"`. |
| **Step 4** commit | Exactly **one** commit per invocation: `[start] <task> <period>: draft ready for review` (success) or `... blocked — <reason>` (failure); **no** commit for `done`/`abandoned`. |

**All status writes go through `set-status.py`; all scaffolding through the init scripts** — never
direct YAML edits. This is the same rule as the skill, and Ticket 04's gate makes it a hard boundary.

### Interactive branches → headless policy (the single rule)

Every point where `/start` waits for a human (blocked menu, empty-period prompt, "ask the user to
provide data via Cowork upload") becomes: **set `blocked` with a precise reason and stop after one
commit.** A future human-in-the-loop milestone (over pi-harness `chat`/`serve`) re-enables them.
Enumerate each such branch in the pin so the behaviour is explicit, not emergent.

## Work items

- [ ] Author `CADENCE_START_METHOD_PIN` (the "how": the rules above, the script-gating mandate, the
      write-scope expectations that match Ticket 04, the no-human policy) and `CADENCE_START_TASK` (the
      per-run "what": execute `$CADENCE_TASK` for its current period). Keep them as named string consts
      (mirroring pi-harness's `SUMMARIZE_METHOD_PIN`/`SUMMARIZE_TASK`).
- [ ] Decide the home of these strings. Recommended: author + freeze them **in cadence** (e.g.
      `plugin/pi/method-pin.ts` or a `.md` the pi-harness row reads) so Cadence owns its own procedure
      text, and have Ticket 02's row import/inline them. Avoid two copies drifting — single source.
- [ ] Add a **freeze test** (mirroring pi-harness `project-config.test.ts`) asserting the pin contains
      the load-bearing invariants: "go through set-status.py", "one commit", "blocked on missing
      data/period", "never write status.yaml/.class.yaml directly", the data/workpapers path rules.
- [ ] Cross-check the pin against `spec/03-status-machine.md` so every routed status + transition the
      pin can emit is a legal transition.

## Acceptance

- The pin, read end-to-end, reproduces `/start` Steps 0–4 for the non-interactive path with no
  ambiguity about the interactive branches (each is explicitly "set blocked + stop").
- Freeze test green. No drift: exactly one source for the strings.
- (Behavioural acceptance — the agent actually following the pin correctly — is proven by the live run
  in Ticket 06, not here.)

## Notes / risks

- The pin is **appended** to Pi's default system prompt (pi-harness appends method-pins so Pi's own
  tool guidance survives) — write it as additive guidance, not a replacement prompt.
- Resist encoding task-specific accounting logic in the pin — that lives in the task's own `SKILL.md`,
  which the agent reads at runtime. The pin is the *generic /start procedure*, identical for every task.
