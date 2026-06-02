# Pi Migration — Detailed Spec

**Status:** spec (promoted from [`notes/v2+/pi-migration-plan.md`](../notes/v2+/pi-migration-plan.md))
**Work order:** [`tickets/ticket-pi-migration.md`](tickets/ticket-pi-migration.md) — the phased build order driving off this spec
**Date:** 2026-06-02
**Supersedes for implementation purposes:** the planning doc's §6 Open Questions. **Q3–Q6 are all fully resolved** below — Q5 (Cowork forbids `../` manifest paths → assemble-on-package) and Q6 (Pi manifest is a root `package.json` `pi` key, not `pi/plugin.json`) are confirmed against primary sources (§6).

This spec turns the planning doc into a buildable work order: the open questions
are resolved against the actual code, the per-file changes are enumerated, and a
test matrix gates each step. Read the planning doc first for the *why*; this doc
is the *how*.

The runtime Pi API assumed throughout is verified against a working Pi
deployment (the sibling `pi-harness` repo, `@earendil-works/pi-coding-agent`
**0.75.4**): extensions are `ExtensionFactory` functions; `pi.on("tool_call", e)`
fires before execution with `{ toolName, input, toolCallId }` and a handler may
return `{ block: true, reason }` to reject the call. Extension registration and
skill/prompt overrides go on a `DefaultResourceLoader` —
`new DefaultResourceLoader({ cwd, agentDir, skillsOverride,
appendSystemPromptOverride, extensionFactories })`, `await loader.reload()` —
which is then passed to `createAgentSession({ cwd, model, tools, …,
resourceLoader: loader })`. (Note the prompt override key is
`appendSystemPromptOverride`, not `systemPromptOverride`, and the loader, not
`createAgentSession`, owns `extensionFactories`/`skillsOverride` — verified in
`pi-harness/harness/session-setup.ts` lines 185–212.) Pin Cadence's Pi
dependency to this exact version (planning doc §6 Q-stability).

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
   the `.claude/` enforcement directory** — `.claude/settings.json` in
   `init-class.py` (lines 71–81) and `init-task.py` (lines 154–164), and **both
   `.claude/tools/` and an allow-only `.claude/settings.json` in
   `init-engagement.py` (lines 98–109)**. Removing those blocks makes all three
   scripts fully shared. `load-context.py` also reads `root/.claude/tools` (line
   189) for global tools — harness-specific *reading* that the Pi track must
   re-home (see S3 / §4).

3. **Engagement folders are external and reference scripts via runtime-resolved
   `${CLAUDE_PLUGIN_ROOT}`.** No repo path is baked into a user's hierarchy. The
   substituted value must point at a directory that contains `scripts/` — that is
   the single packaging invariant the restructure must preserve.

---

## 2. Resolved Open Questions

### Q3 — Init-script harness awareness → **`CADENCE_TRACK` env var (default `claude`)**

**Decision.** All three scaffolders — `init-engagement.py`, `init-class.py`,
`init-task.py` — drop their inline `.claude/` generation (grounding fact 2). The
Claude-track enforcement files are produced by a new `claude/settings-gen.py`
(per-level: root = allow-only, class = deny `.class.yaml`, task = deny
`status.yaml`). The init scripts invoke it **only when `CADENCE_TRACK=claude`**;
the Pi track emits no `.claude/` at any level and needs no per-dir glue because
the gate self-configures from cwd contents (§3a of the plan). The global-tools
directory (`.claude/tools/`, today created by `init-engagement.py` and read by
`load-context.py`) must move to a track-neutral home on the Pi track — see S3.

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
- On `CADENCE_TRACK=claude`, `init-engagement.py`/`init-class.py`/`init-task.py`
  shell out to `claude/settings-gen.py <target-dir> <level>` (level ∈
  {`root`,`class`,`task`}) after the shared scaffold writes succeed. A non-zero
  `settings-gen.py` exit is a system error (exit 2) — the scaffold already wrote,
  so this is the documented "partial-but-recoverable" case; rerunning
  `settings-gen.py` is idempotent.
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

**Packaging approach — CONFIRMED: assemble-on-package is required.** The Claude
Code / Cowork plugin spec mandates that all `plugin.json` paths "must be relative
to the plugin root and start with `./`" — **upward (`../`) escaping is not
supported**
([plugins-reference](https://code.claude.com/docs/en/plugins-reference.md),
"Path behavior rules"). So out-of-tree manifest paths are ruled out, and the
packaging step **must assemble the plugin root**: link or copy the top-level
`scripts/` + `skills/` under `claude/plugin/` (as `./scripts`, `./skills`) so the
install root is self-contained and `${CLAUDE_PLUGIN_ROOT}` resolves to a dir that
contains `scripts/`. The source of truth stays at the top level; `claude/plugin/`
is assembled from it at package time (a thin build/symlink step), never
hand-maintained.

**What actually changes** is repo-internal and caught by tests: the Claude e2e
suite (`tests/claude/`) asserts the generated `.claude/settings.json` content;
unit tests that import scripts by path update to the hoisted location. The
`engagement-template/` is regenerated through the same scripts, so it tracks
automatically. The packaging/assembly step is the one new piece of Claude-track
glue the restructure introduces (alongside `settings-gen.py`).

### Q6 — Distribution → **two install paths, one repo** (manifest format CONFIRMED)

**Decision.**

- **Pi track:** a Pi package is declared by a **`pi` key in the repo-root
  `package.json`** (verified by inspecting `@earendil-works/pi-coding-agent`
  0.75.4's `core/package-manager.js` `readPiManifestFile`/`resolveExtensionEntries`
  and its README "Pi Packages" section + `docs/packages.md`). There is **no
  `pi/plugin.json`** — the planning doc's guess was wrong. Shape:

  ```json
  {
    "name": "cadence",
    "keywords": ["pi-package"],
    "pi": { "extensions": ["./pi/extension"], "skills": ["./skills"] }
  }
  ```

  Paths resolve relative to the package (repo) root; without a `pi` manifest Pi
  auto-discovers conventional `extensions/`/`skills/`/`prompts/`/`themes/` dirs,
  and an extension dir falls back to its `index.ts`/`index.js`. Install:
  `pi install git:github.com/tomfoolerrie/cadence@<ref>` — Pi clones the **whole
  repo** to `~/.pi/agent/git/` (or `.pi/git/` with `-l`) and reads the root
  manifest. Pi packages run with **full system access** (README security note),
  which is exactly why the §3 gate matters on this track.

- **Claude track:** the assembled Cowork plugin (Q5) at
  `claude/plugin/.claude-plugin/plugin.json`, distributed as today.

**Asymmetry to exploit.** Because Pi resolves the manifest at the repo root and
allows relative paths into the tree, the Pi `pi.skills` can point **directly at
the shared top-level `skills/`** (`"./skills"`) with **no assembly** — unlike the
Claude track, which must assemble (Q5). One shared `skills/`, two manifests:
Claude assembles a copy under its plugin root, Pi references it in place.

**Layout correction to the plan.** Plan §2 places a `pi/plugin.json`; replace
that with the root-`package.json` `pi` key above. `pi/extension/` (the
`ExtensionFactory` source) stays as the plan has it — only the manifest's name
and location change. Both Q5 and Q6 are now fully resolved; see §6.

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

This reproduces today's two-rule `settings.json` deny lists exactly: the
`isUnder(target, cwd)` check is the `Write(../**)` rule (no writes above the
agent root), and the `detectGate` file check is the per-level
`Write(./.class.yaml)` (class) / `Write(./status.yaml)` (task) rule. The two
gate branches map one-to-one onto the two deny rules, which is what the §5
"write outside agent root" and "direct status.yaml/.class.yaml write" parity
tests assert.

**Whitelist derivation (plan §4 step 4 prerequisite):** sweep every bash
invocation in the four `skills/*/SKILL.md` bodies and the `reference.md` template
before finalizing `allowed`. Today's bodies emit `python ${...}/scripts/*.py`
plus `git add`/`git commit`/`git checkout` (head `git`, all covered) — but the
sweep is the source of truth, not this sentence. Gate on the `git` head, not a
subcommand allowlist, so `git checkout` isn't accidentally blocked.

---

## 4. Per-file change list (over plan §5 sequencing)

Each step keeps **all 299 Claude-track tests green**.

**Step 1 — In-place cleanups (no structural move).**
- `AGENT.md` → `AGENTS.md` repo-wide. Drive this off `grep -rl 'AGENT\.md'` (the
  sweep is the source of truth), not a hand-list. As of this writing that is:
  the file in `engagement-template/`; `load-context.py` (read path),
  `init-engagement.py` + `init-class.py` (write path); the shared skill body
  `plugin/skills/onboard/SKILL.md` (8 references, including write instructions);
  **all 10 spec files** that mention it (`01-overview`, `02-architecture`,
  `04-scaffolding`, `05-scripts`, `06-separation-of-concerns`, `07-example`,
  `09-glossary`, `diagrams`, `skill-onboard`, and this file); and every test
  asserting the filename. Re-run the grep after the rename to confirm zero
  residual `AGENT.md` (excluding deliberate historical mentions in `notes/`).
- Drop `version:` from `skills/onboard|start|done|status/SKILL.md` frontmatter
  (currently `1.0.0`; `init-task.py`'s `SKILL_MD_TEMPLATE` emits `0.1.0` — drop
  there too).
- `check-periods.py`: extract core logic into an importable function; CLI becomes
  a thin wrapper (Symphony hedge + v2 foundation).

**Step 2 — Restructure to the plan §2 layout.** Move `plugin/` →
`claude/plugin/`; hoist `skills/` + `scripts/` to top level; create empty `pi/`;
split `tests/` → `unit/` + `claude/` + `pi/`. Add the **assemble step** (Q5) that
links/copies top-level `scripts/` + `skills/` under `claude/plugin/` as
`./scripts`/`./skills` (Cowork forbids `../` manifest paths). The Pi manifest
needs no assembly — it references `./skills` from the root `package.json` (Q6).

**Step 3 — Extract settings generation.** New `claude/settings-gen.py <dir>
<level>` carrying the exact `permissions` blocks currently inlined in the three
scaffolders: `init-engagement.py` (root — allow-only, no deny), `init-class.py`
(deny `Write(../**)`, `Write(./.class.yaml)`), and `init-task.py` (deny
`Write(../**)`, `Write(./status.yaml)`). Make **all three** init scripts
`CADENCE_TRACK`-aware per Q3 (each emits `.claude/` only on the claude track).
Decide the Pi-track home for global tools: today `init-engagement.py` creates
`root/.claude/tools/` and `load-context.py` reads it (line 189). Re-home to a
track-neutral `root/tools/` (read by `load-context.py` on both tracks) so the
global-tools convention survives without `.claude/` — and update the tool
resolution order (task → class → global) accordingly in `load-context.py`.

**Step 4 — Build the Pi extension.** `pi/extension/scope-gate.ts` (§3) + TS unit
tests; declare the package via a `pi` key in the **repo-root `package.json`**
(`"pi": { "extensions": ["./pi/extension"], "skills": ["./skills"] }`, Q6 — *not*
a `pi/plugin.json`); set `CADENCE_TRACK=pi` for permitted bash calls.

**Step 5 — Pi e2e tests.** `tests/pi/` mirrors `tests/claude/`: assert the gate
blocks every scenario `.claude/settings.json` blocks today, plus the new
bash-whitelist cases.

**Step 6 — Dry run 3 on Pi.** Full lifecycle (`/onboard` → `/done` →
`check-periods.py` reset → `/start` → `review_ready`) on Pi with a non-Anthropic
model.

**Step 7 — Documentation.** README two-lane install; update the `spec/` files
that reference `.claude/settings.json` (`05-scripts.md` and
`06-separation-of-concerns.md` — confirmed via `grep -rl 'settings\.json' spec/`)
to describe both enforcement mechanisms.

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

## 6. External dependencies — all confirmed (2026-06-02)

Both items the planning doc left open are now resolved against primary sources;
nothing in this spec is blocked on an unverified external assumption.

1. **Pi distributable manifest** (Q6) — **RESOLVED.** It is a `pi` key in the
   repo-root `package.json` (`{ "pi": { "extensions": [...], "skills": [...] } }`),
   *not* a `pi/plugin.json`. Verified by inspecting `@earendil-works/pi-coding-agent`
   0.75.4 (`core/package-manager.js`: `readPiManifestFile` reads `pkg.pi`,
   `resolveExtensionEntries` resolves `manifest.extensions` relative to the package
   dir with an `index.ts`/`index.js` fallback) plus the package README "Pi Packages"
   section and `docs/packages.md`. Paths may reference the shared top-level
   `skills/` directly; no assembly needed on this track.
2. **Cowork manifest path rules** (Q5) — **RESOLVED.** `plugin.json` paths "must be
   relative to the plugin root and start with `./`"; `../` escaping is unsupported
   ([plugins-reference](https://code.claude.com/docs/en/plugins-reference.md),
   "Path behavior rules"). Therefore the Claude track **must assemble** `scripts/`
   + `skills/` under the plugin root at package time (Step 2).

Everything else is verified against the running pi-harness (runtime API), the
pinned Pi package (distribution), the Claude Code docs (Cowork packaging), and
the current Cadence code (script behavior).
