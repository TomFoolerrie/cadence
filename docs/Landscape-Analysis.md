# Landscape Analysis: Context Hierarchy Frameworks

**Author:** Dom LaRocco
**Date:** March 21, 2026
**Status:** Research Artifact
**Related:** [Context Hierarchy Spec](./Context-Hierarchy-Spec.md)

---

## 1. Executive Summary

No single tool combines local file ownership, domain-specific workflow templates, multi-level context hierarchy, and dependency orchestration. The Context Hierarchy Spec occupies an unserved intersection. This document maps the landscape, identifies the closest analogs, and extracts the most applicable ideas for incorporation.

---

## 2. The Context Engineering Landscape

### 2.1 The Field Has a Name Now

Anthropic's engineering team formally defined "context engineering" in September 2025 as *"the systematic curation of the smallest set of high-signal tokens that maximize the likelihood of desired model behavior."* This is distinct from prompt engineering — it encompasses the entire information flow: files loaded at startup, tools available, memory retrieved dynamically, conversation compaction, and sub-agent handoffs.

The field has converged on a key insight: **the agent harness is the new context.** Rather than clever prompting alone, the runtime loop managing plans, subagents, checkpoints, files, approvals, tool execution, and recovery is where context engineering lives.

### 2.2 Context Rot is Real

Chroma Research demonstrated that model performance degrades on retrieval tasks well before hitting token limits, and that degradation is sharper when query-answer similarity is low (i.e., in realistic long-horizon tasks). This validates the "folder as memory" approach — loading only what's needed, when it's needed, rather than stuffing everything into context.

---

## 3. Framework-by-Framework Analysis

### 3.1 Agent Orchestration Frameworks

#### CrewAI

- **Context storage:** YAML files for agent and task definitions; in-memory state during execution; tool outputs chained between tasks via a `context` attribute.
- **Hierarchical inheritance:** Declarative YAML supports task dependency graphs. One task's output can be explicitly listed as context for a downstream task — not automatic inheritance, you wire it manually.
- **Task orchestration:** Role-based (agents as employees with responsibilities). Sequential, parallel, and hierarchical crews. Task dependency via `context:` field.
- **Data ownership:** Local by default. YAML configs are user-owned files on disk. No mandatory cloud.
- **Agent statefulness:** Essentially stateless per run. Multi-run memory requires external stores.
- **Learning loops:** Limited built-in. Relies on external memory integrations.
- **Versioning/audit:** YAML configs are version-controllable. No built-in audit trail of agent decisions.

**Assessment:** Closest to the Spec's mental model in terms of using files to configure context, but it is workflow-config-as-files rather than task-state-as-files. The folder structure holds configuration, not runtime memory.

---

#### LangGraph

- **Context storage:** Typed state objects (Python `TypedDict`); persisted via "checkpointers" (SQLite locally, Postgres in production). State is structured objects, not free-form files.
- **Hierarchical inheritance:** Graph nodes pass state through edges. Sub-graphs nest. No automatic inheritance.
- **Task orchestration:** Graph-based (nodes = tasks, edges = control flow). Conditional branching, parallel fan-out/fan-in, interrupt-and-resume. Dependency expressed as graph topology.
- **Data ownership:** Local (SQLite checkpointer) or cloud via LangSmith. Checkpointed state is in a database, not human-readable files.
- **Agent statefulness:** Fully stateful per thread. Checkpoints survive process restarts.
- **Learning loops:** LangSmith provides tracing and evaluation. State rewinding ("time travel") enables debugging and replay.
- **Versioning/audit:** Checkpoints form a complete history. LangSmith provides full trace visualization. Not git-native.

**Assessment:** Most powerful for complex conditional workflows with explicit dependency management. State is not file-based (database-stored TypedDict), so it does not match the "human-readable folder" criterion. Strong on orchestration and auditability.

---

#### AutoGen / Microsoft Agent Framework

- **Context storage:** In-memory conversation objects. External storage via plugins. Microsoft's combined Semantic Kernel + AutoGen framework adds session-based state management.
- **Hierarchical inheritance:** Group chat patterns where agents converse and pass context via messages. Nested agents possible. Not structured as a file hierarchy.
- **Task orchestration:** Conversation-driven. Agents negotiate roles dynamically. More flexible than CrewAI but less structured than LangGraph.
- **Data ownership:** Local by default. Azure deployment option.
- **Agent statefulness:** Stateless per conversation unless persistence added externally.
- **Learning loops:** AutoGen's Agent Workflow Memory (AWM) induces reusable workflow patterns from training examples, selectively provided to agents at runtime.
- **Versioning/audit:** Limited built-in. Relies on logging infrastructure.

**Assessment:** Best for dynamic, research-style collaboration where roles emerge from conversation. Not a natural fit for structured file-based workflows.

---

#### TaskWeaver (Microsoft Research)

- **Context storage:** Code-first approach. Context maintained as a running Python session (like a Jupyter kernel). Persistent state across sub-tasks within a session.
- **Hierarchical inheritance:** Planner -> CodeInterpreter architecture. Planner decomposes tasks and passes context to code executor. Three dependency types: sequential, interactive, and none.
- **Task orchestration:** Strong — explicit dependency typing between sub-tasks. Vision input support added March 2025.
- **Data ownership:** Local. Runs on-premise.
- **Agent statefulness:** Stateful within a session. Fresh state per new session.
- **Learning loops:** Plugin system for encapsulating domain functions. No built-in cross-session learning.
- **Versioning/audit:** Code generated per task is capturable. No built-in audit trail.

**Assessment:** Uniquely suited for data analytics workflows where tasks involve executable code. The "running Python session as context" is an interesting alternative to file-based memory. Less general than the Spec's use case but worth noting for the dependency model.

---

#### Agency Swarm

- **Context storage:** `files_folder` and `schemas_folder` per agent. Per-agent workspace directories with `/workspace/personal/memory/` subdirectories.
- **Hierarchical inheritance:** Memory files automatically indexed. Relevant memories retrieved before each task and injected into context. Files can be "promoted" from personal to swarm scope.
- **Task orchestration:** Agent-to-agent handoffs via shared communication channel. Each agent can spawn tasks for other agents.
- **Data ownership:** Partially local — workspace directories are user-owned. Relies on OpenAI Assistants API for execution.
- **Agent statefulness:** Hybrid — agents are fresh per call but memory files persist between calls, simulating statefulness.
- **Learning loops:** Memory indexed and retrieved. Agents can write new memory files after tasks.
- **Versioning/audit:** OpenAI API logs. No built-in git-based versioning.

**Assessment:** The `/workspace/personal/memory/` pattern is the closest existing multi-agent framework to the Spec's "folder as memory" model. The memory promotion mechanism (personal -> swarm scope) maps to root -> class -> task inheritance. Limited by OpenAI API dependency.

---

#### Google ADK (Agent Development Kit)

- **Context storage:** `InvocationContext` object compiled at runtime from session state. Dynamic variable substitution from state into system prompts via `{key}` placeholders.
- **Hierarchical inheritance:** Strong — parent agents compose focused context for sub-agents, passing only relevant information via `include_contents` controls. Sub-agents inherit from parent automatically.
- **Task orchestration:** Multi-agent composition with explicit delegation. Parallel sub-agent execution. Sequential pipelines. Context propagation is framework-managed.
- **Data ownership:** Local (open source). Google Cloud deployment option.
- **Agent statefulness:** Session-scoped state. Persistent state via `SessionService`.
- **Learning loops:** Context Engineering framework via `InstructionProcessor`. Dynamic state injection at runtime.
- **Versioning/audit:** Structured logging. No built-in git-native versioning.

**Assessment:** Most sophisticated built-in context propagation mechanism of any framework reviewed. The "context as compiled view over stateful systems" philosophy aligns with the Spec's goals, though the implementation uses state objects rather than files.

---

### 3.2 Memory and Context Management Systems

#### Letta (formerly MemGPT) — MemFS

- **Context storage:** Git-backed filesystem of markdown files organized hierarchically (15-25 focused files). `system/` directory for files pinned to the system prompt. Frontmatter descriptions index each file.
- **Hierarchical inheritance:** File hierarchy is the inheritance structure. `system/` files are inherited by all tasks. Subdirectory organization is agent-managed.
- **Task orchestration:** Memory skills (initialize, reflect, defragment) are orchestrated subagents. Concurrent subagents use isolated git worktrees, then merge.
- **Data ownership:** Full local ownership. Filesystem is the artifact. Git-backed.
- **Agent statefulness:** Hybrid — MemFS persists across agent instances. Any fresh agent can pick up by reading the filesystem.
- **Learning loops:** Background reflection subagent continuously distills conversation history into persistent markdown. Defragmentation reorganizes to prevent entropy.
- **Versioning/audit:** Native git history on MemFS. Every memory write gets an informative commit message. Subagent changes merged via standard git conflict resolution.

**Assessment:** The most direct implementation of the Spec's core concept in the existing landscape. MemFS is a git-backed hierarchy of markdown files serving as the agent's persistent brain, enabling fresh agents to resume any task by reading the filesystem. Key difference: Letta is a general coding agent — no domain-specific workflow scaffolding.

---

#### Mem0

- **Context storage:** Hybrid — vector embeddings (semantic search) + graph database (relationships) + key-value store (fast fact retrieval). Not file-based.
- **Hierarchical inheritance:** None. Flat memory namespace with semantic retrieval.
- **Task orchestration:** Not an orchestration framework. Memory layer that integrates into other frameworks.
- **Data ownership:** Self-hostable via Docker (Postgres + pgvector + Neo4j). OpenMemory MCP provides a fully local option.
- **Agent statefulness:** Stateful memory layer. Agents query Mem0 at session start to retrieve relevant prior context.
- **Learning loops:** Automatic extraction and storage of facts from conversations. Graph relationships update over time.
- **Versioning/audit:** No built-in versioning. Self-hosted relies on database snapshots.

**Assessment:** Strong memory layer for integration into other frameworks, but it is a database, not a filesystem. Does not match the "human owns readable files" criterion.

---

#### Zep

- **Context storage:** Temporal knowledge graph that tracks how facts change over time. Combines graph memory with vector search.
- **Hierarchical inheritance:** Graph-based relationships rather than hierarchical file scopes.
- **Task orchestration:** Memory layer only.
- **Data ownership:** Enterprise SaaS. Self-host option available.
- **Agent statefulness:** Stateful. Tracks temporal evolution of facts.
- **Learning loops:** Automatic graph construction from conversations. Temporal awareness distinguishes it from Mem0.
- **Versioning/audit:** Temporal graph inherently tracks changes over time. Enterprise audit logging.

**Assessment:** Best-in-class for temporal memory evolution, useful when facts change over time (e.g., client preferences, evolving regulatory requirements). Not file-based. Not suited for human-readable local ownership.

---

### 3.3 Academic Research

#### A-MEM (Agentic Memory) — arXiv 2502.12110

Interconnected knowledge notes following the Zettelkasten method. Dynamic indexing and linking between memory nodes. Notes evolve autonomously. Retrieval is associative rather than hierarchical.

**Relevance:** The "evolving interconnected notes" model could inspire how cross-domain knowledge links across the task hierarchy.

---

#### H-MEM (Hierarchical Memory) — arXiv 2507.22925

Four-layer memory hierarchy: Domain Layer -> Category Layer -> Memory Trace Layer -> Episode Layer. Search is hierarchical (layer by layer) via position index.

**Relevance:** The most theoretically aligned academic work with the Spec's multi-level context inheritance. The four-layer hierarchy (Domain -> Category -> Memory Trace -> Episode) maps directly to root -> class -> task.

---

#### G-Memory (Multi-Agent Hierarchical Memory) — arXiv 2506.07398

Three-tier graph hierarchy: insight graph (generalizable principles) -> query graph (task-level experiences) -> interaction graph (agent-specific collaboration trajectories). Each agent maintains its own memory tier. A shared insight layer captures cross-agent generalizations.

**Relevance:** The most sophisticated academic work on multi-agent hierarchical memory. The three-tier architecture separating agent-specific trajectories from generalizable insights is directly applicable — recurring workflow patterns (e.g., monthly close procedures) should rise to a "shared insight" level.

---

#### ACE (Agentic Context Engineering) — arXiv 2510.04618

Treats contexts as "evolving playbooks" that accumulate, refine, and organize strategies. Generator produces reasoning trajectories. Reflector evaluates and extracts insights. Curator converts insights into structured delta updates with helpful/harmful counters. Prevents "context collapse" (where iterative rewriting erodes details) via structured incremental updates. +10.6% improvement on agent benchmarks; +8.6% on finance-specific benchmarks.

**Relevance:** Directly applicable. Shows that maintaining a structured, evolving context document and applying structured incremental updates (rather than rewriting wholesale) is the right approach for domain-specific recurring workflows.

---

### 3.4 File-Based Context Standards

#### AGENTS.md (Linux Foundation / Agentic AI Foundation)

Directory-scoped context inheritance: the closest AGENTS.md to the file being edited takes precedence, with optional upward inheritance. Explicit user prompts override everything. Supported by Claude Code, Cursor, Copilot, Windsurf, Aider, and others.

**Assessment:** The foundational primitive the Spec builds on. The AGENTS.md hierarchy (`root/AGENTS.md` -> `subdirectory/AGENTS.md` -> task-specific overrides) is exactly the multi-level context inheritance model. The gap: no runtime orchestration or dependency management — which is what the Spec adds.

---

#### Manus / Planning-with-Files Pattern

Three-file pattern: `task_plan.md` (phases, progress, decisions), `findings.md` (research and knowledge), `progress.md` (session log). Filesystem is disk, context window is RAM. Session recovery by re-reading plan file. Validated at production scale ($2B acquisition).

**Assessment:** The closest existing pattern to the "folder as memory, fresh agent per task" model. The `planning-with-files` GitHub project (OthmanAdi) operationalizes this as a Claude Code skill installable in 40+ agents. Limitation: single-session and single-level — no cross-task or cross-project hierarchy.

---

#### Andrew Ng's Context Hub (andrewyng/context-hub)

Curated markdown documentation files for specific APIs, fetched via CLI. Local annotation registry for agent-discovered workarounds. `chub annotate` allows agents to save discovered workarounds. Community-level feedback loop.

**Assessment:** Narrow but elegant solution to "stale API knowledge." The annotate -> community feedback -> curated docs loop is a model for how domain-specific knowledge can be maintained as a versioned file corpus.

---

### 3.5 Domain-Specific Platforms (Accounting / Finance)

The Big 4 have all launched proprietary multi-agent platforms:

| Firm | Platform | Architecture |
|------|----------|-------------|
| PwC | Agent OS | ERP/CRM inputs -> proprietary knowledge layer -> governance hub -> structured output. Cloud-hosted. |
| EY | EY.ai Agentic Platform | 150 specialized tax agents for 80,000 professionals. Opaque architecture. |
| KPMG | Workbench | Multi-agent collaboration modeled on human audit teams. Agent handoffs mirror dependency models. |
| Deloitte | (Unnamed) | Embedded agents in SAP/Oracle/Workday ERP workflows. |

Independent players (Docyt, Basis, Truewind, Mesha) are all proprietary cloud SaaS.

**The critical gap:** Every domain-specific accounting/finance AI platform is either proprietary cloud SaaS (no local file ownership) or a general-purpose framework without domain-specific workflow scaffolding. None combine local file ownership + domain-specific workflow templates + hierarchical context inheritance.

---

## 4. Comparative Matrix

| Framework | File-Based Context | Hierarchical Inheritance | Task Orchestration | Local Data Ownership | Stateless Per Task | Learning Loops | Versioning/Audit |
|---|---|---|---|---|---|---|---|
| **Letta MemFS** | High | High | High | High | Yes | High | High (git) |
| **AGENTS.md** | High | High | None | High | Yes | None | High (git) |
| **Manus/planning-with-files** | High | Low (single level) | Low | High | Yes | Low | Medium (git) |
| **Agency Swarm** | High | Medium | Medium | Medium | Yes | Medium | Low |
| **Google ADK** | Low (state objects) | High | High | Medium | No | Low | Medium |
| **LangGraph** | None (DB) | Medium | High | Medium | No | Low | High (checkpoints) |
| **CrewAI** | Medium (YAML config) | Low | High | High | Medium | Low | Medium |
| **ACE** | Medium (evolving docs) | Low | None | High | N/A | High | Low |
| **Mem0** | None (DB) | None | None | Medium | No | High | None |
| **Zep** | None (graph DB) | None | None | Low | No | High | Medium |
| **Context Hierarchy Spec** | **High** | **High** | **High** | **High** | **Yes** | **High** | **High (git)** |

---

## 5. Empirical Validations

### 5.1 File-Based Memory Outperforms Vector DBs

Letta's benchmark study: filesystem-based agent scored 74% on LoCoMo vs Mem0's specialized graph memory at 68.5%. Attributed to LLMs being highly trained on filesystem tool use (especially from coding data). The instinct to use files rather than vector databases is supported by production benchmarks, not just philosophy.

### 5.2 "Fresh Agent Per Task" is Production-Validated

The Manus pattern — context window is RAM, filesystem is disk — was validated at the $2B acquisition scale. A fresh agent reads the plan file, executes work, writes updates, and exits.

### 5.3 Git is the Universal Audit Layer

Letta MemFS, planning-with-files, and AGENTS.md all converge on git as the natural audit and versioning layer. Every context update is a commit; history is a free audit trail.

### 5.4 Hierarchical Memory is Academically Validated

H-MEM's four-layer hierarchy and G-Memory's multi-agent insight distillation both map directly to the root -> class -> task model and demonstrate measurable improvements over flat memory architectures.

---

## 6. Ideas Worth Stealing

### 6.1 From Letta MemFS: Frontmatter Metadata on All Files

Every markdown file carries YAML frontmatter with `name`, `description`, `type`. The agent uses frontmatter to decide relevance *before* reading the full file. The orchestrator can scan descriptions without loading full content.

**Application:** Add frontmatter to `SKILL.md` and `learned.md`. The future orchestrator can scan task descriptions across a class without loading every full procedure.

**Priority:** Low (nice-to-have for orchestrator).

---

### 6.2 From ACE: Structured Delta Updates to learned.md

ACE never rewrites the full context document. It applies deltas: "add this insight," "increment the confidence counter on this pattern," "mark this strategy as harmful." This prevents "context collapse" where iterative rewriting erodes important details over time.

**Application:** During `/done`, instead of the agent rewriting `learned.md` sections, it appends structured entries that accumulate evidence. Each pattern carries a confirmation count and a contradiction count. The agent consolidates when counts are high enough to establish confidence, not on every cycle.

**Example:**
```markdown
## Patterns

- **Chase fee descriptions contain category codes after the pipe character**
  Confirmed: 8 | Contradicted: 0 | First seen: 2025-09
  Used for: fee_categorizer.py input parsing

- **International wire fees appear as "WIRE INTL" not "INTL WIRE"**
  Confirmed: 5 | Contradicted: 1 (2026-01 had "INTL WIRE TRF")
  Used for: fee_categorizer.py pattern matching
```

**Priority:** High — prevents context collapse over many cycles.

---

### 6.3 From ACE: Helpful/Harmful Counters on Strategies

Each learned pattern carries a score. "Fee categorization by description keyword: helpful 8 times, harmful 1 time." This gives the agent (and future orchestrator) a confidence signal when deciding whether to trust a learned pattern.

**Application:** `learned.md` entries carry explicit confidence signals. Low-confidence patterns are flagged for human review. High-confidence patterns are trusted by the orchestrator.

**Priority:** Medium — becomes important when the orchestrator reviews autonomously.

---

### 6.4 From Letta MemFS: Git Worktrees for Parallel Execution

When multiple tasks run in parallel (future orchestrator), each sub-agent gets its own git worktree. Changes merge via standard git. This solves parallel execution without filesystem conflicts.

**Application:** The orchestrator launches sub-agents in isolated worktrees. Each task writes to its own `status.yaml` and `periods/` without conflicting. After completion, changes merge. Conflicts (unlikely given task isolation) resolve via standard git tooling.

**Priority:** Future state — but the architecture should not preclude this.

---

### 6.5 From G-Memory: Cross-Task Knowledge Promotion

G-Memory automatically promotes patterns upward when they appear across multiple agents. Agent-specific experiences (bottom tier) -> task-level patterns (middle tier) -> generalizable insights (top tier).

**Application:** If three different treasury tasks all learn "Chase changed their PDF format in March," that insight should promote from individual `learned.md` files up to the class level (or root level). A future `/done` could detect cross-task patterns and propose class-level or root-level learnings.

**Mechanism:** During `/done`, the agent checks whether the current learning overlaps with patterns in sibling tasks' `learned.md` files. If a pattern appears in 2+ tasks within the same class, the agent proposes promoting it to a class-level `learned.md` or the class `tools/` directory.

**Priority:** Future state — but validates adding a class-level `learned.md` to the spec.

---

### 6.6 From Letta MemFS: Defragmentation as First-Class Operation

A periodic "cleanup" agent reorganizes accumulated knowledge, merges redundant entries, and restructures files. The Spec's `learned.md` self-consolidation is this concept, but Letta makes it an explicit operation rather than an implicit behavior.

**Application:** Consider a `/maintain` skill (or a flag on `/done`) that triggers a focused consolidation pass on `learned.md`. Separate from the normal review cycle. Runs when `learned.md` exceeds a size threshold or after N cycles.

**Priority:** Medium — prevents learned.md from growing unbounded.

---

### 6.7 From AGENTS.md: Standard Inheritance Mechanism

If AGENTS.md becomes the universal standard for directory-scoped context inheritance, the hierarchy could adopt it as the native inheritance mechanism rather than a custom `prime-context.sh` script. Worth watching for ecosystem convergence.

**Priority:** Watch — depends on ecosystem adoption velocity.

---

### 6.8 From Manus: Explicit Session Recovery Path

On session start, read the progress file, determine what's done and what's next, resume. Make the recovery path explicit rather than implicit.

**Application:** `prime-context.sh --level task` already loads `status.yaml`, but the recovery logic (what to do when `status` is `error` or `rejected`) could be more explicit in the loaded context. The agent should see not just "status: error" but also "recovery action: retry or block" as part of the primed context.

**Priority:** Low — the status transitions already define this, but making it visible in the primed context reduces agent reasoning errors.

---

## 7. The Gap Being Filled

### What exists but doesn't combine:

```
Letta MemFS          = git-backed markdown hierarchy + fresh agents
Planning-with-files  = folder as memory + session recovery
AGENTS.md            = directory-scoped inheritance standard
ACE                  = structured learning loops with delta updates
LangGraph            = dependency-aware task orchestration
CrewAI               = role-based YAML workflow definitions
```

### What the Context Hierarchy Spec adds:

```
Domain-specific recurring workflow templates     (no one has this as files)
Class-level orchestration with dependency DAG     (no one has this as YAML + files)
Three-tier context inheritance with runtime state (AGENTS.md has config only)
Human-in-the-loop review cycle baked into state   (no one models this)
Local file ownership as architectural principle    (Big 4 have it as cloud SaaS)
```

### Competitive risks to watch:

1. **Letta MemFS** expanding beyond coding into domain-specific workflows
2. **Agency Swarm** workspace model maturing into full orchestration
3. **Big 4 platforms** opening their workflow template libraries (unlikely near-term)
4. **AGENTS.md** adding orchestration semantics to the standard

---

## 8. Sources

### Frameworks and Tools
- [CrewAI vs LangGraph vs AutoGen: Choosing the Right Multi-Agent AI Framework](https://www.datacamp.com/tutorial/crewai-vs-langgraph-vs-autogen)
- [Introducing Context Repositories: Git-based Memory for Coding Agents](https://www.letta.com/blog/context-repositories)
- [Benchmarking AI Agent Memory: Is a Filesystem All You Need?](https://www.letta.com/blog/benchmarking-ai-agent-memory)
- [GitHub - OthmanAdi/planning-with-files](https://github.com/OthmanAdi/planning-with-files)
- [GitHub - VRSEN/agency-swarm](https://github.com/VRSEN/agency-swarm)
- [GitHub - microsoft/TaskWeaver](https://github.com/microsoft/TaskWeaver)
- [LangGraph Multi-Agent Orchestration Architecture Analysis 2025](https://latenode.com/blog/ai-frameworks-technical-infrastructure/langgraph-multi-agent-orchestration/)
- [Semantic Kernel Agent Orchestration](https://learn.microsoft.com/en-us/semantic-kernel/frameworks/agent/agent-orchestration/)
- [OpenMemory MCP: Local Persistent Memory](https://mem0.ai/blog/introducing-openmemory-mcp)

### Standards and Patterns
- [AGENTS.md: One File to Guide Them All](https://layer5.io/blog/ai/agentsmd-one-file-to-guide-them-all/)
- [Effective Context Engineering for AI Agents (Anthropic)](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [The Complete Guide to AI Agent Memory Files](https://medium.com/data-science-collective/the-complete-guide-to-ai-agent-memory-files-claude-md-agents-md-and-beyond-49ea0df5c5a9)
- [Hierarchical Context Architecture Pattern](https://agentic-design.ai/patterns/context-management/hierarchical-context-architecture)
- [Context Engineering: The Definitive 2025 Guide](https://www.flowhunt.io/blog/context-engineering/)
- [Andrew Ng's Team Releases Context Hub](https://www.marktechpost.com/2026/03/09/andrew-ngs-team-releases-context-hub/)

### Academic Papers
- [ACE: Agentic Context Engineering (arXiv 2510.04618)](https://arxiv.org/abs/2510.04618)
- [H-MEM: Hierarchical Memory (arXiv 2507.22925)](https://arxiv.org/pdf/2507.22925)
- [G-Memory: Tracing Hierarchical Memory for Multi-Agent Systems (arXiv 2506.07398)](https://arxiv.org/abs/2506.07398)
- [A-MEM: Agentic Memory for LLM Agents (arXiv 2502.12110)](https://arxiv.org/abs/2502.12110)
- [GitHub - Meirtz/Awesome-Context-Engineering](https://github.com/Meirtz/Awesome-Context-Engineering)

### Domain-Specific Platforms
- [PwC announces Agent OS](https://www.accountingtoday.com/news/pwc-announces-agent-os-for-coordinating-ai-agents)
- [The Big 4 AI Agents of 2025](https://unity-connect.com/our-resources/blog/big-4-ai-agents/)
- [AI Agent Memory Systems in 2026 Compared](https://yogeshyadav.medium.com/ai-agent-memory-systems-in-2026-mem0-zep-hindsight-memvid-and-everything-in-between-compared-96e35b818da8)
