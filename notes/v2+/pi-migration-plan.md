# Pi Migration — Planning Doc

**Status:** planning
**Date:** 2026-05-09
**Scope:** Migrate Cadence to run on the pi agent harness ([earendil-works/pi](https://github.com/earendil-works/pi)) as the primary target, while keeping a Claude Code track for the "average accountant" audience.
**Sibling to:** [`class-yaml-v2-plan.md`](./class-yaml-v2-plan.md). Orthogonal in implementation; both feed Symphony as a downstream beneficiary. This plan ships first.

This is a planning doc. A detailed spec follows once the shape is agreed.

---

## 1. Goals

1. **Model freedom.** Pi's multi-provider LLM API removes Anthropic lock-in.
2. **Harder boundaries.** Replace `.claude/settings.json` (string-pattern allow/deny, bypassable in edge cases) with a TS `before-tool-use` extension that programmatically inspects every Edit/Write call.
3. **Two tracks, one repo.** Pi as primary; Claude Code track preserved for users on Cowork. Not solving simultaneous portability — the two tracks evolve independently below the shared layer.

## 2. Final Repo Layout

```
cadence/
├── skills/                  # SHARED — procedure markdown (4 skills)
│   ├── onboard/SKILL.md
│   ├── start/SKILL.md
│   ├── done/SKILL.md
│   └── status/SKILL.md
├── scripts/                 # SHARED — Python, harness-agnostic
│   └── (14 scripts; init-class.py / init-task.py lose settings.json
│        generation — replaced by per-track glue)
├── spec/                    # SHARED — design specification
├── tests/                   # SHARED — Python tests
│   ├── unit/                #   harness-agnostic
│   ├── claude/              #   Claude-track e2e (settings.json assertions)
│   └── pi/                  #   pi-track e2e (extension behavior)
├── pi/                      # Pi harness glue
│   ├── extension/           #   TS extension — write-scope gate
│   ├── plugin.json          #   Pi package manifest
│   └── README.md
├── claude/                  # Claude Code harness glue
│   ├── plugin/              #   moved from current plugin/.claude-plugin/
│   ├── settings-gen.py      #   the .claude/settings.json generator
│   │                        #   (extracted from init-class.py / init-task.py)
│   └── README.md
├── engagement-template/
├── notes/
├── docs/
└── pyproject.toml
```

Skill frontmatter is shared across tracks (drop the current `version: 1.0.0` — pi requires only `name` + `description`, both already present).

## 3. The TS Tool-Call Gate Extension

Pi exposes a `tool_call` event that fires before any tool executes. Handlers can return `{ block: true, reason }` or mutate `event.input`. This is strictly more powerful than Claude Code's `settings.json` — we can gate Bash too, which Claude Code cannot. The pi track gets **perfect hard boundaries**, not just file-write ones.

### 3a. Edit/Write gate (replaces today's settings.json)

```ts
pi.on("tool_call", (event) => {
  if (!["edit", "write"].includes(event.toolName)) return;
  const target = resolve(event.input.path);
  const cwd = process.cwd();

  if (!isUnder(target, cwd)) return { block: true, reason: "write outside agent root" };

  const gatedFile = detectGate(cwd);  // "status.yaml" | ".class.yaml" | null
  if (gatedFile && target === path.join(cwd, gatedFile)) {
    return { block: true, reason: `${gatedFile} is script-gated` };
  }
});
```

Self-configuring from cwd contents — class dir has `.class.yaml`, task dir has `status.yaml`, root has neither. No scope file needed. Replicates current settings.json behavior exactly.

When `.class.yaml` v2 lands, the gate also denies writes under `cycles/` at the class level (the cycle-summary directory is script-written; agents never edit it). See `class-yaml-v2-plan.md` §3b.

### 3b. Bash gate (NEW capability — not possible on Claude track)

```ts
pi.on("tool_call", (event) => {
  if (event.toolName !== "bash") return;
  const cmd = (event.input.command ?? "").trim();
  const head = cmd.split(/\s+/)[0];

  // Whitelist: Python invocations and a small set of read-only tools
  const allowed = ["python", "python3", "pip", "git", "ls", "cat", "head", "tail"];
  if (!allowed.includes(head)) {
    return { block: true, reason: `bash head '${head}' not in whitelist` };
  }

  // Block dangerous shell features even within whitelisted heads
  const banned = [/\brm\s+-rf\b/, /\bsed\s+-i\b/, /\b>\s*\/(?!dev\/null)/, /\bcurl\b.*\|\s*sh\b/];
  if (banned.some(re => re.test(cmd))) {
    return { block: true, reason: "command contains banned pattern" };
  }
});
```

Whitelist exact set is TBD — needs a sweep of every Bash call our skills emit today (mostly `python plugin/scripts/*.py`, plus `git status`/`git add`/`git commit`). We can extract this list from skill markdown bodies during migration.

**Implication:** the pi track becomes the *security-stronger* track. Claude track keeps weaker Bash boundary as a known limitation, mitigated by skill discipline and Cowork's container.

## 4. Per-Component Plan

| Area | Pi track | Claude track | Shared |
|------|----------|--------------|--------|
| Skills (4 markdown) | — | — | full SKILL.md (frontmatter + body); drop `version` field |
| Slash command UX | `/<name>` | `/<name>` | (same UX both lanes; registration mechanism differs — see distribution row) |
| Tool-call enforcement | `pi/extension/scope-gate.ts` (Edit/Write + Bash) | `.claude/settings.json` from `claude/settings-gen.py` (Edit/Write only) | — |
| `init-class.py` / `init-task.py` | omit settings.json generation | call `claude/settings-gen.py` | YAML + dir scaffolding |
| Context files | — | — | `AGENTS.md` at all three levels |
| `load-context.py` | — | — | reads `AGENTS.md` |
| Python scripts (14 total) | shell-invoked | shell-invoked | all scripts; `check-periods.py` also library-callable (Symphony hedge) |
| Distribution | `pi install git:...#pi` consuming `pi/plugin.json` | Claude plugin manifest at `claude/plugin/.claude-plugin/plugin.json` | — |
| Tests | new e2e under `tests/pi/` for extension | ported e2e under `tests/claude/` | `tests/unit/` |

## 5. Migration Steps (sequencing, not detailed spec)

Each step ends with **all 299 existing tests still passing on the Claude track** — we don't break the working lane while building the new one.

1. **In-place cleanups (no structural changes yet).**
   - Rename `AGENT.md` → `AGENTS.md` repo-wide. Update `load-context.py`, spec, scaffolding scripts, `engagement-template/`, tests.
   - Drop `version: 1.0.0` from all four `plugin/skills/*/SKILL.md` files.
   - Refactor `check-periods.py` so its core logic is importable as a library function, with the CLI as a thin wrapper. Hedges Symphony (§8) and is the foundation for `class-yaml-v2-plan.md` §5 step 1.
2. **Restructure repo** to the layout in §2. Move `plugin/` under `claude/plugin/`, hoist `skills/` and `scripts/` to top-level, create empty `pi/`, split `tests/` into `unit/`+`claude/`+`pi/`. Resolve Q5 (Cowork compatibility) before this lands.
3. **Extract settings generation** from `init-class.py` and `init-task.py` into `claude/settings-gen.py`. Init scripts become harness-aware (Q3: pick flag, env var, or auto-detect).
4. **Build the TS extension.** Greenfield in `pi/extension/`: §3a Edit/Write gate, §3b Bash whitelist (sweep skill bodies first to derive exact whitelist). TS unit tests. Wire `pi/plugin.json`.
5. **Pi-track e2e tests.** Under `tests/pi/`. Mirror the existing Claude e2e suite; assert the extension blocks every scenario `.claude/settings.json` blocks today, plus the new Bash-whitelist cases.
6. **Dry run 3 on pi.** Full dry-run-2 lifecycle (`/onboard` → `/done` → `check-periods.py` reset → `/start` → `review_ready`) executed on pi instead of Cowork.
7. **Documentation.** README updated to describe both lanes with per-lane install instructions. `spec/` updated where harness-specific details exist (§6 separation-of-concerns and §4 scaffolding both reference `.claude/settings.json` today).

## 6. Open Questions

- **Q1 — Skill frontmatter compatibility.** *Resolved.* Pi requires `name` + `description`. Both already conform. Drop the non-standard `version: 1.0.0` field from all four skills — frontmatter then fully shared, no wrappers or build step needed.
- **Q2 — Slash command UX.** *Tentatively resolved.* Both harnesses appear to surface skills as `/<name>` to the user, with any `skill:` namespacing happening internally. Confirm at first pi run; revisit only if the bodies' `/onboard` references don't resolve on pi.
- **Q3 — Init script harness awareness.** `--track pi|claude` flag, env var, or auto-detect (presence of `.pi/` vs `.claude/`)? Affects how `/onboard` invokes the scripts.
- **Q4 — `requirements.txt` and venv.** Pi runs in Node; Python scripts still need `venv/`. Confirm `init-venv.py` is unchanged on the pi track.
- **Q5 — Cowork compatibility.** Claude track must remain Cowork-compatible. Is restructuring `plugin/` → `claude/plugin/` a breaking change for existing engagement folders, or only for the Cadence repo itself?
- **Q6 — Distribution.** Pi via `pi install git:github.com/.../cadence#pi`? Claude via existing plugin distribution? One repo, two install paths.

## 7. Out of Scope (for now)

- Solving simultaneous portability (running the same engagement folder under either harness in parallel).
- Re-running dry-run-2's engagement folder on pi for parity (we'll do dry-run-3 from a fresh `/onboard` on pi instead — see §5 step 6).
- `pi-share-hf` session-data publishing (interesting but separable).

## 8. Future Path — Symphony (deferred)

End-state vision: a third lane built on [openai/symphony](https://github.com/openai/symphony) for **unattended, scheduled execution** of recurring closes. Symphony is an orchestrator (not a harness) that spawns an agent subprocess per ticket, expects autonomous completion, and uses PRs as the review surface. Pi runs *inside* Symphony as the agent.

### Lane mapping (final state)

| Lane | Onboarding | Recurring runs | Audience |
|------|-----------|----------------|----------|
| Claude (Cowork) | `/onboard` interactive | `/start`+`/done` interactive | Average accountant |
| Pi TUI | `/onboard` interactive | `/start`+`/done` interactive | Power user, model freedom |
| Symphony + pi | done on Claude or Pi TUI first | Symphony fires `/start`; PR comments drive `/done` re-run | Unattended scheduled closes |

### What the Symphony lane will need (not building now, just flagging)

- **Non-interactive `/start` and `/done` variants.** Live under `symphony/skills/`, not `skills/`. Differences from the shared bodies: no in-conversation prompts, structured exit, PR-comment ingestion for `/done`.
- **Branch + PR topology.** Per-run branch (e.g. `task/<class>/<task>/<period>`), end-of-run PR. New helper script or extension to `init-period.py`.
- **Trigger bridge.** `check-periods.py` already computes "task is due"; once `.class.yaml` v2 lands, `class-graph.py` adds "task is *eligible* (blockers cleared)." The Symphony dispatcher consumes both. Cadence stays its own task source — no Linear required.
- **Pi-as-black-box integration (Path A).** Symphony talks Codex app-server protocol; pi has its own RPC. Run pi via `pi --print`/`--json` and accept that Symphony only sees stdout/exit. No protocol shim.

### Why defer

The Claude+pi split is enough work to land cleanly first. Symphony's value (scheduling, PR proof-of-work) only matters once a customer is running enough engagements that human-triggered `/start` becomes a bottleneck. Build the harness migration; let Symphony sit until there's a real pull for it.

### Design constraints to honor *now* so Symphony stays cheap later

- Skills must be writable in a non-interactive form — avoid baking conversation-only patterns into the shared bodies.
- The TS gate extension must work whether pi runs as TUI or subprocess. (It will — it hooks `tool_call` regardless of mode.)
- `check-periods.py` should remain a pure function of filesystem state, callable as a library, not just a CLI. Makes the Symphony trigger trivially wireable.

## 9. Relationship to `.class.yaml` v2

Distinct plan ([`class-yaml-v2-plan.md`](./class-yaml-v2-plan.md)). Orthogonal in implementation but worth noting the touch points:

- **Sequencing:** pi migration first, v2 second. v2 is harness-agnostic and benefits from landing on a stabilized layout.
- **Shared script-library work:** §5 step 1's `check-periods.py` library refactor is the same foundation v2 builds on for `class-graph.py` and `class-rollup.py`.
- **Gate extension:** the §3a gate's "gated files" set grows when v2 lands (`cycles/` becomes script-written). Note already inline at §3a.
- **Symphony alignment:** pi gives Symphony a non-interactive runtime; v2 gives it a richer dispatch graph, schedule signal, and review-routing field. Both are needed for Symphony to be *good*; pi alone makes it *possible*.

---

## Next

Resolve Q3–Q6 (init-script harness awareness, venv handling, Cowork compatibility of the restructure, distribution mechanics). Then promote this to a detailed spec with file-by-file changes and a test matrix.
