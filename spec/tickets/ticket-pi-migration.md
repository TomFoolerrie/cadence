# Ticket: Pi migration — two tracks, one repo

**Status:** IN PROGRESS — Phases 1–5 + 7 done and host-verified; **only Phase 6 (the live dry-run-3 on a non-Anthropic model) remains** — it needs Pi + a key + a billed run, so it stays out of `Complete/` until that one run passes (same posture as the sibling pi-harness ticket).
**Source of truth:** [`spec/pi-migration.md`](../pi-migration.md) (detailed spec — the *how*) and [`notes/v2+/pi-migration-plan.md`](../../notes/v2+/pi-migration-plan.md) (the planning doc — the *why*).

> **Rollup (updated 2026-06-03).** **Phases 1–5 + 7 are BUILT and host-verified;
> only Phase 6 (the billed live dry run) remains.** The two-track layout is real:
> shared `scripts/`+`skills/` under `claude/` (assembled Cowork plugin) and `pi/`
> (the `tool_call` gate), with the Pi package declared by the root `package.json`
> `pi` key. Write-scope enforcement is two mechanisms over one boundary —
> `settings-gen.py`+`CADENCE_TRACK` on Claude, the in-process gate on Pi (which
> also gates Bash). Verified WITHOUT a billed run: **310 pytest green** (unit +
> `tests/claude/` + `tests/pi/`) and **22 TS gate tests + a clean typecheck**, and
> the extension + all 4 skills load through the **real Pi 0.75.4 machinery**
> (`loadExtensions` errors:[], `loadSkillsFromDir` no diagnostics). Every external
> dependency was already confirmed against primary sources (Pi runtime API, the
> root-`package.json` manifest, Cowork's no-`../` rule). Every phase ended with the
> working Claude lane green. **What's left:** Phase 6 — a `/onboard`→`/done`→
> `check-periods`→`/start` lifecycle on Pi with a NON-Anthropic model — needs Pi +
> a key + one billed run, so this ticket stays in `Tickets/` (not `Complete/`)
> until that passes, mirroring the sibling pi-harness ticket's posture.

**Motivation:** Cadence runs only on Claude/Cowork today. Every entry point
(skills, write-scope enforcement, context loading, MCP routing) is wired to
Anthropic's plugin system, so there is no model freedom and a single-vendor
break risk. Cadence's core philosophy — *the folder is the memory, not the
agent* — is runtime-agnostic by design; only the harness coupling stands in the
way.

## Goal

Run Cadence on the **Pi** agent harness ([earendil-works/pi](https://github.com/earendil-works/pi))
as a first-class second track, **keeping the Claude/Cowork track working
unchanged**, with the skills + scripts + spec + unit tests **shared** below a thin
per-track glue layer. The Pi track gains a programmable `tool_call` gate that is
*stronger* than Cowork's static `settings.json` — it can gate Bash, which Cowork
cannot. Two tracks, one repo, one shared spine.

**Non-goals (this ticket):** simultaneous portability (the same engagement folder
under both harnesses in parallel); the Symphony unattended-execution lane (planning
doc §8, deferred); `.class.yaml` v2 (separate plan, sequenced after this).

## Open questions — all resolved (recorded in `spec/pi-migration.md` §2 + §6)

- **Q3 (init-script harness awareness)** → `CADENCE_TRACK` env var (default
  `claude`); init scripts emit `.claude/` only on the claude track, via
  `settings-gen.py`. Pi track needs no per-dir glue (gate self-configures from cwd).
- **Q4 (venv/requirements)** → unchanged on Pi; only needs `python`/`python3`/`pip`
  in the §3b bash whitelist.
- **Q5 (Cowork packaging)** → Claude Code plugin paths must start with `./` and
  cannot escape with `../` → the Claude track **assembles** `scripts/` + `skills/`
  under its plugin root at package time.
- **Q6 (Pi distribution)** → a `pi` key in the **repo-root `package.json`**
  (`{ "pi": { "extensions": ["./pi/extension"], "skills": ["./skills"] } }`); **not**
  a `pi/plugin.json`. Pi references the shared top-level `skills/` directly.

## Grounding facts (de-risk the build; verified against the code)

1. **No Python script reads `CLAUDE_PLUGIN_ROOT`/`os.environ`** — they walk up
   from cwd. The scripts are already harness-agnostic; no path-handling refactor.
2. **The only harness-specific behaviour in the scaffolders is generating
   `.claude/`** — `init-engagement.py` (`.claude/tools/` + allow-only
   `settings.json`), `init-class.py`, `init-task.py`. `load-context.py` also
   *reads* `root/.claude/tools` (the one harness-specific read).
3. **Engagement folders are external** and reference scripts via runtime-resolved
   `${CLAUDE_PLUGIN_ROOT}` — the restructure cannot break them as long as the
   assembled plugin root contains `scripts/`.

---

## Phase 1 — In-place cleanups (no structural move)  ← the safe first commit

> **STATUS: DONE (2026-06-03).** All three cleanups landed; suite green at
> **304 passed** (the original 299 + 5 new `decide_reset` predicate tests). The
> `AGENT.md→AGENTS.md` grep sweep is clean outside `notes/` and the two
> migration meta-docs (which quote the literal as the rename *instruction*).
> One incidental fix: `test_e2e_period_reset.py::test_done_then_check_periods_resets`
> was a latent **date-bomb** — `start_to_done` stamps `done_at` from the wall
> clock, so once the real date passed the test's `as_of` the late-completion
> guard fired an extra hop and the asserted reset period drifted. Pinned that
> test's `done_at` to a deterministic on-time value; the other period-reset
> tests assert only status (or set `done_at` explicitly) and were already
> robust. Host-verifiable with pytest alone; no Pi, no key.

**Why first:** these are harness-neutral improvements that shrink the later
diffs and carry zero restructure risk. Land as one reviewable commit.

- [ ] **`AGENT.md` → `AGENTS.md` repo-wide.** Drive off `grep -rl 'AGENT\.md'`
      (the sweep is the source of truth, not a hand-list). Today that is: the file
      in `engagement-template/`; `load-context.py` (read path); `init-engagement.py`
      + `init-class.py` (write path); the shared skill body
      `plugin/skills/onboard/SKILL.md` (8 refs, incl. write instructions); **all 10
      spec files** that mention it; and every test asserting the filename. Re-run the
      grep after to confirm zero residual `AGENT.md` (excluding deliberate historical
      mentions in `notes/`).
- [ ] **Drop `version:`** from `plugin/skills/{onboard,start,done,status}/SKILL.md`
      frontmatter (currently `1.0.0`) and from `init-task.py`'s `SKILL_MD_TEMPLATE`
      (emits `0.1.0`). Pi requires only `name` + `description` — both already present.
- [ ] **`check-periods.py` library refactor (non-trivial extraction).** The pure
      period-math helpers (`next_period_string`, `compute_anchor_date`) are already
      module-level, but the "is this task due" decision is currently **inline in
      `main()`'s nested loop** (lines ~187–273), entangled with the filesystem walk,
      the late-completion guard, the YAML write, and the per-class git commit.
      Separate the filesystem walk from a **pure due-predicate** function, make the
      predicate importable, and reduce the CLI to a thin wrapper. Add a direct unit
      test for the predicate. (Symphony hedge + `.class.yaml` v2 foundation.)

**Verify Phase 1:** `python -m pytest tests/` — all 299 green; `grep -rl 'AGENT\.md'`
clean outside `notes/`; the new `check-periods` function has a direct unit test.

## Phase 2 — Restructure to the two-track layout

> **STATUS: DONE (2026-06-03).** `plugin/scripts` + `plugin/skills` hoisted to
> top-level `scripts/` + `skills/`; the Cowork manifest moved to
> `claude/plugin/.claude-plugin/plugin.json`; `pi/extension/` created; `tests/`
> split into `unit/` + `claude/` + `pi/` with the shared `conftest.py` kept at
> the `tests/` root (avoids the duplicate-conftest import pitfall). The
> assemble-on-package step is `claude/assemble.py` — it symlinks (or `--copy`s)
> the shared `scripts/`/`skills/` under `claude/plugin/` as `./scripts`/`./skills`
> (gitignored, never hand-maintained), so `${CLAUDE_PLUGIN_ROOT}` resolves to a
> dir containing `scripts/`. The settings.json-asserting tests still live in
> `tests/unit/` for now; Phase 3 relocates them to `tests/claude/`. Suite green
> at **304 passed** from the new locations.

**Target layout** (planning doc §2, with the Q6 manifest correction):

```
cadence/
├── skills/        SHARED — the 4 SKILL.md procedure bodies
├── scripts/       SHARED — the 14 Python scripts (harness-agnostic)
├── spec/          SHARED
├── tests/         SHARED, split: unit/ (neutral) + claude/ + pi/
├── scripts/       SHARED — incl. settings-gen.py (claude-track-only, but shared so it ships in the plugin root)
├── pi/            Pi glue — extension/ (the tool_call gate)
├── claude/        Claude glue — plugin/ (assembled) + assemble.py
├── package.json   ROOT — carries the "pi" manifest key (Q6)
└── engagement-template/, notes/, docs/, pyproject.toml
```

- [ ] Move `plugin/` → `claude/plugin/`; hoist `skills/` + `scripts/` to top level;
      create empty `pi/`; split `tests/` → `unit/` + `claude/` + `pi/`.
- [ ] **Assemble step (Q5):** a thin build/symlink step that places top-level
      `scripts/` + `skills/` under `claude/plugin/` as `./scripts`/`./skills`, so
      `${CLAUDE_PLUGIN_ROOT}` resolves to a dir containing `scripts/` (the one hard
      invariant). Never hand-maintain the assembled copy.
- [ ] Update `tests/unit/` imports to the hoisted script locations; keep `tests/unit/`
      harness-neutral (no `settings.json` assertions — those move to `tests/claude/`
      in Phase 3).

**Verify Phase 2:** all 299 tests green from the new locations; the assembled
`claude/plugin/` resolves `set-status.py` etc. exactly as before; an existing
engagement folder (or `engagement-template/`) still runs unchanged.

## Phase 3 — Settings generation + `CADENCE_TRACK` (Q3) + global-tools re-home

> **STATUS: DONE (2026-06-03).** `scripts/settings-gen.py <dir> <level>` carries
> the three permission blocks; all three init scripts are `CADENCE_TRACK`-aware
> (unset → `claude`; tail-call `settings-gen.py` only on the claude track, emit
> no `.claude/` on `pi`). Global tools re-homed from `.claude/tools/` to a
> track-neutral `root/tools/`, read by `load-context.py` on both tracks. The
> settings.json assertions moved out of `tests/unit/` into a new
> `tests/claude/test_settings_enforcement.py` (per-level content + settings-gen
> idempotency/validation); `tests/pi/test_no_claude_artifacts.py` asserts the
> `CADENCE_TRACK=pi` no-`.claude/` contract at all three levels + global-tools
> survival. `run_script` gained an `env=` param. **Location note:** the spec
> said `claude/settings-gen.py`, but it must live in the **shared `scripts/`**
> dir to ship inside the assembled plugin root (`claude/` is not distributed) —
> spec §2/§4 updated to match. Suite green at **310 passed**.

- [ ] **`scripts/settings-gen.py <dir> <level>`** (shared dir — ships inside the
      assembled plugin root; `claude/` is not distributed) carrying the exact
      `permissions` blocks currently inlined in the three scaffolders:
      `init-engagement.py` (root — allow-only, no deny), `init-class.py` (deny
      `Write(../**)`, `Write(./.class.yaml)`), `init-task.py` (deny `Write(../**)`,
      `Write(./status.yaml)`). Idempotent.
- [ ] **Make all three init scripts `CADENCE_TRACK`-aware:** drop the inline
      `.claude/` generation; tail-call `settings-gen.py` **only when
      `CADENCE_TRACK=claude`** (unset defaults to `claude` — backward compatible).
      On `pi`, emit no `.claude/` at any level. A non-zero `settings-gen.py` exit is a
      system error (exit 2); the scaffold already wrote (documented
      partial-but-recoverable case).
- [ ] **Re-home global tools (S3):** `init-engagement.py` creates `root/.claude/tools/`
      and `load-context.py` reads it. Move to a **track-neutral `root/tools/`** read by
      `load-context.py` on both tracks; update the tool resolution order
      (task → class → global) accordingly.

**Verify Phase 3:** `tests/claude/` asserts `CADENCE_TRACK=claude` emits the right
per-level `settings.json`; a new test asserts `CADENCE_TRACK=pi` emits **no**
`.claude/`; `settings-gen.py` idempotency test; global-tools loading works under
both tracks. All 299 still green.

## Phase 4 — Build the Pi extension (the tool_call gate) + Pi manifest

> **STATUS: DONE (2026-06-03).** Built `pi/extension/policy.ts` (pure, SDK-free
> classifier — the security-critical core), `scope-gate.ts` (the
> `ExtensionFactory` on `pi.on("tool_call")`, fail-open), and `index.ts`
> (`export default makeScopeGate()` — the loader takes the module's default
> export). Added the `pi` manifest to a new **root `package.json`**
> (`extensions: ["./pi/extension"]`, `skills: ["./skills"]`). The factory sets
> `process.env.CADENCE_TRACK = "pi"` so bash children skip `.claude/`. **Bash
> whitelist derived from the sweep** — beyond the spec draft it adds `cd` +
> `source` (skills emit `cd <dir> && …` and `source <root>/venv/bin/activate &&
> …`); gate keys on the `git` HEAD (not a subcommand allowlist), and banned
> patterns scan the whole command so a compound can't smuggle one in.
> **Verified against the REAL Pi machinery (0.75.4, installed as a devDep):**
> `loadExtensions(["./pi/extension"])` → `errors: []`, 1 extension loaded;
> `loadSkillsFromDir({dir:"skills"})` → all 4 skills, no diagnostics (confirms
> Q6 "no assembly on Pi" + that dropping `version:` didn't break loading).
> `npm run test:gate` = 22 green; `npm run typecheck` clean. Remaining for a
> live run (Phase 6): `pi install git:…` + a billed model turn.

**Reuse prior art:** the sibling `pi-harness` `gate/gate.ts` is the verified
reference for the Pi `tool_call` event shape (`{toolName, input, toolCallId}` →
`{block, reason}`) and the throwing-handler-blocks fail-safe.

- [ ] **`pi/extension/scope-gate.ts`** — an `ExtensionFactory` registering
      `pi.on("tool_call", …)` (spec §3):
  - [ ] **§3a Edit/Write gate** (replaces `settings.json`): block writes outside
        the agent root (the `Write(../**)` rule) and direct writes to the gated file
        (`detectGate(cwd)` → `.class.yaml` xor `status.yaml`), with a corrective
        `reason` that tells the agent the right tool/script. Maps one-to-one onto the
        two `settings.json` deny rules.
  - [ ] **§3b Bash gate** (NEW — impossible on the Claude track): head whitelist
        (`python`/`python3`/`pip`/`git`/`ls`/`cat`/`head`/`tail`) + banned-pattern
        list (`rm -rf`, `sed -i`, redirect-to-root, `curl | sh`). **Derive the exact
        whitelist by sweeping every bash invocation in `skills/*/SKILL.md` + the
        `reference.md` template** — the sweep is the source of truth, not the draft
        list. (The sweep surfaces `git add`/`git commit`/`git checkout` among others —
        gate on the **head** `git`; do **not** tighten to a git-subcommand allowlist or
        you risk blocking `git checkout`.)
  - [ ] **Fail-open** in record mode (a throwing handler would brick the tool); keep
        the handler total. Cadence's gate is a hard boundary on top of process trust,
        not the containment boundary — revisit fail-closed only if running untrusted
        models unsandboxed. **This intentionally diverges from pi-harness's
        enforce-mode fail-*closed*:** pi-harness fails closed because it has a
        container boundary to fall back on; Cadence does not, so failing closed on a
        gate bug would brick legitimate work.
- [ ] **Pi manifest (Q6):** add a `pi` key to the **repo-root `package.json`** —
      `"pi": { "extensions": ["./pi/extension"], "skills": ["./skills"] }`. **Not** a
      `pi/plugin.json`.
- [ ] Set `CADENCE_TRACK=pi` in the environment of bash calls the extension permits
      (so Phase 3's init scripts skip `.claude/`).
- [ ] TS unit tests for the gate (no container/key).

**Verify Phase 4:** TS gate tests green; typecheck clean; `pi install` (or a local
load) discovers the extension + skills from the root manifest.

## Phase 5 — Pi-track e2e tests

> **STATUS: DONE (2026-06-03).** The §5 parity table is fully covered, split by
> language: the **gate** parity (write-above-root, direct `status.yaml`/
> `.class.yaml` write → block + corrective reason; bash whitelist allow for
> `python`/`pip`/`git`; banned-pattern block; Q4 `install-deps.py`/`pip install`
> pass; fail-open fault-injection) lives in the TS suite
> `pi/extension/policy.test.ts` + `scope-gate.test.ts` (22 tests) — *beside the
> gate*, since the gate is TypeScript. The **scaffolding** parity
> (`CADENCE_TRACK=pi` → no `.claude/` at root/class/task; global tools load from
> the re-homed `root/tools/`) lives in the Python `tests/pi/test_no_claude_artifacts.py`
> (landed in Phase 3). Together they cover every `tests/pi/` row of the matrix.

- [ ] **`tests/pi/`** mirrors `tests/claude/`: assert the gate **blocks every
      scenario `.claude/settings.json` blocks today** (write-above-root,
      direct `status.yaml`/`.class.yaml` write) **plus** the new bash cases
      (whitelist allow for `python`/`pip`/`git`; banned-pattern block).
- [ ] **Q4 case:** a representative `install-deps.py` bash invocation passes the gate.
- [ ] **Fault-injection:** a throwing gate handler never bricks a tool (fail-open).

**Verify Phase 5:** `tests/pi/` green; the parity table in spec §5 is fully covered.

## Phase 6 — Dry run 3 on Pi (the acceptance proof)

> **STATUS: NOT STARTED.** Needs Pi + a non-Anthropic model key (the model-freedom
> proof). One billed run — don't loop.

- [ ] Run the full dry-run-2 lifecycle **on Pi, with a non-Anthropic model**
      (e.g. an OpenAI or local/Ollama model): `/onboard` → `/done` (approve a period)
      → `check-periods.py` auto-reset → `/start` → `review_ready`.
- [ ] Confirm equivalent workpapers (balanced JEs, all rows categorized) and that
      the gate blocked nothing legitimate (record-mode parity with Cowork).
- [ ] Capture findings in `notes/dry-runs/dry-run-pi-<date>.md`.

**Verify Phase 6:** a clean end-to-end lifecycle on a non-Anthropic model with
correct output — this is the proof the whole ticket exists for.

## Phase 7 — Documentation

> **STATUS: DONE (2026-06-03).** README gained an "Installation — two tracks"
> section (Cowork via `claude/assemble.py` vs `pi install git:…`), a two-tier
> "Running Tests" block (pytest + the TS gate), a "Pi migration" status bullet,
> and updated layout + design-principle + scripts-table rows. `spec/05-scripts.md`
> + `spec/06-separation-of-concerns.md` now describe BOTH enforcement mechanisms
> (Claude `settings.json` via `settings-gen.py` + the Pi `tool_call` gate) and the
> `tools/` re-home. `.claude/CLAUDE.md` carries the two-track layout (Phase 2),
> the TS test commands, the assemble reminder, and the commit-signing gotcha.

- [ ] README: describe both lanes with per-lane install instructions
      (Cowork plugin vs `pi install git:github.com/tomfoolerrie/cadence@<ref>`).
- [ ] Update the `spec/` files that reference `.claude/settings.json`
      (`05-scripts.md`, `06-separation-of-concerns.md` — confirmed via
      `grep -rl 'settings\.json' spec/`) to describe both enforcement mechanisms.
- [ ] Update `.claude/CLAUDE.md` (project notes) for the two-track layout.

---

## Sequencing & risk

1. **Phase 1 is the safe first commit** — pure cleanups, no restructure; ends with
   all 299 green. Ship it standalone.
2. **Phases 2–3 are the Claude-track restructure** — host-verifiable with pytest;
   the Claude lane must stay byte-for-byte behavioural after each.
3. **Phases 4–5 build + test the Pi track** — TS, no key needed for the unit tier.
4. **Phase 6 is the billed acceptance proof**; Phase 7 locks in the docs.

**Test-green invariant:** every phase ends with **all 299 Claude-track tests
passing**. The working lane never regresses while the new one is built.

**Known coupling risk:** the Pi extension leans on Pi `0.75.4` internals
(`ExtensionFactory`, the `tool_call` event/return shape, `DefaultResourceLoader`).
Pin Pi to `0.75.4` exactly (it is what the sibling `pi-harness` proves against);
do not bump inside this ticket.

**Each live run (Phase 6) is billed** — run the dry run once, never in a loop.

## Done criteria (when this moves to `tickets/Complete/`)

- All 7 phases complete; 299 Claude-track tests + the new `tests/pi/` suite green.
- A clean Pi dry-run-3 lifecycle on a **non-Anthropic** model (Phase 6) — the
  model-freedom proof.
- Both install paths documented and working: Cowork plugin + `pi install`.
