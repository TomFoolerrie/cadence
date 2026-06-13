# Ticket 05: Stage-B verifier for a Cadence run (`verify-cadence.py`)

**Status:** TODO
**Repo:** pi-harness (the verifier script + `verifyCmd` wiring) — logic mirrors cadence's status machine
**Depends on:** 02, 03
**Source of truth:** pi-harness `verify-docx.py`/`verify-pptx.py` (the Stage-B pattern), `harness/package.json`;
this repo's `spec/03-status-machine.md`, `plugin/skills/start/SKILL.md`; `00-integration-design.md`
(§"Deliverable model").

## Goal

Give the `cadence-start` project a Stage-B verifier that checks the **result** of an autonomous
`/start` run (not the trace), the same way docx/pptx verifiers do. This is what turns "milestone 1" into
a mechanical pass/fail and is the verifier wired to `verifyCmd: "verify:cadence"`.

## Design — what a correct autonomous `/start` looks like, after the fact

Given the engagement at `/work` and the task `$CADENCE_TASK`, assert:

1. **Status reached a valid run-terminal state.** `status.yaml.status ∈ {review_ready, blocked,
   abandoned}` and the transition from the pre-run status is legal per `spec/03-status-machine.md`.
   (`review_ready` = success; `blocked`/`abandoned` = a *correct* headless outcome when the run hit a
   would-be-interactive branch — verify the reason is populated, don't fail the verifier for it.)
2. **Exactly one new git commit** for this invocation, with a `[start] <task> <period>: …` message
   matching the status outcome (`draft ready for review` ⇔ `review_ready`; `blocked — …` ⇔ `blocked`).
3. **On `review_ready`:** `periods/<period>/workpapers/` is non-empty (a draft was produced), and the
   task's `## Completion Criteria` (parsed from its `SKILL.md`) are at least structurally satisfiable
   (file(s) present). Deep, task-specific output validation stays the task's own concern.
4. **No out-of-scope mutation.** Cross-check the run's `audit.jsonl` (under `/runs/audit/<run_id>/`):
   **zero** `deny` tier entries, and no `edit`/`write` outside `/work/$CADENCE_TASK/`. This is where the
   pi-harness audit and the gate (Ticket 04) pay off — the verifier proves the boundary held.
5. **`status.yaml` was written only by `set-status.py`** (heuristic: no direct-edit deny in the audit
   for it; status content is well-formed per the schema).

Exit-code contract (match Cadence's + pi-harness's verifiers): `0` pass, `1` verification failure
(a real "this run was wrong"), `2` system/parse error.

## Work items

- [ ] Write `harness/verify-cadence.py` implementing checks 1–5. Parse YAML with the stdlib/`pyyaml`
      already available; read the audit JSONL from `$AUDIT_ROOT`/`/runs`. Reuse Cadence's own status
      transition table (import it, or vendor a tiny copy with a test that it matches
      `spec/03-status-machine.md`).
- [ ] Add `"verify:cadence": "python3 verify-cadence.py"` to `harness/package.json` (a one-time
      `--rebuild` since the script list is baked) and set `verifyCmd: "verify:cadence"` on the
      `cadence-start` row (Ticket 02).
- [ ] The verifier needs to know `$CADENCE_TASK` and the period — forward/derive them (period is read
      from `status.yaml`).
- [ ] Unit-test the verifier's pure pieces (transition legality, commit-message↔status matching, audit
      out-of-scope detection) against fixture inputs, no container needed — mirror how
      `test_extract.py` tests verifier internals host-side.

## Acceptance

- `./run --project cadence-start --task verify --work <dir>` exits `0` on a known-good run and `1` on a
  seeded-bad one (e.g. an injected out-of-scope write, a missing commit, or an illegal transition).
- Unit tests for the pure pieces green.
- Verifier is **base-image**-runnable (no Office toolchain): it needs only python3 + a YAML lib + git
  + file reads. Confirm those are in `Dockerfile.base`.

## Notes / risks

- Keep the verifier **result-oriented**, not trace-prescriptive: it checks the engagement + git + audit
  end-state, not that the agent took a specific path. Task-specific number-checking (e.g. "JE balances")
  belongs in the task's tooling/`SKILL.md`, not here.
- The audit cross-check (check 4) is the highest-value, lowest-cost assurance — it is the mechanical
  proof that Ticket 04's gate actually contained the run. Prioritize it.
