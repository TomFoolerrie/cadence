/**
 * scope-gate.ts — the Pi `ExtensionFactory` wiring for Cadence's write-scope +
 * bash gate. All classification lives in the pure `policy.ts`; this file only
 * binds it to Pi's `tool_call` hook (the event/return shape is the one the
 * sibling pi-harness gate uses in production, so it is known-good).
 *
 * Fail-open: a `tool_call` handler that THROWS causes Pi to block the tool, so
 * the body is wrapped in try/catch and, on any internal error, ALLOWS. Cadence's
 * gate is a hard boundary layered on top of process trust — NOT the containment
 * boundary — so failing closed on a gate bug would brick legitimate work. This
 * intentionally diverges from pi-harness's enforce-mode fail-CLOSED: pi-harness
 * has a container boundary to fall back on; Cadence does not. (Revisit only if
 * Cadence ever runs untrusted models unsandboxed.)
 */

import type { ExtensionAPI, ExtensionFactory } from "@earendil-works/pi-coding-agent";

import { classifyBash, classifyWrite } from "./policy.ts";

export function makeScopeGate(): ExtensionFactory {
  return (pi: ExtensionAPI) => {
    // Declare the track to every child process the bash tool spawns, so the
    // shared init scripts skip `.claude/` generation (Phase 3 / CADENCE_TRACK).
    process.env.CADENCE_TRACK = "pi";

    pi.on("tool_call", (event) => {
      try {
        const cwd = process.cwd();

        if (event.toolName === "edit" || event.toolName === "write") {
          const path = (event.input as { path?: unknown }).path;
          const d = classifyWrite(cwd, typeof path === "string" ? path : "");
          return d ? { block: true, reason: d.reason } : undefined;
        }

        if (event.toolName === "bash") {
          const command = (event.input as { command?: unknown }).command;
          const d = classifyBash(typeof command === "string" ? command : "");
          return d ? { block: true, reason: d.reason } : undefined;
        }

        return undefined;
      } catch {
        // Total fail-safe: never let a gate bug block a legitimate tool.
        return undefined;
      }
    });
  };
}
