# Pi Migration — Detailed Spec

**Status:** spec (promoted from [`notes/v2+/pi-migration-plan.md`](../notes/v2+/pi-migration-plan.md))
**Date:** 2026-06-02
**Supersedes for implementation purposes:** the planning doc's §6 Open Questions (Q3–Q6 resolved below).

This spec turns the planning doc into a buildable work order: the open questions
are resolved against the actual code, the per-file changes are enumerated, and a
test matrix gates each step. Read the planning doc first for the *why*; this doc
is the *how*.

The runtime Pi API assumed throughout is verified against a working Pi
deployment (the sibling `pi-harness` repo, `@earendil-works/pi-coding-agent`
**0.75.4**): extensions are `ExtensionFactory` functions; `pi.on("tool_call", e)`
fires before execution with `{ toolName, input, toolCallId }` and a handler may
return `{ block: true, reason }` to reject the call; the session is built with
`createAgentSession({ extensionFactories, skillsOverride, systemPromptOverride })`.
Pin Cadence's Pi dependency to this exact version (planning doc §6 Q-stability).

---

## 1. Grounding facts (verified against the current code)

These three facts de-risk the migration and drive the resolutions below.

1. **No Python script reads `CLAUDE_PLUGIN_ROOT` or `os.environ`.** `grep` across
   `plugin/scripts/` finds the token only inside `init-task.py`'s `reference.md`
   *template string* — a literal written into scaffolded folders, never read. Every
   script resolves paths by walking up from cwd to `.context-root` / `.class.yaml`.
   The scripts are therefore **already harness-agnostic**; the migration does not
   need to refactor their path handling.

2. **The only harness-specific behavior in the scaffolding scripts is generating
   `.claude/settings.json`** (`init-class.py` lines 71–81, `init-task.py` lines
   154–164). Removing that one block makes both scripts fully shared.

3. **Engagement folders are external and reference scripts via runtime-resolved
   `${CLAUDE_PLUGIN_ROOT}`.** No repo path is baked into a user's hierarchy. The
   substituted value must point at a directory that contains `scripts/` — that is
   the single packaging invariant the restructure must preserve.

---

## 2. Resolved Open Questions

### Q3 — Init-script harness awareness → **`CADENCE_TRACK` env var (default `claude`)**

**Decision.** `init-class.py` and `init-task.py` drop their inline
`.claude/settings.json` generation (grounding fact 2). The Claude-track
enforcement file is produced by a new `claude/settings-gen.py`. The init scripts
invoke it **only when `CADENCE_TRACK=claude`**; the Pi track needs no per-dir
glue at all because the gate self-configures from cwd contents (§3a of the plan).

**Why env var, not flag or auto-detect.**

- **A `--track` flag** would have to be passed from the skill body, and the skill
  bodies are *shared* across tracks — putting a Claude-only argument in a shared
  body reintroduces the coupling we are removing.
- **Auto-detect** (`.pi/` vs `.claude/`) is unreliable at scaffold time: a freshly
  `init-engagement.py`'d folder has neither marker yet, and the harness, not the
  folder, is the authoritative source of "which track am I."
- **An env var set by each harness** is invisible to the shared skill body and is
  always correct because the harness that launched the agent sets it.

**Contract.**

- `CADENCE_TRACK` ∈ {`claude`, `pi`}; **unset defaults to `claude`** (backward
  compatible — existing Cowork runs keep generating `settings.json` with no change).
- The Claude harness glue sets `CADENCE_TRACK=claude`. The Pi extension sets
  `CADENCE_TRACK=pi` in the environment of any bash tool call it permits.
- On `CADENCE_TRACK=claude`, `init-class.py`/`init-task.py` shell out to
  `claude/settings-gen.py <target-dir> <level>` after the shared scaffold writes
  succeed. A non-zero `settings-gen.py` exit is a system error (exit 2) — the
  scaffold already wrote, so this is the documented "partial-but-recoverable"
  case; rerunning `settings-gen.py` is idempotent.
- On `CADENCE_TRACK=pi` (or any non-`claude` value), the scripts emit no
  `.claude/` directory.

### Q4 — `requirements.txt` and venv → **unchanged on the Pi track**

**Decision.** `init-venv.py` and `install-deps.py` are pure Python with no Cowork
coupling (`sys.executable -m venv`, cwd walk-up, system-pip fallback). Pi invokes
them through its `bash` tool exactly as Cowork does. **No code change.**

**One dependency on the gate.** The §3b bash whitelist must include the heads the
venv path uses: `python`, `python3`, and `pip`. All three are already in the
planning doc's draft whitelist. The gate's banned-pattern list must not match a
normal `pip install -r requirements.txt` or `python -m venv` invocation — covered,
since the banned patterns target `rm -rf`, `sed -i`, redirection-to-root, and
`curl | sh`, none of which appear in venv/pip usage. A `tests/pi/` case asserts a
representative `install-deps.py` bash call passes the gate (see §5 matrix).

### Q5 — Cowork compatibility of the restructure → **safe for engagement folders; risk is repo-internal only**

**Decision.** Moving `plugin/` → `claude/plugin/` and hoisting `skills/` +
`scripts/` to the repo top level does **not** break any existing engagement
folder, because (grounding fact 3) folders reference scripts via the
runtime-resolved `${CLAUDE_PLUGIN_ROOT}`, not a repo-relative path.

**The single hard invariant.** Whatever Cowork resolves `${CLAUDE_PLUGIN_ROOT}`
to **must contain `scripts/`** (existing `reference.md` files embed
`${CLAUDE_PLUGIN_ROOT}/scripts/set-status.py` literally) and the skills Cowork
loads. Therefore the Claude plugin must be *packaged* so its install root carries
`scripts/` and `skills/`.

**Packaging approach.** The repo's source-of-truth `scripts/` and `skills/` live
at the top level (shared). The Claude plugin manifest at
`claude/plugin/.claude-plugin/plugin.json` references them. Two acceptable
mechanisms, decided at implementation:

- **(Preferred) Path references in the manifest** if Cowork accepts manifest
  `skills`/`scripts` paths that resolve outside the `.claude-plugin/` dir (e.g.
  `"scripts": "../../scripts/"`). Zero duplication.
- **(Fallback) Assemble-on-package**: a packaging step links/copies top-level
  `scripts/` + `skills/` under `claude/plugin/` so the install root is
  self-contained. Use only if Cowork rejects out-of-tree manifest paths.

**What actually changes** is repo-internal and caught by tests: the Claude e2e
suite (`tests/claude/`) asserts the generated `.claude/settings.json` content;
unit tests that import scripts by path update to the hoisted location. The
`engagement-template/` is regenerated through the same scripts, so it tracks
automatically. **Resolve which packaging mechanism Cowork supports before
landing the §4 step-2 restructure** (one quick check against Cowork plugin docs).

### Q6 — Distribution → **two install paths, one repo**

**Decision.**

- **Pi track:** distribute as a Pi package consumed from the `pi/` subtree:
  `pi install git:github.com/tomfoolerrie/cadence#<pi-branch>`. The extension's
  default export is the `ExtensionFactory`; the skills ship alongside it.
- **Claude track:** the existing Cowork plugin manifest at
  `claude/plugin/.claude-plugin/plugin.json`, distributed exactly as today.

**One external confirmation required before implementing the Pi manifest.** The
sibling `pi-harness` *embeds* Pi via `createAgentSession({extensionFactories})`
rather than *installing* a third-party Pi package, so it does not pin down the
on-disk manifest key for a distributable extension. The two candidates are a
`package.json` `"pi"` field (per the older `docs/pi-migration-strategy.md`) versus
a standalone `pi/plugin.json` (per the planning doc). **Confirm the exact key and
skills-discovery convention against Pi 0.75.4's own docs/types**, then pin. This
is the only unresolved external dependency in the migration; everything else is
verified against the running pi-harness.

---

## 3. The Tool-Call Gate Extension (detail over plan §3)

Lives in `pi/extension/scope-gate.ts`. Registered as an `ExtensionFactory` and
wired with `pi.on("tool_call", …)`. The event/return shape below is the one the
pi-harness gate uses in production (`gate/gate.ts`), so it is known-good:

```ts
import type { ExtensionAPI, ExtensionFactory } from "@earendil-works/pi-coding-agent";
import { resolve, join } from "node:path";

export function makeScopeGate(): ExtensionFactory {
  return (pi: ExtensionAPI) => {
    pi.on("tool_call", (event) => {
      // event: { toolName, input, toolCallId }
      // return { block: true, reason } to reject; undefined to allow.
      const cwd = process.cwd();

      // --- §3a Edit/Write gate (replaces .claude/settings.json) ---
      if (event.toolName === "edit" || event.toolName === "write") {
        const target = resolve(cwd, String((event.input as any).path ?? ""));
        if (!isUnder(target, cwd)) {
          return { block: true, reason: "write outside agent root" };
        }
        const gated = detectGate(cwd); // "status.yaml" | ".class.yaml" | null
        if (gated && target === join(cwd, gated)) {
          return { block: true, reason: `${gated} is script-gated — use the Cadence tool/script` };
        }
        return undefined;
      }

      // --- §3b Bash gate (NEW — not possible on the Claude track) ---
      if (event.toolName === "bash") {
        const cmd = String((event.input as any).command ?? "").trim();
        const head = cmd.split(/\s+/)[0] ?? "";
        const allowed = ["python", "python3", "pip", "git", "ls", "cat", "head", "tail"];
        if (!allowed.includes(head)) {
          return { block: true, reason: `bash head '${head}' not in whitelist` };
        }
        const banned = [/\brm\s+-rf\b/, /\bsed\s+-i\b/, /\b>\s*\/(?!dev\/null)/, /\bcurl\b.*\|\s*sh\b/];
        if (banned.some((re) => re.test(cmd))) {
          return { block: true, reason: "command contains banned pattern" };
        }
        return undefined;
      }
    });
  };
}
```

**Fail-safe (carried over from the pi-harness gate, a hard lesson there):** a
`tool_call` handler that *throws* causes Pi to block the tool. Keep the handler
total — wrap the body in try/catch and, on an internal error, **allow** (Cadence's
gate is a hard boundary layered on top of process trust, not the containment
boundary; failing closed on a gate bug would brick legitimate work). Revisit
fail-open vs fail-closed if Cadence ever runs untrusted models in an unsandboxed
host (then mirror pi-harness's enforce-mode fail-closed).

**`detectGate(cwd)`** is the self-configuring core: `.class.yaml` present → gate
`.class.yaml`; `status.yaml` present → gate `status.yaml`; root (neither) → no
file gate. No scope file needed (plan §3a). When `.class.yaml` v2 lands, extend to
also deny writes under `cycles/` at the class level (plan §3a note).

**Whitelist derivation (plan §4 step 4 prerequisite):** sweep every bash
invocation in the four `skills/*/SKILL.md` bodies and the `reference.md` template
before finalizing `allowed`. Today's bodies emit `python ${...}/scripts/*.py`
plus `git status`/`git add`/`git commit` — all covered — but the sweep is the
source of truth, not this sentence.

---

## 4. Per-file change list (over plan §5 sequencing)

Each step keeps **all 299 Claude-track tests green**.

**Step 1 — In-place cleanups (no structural move).**
- `AGENT.md` → `AGENTS.md` repo-wide: rename in `engagement-template/`, update
  `load-context.py` (read path), `init-engagement.py` + `init-class.py` (write
  path), `spec/02-architecture.md` + `spec/04-scaffolding.md` (references), and
  every test asserting the filename.
- Drop `version:` from `skills/onboard|start|done|status/SKILL.md` frontmatter
  (currently `1.0.0`; `init-task.py`'s `SKILL_MD_TEMPLATE` emits `0.1.0` — drop
  there too).
- `check-periods.py`: extract core logic into an importable function; CLI becomes
  a thin wrapper (Symphony hedge + v2 foundation).

**Step 2 — Restructure to the plan §2 layout.** *(Resolve Q5 packaging mechanism
first.)* Move `plugin/` → `claude/plugin/`; hoist `skills/` + `scripts/` to top
level; create empty `pi/`; split `tests/` → `unit/` + `claude/` + `pi/`. Update
the Claude plugin manifest's `skills`/`scripts` paths per the Q5 decision.

**Step 3 — Extract settings generation.** New `claude/settings-gen.py <dir>
<level>` carrying the exact `permissions` blocks currently inlined in
`init-class.py` (deny `Write(../**)`, `Write(./.class.yaml)`) and `init-task.py`
(deny `Write(../**)`, `Write(./status.yaml)`). Make both init scripts
`CADENCE_TRACK`-aware per Q3.

**Step 4 — Build the Pi extension.** `pi/extension/scope-gate.ts` (§3) + TS unit
tests; `pi/plugin.json` (or `package.json "pi"` field per Q6 confirmation); set
`CADENCE_TRACK=pi` for permitted bash calls.

**Step 5 — Pi e2e tests.** `tests/pi/` mirrors `tests/claude/`: assert the gate
blocks every scenario `.claude/settings.json` blocks today, plus the new
bash-whitelist cases.

**Step 6 — Dry run 3 on Pi.** Full lifecycle (`/onboard` → `/done` →
`check-periods.py` reset → `/start` → `review_ready`) on Pi with a non-Anthropic
model.

**Step 7 — Documentation.** README two-lane install; update `spec/` files that
reference `.claude/settings.json` (06-separation-of-concerns, 04-scaffolding) to
describe both enforcement mechanisms.

---

## 5. Test matrix

| Concern | `tests/unit/` (shared) | `tests/claude/` | `tests/pi/` |
|---|---|---|---|
| Scaffold writes (dirs, YAML, AGENTS.md) | ✓ assert files + content | — | — |
| `CADENCE_TRACK=claude` → settings.json emitted | — | ✓ content of deny rules | — |
| `CADENCE_TRACK=pi` → **no** `.claude/` dir | — | — | ✓ absence |
| `settings-gen.py` idempotent + correct per level | — | ✓ | — |
| Write outside agent root blocked | — | ✓ deny rule | ✓ gate `block` |
| Direct `status.yaml` / `.class.yaml` write blocked | — | ✓ deny rule | ✓ gate `block` + corrective `reason` |
| Bash whitelist: `python`/`pip`/`git` allowed | — | n/a (no bash gate) | ✓ allow |
| Bash banned pattern (`rm -rf`, `curl\|sh`) blocked | — | n/a | ✓ block |
| `install-deps.py` bash call passes the gate (Q4) | — | — | ✓ allow |
| Status-machine transitions | ✓ | — | — |
| Gate handler never throws → never bricks a tool | — | — | ✓ fault-injection allows |

The shared `tests/unit/` suite must stay harness-neutral (no settings.json
assertions — those move to `tests/claude/`).

---

## 6. Residual external dependencies (must confirm before coding the relevant step)

1. **Pi distributable manifest key** (Q6) — `package.json "pi"` field vs
   `pi/plugin.json`, and the skills-discovery convention, against Pi 0.75.4.
   *Blocks Step 4's `pi/plugin.json`.*
2. **Cowork out-of-tree manifest paths** (Q5) — whether `plugin.json` may point
   `skills`/`scripts` outside `.claude-plugin/`, or packaging must assemble.
   *Blocks Step 2's restructure landing.*

Everything else is verified against the running pi-harness and the current
Cadence code.
