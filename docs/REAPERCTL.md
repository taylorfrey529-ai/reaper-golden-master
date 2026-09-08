# reaperctl

`reaperctl` is the deterministic control-plane CLI for the Reaper Golden Master continuation.

The control plane validates the immutable `GM-2026-09-08` baseline before it observes or drives the live DAW. Transport control is state-confirmed through REAPER's Web Interface rather than keyboard toggles.

## Commands

```bash
bin/reaperctl baseline
bin/reaperctl baseline --json
bin/reaperctl health --static
bin/reaperctl health --json
bin/reaperctl session
bin/reaperctl session --json
bin/reaperctl session --require-transport
bin/reaperctl play
bin/reaperctl play --json
bin/reaperctl stop
bin/reaperctl stop --json
```

## Session discovery

`session` resolves and reports:

- canonical workspace and Virtual Apollo roots;
- `ASIO-Routing-Project.RPP`;
- REAPER binary and process IDs;
- X11 display `:88`;
- REAPER windows discovered from X11;
- the canonical `ASIO-Routing-Project - REAPER v7.79` window;
- a REAPER Web Interface endpoint when one is explicitly supplied, set in the environment, or discoverable from `reaper.ini`;
- live `TRANSPORT` state when the endpoint responds.

`session` succeeds when the canonical live session is found even if Web transport is not configured. `session --require-transport` also requires a responding Web endpoint.

## Deterministic transport

`play` and `stop` use REAPER Web Interface commands and confirm the resulting `TRANSPORT` state.

- Play action ID: `1007`.
- Stop action ID: `1016`.
- `play` is idempotent: if REAPER already reports playing/recording, no action is sent.
- `stop` is idempotent: if REAPER already reports stopped, no action is sent.
- After an action is sent, `reaperctl` polls `TRANSPORT` until the target state is confirmed or the timeout expires.
- No success is reported from request delivery alone.

The Web endpoint is resolved in this order:

1. `--web-url`;
2. `REAPERCTL_WEB_URL`;
3. the first `csurf_N=HTTP ...` entry found in the active REAPER resource `reaper.ini`.

Non-loopback endpoint URLs are rejected unless `--allow-remote-web` is explicitly supplied.

## Web control admission

The continuation carries a reproducible configuration helper:

```bash
python3 scripts/configure-web-control.py \
  --ini /mnt/data/ubuntu-desktop-workspace/config/REAPER/reaper.ini \
  --backup-dir /mnt/data/reaperctl-live-backups \
  --reaper-binary /mnt/data/ubuntu-desktop-workspace/apps/REAPER/reaper
```

Without `--apply`, this is a check/plan operation. With `--apply`, it:

- refuses an ambiguous/different existing HTTP control surface;
- refuses to modify the INI when the specified REAPER binary is running;
- creates a pre-change backup first;
- adds the standard continuation surface `csurf_N=HTTP 0 2307 '' 'index.html' 0 ''`;
- preserves existing non-HTTP control surfaces;
- is idempotent when the exact surface already exists;
- reports before/after SHA-256 values and whether a restart is required.

REAPER must be restarted after a newly applied Web surface so it loads the control-surface configuration.

## Live verification

On 2026-09-08 the canonical live workspace was restarted with the admitted Web surface on port `2307`. `session --require-transport` passed, `play` confirmed `playstate 0 → 1`, an independent `TRANSPORT` read observed the playhead at `0.501333s`, and `stop` confirmed `playstate 1 → 0` with a final independent stopped read at `0.000000s`.

The canonical project SHA-256 was unchanged across the controlled restart. The legitimate REAPER evaluation/About dialog remained visible and was not bypassed or suppressed. Evidence is recorded in `evidence/LIVE-TRANSPORT-2026-09-08.md`.

## Network boundary

REAPER 7.79 itself was observed listening on `0.0.0.0:2307` for the Web Interface. Therefore the **server is not described as loopback-only**. `reaperctl` targets `127.0.0.1:2307` and refuses non-loopback endpoint URLs by default, but server-side interface binding remains a hardening item for any environment where the VM network is externally reachable.

## Environment overrides

```text
REAPER_GM_WORKSPACE_ROOT
REAPER_GM_VIRTUAL_APOLLO_ROOT
REAPER_GM_PROJECT
REAPER_GM_REAPER_BINARY
REAPER_GM_APOLLO_STATUS
REAPER_GM_REAPER_RESOURCE
REAPER_GM_DISPLAY
REAPERCTL_BASELINE
REAPERCTL_WEB_URL
```

Overrides change where `reaperctl` looks; they do not change the immutable continuity values admitted in `BASELINE.json`.

## Exit codes

```text
0  requested check/action completed and, for transport, target state confirmed
1  health/session requirement failed
2  invalid baseline or command configuration
3  canonical live session or transport backend unavailable
4  transport request/confirmation failed
```

## Development order

1. `baseline` / `health` — admission and observation. **Implemented.**
2. `session` / `play` / `stop` — deterministic discovery and state-confirmed transport. **Implemented and live-verified.**
3. Web control-surface admission and controlled REAPER restart. **Implemented and live-verified.**
4. `render` / `export-stems` — production actions with output verification. **Next.**
5. `align-drums` — invoke the admitted overhead-anchored drum workflow.
6. `screenshot` / `snapshot` / `backup` — evidence and recovery operations.
