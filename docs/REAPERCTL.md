# reaperctl

`reaperctl` is the deterministic control-plane CLI for the Reaper Golden Master continuation.

The control plane validates the immutable `GM-2026-09-08` baseline before it observes or drives the live DAW. Transport and production actions are admitted only when their resulting state or output bytes can be verified.

## Commands

```bash
bin/reaperctl baseline
bin/reaperctl health --static
bin/reaperctl health --json
bin/reaperctl session --json
bin/reaperctl session --require-transport
bin/reaperctl play --json
bin/reaperctl stop --json
bin/reaperctl render --output /absolute/path/mix.wav --json
bin/reaperctl export-stems --track 'Kick Test' --track 'Snare Test' --output-dir /absolute/path/stems --json
```

## Session and transport

`session` discovers the canonical workspace, Virtual Apollo roots, REAPER process, X11 display `:88`, canonical project window, and REAPER Web Interface endpoint. `play` and `stop` use state-confirmed REAPER Web Interface actions (`1007` and `1016`) and are idempotent.

The Web endpoint is resolved from `--web-url`, `REAPERCTL_WEB_URL`, or the active `reaper.ini`. Non-loopback endpoint URLs are refused unless `--allow-remote-web` is explicit.

## Render

`render` performs a verified offline render without changing the canonical project. The admitted contract is WAV / PCM / 48,000 Hz / stereo / 24-bit / entire project.

The command hashes the canonical RPP, creates a temporary RPP in the canonical project directory, forces the render contract, invokes REAPER 7.79 with `-newinst -nosplash -renderproject`, removes the temporary RPP, verifies format/duration/non-silence/SHA-256, and hashes the canonical project again. Any canonical-project byte change is a failure.

An exploratory 44.1 kHz render was rejected; the admitted implementation explicitly forces and verifies 48 kHz.

## Export selected-track stems

`export-stems` exports REAPER's native **Selected tracks (stems)** source rather than approximating stems through solo/master routing.

```bash
bin/reaperctl export-stems \
  --track 'Kick Test' \
  --track 'Snare Test' \
  --output-dir /mnt/data/reaperctl-stems \
  --json
```

The initial admitted stem contract is deliberately strict:

```text
source: REAPER native Selected tracks (stems)
track selection: exact track-name match
naming: $track.wav
track names: filename-safe names only
container: WAV
encoding: PCM
sample rate: 48000 Hz
channels: 2
sample width: 24 bit
bounds: entire project
output directory: absent or empty
silence: rejected unless --allow-silent is explicit
```

Implementation safeguards:

- the canonical RPP is hashed before and after;
- a disposable RPP is created in the canonical project directory so relative media remains valid;
- a disposable copy of the REAPER resource/config tree is used, with Web control disabled in that copy;
- a generated ReaScript selects only the requested tracks in memory and requests `RENDER_SETTINGS=2`, 48 kHz, stereo, whole-project bounds and `$track` naming;
- the script opens action `40015` (the current Render-to-File surface);
- `reaperctl` requires the known REAPER 7.79 Render-dialog and source-menu geometry before any X11 click is allowed;
- the native `Selected tracks (stems)` source is selected and REAPER must report `RENDER_SETTINGS=2` before rendering;
- only the exact expected `$track.wav` files are admitted;
- every stem is checked for PCM format, 48 kHz, stereo, 24-bit, frames, duration, non-silence unless explicitly allowed, size and SHA-256;
- the disposable REAPER process/project/config are destroyed afterward.

Two tempting paths were rejected during development: headless `-renderproject` with persisted selection produced `Nothing to render!`, and action `42230` reset stems to master mix. Neither is used by the admitted exporter.

## Web control admission

`scripts/configure-web-control.py` safely admits the continuation Web surface. It is backup-first, idempotent, preserves non-HTTP surfaces, refuses a conflicting HTTP surface, and refuses to write while the specified REAPER binary is running.

The continuation Web surface is:

```text
csurf_0=HTTP 0 2307 '' 'index.html' 0 ''
```

REAPER 7.79 itself was observed listening on `0.0.0.0:2307`; therefore the server is **not** described as loopback-only. `reaperctl` targets `127.0.0.1` and refuses non-loopback URLs by default, but server-side binding remains a hardening item.

## Live evidence

- `evidence/LIVE-TRANSPORT-2026-09-08.md` — canonical session, play and stop state transitions.
- `evidence/LIVE-RENDER-2026-09-08.md` — verified 48 kHz master render.
- `evidence/LIVE-STEMS-2026-09-08.md` — verified native selected-track stem export.

## Environment overrides

```text
REAPER_GM_WORKSPACE_ROOT
REAPER_GM_VIRTUAL_APOLLO_ROOT
REAPER_GM_PROJECT
REAPER_GM_REAPER_BINARY
REAPER_GM_APOLLO_STATUS
REAPER_GM_REAPER_RESOURCE
REAPER_GM_DISPLAY
REAPER_GM_HOME
REAPER_GM_XDG_CONFIG_HOME
REAPERCTL_BASELINE
REAPERCTL_WEB_URL
```

Overrides change where `reaperctl` looks; they do not alter immutable baseline values.

## Development order

1. `baseline` / `health` — **implemented**.
2. `session` / `play` / `stop` — **implemented and live-verified**.
3. Web control admission — **implemented and live-verified**.
4. `render` — **implemented and live-verified at 48 kHz stereo PCM**.
5. `export-stems` — **implemented and live-verified using native selected-track stem semantics**.
6. `align-drums` — next: invoke the admitted overhead-anchored drum workflow.
7. `screenshot` / `snapshot` / `backup` — evidence and recovery operations.
