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
```

## Session and transport

`session` discovers the canonical workspace, Virtual Apollo roots, REAPER process, X11 display `:88`, canonical project window, and REAPER Web Interface endpoint. `play` and `stop` use state-confirmed REAPER Web Interface actions (`1007` and `1016`) and are idempotent.

The Web endpoint is resolved from `--web-url`, `REAPERCTL_WEB_URL`, or the active `reaper.ini`. Non-loopback endpoint URLs are refused unless `--allow-remote-web` is explicit.

## Render

`render` performs a verified offline render without changing the canonical project.

```bash
bin/reaperctl render \
  --output /mnt/data/reaperctl-renders/ASIO-Routing-Project.wav \
  --json
```

The initial admitted render contract is deliberately narrow:

```text
container: WAV
encoding: PCM
sample rate: 48000 Hz
channels: 2
sample width: 24 bit
bounds: entire project
```

The command validates the baseline, hashes the canonical RPP, refuses an existing target unless `--overwrite` is explicit, creates a temporary RPP in the canonical project directory, forces an absolute `RENDER_FILE`, empty `RENDER_PATTERN`, `RENDER_FMT 0 2 48000`, and entire-project bounds, invokes the actual REAPER 7.79 binary with `-newinst -nosplash -renderproject`, removes the temporary RPP, verifies the output format/duration/non-silence/SHA-256, and hashes the canonical project again. Any canonical-project byte change is a failure.

A first exploratory render that inherited the prior render settings produced 44.1 kHz and was **rejected**. The admitted implementation explicitly forces 48 kHz and has a unit test that rejects 44.1 kHz output.

`render` currently accepts `.wav` only. Other formats should be added as separate verified continuation increments rather than inferred from filenames or REAPER defaults.

## Web control admission

`scripts/configure-web-control.py` safely admits the continuation Web surface. It is backup-first, idempotent, preserves non-HTTP surfaces, refuses a conflicting HTTP surface, and refuses to write while the specified REAPER binary is running.

The continuation Web surface is:

```text
csurf_0=HTTP 0 2307 '' 'index.html' 0 ''
```

REAPER 7.79 itself was observed listening on `0.0.0.0:2307`; therefore the server is **not** described as loopback-only. `reaperctl` targets `127.0.0.1` and refuses non-loopback URLs by default, but server-side binding remains a hardening item.

## Live evidence

- `evidence/LIVE-TRANSPORT-2026-09-08.md` — canonical session, play and stop state transitions.
- `evidence/LIVE-RENDER-2026-09-08.md` — actual `reaperctl render` output and byte-level verification.

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

Overrides change where `reaperctl` looks; they do not alter the immutable baseline values.

## Exit codes

```text
0  check/action completed and resulting state/output was verified
1  health/session requirement failed
2  invalid baseline, argument, output contract, or overwrite condition
3  canonical live session or transport backend unavailable
4  REAPER action/render execution or post-action verification failed
```

## Development order

1. `baseline` / `health` — **implemented**.
2. `session` / `play` / `stop` — **implemented and live-verified**.
3. Web control admission — **implemented and live-verified**.
4. `render` — **implemented and live-verified at 48 kHz stereo PCM**.
5. `export-stems` — next production action.
6. `align-drums` — admitted overhead-anchored drum workflow.
7. `screenshot` / `snapshot` / `backup` — evidence and recovery operations.
