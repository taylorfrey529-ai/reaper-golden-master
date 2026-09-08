# reaperctl

`reaperctl` is the deterministic control-plane CLI for the Reaper Golden Master continuation.

This first development increment intentionally controls **admission and observation**, not transport or rendering. It must be able to prove what baseline it is operating against before later commands are allowed to mutate or drive the live DAW.

## Commands

```bash
bin/reaperctl baseline
bin/reaperctl baseline --json
bin/reaperctl health --static
bin/reaperctl health --static --json
bin/reaperctl health
bin/reaperctl health --json
```

### `baseline`

Validates and reports the immutable `GM-2026-09-08` ancestry defined in `BASELINE.json`, including the Golden Master ID, proof head, and canonical audio locks.

### `health --static`

Runs repository-safe continuity checks without requiring the VM/DAW to exist. This is the CI gate for the CLI itself.

### `health`

Adds live-environment probes for:

- `/mnt/data/ubuntu-desktop-workspace`
- `/mnt/data/virtual-apollo`
- canonical `ASIO-Routing-Project.RPP`
- REAPER binary
- Virtual Apollo status script
- X11 display `:88` via `xdpyinfo`
- running REAPER process

A failed required probe returns exit code `1`. Invalid or unreadable baseline input returns exit code `2`.

## Environment overrides

The live probe paths are overrideable without changing the immutable baseline:

```text
REAPER_GM_WORKSPACE_ROOT
REAPER_GM_VIRTUAL_APOLLO_ROOT
REAPER_GM_PROJECT
REAPER_GM_REAPER_BINARY
REAPER_GM_APOLLO_STATUS
REAPER_GM_DISPLAY
REAPERCTL_BASELINE
```

Overrides change **where reaperctl looks**, not what continuity values are admitted.

## Development order

The intended command progression is:

1. `baseline` / `health` — admission and observation.
2. `play` / `stop` — deterministic transport.
3. `render` / `export-stems` — production actions with explicit output verification.
4. `align-drums` — invoke the admitted overhead-anchored drum workflow.
5. `screenshot` / `snapshot` / `backup` — evidence and recovery operations.

Each action becomes part of the continuation only after its tests and live verification pass.
