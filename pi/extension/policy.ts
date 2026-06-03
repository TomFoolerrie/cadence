/**
 * policy.ts — the pure, SDK-free classification core of Cadence's Pi gate.
 *
 * This is the security-critical piece; its tests (policy.test.ts) are its
 * contract. It has NO `@earendil-works/pi-coding-agent` import, so it runs under
 * `node --test` with no SDK, container, or model — exactly like the sibling
 * pi-harness's `gate/policy.ts`.
 *
 * It reproduces, on the Pi track, the two `.claude/settings.json` deny rules the
 * Claude track relies on (§3a), and adds a bash gate the Claude track cannot
 * express (§3b):
 *
 *   §3a  Edit/Write — block writes that escape the agent's own directory
 *        (the `Write(../**)` rule) and direct writes to the script-gated file
 *        for the level (`.class.yaml` at a class dir, `status.yaml` at a task
 *        dir — the per-level `Write(./<gated>)` rule).
 *
 *   §3b  Bash — allow only a whitelist of command heads, then reject any command
 *        whose full text matches a banned destructive pattern.
 *
 * A blocked decision carries a corrective `reason` pointing at the right
 * script/tool. The whitelist + banned list were derived by sweeping every bash
 * invocation in `skills/*​/SKILL.md` and the `reference.md` template (the sweep
 * is the source of truth): the skills emit `python`/`pip`, `git add|commit|
 * checkout`, `cd <dir> && …`, and `source <root>/venv/bin/activate && …` — hence
 * `cd` and `source` are whitelisted heads (compound commands are still scanned
 * whole for banned patterns), and the gate keys on the `git` HEAD, never a
 * git-subcommand allowlist (so `git checkout` is not accidentally blocked).
 */

import { existsSync } from "node:fs";
import { join, resolve, sep } from "node:path";

export interface BlockDecision {
  /** Always true — a decision object means "block"; `null` means "allow". */
  block: true;
  /** Corrective message handed back to the agent. */
  reason: string;
  /** Stable rule id (for audit/debugging). */
  rule: string;
}

/** Whitelisted bash command heads (first token). Derived from the skill sweep. */
export const BASH_WHITELIST: readonly string[] = [
  "python", "python3", "pip", // script + venv/deps (Q4)
  "git",                       // add / commit / checkout (head only — not a subcommand allowlist)
  "cd", "source",              // compound: `cd <dir> && …`, `source <root>/venv/bin/activate && …`
  "ls", "cat", "head", "tail", // read-only inspection
];

/** Destructive patterns rejected anywhere in a command (covers compound `&&`/`;`/`|`). */
export const BASH_BANNED: readonly { re: RegExp; rule: string }[] = [
  // recursive-force rm in any flag spelling: -rf, -fr, -rfv, or split -r … -f.
  { re: /\brm\s+-\S*r\S*f|\brm\s+-\S*f\S*r|\brm\b[^|;&]*\s-r\b[^|;&]*\s-f\b|\brm\b[^|;&]*\s-f\b[^|;&]*\s-r\b/, rule: "bash.rm-rf" },
  // in-place sed would mutate a gated/owned file outside the edit/write gate.
  { re: /\bsed\s+-i\b/, rule: "bash.sed-i" },
  // redirect to an absolute system path (escapes the agent dir); /dev/null is fine.
  { re: />\s*\/(?!dev\/null\b)/, rule: "bash.redirect-root" },
  // piping a download straight into a shell.
  { re: /\b(?:curl|wget)\b[^|]*\|\s*(?:sh|bash)\b/, rule: "bash.curl-pipe-sh" },
];

/**
 * Which file at `cwd` is script-gated, inferred from the directory's own
 * markers (self-configuring — no scope file). A class dir (`​.class.yaml`
 * present) gates `.class.yaml`; a task dir (`status.yaml` present) gates
 * `status.yaml`; the root (neither) gates nothing.
 */
export function detectGate(cwd: string): string | null {
  if (existsSync(join(cwd, ".class.yaml"))) return ".class.yaml";
  if (existsSync(join(cwd, "status.yaml"))) return "status.yaml";
  return null;
}

/** True iff `target` is `root` itself or strictly within it (no `../` escape). */
export function isUnder(target: string, root: string): boolean {
  const t = resolve(target);
  const r = resolve(root);
  return t === r || t.startsWith(r + sep);
}

/**
 * Classify an edit/write to `rawPath` (resolved against the agent `cwd`).
 * Returns a BlockDecision to reject, or `null` to allow.
 */
export function classifyWrite(cwd: string, rawPath: string): BlockDecision | null {
  const target = resolve(cwd, rawPath || "");

  if (!isUnder(target, cwd)) {
    return {
      block: true,
      rule: "write.outside-root",
      reason:
        "Write blocked: target is outside this agent's directory. Cadence agents " +
        "may only write within their own folder; work in the current task/class dir.",
    };
  }

  const gated = detectGate(cwd);
  if (gated && target === join(resolve(cwd), gated)) {
    const hint =
      gated === "status.yaml"
        ? "use ${CLAUDE_PLUGIN_ROOT}/scripts/set-status.py to change status"
        : "use ${CLAUDE_PLUGIN_ROOT}/scripts/edit-class-yaml.py to change the manifest";
    return {
      block: true,
      rule: "write.gated-file",
      reason: `Write blocked: ${gated} is script-gated — ${hint}.`,
    };
  }

  return null;
}

/**
 * Classify a bash `command`. Returns a BlockDecision to reject, or `null` to
 * allow. Head must be whitelisted; the whole command is then scanned for banned
 * destructive patterns (so compound commands cannot smuggle one in).
 */
export function classifyBash(command: string): BlockDecision | null {
  const cmd = (command || "").trim();
  const head = cmd.split(/\s+/)[0] ?? "";

  if (!BASH_WHITELIST.includes(head)) {
    return {
      block: true,
      rule: "bash.head-not-whitelisted",
      reason:
        `Bash blocked: '${head || "(empty)"}' is not an allowed command. Cadence ` +
        `runs its scripts via python (e.g. python \${CLAUDE_PLUGIN_ROOT}/scripts/...), ` +
        `git, and the venv; never create dirs or edit YAML by hand.`,
    };
  }

  for (const { re, rule } of BASH_BANNED) {
    if (re.test(cmd)) {
      return {
        block: true,
        rule,
        reason: `Bash blocked: command matches a banned destructive pattern (${rule}).`,
      };
    }
  }

  return null;
}
