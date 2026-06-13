# Ticket 04: Write-scope → gate enforce policy (the load-bearing ticket)

**Status:** TODO
**Repo:** pi-harness (branch `claude/quirky-ptolemy-htwb4n`)
**Depends on:** 02
**Source of truth:** pi-harness `harness/gate/policy.ts`, `gate/gate.ts`, `gate/guard.ts`,
`gate/gate.test.ts`, `spec/pi-skill-harness.md` §9; this repo's `spec/06-separation-of-concerns.md`
(§6.2 Write Scope Enforcement); `00-integration-design.md`.

## Why this is the load-bearing ticket

Cadence's reliability rests on **hard boundaries, not instructions**. Its own dry runs proved the
agent *bypasses* a procedure that only tells it to use the gated scripts — after a long session it
hand-edited `.class.yaml` directly despite explicit instructions (`notes/open-items.md`, "Post-Dry-Run
Review"). Claude Code's fix was the `.claude/settings.json` write-scope deny rules. **Pi does not honour
`.claude/settings.json`.** So if we run Cadence under Pi with the gate in its default *record* mode
(logs, blocks nothing), we silently regress Cadence's most important invariant. Preserving the hard
boundary across the runtime swap **is** the integration's security story.

pi-harness already has everything needed: **enforce mode is implemented and tested** (`GATE_MODE=enforce`,
`gate.ts` returns `{block:true}` on a deny, `guard.ts` fails closed), and `policy.classify()` already
takes a `cwd`. This ticket authors the *Cadence policy* and runs enforce mode for `cadence-start`.

## Design — map the `.claude/settings.json` deny rules to gate rules

The Cadence write-scope, per `spec/06-separation-of-concerns.md` §6.2, for a **task agent**:

```json
{ "permissions": {
    "allow": ["Read", "Write(./**)"],
    "deny":  ["Write(../**)", "Write(./status.yaml)"] } }
```

Translate to gate policy, scoped to the **active task dir** (`/work/$CADENCE_TASK`):

| Cadence rule | Gate rule (tier) | Applies to tools |
|---|---|---|
| `deny Write(../**)` (no writes above the task dir) | **deny** any `edit`/`write` whose resolved path is outside `/work/$CADENCE_TASK/` | `edit`, `write` |
| `deny Write(./status.yaml)` (must use `set-status.py`) | **deny** direct `edit`/`write` to `<task>/status.yaml` | `edit`, `write` |
| (class-level) `deny Write(./.class.yaml)` | **deny** direct `edit`/`write` to any `*.class.yaml` | `edit`, `write` |
| "Bash scripts are NOT restricted by Write permissions" | **allow** `bash` invoking `$CADENCE_PLUGIN_ROOT/scripts/*.py` (these are the gated writers) — subject to pi-harness's existing bash safety rules (the `/etc`,`/dev`, out-of-`/work` `rm` denies still apply) | `bash` |

**The crucial fidelity point:** in Cadence, the gated scripts (`set-status.py`, `edit-class-yaml.py`,
`init-*.py`) *do* write `status.yaml`/`.class.yaml`/parent dirs — they are infrastructure with their
own filesystem authority, invoked via `Bash`, which Claude Code's Write-scope does not restrict. The
gate must reproduce exactly this asymmetry: **deny the agent's direct `edit`/`write` to protected
paths, but allow `bash`-invoked scripts to do those same writes.** This is the whole point — it forces
the agent through the state-machine enforcer instead of hand-editing YAML.

### How the active scope reaches the policy

`gate.ts` already passes the live `WORK_DIR` as `cwd` to `classify()`. Extend the forwarded config with
the **active task subdir** and the **protected-file globs** (from Ticket 02's `CADENCE_TASK`). Decide
the cleanest seam — preferred: a small Cadence policy layer / rule set keyed off a forwarded
`CADENCE_TASK` (+ derived protected paths), composed with the existing global policy rather than
editing the shared classifier's core. Keep `policy.ts` pure and host-testable (its tests are its
contract).

### Mode

`cadence-start` runs `GATE_MODE=enforce` (set by Ticket 02's row/forwarding). This is a **deliberate
departure** from pi-harness's default `record` — and it must be, because record mode would not
preserve Cadence's hard boundary. Document this prominently in the row and in `00`.

## Work items

- [ ] Author the Cadence gate rules (the table above) as a composable policy layer; keep the core
      classifier pure.
- [ ] Forward `CADENCE_TASK` (+ derived protected globs) from the host entrypoint → `session-setup.ts`
      → `gate.ts` → `classify()` (Ticket 02 forwards the env; this ticket consumes it in the policy).
- [ ] Run `cadence-start` in **enforce** mode; ensure `guard.ts` fail-closed semantics hold and the
      record-mode handler-totality rule (catch/record/never-throw) is respected.
- [ ] **Probe before asserting** (pi-harness discipline): use the host one-liner
      `node --import tsx -e "import('./gate/policy.ts').then(...)"` to verify real classification of each
      case before writing the test.
- [ ] Add `gate.test.ts` cases proving, through the **real gate in enforce mode**:
      - direct `edit`/`write` to `<task>/status.yaml` → **deny**;
      - direct `edit`/`write` to a `*.class.yaml` → **deny**;
      - `edit`/`write` to a path above the task dir → **deny**;
      - `edit`/`write` **within** the task dir (e.g. `workpapers/…`, `learned.md`) → **allow**;
      - `bash python $CADENCE_PLUGIN_ROOT/scripts/set-status.py review_ready` → **allow**;
      - the pre-existing global denies (`rm` outside `/work`, `cat /etc/passwd`) still **deny**
        (no regression of pi-harness's baseline).

## Acceptance

- `npm test` (pi-harness) green incl. the new `gate.test.ts` cases; typecheck clean; `policy.ts` stays
  pure (no I/O).
- The asymmetry is demonstrably correct: agent can't touch `status.yaml`/`.class.yaml`/parent dirs
  directly, but the gated scripts can — exactly reproducing `.claude/settings.json` §6.2.
- Live confirmation (gate actually blocking a real over-reach without breaking a legitimate run) is
  Ticket 06.

## Notes / risks

- **False-positive risk** is the thing to watch — pi-harness already hit two record-mode false
  positives (a bare relative `edit` path; `rm -rf /work/unpacked`) and fixed them with `cwd` resolution
  + path-scoping. Re-use that hard-won approach: resolve the agent's relative `edit`/`write` path under
  `/work/$CADENCE_TASK` before classifying, or a legitimate `workpapers/foo.csv` write will be denied.
- Do **not** weaken pi-harness's existing global bash rules to make room for Cadence; compose, don't
  loosen.
