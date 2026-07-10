# Ticket 02a: pi-harness foundational extension — generic mounts/env + task-scoped cwd

**Status:** TODO (NEW, added 2026-06-13 after review). **Foundational — 02/03/04/05/06 depend on it.**
**Repo:** pi-harness (branch `claude/quirky-ptolemy-htwb4n`)
**Depends on:** 00
**Source of truth:** pi-harness `harness/project-config.ts` (the closed `ProjectConfig` interface +
purity contract), `harness/cli.ts` (mount list, `envNames`, `parseArgs`, general-mode detection),
`harness/session-setup.ts` (`cwd=/work`, env consumption), `harness/run.ps1`; `00-integration-design.md`.

## Why this exists

Review found that **Cadence is the first pi-harness project that cannot be "just a config row."**
Three structural gaps must be closed *once*, generically, before any Cadence-specific work — otherwise
each of 02/04/06 grows its own Cadence branch in the core. Solve it as a small reusable extension so
pi-harness keeps its "config over fork" spirit even though the row alone is no longer sufficient.

### Gap 1 — `ProjectConfig` can't express an extra mount or extra env
`ProjectConfig` is a closed interface (`project-config.ts`) with fields only for skill/input/output/
verify/pin/task. There is no way for a row to say "also bind `<X>` → `/opt/cadence:ro`" or "also export
`CADENCE_PLUGIN_ROOT`." The module is **pure** (no `fs`, all paths repo-relative or container-absolute;
`test:project` freezes it), so a host-absolute path can't live in a row either.

### Gap 2 — the agent's cwd is always `/work`
`session-setup.ts` hardcodes `cwd=/work`. Cadence needs cwd = the **task subdir** (`/work/$CADENCE_TASK`)
so its walk-up scripts resolve and the gate (Ticket 04) can scope writes to the task subtree. Note this
is **two** distinct forwards: (a) the agent session's cwd, and (b) the value the gate's `classify()`
resolves relative paths against — both must become the task dir.

### Gap 3 — `run.ps1` never adopted `project-config.ts`
`run.ps1` hardcodes `docx`/`pptx`/`general` string branches and does **no** registry resolution — it
cannot run any preset (`summarize` included). Out of scope to fix here. **Decision: Cadence is `cli.ts`
(Linux/CI) only; `run.ps1` is explicitly unsupported for `cadence-start`.** Record it in `CLAUDE.md`.

## Design

Extend `ProjectConfig` with two **generic, optional** fields (reusable by any future project, not
Cadence-specific):

```ts
interface ProjectConfig {
  // ...existing...
  extraMounts?: { fromArg: string; to: string; readOnly: boolean }[];
  extraEnv?: string[];   // names of env vars cli.ts forwards by name (least-privilege, like creds)
  cwdSubdirEnv?: string; // name of an env var whose value (relative to /work) becomes the agent cwd
}
```

- **`extraMounts`** entries reference a **CLI-arg-supplied host path** (`fromArg: "cadence-root"` →
  the `--cadence-root` value), never a baked host path — preserving `project-config.ts` purity. `cli.ts`
  resolves the arg to an absolute path, validates `existsSync` (fail-fast, mirroring the skill-missing
  check), and adds the bind mount.
- **`extraEnv`** lists env var *names* `cli.ts` forwards by name (`.env`-first-then-host), exactly like
  the provider-credential forwarding — keeping secrets/values off the command line and out of the row.
- **`cwdSubdirEnv`** names the env var (`CADENCE_TASK`) whose value `cli.ts` forwards and
  `session-setup.ts` joins under `/work` to set the agent cwd **and** passes to the gate as the
  resolution root. Absent ⇒ cwd stays `/work` (every existing project unchanged).

`session-setup.ts` stays project-agnostic: it reads the generic `cwdSubdirEnv` value, not "Cadence."

## Work items

- [ ] Add the three optional fields to `ProjectConfig`; keep the module pure (no `fs`).
- [ ] `cli.ts`: `parseArgs`/`Args`/`HELP` gain the generic arg(s) that `extraMounts.fromArg` references
      (e.g. `--cadence-root`); build the extra bind mounts (validated) and append `extraEnv` to
      `envNames` + `childEnv`; forward `cwdSubdirEnv`'s var.
- [ ] `session-setup.ts`: if `cwdSubdirEnv`'s value is present, set the session cwd to
      `path.join("/work", value)` and forward that path to `makeGate`/`classify` (the Ticket-04 hook).
      Default unchanged when absent.
- [ ] `CLAUDE.md`: document the new fields and the **`cli.ts`-only, `run.ps1`-unsupported** decision.
- [ ] Tests: `project-config.test.ts` + a `docker`-argv stub test proving a row with `extraMounts`/
      `extraEnv`/`cwdSubdirEnv` produces the right mounts/env/cwd, and that a row *without* them is
      byte-identical to today (no regression for docx/pptx/general/summarize).

## Acceptance

- A synthetic test row with all three fields yields the expected `docker` argv (extra ro mount, extra
  env forwarded by name, cwd = `/work/<subdir>`); existing rows unchanged; typecheck + `npm test` green.
- `cli.ts` fails fast with a clear message if an `extraMounts.fromArg` path is missing.

## Notes

- This is the *generic seam*; Ticket 02 consumes it to define the `cadence-start` row. Resist baking
  anything Cadence-named into `project-config.ts`/`session-setup.ts` — the whole point is that the next
  project (and Cadence) is data over this seam.
