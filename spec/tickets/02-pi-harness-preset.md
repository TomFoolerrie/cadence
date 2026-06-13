# Ticket 02: pi-harness `cadence-start` preset (row + plugin mount + git)

**Status:** TODO (revised 2026-06-13 after review)
**Repo:** pi-harness (branch `claude/quirky-ptolemy-htwb4n`)
**Depends on:** 00, 01, **02a** (the generic `extraMounts`/`extraEnv`/`cwdSubdirEnv` seam)
**Source of truth:** pi-harness `harness/project-config.ts`, repo-root `projects/README.md`,
`harness/cli.ts`, `harness/session-setup.ts`, `harness/Dockerfile.base`; `00`, `02a`.

## Goal

Define the `cadence-start` project **on top of Ticket 02a's generic seam**: a config row that mounts
Cadence's `plugin/` read-only, forwards `CADENCE_PLUGIN_ROOT` + `CADENCE_TASK`, runs the agent with
cwd = the task subdir, and guarantees the container can commit to `/work`. After this,
`./run --project cadence-start --cadence-root <cadence> --cadence-task <class>/<task> --work <eng>`
builds the right container — even before the pin (03) and gate policy (04) land.

## What review changed

- The mount + env + cwd are **not** expressible in a bare row → they ride Ticket 02a's generic fields
  (don't re-invent Cadence-specific `cli.ts` branches here).
- **`base` ships neither `git` nor `pyyaml`** — both must be added to `Dockerfile.base` (a one-time
  `--rebuild`; busts the office overlay's apt layer, acceptable). Treat git as a hard dep, not "verify."
- **Git identity** must be both pin-supplied *and* baked-fallback (model may forget the `-c` flags).
- **`run.ps1` is unsupported** for this project (decided in 02a).

## The `ProjectConfig` row

```ts
"cadence-start": {
  name: "cadence-start",
  image: "base",                 // lean + git + pyyaml (added in this ticket)
  general: true,                 // skill-free; --work = engagement root, mounted rw
  // no skillRelPath / skillDir / inputDoc / outputDoc
  extraMounts: [{ fromArg: "cadence-root", to: "/opt/cadence", readOnly: true }],  // 02a
  extraEnv: ["CADENCE_PLUGIN_ROOT", "CADENCE_TASK"],                                // 02a
  cwdSubdirEnv: "CADENCE_TASK",                                                     // 02a → cwd=/work/<task>
  methodPin: CADENCE_START_METHOD_PIN,   // Ticket 03 (lives in pi-harness; see 03 for the why)
  defaultTask: CADENCE_START_TASK,       // Ticket 03
  // verifyCmd: "verify:cadence",        // Ticket 05
}
```

`CADENCE_PLUGIN_ROOT` is set to `/opt/cadence` (the mount target). `CADENCE_TASK` comes from
`--cadence-task`. The pin (03) instructs the agent to invoke `$CADENCE_PLUGIN_ROOT/scripts/*.py` and
read `$CADENCE_TASK` itself (the pin is a static string; it can't interpolate runtime env).

## Work items

- [ ] Land the `cadence-start` row consuming 02a's fields (+ `projects/cadence-start/README.md`).
- [ ] `cli.ts`: ensure `--cadence-root` (referenced by `extraMounts.fromArg`) and `--cadence-task`
      (`cwdSubdirEnv`) are wired through 02a's generic path; set `CADENCE_PLUGIN_ROOT=/opt/cadence`.
- [ ] **`Dockerfile.base`: add `git` and `pyyaml`** (and confirm `python3` — present). One-time rebuild.
- [ ] **Git identity:** (a) bake a fallback `[user]` in the base image's `~/.gitconfig`
      (`user.name="cadence-agent"`, a noreply email) so a commit never aborts; (b) the pin (03) may also
      pass `-c user.…` per commit. Belt-and-suspenders because pin compliance isn't guaranteed.
- [ ] `GATE_MODE=enforce` for this row (the actual policy is Ticket 04; this just sets the mode).
- [ ] `project-config.test.ts` + docker-argv stub: confirm `/work` rw, `/opt/cadence` ro,
      `CADENCE_PLUGIN_ROOT`/`CADENCE_TASK` forwarded, cwd=`/work/<task>`, `base` image, `/runs` redirect.
- [ ] Typecheck clean against the CI list.

## Acceptance

- `./run --project cadence-start --cadence-root <c> --cadence-task t/x --work <e> --task shell` (or the
  docker-argv stub) shows all of the above; missing `--cadence-root` fails fast.
- `npm test` (pi-harness) green incl. updated `project-config.test.ts`; typecheck clean.
- `git commit` succeeds inside the container with **no** `-c` flags (baked-fallback proof).
- Live run is **not** required here (plumbing) — Ticket 06 owns it.

## Notes

- Keep `session-setup.ts` project-agnostic (it consumes 02a's generic `cwdSubdirEnv`, never "Cadence").
- Never `2>&1` a live run; `run.ps1` stays ASCII (moot — unsupported here).
