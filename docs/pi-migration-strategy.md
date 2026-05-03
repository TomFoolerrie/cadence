# Cadence on Pi — Migration Strategy

> Status: **Planning document** — no code changes yet.  
> Goal: Run Cadence on [pi-mono](https://github.com/badlogic/pi-mono) to gain
> multi-provider LLM support and escape single-vendor lock-in, while preserving
> the design invariants that make Cadence work.

---

## Why Pi

Cadence's core philosophy — *the folder is the memory, not the agent* — is
runtime-agnostic by design. The hierarchy of folders, YAML, markdown, and Python
scripts doesn't care who invokes it. But today every entry point (skills,
environment variables, write-scope enforcement, MCP routing) is wired to
Anthropic's Cowork plugin system. That means:

- Cadence only runs on Claude.
- Users can't bring their own model (cost, compliance, preference).
- If Anthropic changes the plugin API, Cadence breaks with no fallback.

Pi solves this. It's an open-source, MIT-licensed agent framework with a clean
layered architecture:

| Pi package | What it does |
|---|---|
| `pi-ai` | Unified LLM abstraction — 20+ providers (OpenAI, Anthropic, Google, Mistral, Groq, Ollama, vLLM, etc.) |
| `pi-agent-core` | Stateful agent runtime with tool calling, event lifecycle, and steering |
| `pi-coding-agent` | CLI agent with sessions, extensions, skills, and a TUI |

Pi already has SKILL.md support with the same YAML-frontmatter-plus-markdown
format Cadence uses. It reads `CLAUDE.md`/`AGENTS.md` for project context. Its
extension system lets you register custom tools, commands, lifecycle hooks, and
message types — everything needed to implement Cadence's domain logic.

---

## What Maps Cleanly

These Cadence concepts have direct Pi equivalents:

| Cadence (Cowork) | Pi equivalent | Notes |
|---|---|---|
| `plugin/skills/*.md` | `.pi/agent/skills/*/SKILL.md` | Same format — YAML frontmatter + markdown body. Pi auto-discovers and injects into system prompt. |
| `plugin.json` manifest | `package.json` with `"pi"` field | Pi uses npm/git packaging for distribution. |
| `${CLAUDE_PLUGIN_ROOT}` | Extension `__dirname` or config path | Extensions know their own install path. |
| `load-context.py` (context assembly) | `buildSystemPrompt()` layers | Pi assembles system prompt from base + tools + context files + skills. We'd add a Cadence layer. |
| Slash commands (`/onboard`, `/start`, etc.) | `registerCommand()` in extension API | Extensions register commands with handlers and completers. |
| MCP tool calls (Google Drive) | Extension-registered tools | `pi.registerTool()` with TypeBox schema and async execute function. |
| Fresh-instance model | Session branching or `newSession()` | Pi sessions are JSONL with tree structure; we can start fresh per task execution. |
| `CLAUDE.md` project context | `CLAUDE.md` / `AGENTS.md` | Pi reads these natively — walks up directory tree. |

---

## Where Pi Makes Cadence *More* Robust

Pi's hook and extension surface is deeper than Cowork's plugin system. Several
Cadence invariants that are currently enforced by convention or by a single
mechanism get **defense in depth** on Pi.

### 1. `beforeToolCall` — Programmable Gate on Every Tool Invocation

Cowork's write-scope enforcement is a static allowlist/denylist in
`.claude/settings.json`. It works, but it's binary: you can allow or deny a
tool pattern, and that's it.

Pi's `beforeToolCall` hook runs **your code** before every tool executes. It
receives the tool name, the parsed arguments, and full agent context. It can
return `{ block: true, reason: "..." }` to reject the call with a message the
agent sees.

**What this enables for Cadence:**

- **Write-scope enforcement** — same as Cowork, but in code. Check the target
  path of `write`/`edit` calls against the hierarchy level.
- **`status.yaml` protection** — if the agent tries to `write` or `edit`
  `status.yaml` directly, block it with: *"Use cadence_set_status instead."*
  Today this relies on the deny rule `Write(./status.yaml)` plus instructions
  in the skill. On Pi, the rejection message *tells the agent what to do
  instead* — the agent self-corrects in one turn instead of failing opaquely.
- **`.class.yaml` protection** — same pattern: block direct writes, redirect
  to `cadence_edit_class_yaml`.
- **Bash command filtering** — inspect the command string before execution.
  Block `rm -rf` on hierarchy paths, block direct `python set-status.py`
  invocations that bypass the tool wrapper (forces the agent through the
  TypeBox-validated tool interface).
- **Conditional enforcement** — write-scope rules can vary by *which skill is
  active*, not just by directory. During `/start`, the agent gets task-level
  scope. During `/onboard`, it gets class-level scope. The hook knows which
  command is running because the extension tracks it.

### 2. `afterToolCall` — Audit and Correction After Execution

Pi's `afterToolCall` hook runs after every tool completes. It can **modify the
result** the agent sees (field-by-field merge into the tool result).

**What this enables:**

- **Mutation audit log** — after any `write`, `edit`, or `cadence_set_status`
  call, log the change to a structured audit file. Today Cadence relies on git
  commits for audit trail. Pi lets you keep a parallel machine-readable log
  (who changed what, when, via which tool, during which skill).
- **Result enrichment** — after `load-context.py` runs, the hook can append
  validation warnings (e.g., "3 tasks are blocked — check before proceeding").
- **Auto-git-commit** — after any file mutation, automatically stage and
  commit. Cadence currently asks the agent to commit; this makes it
  infrastructure.

### 3. `prepareArguments` — Per-Tool Input Normalization

Each Pi tool definition can have a `prepareArguments` shim that transforms
arguments before `execute` runs.

**What this enables:**

- **Path normalization** — resolve relative paths to absolute, strip trailing
  slashes, canonicalize `..` traversals *before* the tool sees them. Prevents
  path-traversal bypasses of write-scope enforcement.
- **Default injection** — if `set-status` is called without a `reason`, inject
  a default from the current conversation context.
- **Schema-level validation** — Pi tools use TypeBox schemas. The argument
  types are validated *before* your code runs. Today, Cadence scripts do their
  own `sys.argv` parsing and validation (exit code 1). On Pi, malformed
  arguments never reach the Python script — they're caught at the schema layer.

### 4. TypeBox Tool Schemas — Type-Safe Boundaries

Cowork skills invoke scripts via bash (`python set-status.py $task_dir
$new_status`). The script parses `sys.argv` and validates. If the agent passes
wrong arguments, the script exits 1 and the agent reads stderr.

Pi tools define parameters with TypeBox JSON Schema:

```typescript
parameters: Type.Object({
    task_dir: Type.String({ description: "Absolute path to task directory" }),
    new_status: Type.Enum(StatusEnum),  // only valid statuses accepted
    reason: Type.Optional(Type.String({ maxLength: 500 })),
})
```

Invalid arguments are rejected *by the framework* before `execute` runs. The
agent gets a structured error. This is a free validation layer Cadence
currently implements by hand in every script.

### 5. Custom Agent Messages — Structured Event Trail

Pi supports custom message types via TypeScript declaration merging. These are
persisted in the session JSONL alongside LLM messages.

**What this enables:**

- **Status transition events** — when `cadence_set_status` succeeds, emit a
  `CadenceStatusChange` message with `{ task, from, to, timestamp }`. This
  creates a first-class event stream for the state machine, separate from
  the LLM conversation.
- **Skill boundary markers** — emit `CadenceSkillStart` / `CadenceSkillEnd`
  messages. The `beforeToolCall` hook reads these to know which skill is
  active and apply the correct write-scope rules.
- **Review decisions** — during `/done`, emit `CadenceReviewDecision` with
  the human's accept/reject and notes. Machine-readable review history.

### 6. `steer()` and `followUp()` — Programmatic Course Correction

Pi's agent has `steer(message)` (inject after current turn) and
`followUp(message)` (inject only if the agent would otherwise stop).

**What this enables:**

- **Guardrail steering** — if `afterToolCall` detects the agent wrote to a
  file it probably shouldn't have (e.g., modified `AGENT.md` during `/start`),
  steer it: *"You modified AGENT.md — this file is read-only during /start.
  Please revert the change."*
- **Completion checklist** — when the agent produces its final response during
  `/start`, inject a follow-up: *"Before finishing, verify: (1) all workpapers
  are in the period directory, (2) status is review_ready, (3) git commit
  includes all changes."*
- **Context refresh** — if the conversation runs long, inject a steering
  message that re-loads the SKILL.md and learned.md to prevent drift.

### 7. Extension Lifecycle Events — Session-Level Control

Pi extensions can subscribe to lifecycle events: session start/end, model
change, pre-switch (before session changes).

**What this enables:**

- **Automatic context loading (eliminates `load-context.py` at runtime)** —
  this is a major architectural improvement. On Cowork, every skill starts with
  instructions telling the agent to "run `load-context.py` and read the
  output." The dry run proved agents skip steps — if the agent skips context
  loading, it operates blind and produces garbage.

  On Pi, the extension's `session` lifecycle event fires *before the agent sees
  its first message*. The extension walks the hierarchy itself (root `AGENT.md`
  → class `AGENT.md` → `SKILL.md` + `learned.md` + `status.yaml`), assembles
  the full context chain, and injects it into the system prompt via
  `buildSystemPrompt()`. The agent starts every session with context already
  loaded — it's not a step it can forget, skip, or do wrong.

  `load-context.py` remains useful as a **developer/debugging tool** (humans
  can run it to inspect what the agent would see), but it exits the critical
  path of agent execution. Context loading becomes infrastructure, not an
  instruction.

  ```typescript
  // Simplified — what auto-loading looks like in the extension
  pi.on("session", async ({ event, context }) => {
      if (event === "start") {
          const cwd = context.cwd;
          const level = detectHierarchyLevel(cwd);  // root, class, or task
          const chain = await assembleContextChain(cwd, level);
          context.systemPrompt.append(chain);
      }
  });
  ```

  This also opens the door to **context refresh mid-session** — if `learned.md`
  is updated during `/done`, the extension can re-inject the updated context
  via `steer()` so the agent sees its own changes reflected immediately.

- **Session-end cleanup** — on session end, verify the task isn't left in
  `in_progress` (which would indicate a crash). If it is, log a warning or
  auto-transition to `blocked`.
- **Model-appropriate prompting** — on model change, adjust the system prompt
  for the model's strengths. Claude gets concise instructions; a weaker model
  gets more explicit step-by-step guidance.

### 8. Infrastructure Steps the Agent Shouldn't Be Doing

The auto-context-loading pattern generalizes. Across the four skills, there are
many steps that are currently *instructions the agent follows* but should be
*infrastructure the extension handles*. On Pi, these move from "agent judgment"
to "extension code" — eliminating entire classes of failure.

#### a. Git Commits — `afterToolCall` Auto-Commit

**Today:** Every skill ends with instructions like "run `git add .` and
`git commit -m '[start] <task> <period>: draft ready for review'`." The agent
has to remember the commit message format, stage the right files, and actually
do it. Sometimes it doesn't.

**On Pi:** The `afterToolCall` hook detects file mutations (`write`, `edit`,
or any `cadence_*` tool that changes state). At skill completion, the extension
auto-commits with the correct message format based on which command is active
and the current task/period. The agent never touches git.

```typescript
pi.on("tool", async ({ event, tool, result }) => {
    if (event === "after" && isMutatingTool(tool.name)) {
        trackMutation(tool, result);  // accumulate for end-of-skill commit
    }
});
```

#### b. Status Routing — Command Preconditions

**Today:** `/start` begins with "Read `status.yaml` and route based on the
status field." The agent reads the file, interprets the status, and decides
what to do. If it misreads, it goes down the wrong path.

**On Pi:** The `/start` command handler reads `status.yaml` *before invoking
the agent*, determines the routing, and injects the appropriate instructions.
The agent never sees the routing logic — it just gets "you are executing task X
for period Y" or "this task is blocked, present the issues to the user."

```typescript
pi.registerCommand("start", "Execute task for current period", async (ctx) => {
    const status = readStatusYaml(ctx.cwd);
    if (status.status === "done" || status.status === "abandoned") {
        ctx.notify("Task is already terminal. Nothing to do.");
        return;
    }
    if (status.status === "blocked") {
        ctx.agent.prompt(buildBlockedRecoveryPrompt(status));
        return;
    }
    // Normal path — run setup, then hand off to agent
    await runStartSetup(ctx.cwd, status);
    ctx.agent.prompt(buildExecutionPrompt(status));
});
```

#### c. Period Computation — Extension Logic, Not Agent Math

**Today:** The agent computes the period from the current date + period_format
+ anchor. "If monthly, use the previous month. If adhoc, ask the user." This
is date arithmetic the agent can get wrong.

**On Pi:** The command handler computes the period before the agent starts. The
agent receives "you are working on period 2026-03" as a fact, not a
calculation.

#### d. Dependency Installation — Session Start Hook

**Today:** `start-setup.py` calls `install-deps.py` as one of its four atomic
steps. The agent has to invoke the setup script.

**On Pi:** The extension's session start event activates the venv and installs
deps. By the time the agent's first turn begins, the environment is ready.

#### e. Location Validation — Command Preconditions

**Today:** `/status` starts with "Check `.class.yaml` exists in cwd. If not,
tell user to navigate." The agent does this check.

**On Pi:** The command handler checks before invoking the agent. If you're not
in the right directory, the user gets an immediate error — no LLM call wasted.

#### f. `/status` Dashboard — No LLM Needed At All

**Today:** `/status` is a skill the agent executes. But every step is pure
infrastructure — read files, derive status, format output. Zero judgment.

**On Pi:** `/status` is a command handler that reads `.class.yaml` and
`status.yaml` files, computes the rollup, and prints a formatted dashboard.
It never touches the LLM. Instant, free, deterministic.

```typescript
pi.registerCommand("status", "Show class progress dashboard", async (ctx) => {
    const dashboard = buildDashboard(ctx.cwd);  // pure file reads + math
    ctx.print(dashboard);  // no agent.prompt() — direct output
});
```

#### g. Skill-End Completion Checklist — `followUp()`

**Today:** The skill says things like "Check Completion Criteria before setting
`review_ready`." The agent may or may not actually check.

**On Pi:** After the agent's execution turn, the extension injects a follow-up:
*"Before finishing: (1) are all workpapers in the period directory? (2) do
outputs pass the validation rules in SKILL.md? (3) have you checked results
against learned.md patterns?"* The agent must respond to this before the
session ends.

### Summary: What Moves from Agent to Infrastructure

| Step | Cowork (agent does it) | Pi (extension does it) |
|---|---|---|
| Load hierarchy context | Agent runs `load-context.py` (skippable) | Auto-injected at session start |
| Read status and route | Agent reads file, interprets, decides | Command precondition — agent gets the right path |
| Compute period | Agent does date math | Command handler computes, agent gets the answer |
| Install dependencies | Agent invokes `start-setup.py` | Session start hook |
| Validate location | Agent checks for `.class.yaml` | Command precondition — instant error if wrong |
| Git add + commit | Agent runs git commands (skippable) | `afterToolCall` auto-commit with correct message |
| `/status` dashboard | Agent reads files, formats output | Pure command handler — no LLM call |
| Completion checklist | Instructions say "check before finishing" | `followUp()` forces the agent to verify |
| Crash detection | Agent re-enters `in_progress` (idempotent) | Session-end event catches orphaned state |

### Defense in Depth — Full Picture

| Cadence invariant | Cowork enforcement | Pi enforcement (layered) |
|---|---|---|
| Agent can't write outside its scope | `.claude/settings.json` deny rules | `beforeToolCall` hook + `prepareArguments` path normalization |
| Agent can't edit `status.yaml` directly | `Write(./status.yaml)` deny + instructions | `beforeToolCall` block with corrective message |
| Agent can't edit `.class.yaml` directly | `Write(./.class.yaml)` deny + instructions | `beforeToolCall` block with corrective message |
| Script arguments are valid | `sys.argv` parsing in each script (exit 1) | TypeBox schema validation + script-level validation (two layers) |
| State transitions are valid | `set-status.py` checks (exit 1) | TypeBox enum constraint + `set-status.py` checks (two layers) |
| All mutations are audited | Git commits (agent-initiated, skippable) | `afterToolCall` auto-commit + structured audit log |
| Context is loaded before execution | Skill instructions (skippable) | Extension lifecycle event — zero steps to skip |
| Status routing is correct | Agent reads + interprets (error-prone) | Command precondition — deterministic |
| Period is correct | Agent computes (error-prone) | Command handler computes — deterministic |
| Agent follows the skill procedure | Instructions only | Instructions + `followUp()` checklist + `steer()` corrections |
| Crash recovery | `in_progress` is idempotent | Same + session-end lifecycle event detects orphaned state |
| `/status` is accurate | Agent reads + formats (LLM cost) | Pure code — instant, free, deterministic |

The key insight: **Cowork gives you one enforcement point (static permission
rules). Pi gives you six (schema validation, argument preparation, pre-call
hooks, post-call hooks, steering, lifecycle events).** And beyond enforcement,
Pi lets you **remove entire steps from the agent's responsibility** — every
infrastructure step that becomes extension code is a step the agent can no
longer skip, misinterpret, or get wrong.

---

## What Doesn't Exist in Pi (Gaps to Fill)

### 1. Write-Scope Enforcement

**Cadence today:** Each hierarchy level has `.claude/settings.json` restricting
agent writes to that subtree. This is a hard permission boundary enforced by the
runtime — agents literally cannot write outside their scope.

**Pi today:** No sandboxing. Bash runs with full OS permissions. The docs
explicitly state "Pi packages run with full system access."

**Migration path:**
- Implement write-scope as a `beforeToolCall` hook in the Cadence extension.
  Pi's agent core supports `beforeToolCall` returning `{ block: true, reason }`
  to reject tool calls before execution.
- Intercept `write`, `edit`, and `bash` tool calls. For file tools, validate
  the target path is within the allowed scope. For bash, this is harder — we'd
  need to parse commands or run in a chroot/container.
- Alternatively, wrap the built-in tools with scoped versions that enforce
  path restrictions before delegating to the real implementation.
- **Risk:** Bash sandboxing is an unsolved problem in Pi. Cadence could
  contribute upstream, or accept that bash scope enforcement is best-effort
  (matching the current Cowork behavior, which also can't fully sandbox bash).

### 2. Environment Variable Contract

**Cadence today:** Scripts rely on `${CLAUDE_PLUGIN_ROOT}` and
`${CLAUDE_PLUGIN_DATA}` for path resolution.

**Migration path:**
- The Cadence extension sets these environment variables at startup.
- Or: refactor scripts to accept explicit `--plugin-root` / `--data-dir` args
  (better for portability anyway).

### 3. MCP Integration

**Cadence today:** `/done` uses MCP to archive periods to Google Drive. Cowork
handles OAuth and tool routing.

**Migration path:**
- Implement Google Drive archiving as a Pi tool via the extension API, using
  the Google Drive API directly (or a lightweight SDK).
- Pi's proxy module could handle auth token management for multi-user deploys.
- Long-term: Pi may add MCP support — it's a natural fit for its extension model.

### 4. Desktop Experience for Non-Developers

**Cadence today:** Cowork provides a desktop GUI for accountants and other
non-technical users.

**Pi today:** CLI-first with a TUI. There's a `pi-web-ui` package with web chat
components, but no standalone desktop app.

**Migration path:**
- For v1 of the Pi port, accept the CLI as the interface. Cadence's users during
  early adoption are likely technical enough.
- `pi-web-ui` could be wrapped in Electron/Tauri for a desktop experience later.
- The `pi-mom` Slack bot pattern shows Pi can be embedded in non-CLI surfaces.

---

## Proposed Architecture on Pi

```
cadence-pi/
├── packages/
│   └── cadence/                          # Pi extension package
│       ├── package.json                  # npm distributable with "pi" field
│       ├── src/
│       │   ├── index.ts                  # Extension factory — default export
│       │   ├── tools/
│       │   │   ├── set-status.ts         # Wraps set-status.py as a Pi tool
│       │   │   ├── edit-class-yaml.ts    # Wraps edit-class-yaml.py
│       │   │   ├── init-engagement.ts    # Wraps init-engagement.py
│       │   │   ├── load-context.ts       # Wraps load-context.py
│       │   │   ├── archive-period.ts     # Google Drive via API (replaces MCP)
│       │   │   └── ...                   # One tool wrapper per script
│       │   ├── hooks/
│       │   │   └── write-scope.ts        # beforeToolCall — enforces hierarchy boundaries
│       │   ├── commands/
│       │   │   ├── onboard.ts            # /onboard slash command
│       │   │   ├── start.ts              # /start
│       │   │   ├── done.ts               # /done
│       │   │   └── status.ts             # /status
│       │   └── context/
│       │       └── hierarchy-loader.ts   # Assembles root > class > task context chain
│       └── skills/                       # SKILL.md files (unchanged from Cowork version)
│           ├── onboard/SKILL.md
│           ├── start/SKILL.md
│           ├── done/SKILL.md
│           └── status/SKILL.md
│
├── scripts/                              # Python scripts (unchanged)
│   ├── init-engagement.py
│   ├── set-status.py
│   └── ...
│
└── tests/                                # Existing pytest suite (unchanged)
```

### How the Extension Works

```typescript
// cadence/src/index.ts — simplified
import { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { registerCadenceTools } from "./tools";
import { registerCadenceCommands } from "./commands";
import { enforceWriteScope } from "./hooks/write-scope";

export default function cadence(pi: ExtensionAPI) {
    // Register tools that wrap Python scripts
    registerCadenceTools(pi);

    // Register /onboard, /start, /done, /status commands
    registerCadenceCommands(pi);

    // Enforce write-scope boundaries via beforeToolCall
    pi.on("tool", ({ event, context }) => {
        if (event === "before") {
            return enforceWriteScope(context);
        }
    });
}
```

### Tool Wrapper Pattern

Each Python script becomes a Pi tool:

```typescript
// cadence/src/tools/set-status.ts — simplified
import { Type } from "@sinclair/typebox";

export const setStatusTool = {
    name: "cadence_set_status",
    label: "Set Task Status",
    description: "Transition a task's status (enforces valid state machine transitions)",
    parameters: Type.Object({
        task_dir: Type.String({ description: "Path to the task directory" }),
        new_status: Type.String({ description: "Target status" }),
        reason: Type.Optional(Type.String()),
    }),
    execute: async (args, { signal }) => {
        const result = await exec(
            "python", ["scripts/set-status.py", args.task_dir, args.new_status],
            { signal }
        );
        return {
            content: [{ type: "text", text: result.stdout }],
            details: { exitCode: result.exitCode },
        };
    },
    executionMode: "sequential" as const,
};
```

---

## Migration Phases

### Phase 0 — Abstraction Seam (Do Now, on Cowork)

Before touching Pi, isolate the harness coupling in the current codebase:

- [ ] Define a `HarnessInterface` that captures what Cadence needs from any
      runtime (skill dispatch, write-scope enforcement, context loading, tool
      invocation).
- [ ] Refactor scripts to accept explicit path arguments instead of relying on
      `${CLAUDE_PLUGIN_ROOT}`.
- [ ] Move write-scope rules into a Cadence-owned config format (e.g.,
      `.cadence/scope.yaml`) that the current Cowork plugin reads, so the rules
      aren't embedded in `.claude/settings.json`.
- [ ] Add integration tests that validate the interface contract, not the
      Cowork-specific implementation.

### Phase 1 — Proof of Concept (Pi Extension)

Build a minimal Cadence extension for Pi that can run `/start` on a single task:

- [ ] Create the extension scaffold (`package.json`, `index.ts`).
- [ ] Wrap `load-context.py`, `set-status.py`, `start-setup.py` as Pi tools.
- [ ] Implement the `/start` command using Pi's `registerCommand()`.
- [ ] Implement basic write-scope enforcement via `beforeToolCall`.
- [ ] Run against a test engagement hierarchy with a non-Anthropic model
      (e.g., GPT-4o via OpenAI, or a local model via Ollama).
- [ ] Validate that SKILL.md execution produces equivalent workpapers.

### Phase 2 — Full Port

- [ ] Port remaining commands (`/onboard`, `/done`, `/status`).
- [ ] Replace MCP-based Google Drive archiving with a native Pi tool.
- [ ] Port all 14 script wrappers.
- [ ] Adapt the test suite to run against both Cowork and Pi harnesses.
- [ ] Distribution: publish as an npm package installable via `pi install`.

### Phase 3 — Pi-Native Features

Things Pi enables that Cowork doesn't:

- [ ] **Automatic context loading** — eliminate `load-context.py` from the
      agent's critical path. Context is injected by the extension before the
      agent's first turn. `load-context.py` becomes a developer debugging tool
      only. This removes an entire class of failure mode (agent skips context
      loading) that the dry run exposed.
- [ ] **Model selection per task** — complex tasks get Opus, routine tasks get
      Haiku or a local model. Configurable in `.class.yaml`.
- [ ] **Session persistence** — Pi's JSONL sessions with branching could replace
      Cadence's fresh-instance model for tasks that benefit from conversation
      continuity (e.g., multi-step onboarding).
- [ ] **Self-hosted deployment** — Pi's proxy module + vLLM pods for
      organizations that can't send data to external APIs.
- [ ] **Slack integration** — `pi-mom` pattern: accountants interact via Slack
      instead of a CLI or desktop app.

---

## Risks and Open Questions

1. **Bash sandboxing.** Pi has none. Cadence's write-scope enforcement for bash
   commands will be best-effort (path checking on file-touching commands). Is
   this acceptable, or do we need container isolation?

2. **SKILL.md compatibility.** Pi's skill format matches Cadence's, but the
   system prompt injection differs. Need to verify that Cadence skills execute
   correctly when loaded by Pi's `formatSkillsForPrompt()`.

3. **Model quality variance.** Cadence skills were authored and tested against
   Claude. Some procedures may produce worse results on other models. Need a
   quality evaluation framework per model.

4. **Dual maintenance.** During migration, we'd maintain both Cowork and Pi
   targets. The abstraction seam (Phase 0) is critical to making this
   sustainable.

5. **Upstream stability.** Pi is a single-maintainer project (Mario Zechner).
   Evaluate bus factor and consider whether to fork or contribute upstream.

6. **Extension API maturity.** Pi's extension types file is 49 KB — the API
   surface is large but may have breaking changes as the project evolves.
   Pin to a specific version and track upstream.

---

## Decision Record

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-04-19 | Document migration strategy | Reduce vendor lock-in risk; Pi aligns well with Cadence's architecture |
| — | Phase 0 first | De-risk by abstracting before porting; keeps Cowork working while we build |
