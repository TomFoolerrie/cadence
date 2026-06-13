# Ticket 02: pi-harness `cadence-start` preset + plugin mount

**Status:** TODO
**Repo:** pi-harness (branch `claude/quirky-ptolemy-htwb4n`)
**Depends on:** 00, 01
**Source of truth:** pi-harness `harness/project-config.ts`, `projects/README.md`, `harness/cli.ts`,
`harness/session-setup.ts`; `00-integration-design.md`.

## Goal

Add Cadence to pi-harness as a **config row + a mount**, per pi-harness's "a new project is a row, not
a fork" recipe. After this ticket, `./run --project cadence-start --work <engagement-root>` builds the
right container with Cadence's scripts available and the engagement folder mounted — even before the
method-pin (Ticket 03) and gate policy (Ticket 04) are authored.

## Design

A general-mode project (`image: "base"`, `general: true`) — no skill mount, no fixed input/output doc.
What it adds over the bare `general` kind:

- **A plugin mount.** Cadence's `plugin/` (scripts + skills) must be readable inside the container at a
  fixed path. Bind-mount it **read-only** (e.g. host `<cadence>/plugin` → `/opt/cadence` ro), mirroring
  how pi-harness mounts a skill read-only. Export `CADENCE_PLUGIN_ROOT=/opt/cadence` (consumed by
  Ticket 01's resolution order). Read-only is correct: the plugin is infrastructure, not the work
  product — only `/work` (the engagement) is writable.
- **Task selection.** Forward `CADENCE_TASK=<class>/<task>` (relative to `/work`) into the container so
  the method-pin (Ticket 03) knows which task to execute. Decide the surface: a new `--cadence-task`
  CLI flag, or reuse an existing env passthrough. Prefer a flag for discoverability; keep it
  general-mode-only.
- **`methodPin` / `defaultTask`** come from Ticket 03 (this ticket lands the row with placeholders or
  co-lands with 03).
- **`verifyCmd`** is wired in Ticket 05 (`verify:cadence`). Leave unset here ⇒ `--task verify` correctly
  reports "no verifier" until 05.
- **Git identity.** The container must commit to `/work`. Set a deterministic identity for the run
  (e.g. `git -c user.name=... -c user.email=...` in the method-pin, or a baked default in the image).
  Decide here; Ticket 06 verifies commits land on the host.

### The `ProjectConfig` row (shape — fill `methodPin`/`defaultTask` from Ticket 03)

```ts
"cadence-start": {
  name: "cadence-start",
  image: "base",          // lean: Node + Pi + python3 + git; NO Office toolchain
  general: true,          // skill-free; --work is the engagement root, mounted rw
  // no skillRelPath / skillDir / inputDoc / outputDoc
  methodPin: CADENCE_START_METHOD_PIN,   // Ticket 03
  defaultTask: CADENCE_START_TASK,       // Ticket 03
  // verifyCmd: "verify:cadence",        // Ticket 05
},
```

## Work items

- [ ] Add the `cadence-start` row to `PROJECTS` in `harness/project-config.ts` (+ a
      `projects/cadence-start/README.md` per the recipe).
- [ ] Implement the **plugin mount** in both host entrypoints (`cli.ts` and `run.ps1`, kept in sync):
      bind `<cadence>/plugin` → `/opt/cadence:ro`, forward `CADENCE_PLUGIN_ROOT`. Decide how the host
      locates the Cadence repo (a `--cadence-root` flag or an env var; document it).
- [ ] Implement **`CADENCE_TASK`** forwarding (the `--cadence-task` flag).
- [ ] Decide + implement the **container git identity**.
- [ ] Confirm the `base` image has `git` and `python3` (it has python3 per pi-harness CLAUDE.md; verify
      `git` — add to `Dockerfile.base` if missing, which is a one-time `--rebuild`).
- [ ] Update `project-config.test.ts` to include the new row; freeze any contract-critical strings.
- [ ] Typecheck clean against pi-harness's CI list (which already includes `project-config.ts`,
      `cli.ts`, `session-setup.ts`).

## Acceptance

- `./run --project cadence-start --work <dir> --task shell` (or a `docker`-argv stub like pi-harness
  uses) shows: `/work` mounted rw = the engagement, `/opt/cadence` mounted ro, `CADENCE_PLUGIN_ROOT`
  and `CADENCE_TASK` exported, `base` image selected, audit redirected to `/runs`.
- `npm test` (pi-harness) stays green including the updated `project-config.test.ts`; typecheck clean.
- A live container run is **not** required to close this ticket (it's plumbing) — Ticket 06 owns the
  live run.

## Notes / risks

- Keep `run.ps1` ASCII-only (pi-harness gotcha) and never `2>&1` a live run.
- This ticket forwards config **by name** through the process env, exactly like every other
  pi-harness project — `session-setup.ts` stays project-agnostic; do not hardcode Cadence in it.
