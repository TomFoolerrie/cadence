# Ticket 04: Write-scope → gate enforce policy (the load-bearing ticket)

**Status:** TODO (revised 2026-06-13 after review)
**Repo:** pi-harness (branch `claude/quirky-ptolemy-htwb4n`)
**Depends on:** 02, **02a** (the `cwd=/work/$CADENCE_TASK` forward)
**Source of truth:** pi-harness `harness/gate/policy.ts` (`classify`, `resolveLexical`, `POLICY.workRoot`,
the write/edit vs bash branches), `gate/gate.ts` (`makeGate(audit,mode,workDir)`), `gate/guard.ts`
(fail-closed), `gate/gate.test.ts`; this repo's `spec/06-separation-of-concerns.md` §6.2; `00`, `02a`.

## Why this is load-bearing

Cadence's reliability rests on **hard boundaries, not instructions** — the dry runs proved the agent
hand-edits YAML despite being told not to (`notes/open-items.md`). Claude Code enforces this with
`.claude/settings.json`. **Pi ignores those files.** And pi-harness's gate today has **no sub-`/work`
granularity** — `policy.ts` classifies *any* write under `POLICY.workRoot = /work` as `record`/allow
(`write.work-root`). So a write one level above the task dir but still inside `/work` is **not denied**.
Running record mode, or enforce mode with only the stock policy, **silently regresses Cadence's most
important invariant.** This ticket adds the missing granularity. It is net-new policy code, not a
config flip.

## What review established about `policy.ts`

- **No task-subtree or protected-file concept exists** — only the two fixed roots (`workRoot`,
  `skillRoot`) and root-containment classification. Everything below is new.
- **The asymmetry is achievable** because `classify()` dispatches on `toolName` into **separate**
  `write|edit` vs `bash` branches. Deny in the write/edit branch; leave bash untouched.
- **`set-status.py` via bash classifies as `record` tier, not `allow`** (it's not a known skill script →
  `bash.unrecognized` → record). Record is **not blocked** in enforce mode (only `deny` blocks), so it
  passes — but assert `record` (not `allow`) in tests.
- **`resolveLexical(p, cwd)`** resolves a bare relative path against `cwd`. Today the gate passes
  `cwd=/work`. For task-relative writes (`workpapers/foo.csv`) to land in the task dir, the gate must
  receive **`cwd=/work/$CADENCE_TASK`** (Ticket 02a's forward) — this is distinct from passing the task
  dir as the "scope to check." **Both** are needed.
- **`classify()` has no composition hook** — its signature is positional. Either add a param
  (`taskRoot`/`protectedGlobs`, appended or as an options object) and new branches in the write/edit
  block, or **wrap** `classify()` in a Cadence module that post-processes its result. Wrapping keeps
  `policy.ts` pure/frozen but moves the rules outside `test:gate` — pick and record.

## Design — the Cadence policy (scoped to `/work/$CADENCE_TASK`)

| Cadence rule (`§6.2`) | Gate rule (tier) | Tools |
|---|---|---|
| `deny Write(../**)` | **deny** `edit`/`write` resolving outside `/work/$CADENCE_TASK/` | edit, write |
| `deny Write(./status.yaml)` | **deny** direct `edit`/`write` to `<task>/status.yaml` | edit, write |
| `deny Write(./.class.yaml)` | **deny** direct `edit`/`write` to any `*.class.yaml` | edit, write |
| "Bash scripts unrestricted by Write" | leave `bash` to the **existing** policy (gated scripts → `record`, dangerous ops still **deny**) | bash |

The asymmetry — agent's direct `edit`/`write` to protected paths denied, but `bash`-invoked
`set-status.py`/`edit-class-yaml.py`/`init-*.py` allowed to make those same writes — is the whole point:
it forces the agent through the state-machine enforcer.

> **Coverage limit (be honest):** the gate sees `bash` command *text*, not files a `bash` command
> writes. A mutation via `bash` redirection/`cp`/a script is not path-classified. Containment of
> `bash`-driven escapes comes from (a) the existing dangerous-op/`rm`/`/etc` rules and (b) the container
> boundary — not from this write-scope. State this; don't over-claim.

## Mode

`cadence-start` runs `GATE_MODE=enforce` — a **deliberate** departure from pi-harness's `record`
default (record wouldn't preserve the boundary). Per-project via the row (Ticket 02), not a global flip.
**Enforce makes fail-closed live:** `guard.ts`/`gate.ts` block on any handler throw, so the new rules
must be total (bad glob, null `CADENCE_TASK` → must not throw). Test the throw-paths.

## Work items

- [ ] Implement the Cadence rules (table) via the chosen seam (param vs wrapper); keep `policy.ts` pure.
- [ ] Consume Ticket 02a's `cwd=/work/$CADENCE_TASK` for **both** path resolution and the task-scope
      check; derive the protected globs (`status.yaml`, `*.class.yaml`) from it.
- [ ] **Probe before asserting** (host one-liner over `policy.ts`) for each case below.
- [ ] `gate.test.ts` cases through the **real gate in enforce mode**, with `workDir=/work/<task>`:
      - direct `edit`/`write` to `<task>/status.yaml` → **deny**
      - direct `edit`/`write` to a `*.class.yaml` → **deny**
      - `edit`/`write` resolving outside the task dir (e.g. `../foo`, `/etc/x`) → **deny**
      - `edit`/`write` within the task dir (`workpapers/x.csv`, `learned.md`) → **allow**
      - `bash python $CADENCE_PLUGIN_ROOT/scripts/set-status.py review_ready` → **record** (not `allow`)
      - regression: `rm` outside `/work`, `cat /etc/passwd` → still **deny**
      - throw-path: null/empty `CADENCE_TASK` and a malformed glob → handler does **not** throw (fails
        safe, not open) and the run isn't bricked.

## Acceptance

- `npm test` green incl. new cases; typecheck clean; `policy.ts` stays pure.
- The asymmetry demonstrably holds; a write one level above the task dir (still in `/work`) is now
  **denied** (it wasn't before this ticket).
- Live confirmation (real block without breaking a legit run) is Ticket 06.

## Notes

- Don't loosen pi-harness's existing global bash rules to fit Cadence — compose, don't weaken.
