# Hierarchy Independence and Portability

The most important architectural property of the hierarchy is that **it doesn't belong to the plugin that created it**. It belongs to the user. It's folders and markdown on a filesystem. Any runtime that knows how to walk the tree can load it.

The plugin scaffolds the hierarchy, but after that, the hierarchy is a standalone artifact. It doesn't import anything from the plugin, doesn't reference the plugin by path, and doesn't require the plugin to be installed in order to function. The hierarchy is exactly three levels deep (root → class → task) — see Section 5.3.

## What this enables

**Today:** A plugin scaffolds the hierarchy on the user's Cowork VM. The agent manages it through conversation in Cowork.

**Tomorrow:** The same hierarchy — same folders, same `.class.yaml` files, same SKILL.md files — could sit on a server. A headless agent, a CI pipeline, a cron job, or any orchestrator that can parse YAML and run Python can execute it. No plugin required. `load-context.py` is a standalone script — any caller can invoke it.

**Future (teams):** The hierarchy could be pushed to a git remote for collaboration, but multi-user support is out of scope for the MVP. The current design is single-user, local-only.

## Multiple hierarchies

Each plugin scaffolds its own hierarchy in a separate folder. No coordination needed.

```
~/Documents/Accounting/     ← scaffolded by accounting plugin
~/Documents/Legal/          ← scaffolded by legal plugin
~/Projects/Website/         ← scaffolded by engineering plugin
```

Each has its own root context and independent class/task structure. The runtime loads whichever one the user mounts.
