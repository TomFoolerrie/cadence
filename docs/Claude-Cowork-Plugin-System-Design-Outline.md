# Claude Cowork Plugin System — Design Outline

**Author:** Dom LaRocco
**Date:** March 21, 2026
**Status:** Research Document

---

## 1. Executive Summary

The Claude Cowork plugin system is a modular extension architecture shared between Claude Code (the CLI tool) and Cowork (the desktop app for knowledge work). Plugins are self-contained directory bundles that extend Claude's capabilities with skills, commands, agents, hooks, MCP (Model Context Protocol) servers, and LSP (Language Server Protocol) servers. They are packaged as `.plugin` files, distributed through marketplaces (including Anthropic's official marketplace), and installed locally on the user's machine.

This document outlines the full architecture — from the directory layout and manifest schema, through each component type, to the marketplace distribution system and enterprise governance model.

---

## 2. Architectural Overview

### 2.1 Design Philosophy

The plugin system is built around several core principles:

- **Self-contained portability.** A plugin is a directory. Everything it needs lives inside that directory (or is declared as an external dependency via MCP). No hidden state, no ambient configuration.
- **Progressive disclosure.** Metadata is always in context (~100 words); skill bodies load on trigger (~3,000 words); reference files load on demand (unlimited). This keeps the context window lean.
- **Namespace isolation.** Every plugin component is prefixed with the plugin name (e.g., `/my-plugin:hello`) to prevent collisions when multiple plugins coexist.
- **Shared architecture, different surfaces.** The same plugin format works in both Claude Code (terminal) and Cowork (desktop app). Cowork users tend to rely more on skills and commands; developers in Claude Code also use hooks, agents, and LSP servers.

### 2.2 High-Level Data Flow

```
User installs plugin from marketplace (or loads via --plugin-dir)
        │
        ▼
Plugin directory copied to local cache (~/.claude/plugins/cache)
        │
        ▼
Claude Code / Cowork reads plugin.json manifest
        │
        ▼
Auto-discovers components: skills/, commands/, agents/, hooks/, .mcp.json, .lsp.json
        │
        ▼
Components registered:
  ├── Skills/commands → available as /plugin-name:skill-name
  ├── Agents → available in /agents list
  ├── Hooks → bound to lifecycle events
  ├── MCP servers → started, tools exposed
  └── LSP servers → started, diagnostics flowing
```

---

## 3. Plugin Directory Structure

Every plugin follows this canonical layout. Only `.claude-plugin/plugin.json` is strictly required (and even the manifest is optional if defaults suffice). All other directories are created only for the component types the plugin uses.

```
plugin-name/
├── .claude-plugin/
│   └── plugin.json           # Plugin manifest (required)
├── commands/                  # Slash commands (.md files)
│   ├── review.md
│   └── deploy.md
├── skills/                    # Agent Skills (subdirs with SKILL.md)
│   └── coding-standards/
│       ├── SKILL.md
│       └── references/
│           └── style-rules.md
├── agents/                    # Subagent definitions (.md files)
│   └── ticket-analyzer.md
├── hooks/                     # Event handlers
│   └── hooks.json
├── scripts/                   # Utility scripts for hooks/skills
│   └── validate.sh
├── settings.json              # Default settings (e.g., default agent)
├── .mcp.json                  # MCP server definitions
├── .lsp.json                  # LSP server definitions
├── CONNECTORS.md              # Tool-agnostic connector mappings (optional)
├── README.md                  # Documentation
├── LICENSE
└── CHANGELOG.md
```

**Critical rule:** Component directories (`commands/`, `agents/`, `skills/`, `hooks/`) go at the plugin root — never inside `.claude-plugin/`. Only `plugin.json` lives in `.claude-plugin/`.

---

## 4. Plugin Manifest (`plugin.json`)

Located at `.claude-plugin/plugin.json`. The only required field is `name`.

### 4.1 Schema

```json
{
  "name": "plugin-name",              // Required. Kebab-case, lowercase.
  "version": "1.0.0",                 // Semver. MAJOR.MINOR.PATCH.
  "description": "Brief explanation",
  "author": {
    "name": "Author Name",
    "email": "author@example.com",
    "url": "https://example.com"
  },
  "homepage": "https://docs.example.com",
  "repository": "https://github.com/user/plugin",
  "license": "MIT",
  "keywords": ["keyword1", "keyword2"],

  // Optional: custom component paths (supplement defaults, don't replace)
  "commands": ["./custom/commands/"],
  "agents": "./custom/agents/",
  "skills": "./custom/skills/",
  "hooks": "./config/hooks.json",
  "mcpServers": "./mcp-config.json",
  "lspServers": "./.lsp.json",
  "outputStyles": "./styles/"
}
```

### 4.2 Environment Variables

Two special variables are available across all plugin component files:

| Variable | Purpose | Persistence |
|----------|---------|-------------|
| `${CLAUDE_PLUGIN_ROOT}` | Absolute path to the plugin's installation directory. Use for bundled scripts, configs, and binaries. | Replaced on each plugin update. |
| `${CLAUDE_PLUGIN_DATA}` | Persistent directory for plugin state (`~/.claude/plugins/data/{id}/`). Use for installed dependencies, caches, generated files. | Survives plugin updates; deleted on uninstall. |

---

## 5. Component Types

### 5.1 Commands

Commands are user-initiated slash actions. They are markdown files with optional YAML frontmatter.

**Location:** `commands/command-name.md`

**Frontmatter fields:**

| Field | Type | Description |
|-------|------|-------------|
| `description` | String | Brief description shown in `/help` (under 60 chars) |
| `allowed-tools` | String or Array | Tools the command can use (e.g., `Read, Write, Bash(git:*)`) |
| `model` | String | Model override: `sonnet`, `opus`, `haiku` |
| `argument-hint` | String | Documents expected arguments for autocomplete |

**Key design rules:**
- Commands are instructions *for Claude*, not messages to the user. Written as imperative directives.
- `$ARGUMENTS` captures all arguments; `$1`, `$2`, `$3` capture positional args.
- `@path` syntax includes file contents in context.
- `` !`command` `` syntax executes bash inline for dynamic context.

**Example:**

```markdown
---
description: Review code for security issues
allowed-tools: Read, Grep, Bash(git:*)
argument-hint: [file-path]
---

Review @$1 for security vulnerabilities including:
- SQL injection
- XSS attacks
- Authentication bypass

Provide specific line numbers, severity ratings, and remediation suggestions.
```

### 5.2 Skills (Agent Skills)

Skills are model-invoked: Claude automatically consults them based on task context, without the user typing a slash command. They use a three-level progressive disclosure system.

**Location:** `skills/skill-name/SKILL.md`

**Progressive Disclosure:**

| Level | Content | Size | When Loaded |
|-------|---------|------|-------------|
| Metadata | name + description from frontmatter | ~100 words | Always in context |
| SKILL.md body | Core knowledge and instructions | <3,000 words ideal | When skill triggers |
| Bundled resources | references/, examples/, scripts/ | Unlimited | On demand |

**Frontmatter fields:**

| Field | Type | Description |
|-------|------|-------------|
| `name` | String (required) | Skill identifier |
| `description` | String (required) | Third-person trigger description with quoted phrases |
| `version` | String | Semver version |
| `disable-model-invocation` | Boolean | If true, only triggered by explicit slash command |

**Writing style rules:**
- Frontmatter description: third-person ("This skill should be used when the user asks to..."), with specific trigger phrases in quotes.
- Body: imperative form ("Parse the config file," not "You should parse the config file").
- Keep SKILL.md body under 3,000 words; move detailed content to `references/`.

**Skill directory structure:**

```
skill-name/
├── SKILL.md              # Core knowledge (required)
├── references/           # Detailed docs loaded on demand
│   ├── patterns.md
│   └── advanced.md
├── examples/             # Working code examples
│   └── sample-config.json
└── scripts/              # Utility scripts
    └── validate.sh
```

### 5.3 Agents (Subagents)

Agents are specialized sub-processes that Claude can invoke for multi-step autonomous tasks. Less commonly used in Cowork than in Claude Code.

**Location:** `agents/agent-name.md`

**Frontmatter fields:**

| Field | Type | Description |
|-------|------|-------------|
| `name` | String (required) | 3-50 chars, lowercase, hyphens |
| `description` | String (required) | Triggering conditions with `<example>` blocks |
| `model` | String (required) | `inherit`, `sonnet`, `opus`, `haiku` |
| `color` | String (required) | `blue`, `cyan`, `green`, `yellow`, `magenta`, `red` |
| `tools` | Array | Restrict to specific tools |
| `disallowedTools` | Array | Tools the agent cannot use |
| `effort` | String | Model effort level |
| `maxTurns` | Number | Maximum conversation turns |
| `isolation` | String | Only valid value: `"worktree"` |

**Security restriction:** Plugin agents cannot declare `hooks`, `mcpServers`, or `permissionMode`.

**Color conventions:**
- Blue/Cyan: analysis, review
- Green: success-oriented tasks
- Yellow: caution, validation
- Red: critical, security
- Magenta: creative, generation

### 5.4 Hooks

Hooks are event-driven handlers that fire automatically on Claude lifecycle events.

**Location:** `hooks/hooks.json`

**Available events:**

| Event | When It Fires |
|-------|---------------|
| `SessionStart` | Session begins or resumes |
| `UserPromptSubmit` | User sends a prompt, before Claude processes it |
| `PreToolUse` | Before a tool call executes (can block) |
| `PostToolUse` | After a tool call succeeds |
| `PostToolUseFailure` | After a tool call fails |
| `PermissionRequest` | When a permission dialog appears |
| `Stop` | Claude finishes responding |
| `StopFailure` | Turn ends due to API error |
| `SubagentStart` | Subagent is spawned |
| `SubagentStop` | Subagent finishes |
| `PreCompact` | Before context compaction |
| `PostCompact` | After context compaction |
| `SessionEnd` | Session terminates |
| `Notification` | Notification fires |
| `InstructionsLoaded` | CLAUDE.md or rules file loaded |
| `ConfigChange` | Config file changes during session |
| `WorktreeCreate` | Worktree is being created |
| `WorktreeRemove` | Worktree is being removed |
| `Elicitation` | MCP server requests user input |
| `ElicitationResult` | User responds to MCP elicitation |
| `TaskCompleted` | Task marked as completed |
| `TeammateIdle` | Agent team teammate going idle |

**Hook types:**

| Type | Use Case |
|------|----------|
| `command` | Execute shell commands or scripts (deterministic) |
| `prompt` | Evaluate a prompt with an LLM (complex logic) |
| `http` | POST event JSON to a URL |
| `agent` | Run an agentic verifier with tools |

**Command hook output format:**

```json
{
  "decision": "approve",   // or "block" or "ask_user"
  "reason": "Explanation"
}
```

**Example hooks.json:**

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "prompt",
            "prompt": "Check that this file write follows project coding standards.",
            "timeout": 30
          }
        ]
      }
    ],
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "cat ${CLAUDE_PLUGIN_ROOT}/context/project-context.md",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

### 5.5 MCP Servers

MCP (Model Context Protocol) servers connect Claude to external tools and services through a standardized interface.

**Location:** `.mcp.json` at plugin root

**Server transport types:**

| Type | Use Case | Example |
|------|----------|---------|
| `stdio` | Local process (default) | Node.js script, Python server |
| `sse` | Remote server (server-sent events) | `https://mcp.asana.com/sse` |
| `http` | Remote server (streamable HTTP) | `https://api.githubcopilot.com/mcp/` |

**Example configuration:**

```json
{
  "mcpServers": {
    "local-db": {
      "command": "node",
      "args": ["${CLAUDE_PLUGIN_ROOT}/servers/db-server.js"],
      "env": {
        "DB_PATH": "${CLAUDE_PLUGIN_ROOT}/data"
      }
    },
    "slack": {
      "type": "http",
      "url": "https://mcp.slack.com/mcp"
    },
    "asana": {
      "type": "http",
      "url": "https://mcp.asana.com/v2/mcp"
    }
  }
}
```

Plugin MCP servers start automatically when the plugin is enabled and appear as standard tools in Claude's toolkit.

### 5.6 LSP Servers

LSP (Language Server Protocol) servers give Claude real-time code intelligence: instant diagnostics, go-to-definition, find references, and hover information.

**Location:** `.lsp.json` at plugin root

**Required fields:** `command` (binary to execute) and `extensionToLanguage` (maps file extensions to language IDs).

```json
{
  "go": {
    "command": "gopls",
    "args": ["serve"],
    "extensionToLanguage": {
      ".go": "go"
    }
  }
}
```

**Note:** LSP plugins configure the *connection* to a language server. The server binary itself must be installed separately by the user.

### 5.7 Settings

Plugins can include a `settings.json` at the plugin root. Currently only the `agent` key is supported — it activates one of the plugin's agents as the default main-thread agent.

```json
{
  "agent": "security-reviewer"
}
```

---

## 6. Connectors and Tool-Agnostic Plugins

For plugins designed to be shared across organizations (where different companies use different tools), the system supports `~~` placeholder syntax.

**CONNECTORS.md** at the plugin root documents the tool categories:

```markdown
# Connectors

## Connectors for this plugin

| Category | Placeholder | Options |
|----------|-------------|---------|
| Chat | `~~chat` | Slack, Microsoft Teams, Discord |
| Project tracker | `~~project tracker` | Linear, Asana, Jira, Monday |
| Source control | `~~source control` | GitHub, GitLab, Bitbucket |
```

In plugin files, instructions reference tools generically:

```
Check ~~project tracker for open tickets assigned to the user.
Post a summary to ~~chat in the team channel.
```

During customization (via the `cowork-plugin-customizer` skill), these placeholders get replaced with the organization's specific tool names.

---

## 7. Plugin Lifecycle

### 7.1 Creation

Plugins can be created through several paths:

1. **Manual creation** — build the directory structure and files by hand.
2. **Guided creation in Cowork** — the `create-cowork-plugin` skill walks users through a five-phase process: Discovery, Component Planning, Design, Implementation, and Review & Packaging.
3. **Migration from standalone** — convert existing `.claude/` configurations into a plugin directory.
4. **Skill Creator** — the `skill-creator` skill provides an iterative build-test-evaluate loop for developing and benchmarking individual skills.

### 7.2 Packaging

Plugins are packaged as `.plugin` files (ZIP archives) for distribution:

```bash
cd /path/to/plugin-dir && zip -r /tmp/plugin-name.plugin . -x "*.DS_Store"
```

In Cowork, the `.plugin` file renders as a rich preview card where the user can browse files and accept the plugin.

### 7.3 Validation

```bash
claude plugin validate <path-to-plugin>
```

Validates `plugin.json`, skill/agent/command frontmatter, and `hooks/hooks.json` for syntax and schema errors.

### 7.4 Installation Scopes

| Scope | Settings File | Use Case |
|-------|--------------|----------|
| `user` | `~/.claude/settings.json` | Personal plugins, all projects (default) |
| `project` | `.claude/settings.json` | Team plugins, version-controlled |
| `local` | `.claude/settings.local.json` | Project-specific, gitignored |
| `managed` | Managed settings (read-only) | Organization-enforced plugins |

### 7.5 Caching

When installed from a marketplace, plugins are copied to `~/.claude/plugins/cache`. This provides security (plugins can't reference files outside their directory) and version integrity (plugins don't change unexpectedly). Symlinks within the plugin directory are followed during the copy process.

### 7.6 Updates

```bash
claude plugin update <plugin-name>
```

Version detection is based on the `version` field in `plugin.json`. If the version doesn't change, the update is skipped.

---

## 8. Marketplace System

### 8.1 Marketplace Architecture

A marketplace is a repository containing a `.claude-plugin/marketplace.json` catalog file that lists available plugins and where to find them.

```json
{
  "name": "company-tools",
  "owner": {
    "name": "DevTools Team",
    "email": "devtools@example.com"
  },
  "metadata": {
    "description": "Internal tools for the engineering team",
    "version": "1.0.0",
    "pluginRoot": "./plugins"
  },
  "plugins": [
    {
      "name": "code-formatter",
      "source": "./plugins/formatter",
      "description": "Automatic code formatting",
      "version": "2.1.0"
    },
    {
      "name": "deploy-tools",
      "source": {
        "source": "github",
        "repo": "company/deploy-plugin",
        "ref": "v2.0.0"
      },
      "description": "Deployment automation"
    }
  ]
}
```

### 8.2 Plugin Source Types

| Source | Format | Notes |
|--------|--------|-------|
| Relative path | `"./plugins/my-plugin"` | Local directory within marketplace repo |
| GitHub | `{"source": "github", "repo": "owner/repo"}` | Supports `ref` and `sha` pinning |
| Git URL | `{"source": "url", "url": "https://..."}` | Any git host |
| Git subdirectory | `{"source": "git-subdir", "url": "...", "path": "..."}` | Sparse clone for monorepos |
| npm | `{"source": "npm", "package": "@org/plugin"}` | Supports version ranges and custom registries |

### 8.3 Distribution Channels

- **Official Anthropic Marketplace** — submission via `claude.ai/settings/plugins/submit` or `platform.claude.com/plugins/submit`.
- **GitHub/GitLab hosting** — any git repository can serve as a marketplace.
- **Private repositories** — supported via standard git credential helpers; background auto-updates use environment tokens (`GITHUB_TOKEN`, `GITLAB_TOKEN`, `BITBUCKET_TOKEN`).
- **Container pre-population** — `CLAUDE_CODE_PLUGIN_SEED_DIR` environment variable enables baking marketplaces into container images.

### 8.4 Release Channels

Teams can maintain separate "stable" and "latest" marketplaces pointing to different `ref` values of the same plugin repos, then assign each marketplace to different user groups through managed settings.

---

## 9. Enterprise Governance

### 9.1 Organization-Managed Plugins

On Team and Enterprise plans, administrators can:

- Distribute plugins through organization marketplaces.
- Force-enable plugins that users cannot disable.
- Prevent users from editing organization-managed plugins (ensuring consistency).
- Auto-install plugins for new team members.

### 9.2 Marketplace Restrictions (`strictKnownMarketplaces`)

Admins can control which marketplaces users are allowed to add:

| Configuration | Behavior |
|--------------|----------|
| Undefined (default) | No restrictions — users can add any marketplace |
| Empty array `[]` | Complete lockdown — no new marketplaces |
| List of sources | Users can only add allowlisted marketplaces |

Supports exact matching, `hostPattern` (regex on hostname), and `pathPattern` (regex on filesystem path).

### 9.3 Known Marketplaces (`extraKnownMarketplaces`)

Admins can pre-register marketplaces so they appear automatically:

```json
{
  "extraKnownMarketplaces": {
    "company-tools": {
      "source": {
        "source": "github",
        "repo": "your-org/claude-plugins"
      }
    }
  },
  "enabledPlugins": {
    "code-formatter@company-tools": true
  }
}
```

---

## 10. Cowork-Specific Considerations

While the plugin architecture is shared with Claude Code, Cowork users interact with plugins differently:

- **Skills and commands are the primary value.** Most Cowork users are non-developers doing knowledge work. They benefit from domain-specific skills (finance, legal, marketing, HR) more than hooks or LSP servers.
- **Plugin browsing is visual.** Cowork provides a "Browse plugins" UI in the Customize sidebar; Claude Code uses the `/plugin` CLI interface.
- **`.plugin` file installation.** Cowork renders `.plugin` files as rich preview cards with an install button.
- **Customization via conversation.** The `cowork-plugin-customizer` skill lets users configure plugins by answering questions, with Claude searching knowledge MCPs (Slack, Notion, Gmail) to pre-fill answers.
- **Scheduled tasks.** Cowork supports scheduled tasks (cron or one-time) that can use plugin skills autonomously.
- **Available official plugins** span domains including enterprise search, finance/accounting, and plugin management itself (`cowork-plugin-management`).

---

## 11. Existing Plugin Examples (Observed in the Wild)

| Plugin | Version | Description | Key Components |
|--------|---------|-------------|----------------|
| `cowork-plugin-management` | 0.2.2 | Create, customize, and manage plugins | Skills: `create-cowork-plugin`, `cowork-plugin-customizer` |
| `enterprise-search` | 1.1.0 | Cross-tool search (email, chat, docs, wikis) | Commands: `search`, `digest`; Skills: `search-strategy`, `knowledge-synthesis`, `source-management`; MCP: Slack, Notion, Guru, Atlassian, Asana, MS365, Gmail, Google Calendar |
| `finance` | 1.1.0 | Finance & accounting workflows | Commands: `journal-entry`, `sox-testing`, `reconciliation`, `income-statement`, `variance-analysis`; Skills: `reconciliation`, `journal-entry-prep`, `close-management`, `financial-statements`, `audit-support`, `variance-analysis` |
| `agentic-accountant` | (user-uploaded) | Autonomous accounting with human-in-the-loop | Skills: `onboard`, `start`, `done` |

---

## 12. Summary of Component Comparison

| Component | Trigger | Format | Location | Typical Use |
|-----------|---------|--------|----------|-------------|
| Command | User types `/plugin:name` | Markdown + frontmatter | `commands/*.md` | Explicit user-initiated actions |
| Skill | Claude auto-detects from context | SKILL.md + frontmatter | `skills/*/SKILL.md` | Domain knowledge, workflow guidance |
| Agent | Claude auto-invokes or user selects | Markdown + frontmatter | `agents/*.md` | Multi-step autonomous tasks |
| Hook | Event-driven (lifecycle) | JSON config | `hooks/hooks.json` | Validation, enforcement, context injection |
| MCP Server | Always-on when plugin enabled | JSON config | `.mcp.json` | External tool/service integration |
| LSP Server | Always-on when plugin enabled | JSON config | `.lsp.json` | Real-time code intelligence |
| Settings | Applied when plugin enabled | JSON | `settings.json` | Default agent, config overrides |

---

## 13. Sources

- [Create plugins — Claude Code Docs](https://code.claude.com/docs/en/plugins)
- [Plugins reference — Claude Code Docs](https://code.claude.com/docs/en/plugins-reference)
- [Create and distribute a plugin marketplace — Claude Code Docs](https://code.claude.com/docs/en/plugin-marketplaces)
- [Use plugins in Cowork — Claude Help Center](https://support.claude.com/en/articles/13837440-use-plugins-in-cowork)
- [Get started with Cowork — Claude Help Center](https://support.claude.com/en/articles/13345190-get-started-with-cowork)
- [Cowork and plugins for teams across the enterprise — Claude Blog](https://claude.com/blog/cowork-plugins-across-enterprise)
- [Claude Code Skills vs MCP vs Plugins — MorphLLM](https://www.morphllm.com/claude-code-skills-mcp-plugins)
- [Understanding Claude Code's Full Stack — alexop.dev](https://alexop.dev/posts/understanding-claude-code-full-stack/)
