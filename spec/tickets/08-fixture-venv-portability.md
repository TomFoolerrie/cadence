# Ticket 08: Portable fixture venv + `install-deps` empty-requirements short-circuit (Finding 1)

**Status:** DONE (2026-07-04) — install-deps short-circuit + fixture ships no host venv; GOOD seed reaches review_ready with zero denies. Verified live: dry-run-cadence-on-pi-harness-2026-07-04.md.
**Repo:** cadence (branch `claude/quirky-ptolemy-htwb4n`)
**Depends on:** 01, 03 (transitively 00); blocks **06** (its GOOD-seed happy path)
**Source of truth:** `notes/dry-runs/dry-run-cadence-on-pi-harness-2026-07-03.md` §"Finding 1";
`plugin/scripts/install-deps.py` (top-of-`main()` pip-resolution block, lines 64–75 — `venv_pip`
resolve at 65, `return 2` at 75; `should_install`, lines 33–38; `req_paths` build, lines 80–92;
skip-empty loop, lines 93–100), `plugin/scripts/init-venv.py` (idempotent `venv/bin/python.exists()`
short-circuit at line 39, `sys.executable -m venv` at line 44), `plugin/scripts/start-setup.py`
(step 1.5 init-venv, lines 89–94; step 2 install-deps, lines 96–102),
`plugin/scripts/init-engagement.py` (it is the script that actually builds the venv — calls
`init-venv.py` at lines 152–163; also writes `venv/` into the root `.gitignore` at line 33),
`tests/fixtures/generate_fixture.py` (step 1 base build calls `init-engagement.py` at line 347;
force-add + commit at lines 400–410), `tests/test_install_deps.py`, `tests/test_e2e_fixture.py`,
`tests/test_start_setup.py`, `tests/conftest.py` (`make_context_root` seeds an **empty**
`requirements.txt`, line ~213).

## Why this blocks the milestone

The GOOD live run never reached `review_ready`. It self-blocked in Stage-A setup with
`status: blocked`, `issues: [No venv found at /work/venv/ and no system pip available]`, one **blocked**
commit, no workpaper — so the Ticket-06 verifier exits 1. Two defects combine:

1. **Non-portable fixture venv (the load-bearing defect).** `generate_fixture.py` → `init-engagement.py`
   → `init-venv.py` builds a real venv at the engagement root **on the host**. `init-venv.py` runs
   `sys.executable -m venv` (line 44), so the interpreter symlinks + `pyvenv.cfg` point at the host
   Python (macOS 3.9). Mounted into the Debian/arm64 container that venv is unusable, and
   `start-setup.py` step 1.5's re-`init-venv` no-ops because `venv/bin/python` already **exists**
   (`init-venv.py` line 39 → idempotent return 0), so it never repairs it.
2. **`install-deps.py` hard-requires a pip binary even when nothing is installable.** The top-of-`main()`
   pip-resolution block (lines 64–75) resolves `venv/bin/pip`, falls back to `shutil.which("pip"/"pip3")`,
   and `return 2`s when neither exists — **before** the `req_paths` build (lines 80–92) and the
   `should_install()` loop (lines 93–100) that skips empty/missing requirements. So the Ticket-06
   "empty requirements ⇒ install-deps is a no-op" invariant is **false**: it no-ops the pip *install call*,
   not the pip *exists precondition*. An engagement whose every `requirements.txt` is empty (exactly the
   offline fixture) still dies at `return 2`.
   (Confirmed against code 2026-07-03: `main()` orders the pip precondition strictly before the
   empty-requirements check — the empty case is **not** short-circuited first, so the ticket's premise is
   accurate.)

## Work items

- [ ] **`install-deps.py`: short-circuit "nothing installable" to success before requiring pip.**
      Reorder `main()` so the `req_paths` list (root/class/task requirements, currently lines 80–92) is
      built **before** the pip-resolution block (currently lines 64–75). If **none** of the paths
      `should_install()` (all empty or absent), `return 0` immediately. Only run the pip-resolution
      block (and its `return 2`) when there is at least one non-empty requirements file. This requires
      moving `detect_level()`/`req_paths` construction above the pip resolve; `find_context_root` stays
      first (its `return 1` on no `.context-root` is unchanged). Preserve the existing `return 2` for the
      real case (a non-empty requirements file and no pip). Keep exit-code contract intact
      (0 success / 1 validation / 2 system).
- [ ] **Fixture must not ship a host-built venv.** The venv is built by `init-engagement.py`
      (lines 152–163, which shells `init-venv.py`), invoked from `generate_fixture.py` step 1 (line 347).
      Stop the base build from leaving a host venv on disk under `<root>/venv/` (that dir is mounted into
      the container as `/work/venv`). Pick and document one:
      - (a) **Omit the venv** — after `generate_fixture.py` step 1, delete `<root>/venv/` (simplest: an
        `shutil.rmtree(target / "venv", ignore_errors=True)` in the generator, since `init-engagement.py`
        is shared production code and should not be changed just for the fixture). `venv/` is already in
        the root `.gitignore` (init-engagement line 33), so it is never in the base commit — deleting the
        on-disk dir is a no-op to git and cannot affect the commit or the `git add -f` data seeding. With
        the `install-deps` fix above, the empty-requirements engagement needs no venv at all; step 1.5 can
        rebuild in-container if a future fixture ever needs deps. This is the minimal, offline-clean option.
      - (b) **Build in-container** — leave venv creation to `start-setup.py` step 1.5 inside the
        container (host-side generation skips it). Heavier; only needed if a fixture ever ships deps.
      Recommend (a) for milestone 1 (empty-requirements, pure-stdlib task tool). Update the generator
      docstring's OFFLINE INVARIANT section and `tests/fixtures/README.md` to state the venv is
      deliberately absent and why.
- [ ] **Decide `init-venv.py` idempotence vs. portability.** Note (do not necessarily fix here) that a
      host-built venv is silently trusted by the `venv/bin/python.exists()` check; if option (b) is
      chosen, `init-venv.py` must detect a stale/foreign venv (e.g. `pyvenv.cfg` home mismatch) rather
      than no-op. If option (a), record that this is out of scope.
- [ ] **Tests.**
      - `tests/test_install_deps.py`: add a case asserting that with **no venv and no system pip** but
        **all requirements empty/absent**, `main()` returns **0** (regression for the exact live
        failure). Simulate "no system pip" by monkeypatching `shutil.which` to return `None` (or by
        running the reordered code so the pip block is never reached when nothing is installable).
      - **`tests/test_install_deps.py::TestPreconditions::test_falls_back_to_system_pip_when_no_venv`
        (line ~114) asserts the CURRENT buggy behavior and WILL BREAK under this fix — it must be
        updated.** Today it calls `make_context_root` (which seeds an **empty** `requirements.txt`, per
        `conftest.py`) with no venv and asserts `returncode == 0` **and** `"No venv found"` /
        `"using system pip"` in stderr. After the short-circuit, empty requirements return 0 **without
        ever resolving pip**, so those stderr strings vanish and the assertion fails. Fix: give this test
        a **non-empty** `requirements.txt` (e.g. a comment-only or already-installed dep like `pip`) so it
        genuinely exercises the pip-fallback path it is meant to cover — then it still returns 0 and still
        prints the fallback messages. Add a **separate** case for the empty-requirements short-circuit.
      - There is currently **no** "non-empty requirements + no pip ⇒ 2" test; add one so the preserved
        `return 2` path is covered (non-empty `requirements.txt`, `shutil.which` → `None`, no venv ⇒ 2).
      - `tests/test_e2e_fixture.py`: assert the generated GOOD fixture has **no** `venv/` at the root
        (option a), and that the existing offline `start_setup` dry-run still reaches
        `status: in_progress` and produces the balanced workpaper (`total: 50.00`).
      - `tests/test_start_setup.py`: assert step 2 no longer blocks when the venv is absent and
        requirements are empty (start-setup step 1.5 init-venv is already non-fatal, so with the
        install-deps fix the sequence should reach load-context and exit 0).

## Acceptance

- Re-running **Ticket 06** GOOD seed (`generate_fixture.py … --seed good` then the two `./run`
  commands): `/start` reaches `status: review_ready`, `issues: []`; exactly one **review-ready** commit
  (not "blocked"); the workpaper is present on the working tree (`total 50.00`); no pip/network tool
  call in the audit; verifier exits 0; **zero** `deny` records in the GOOD audit.
- `python -m pytest tests/` green (the suite is ~326 today; the one pre-existing date-sensitive failure
  in `test_e2e_period_reset.py` is unrelated and may remain). New install-deps / fixture / start-setup
  cases pass.

## Notes / risks

- The `install-deps` short-circuit is the cheap guard that would have let this exact fixture pass; the
  no-host-venv change is the real fix. Do **both** — a future fixture with deps still needs a portable
  venv path, and the short-circuit keeps the empty-deps offline invariant honestly true.
- Option (a) changes what the fixture commits (no `venv/`, already git-ignored so likely a no-op to the
  base commit) — confirm the base commit + `git add -f` data seeding are unaffected.
- Do not introduce any network path — the offline invariant (no PyPI) is load-bearing for the billed run.
