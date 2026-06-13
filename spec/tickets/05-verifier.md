# Ticket 05: Stage-B verifier for a Cadence run (`verify-cadence.py`)

**Status:** TODO (revised 2026-06-13 after review)
**Repo:** pi-harness (verifier + `verifyCmd`) — logic mirrors cadence's status machine
**Depends on:** 02, 02a, 03 (and 04 for the enforce-mode checks to be meaningful)
**Source of truth:** pi-harness `verify-docx.py`/`verify-pptx.py` (the Stage-B pattern + exit codes),
`harness/package.json`, `harness/gate/audit.ts` (the `audit.jsonl`/`manifest.json` format),
`harness/session-setup.ts` (run_id minting, AUDIT_ROOT), `harness/Dockerfile.base`; this repo's
`spec/03-status-machine.md`, `plugin/skills/start/SKILL.md` (commit formats), `plugin/scripts/set-status.py`
(`VALID_TRANSITIONS`); `00`.

## Goal

A result-oriented Stage-B verifier (`verifyCmd: "verify:cadence"`) that turns milestone 1 into a
mechanical pass/fail by checking the end-state of an autonomous `/start` run.

## Prerequisites review surfaced (must land first)

- **`Dockerfile.base` has neither `pyyaml` nor `git`** — the verifier reads `status.yaml` and `git log`.
  Ticket 02 adds both; this ticket depends on that (or the verifier parses YAML stdlib-only). The
  verifier runs under the **base image's system python at `/app`**, not the engagement venv.
- **A pre-run baseline must be captured** (see check 1/2) — nothing records it today. Add it in the host
  entrypoint/manifest (see work items).
- **Audit-dir discovery:** `run_id` is a runtime timestamp+suffix; the verifier isn't handed it. Define
  "the newest run dir under `/runs/audit/`" (lexically-max / newest mtime) explicitly.

## Checks (revised)

1. **Terminal status valid + (if baseline available) transition legal.** `status.yaml.status ∈
   {review_ready, blocked, abandoned}`. If the host captured the **pre-run status** (work item), assert
   the transition is legal per `03-status-machine.md`; otherwise assert only that the terminal status is
   a valid run-terminal state (don't claim transition-legality without the baseline). `blocked`/
   `abandoned` with a populated reason is a **correct** headless outcome — don't fail on it.
2. **Commit count + message.** With a captured **pre-run HEAD**, assert **exactly one** new commit
   whose message matches the outcome. Without it, assert the **latest** commit matches and drop "exactly
   one." Match on the suffix token after `: ` — `draft ready for review` (⇔ review_ready) /
   `blocked` / `abandoned` (the em-dash `—` is free-text; match the keyword, include `abandoned`).
3. **On `review_ready`:** `periods/<period>/workpapers/` non-empty; the task's `## Completion Criteria`
   (parsed from its `SKILL.md`) are structurally satisfiable (files present). Deep number-checking stays
   the task's concern.
4. **No out-of-task `edit`/`write` + no `deny` (enforce).** Scan the newest `audit.jsonl`: zero
   `tier=="deny"`; every `edit`/`write` record's `file.path`, **resolved against the manifest's `cwd`
   exactly as the gate does**, lands inside `/work/$CADENCE_TASK/`. **Known blind spot:** `file.path` is
   recorded only for the `edit`/`write` tools — `bash`-driven file mutations are invisible here;
   containment of those is the gate's enforce denial + the container, not this check (state it).
5. **Status content well-formed per schema.** *(Reframed — review found the old "written only by
   set-status.py" check is trace-prescriptive and vacuous in record mode.)* Just validate `status.yaml`
   against its schema. The "only `set-status.py` writes it" guarantee is **Ticket 04's enforce-mode
   denial of direct status.yaml edits**, proven there, not re-inferred from the trace here.

Exit codes: `0` pass, `1` verification failure, `2` system/parse error.

## Work items

- [ ] **Host entrypoint captures a pre-run baseline** for `cadence-start`: pre-run `git rev-parse HEAD`
      and pre-run `status.yaml.status`, written into the manifest (or a side file under `/runs`). Without
      this, checks 1–2 degrade to the weaker "latest commit/terminal status" form — decide if that's
      acceptable for milestone 1 or do the capture.
- [ ] Write `harness/verify-cadence.py` (checks 1–5), discovering the newest run dir, resolving
      `file.path` against the manifest `cwd`.
- [ ] Add `git` + `pyyaml` to `Dockerfile.base` (shared with Ticket 02) **or** parse YAML stdlib-only.
- [ ] `package.json`: `"verify:cadence": "python3 verify-cadence.py"` (one-time `--rebuild`); set
      `verifyCmd` on the row (Ticket 02). Forward `$CADENCE_TASK`; read period from `status.yaml`.
- [ ] Vendor a tiny copy of `VALID_TRANSITIONS` (set-status.py:21–30) **with a test asserting it matches
      `03-status-machine.md`** (can't cleanly import a cadence venv module from pi-harness).
- [ ] Unit-test the pure pieces (transition legality, commit-message↔status match incl. `abandoned`,
      audit out-of-scope detection, manifest-cwd path resolution) host-side, like `test_extract.py`.

## Acceptance

- `./run --project cadence-start --task verify --work <dir>` → `0` on a good run, `1` on a seeded-bad
  one (out-of-task `edit`/`write`, missing/mis-messaged commit, illegal/invalid terminal status).
- Unit tests green; verifier runs under the base image (git + YAML available).

## Notes

- Keep it **result-oriented**. Check 4's audit cross-check is the highest-value, lowest-cost assurance
  that Ticket 04's gate contained the run — prioritize it, while being honest about its `bash` blind spot.
