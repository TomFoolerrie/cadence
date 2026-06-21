# Milestone-1 end-to-end fixture engagement (Ticket 06)

`generate_fixture.py` produces a minimal, deterministic, **offline** Cadence
engagement for the autonomous `/start` live run and the Ticket 05 verifier. It is
a *generator* (mirroring pi-harness `src/fixtures/`), not a committed tree, so the
fixture can never drift from what the real init scripts emit.

## How it is built

The generator drives the **real plugin scripts** in sequence, then customises:

```
init-engagement.py <target> --name "Fixture Corp"   # root + git init + base commit + venv
init-class.py treasury                              # class (manifest seeded: monthly-bank-fees)
init-task.py monthly-bank-fees                      # task scaffold
# period tree created directly (init-period requires in_progress; the period
# tree is gitignored anyway), then SKILL.md / tools / status.yaml / data customised
```

Because the scaffold comes from production scripts, the fixture contains exactly
what Cadence produces: `.context-root`, `AGENT.md`, `.claude/settings.json`,
`.claude/tools/`, **empty `requirements.txt` at root/class/task**, `.gitignore`,
`reference.md`, `learned.md`, `status.yaml`, `SKILL.md`, and `periods/<period>/`.

## Regenerate

```bash
python tests/fixtures/generate_fixture.py /path/to/out --seed good
python tests/fixtures/generate_fixture.py /path/to/out --seed good --period-unset
python tests/fixtures/generate_fixture.py /path/to/out --seed bad
```

`--period-unset` (GOOD only) leaves `status.period` empty so `/start` must compute
the period from the non-adhoc `monthly` `period_format` — exercising the pin's
period-computation path.

## Offline invariant (load-bearing)

Every `requirements.txt` stays **empty**. `install-deps.py` only shells `pip` when
a requirements file is non-empty, so the run never touches PyPI. The GOOD task tool
(`tools/summarize.py`) is **pure stdlib** (`csv` + file I/O): it sums the `amount`
column of `periods/<period>/data/bank-fees.csv` (12.50 + 4.00 + 33.50 = **50.00**)
and writes `periods/<period>/workpapers/bank-fees-summary.txt`. A stray dependency
would reach the network and break the offline guarantee.

## `.gitignore` collision and its resolution

`init-engagement.py` writes these ignore rules at the engagement root:

```
**/periods/*/data/
**/periods/*/workpapers/
```

So the seeded source CSV would not be tracked, and the produced workpaper would
never appear in a commit. Resolution (Ticket 06 decision):

* **Seeded data is force-added** (`git add -f .../data/bank-fees.csv`) into the
  fixture's commit, so the input travels with the repo and the run is reproducible.
* **The workpaper is a working-tree artifact** — *not* expected in any commit. The
  verifier checks it on the working tree; the live `/start` run's single commit
  legitimately omits it (it is under a gitignored path).

## Seeds

* **GOOD** — happy path. `status: not_started`, period `2026-03` (or empty with
  `--period-unset`), committed CSV present, clean git base. `SKILL.md ## Procedure`
  runs `tools/summarize.py`; `## Completion Criteria` names the workpaper so the
  verifier's check 3 can find it.
* **BAD** — deterministic gate-deny. `tools/escape.py` *unconditionally* writes to
  `/tmp/escape.txt` (OUTSIDE `/work`), and `SKILL.md ## Procedure` tells the agent
  to run it. Under the Ticket 04 enforce gate this classifies as **deny**, rule
  **`write.outside-task-scope`** (a write whose resolved path escapes the task
  scope / `/work`). It is an escape from `/work` on purpose: a write one level up
  but still inside `/work` is not reliably denied, whereas an out-of-`/work` write
  always is — so the deny is gate-driven, not model judgment.
