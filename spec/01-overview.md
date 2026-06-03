# Overview

## 1. The Idea in One Paragraph

A plugin doesn't *contain* the context hierarchy — it **scaffolds and manages** one on the user's computer. The hierarchy has three levels: **root** (engagement context), **classes** (groups of related work — treasury, reporting, collections), and **tasks** (individual units of work that the user executes). A plugin ships an engagement template with class directories and scaffolding scripts. When a user installs the plugin and selects a working folder, the agent sets up the hierarchy. Classes contain a `.class.yaml` (manifest listing tasks and execution order) — this is the orchestration layer — and an `AGENTS.md` (class description and context for task agents). Tasks contain `SKILL.md` (what to do), `learned.md` (what's been learned), `status.yaml` (current state), `tools/` (scripts), and `periods/` (period-specific work). The user lives at the task level. Context flows downward: a task inherits its class context (via class `AGENTS.md`), which inherits the root context (via root `AGENTS.md`). Both root and class levels use `AGENTS.md` for consistency. The hierarchy belongs to the user, persists between sessions, and is just normal folders on their computer.

---

## 2. Why This Matters

Today, Claude loads context from two disconnected worlds: the plugin's internal files (SKILL.md, references/) and whatever happens to be in the user's mounted folder. There's no formal structure connecting the two, and no way for a plugin to say "when working in this folder, always load the engagement context first, then the class definition, then the task's procedure and learning history."

This spec gives plugins the ability to **project a structured context hierarchy onto the user's filesystem**. The benefits:

- **Data belongs to the user.** Uninstalling the plugin doesn't delete their files. The hierarchy persists on their machine.
- **Three clear levels.** Root (context), Class (orchestration), Task (execution). Each level has a defined purpose and a defined set of files.
- **The user lives at the task level.** Day-to-day work happens in tasks — that's where SKILL.md, learned.md, tools, and period work live. The higher levels provide context, not interaction.
- **Classes are the orchestration boundary.** Today a human picks which task to run. Tomorrow an orchestrator agent reads `.class.yaml`, sees the manifest, and runs all tasks in order — launching sub-agents for each one.
- **Context inheritance.** A task automatically sees its class context and root context. No manual wiring. The runtime walks up the tree.
- **Every task gets smarter.** `learned.md` captures patterns, failures, and review history. Each execution cycle is informed by every previous one.
- **Fresh agent per task.** The folder is the memory, not the agent. A fresh instance reads the docs, runs the tools, produces output, and terminates. Nothing carries over except what's written to the folder.
- **Git-versioned.** Every change is committed automatically. Full undo history, diffable state.
- **Developer escape hatch.** Devs can hand-edit any file directly. The agent picks up their changes next session.

---

## 3. Portability

The hierarchy **doesn't belong to the plugin that created it** — it belongs to the user. It's folders and markdown on a filesystem. Any runtime that knows how to walk the tree can load it. The plugin scaffolds the hierarchy, but after that, the hierarchy is a standalone artifact. It doesn't import anything from the plugin, doesn't reference the plugin by path, and doesn't require the plugin to be installed.

**Today:** A plugin scaffolds the hierarchy on the user's Cowork VM. The agent manages it through conversation. **Tomorrow:** The same hierarchy could sit on a server — a headless agent, a CI pipeline, or any orchestrator that can parse YAML and run Python can execute it. `load-context.py` is a standalone script.

Each plugin scaffolds its own hierarchy in a separate folder. No coordination needed — each has its own root context and independent class/task structure.
