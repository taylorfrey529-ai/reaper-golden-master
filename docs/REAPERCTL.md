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

Non-loopback endpoints are rejected unless `--allow-remote-web` is explicitly supplied.

The Golden Master live workspace initially had no Web control surface configured. Until a control surface is admitted as continuation state, `play` and `stop` correctly refuse with an operational-unavailable result instead of falling back to synthetic keyboard input.

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
2. `session` / `play` / `stop` — deterministic discovery and state-confirmed transport. **Implemented.**
3. Web control-surface admission and controlled REAPER restart. **Next live gate.**
4. `render` / `export-stems` — production actions with output verification.
5. `align-drums` — invoke the admitted overhead-anchored drum workflow.
6. `screenshot` / `snapshot` / `backup` — evidence and recovery operations.
