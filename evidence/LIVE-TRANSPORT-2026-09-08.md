# Live REAPER transport verification — 2026-09-08

Branch: `development/reaperctl`
Baseline: `GM-2026-09-08`

## Live session before transport

```text
REAPER PID: 3711
Display: :88
Project: ASIO-Routing-Project
Window: ASIO-Routing-Project - REAPER v7.79 - EVALUATION LICENSE
Web endpoint used by reaperctl: http://127.0.0.1:2307
Endpoint source: active reaper.ini
Initial TRANSPORT: stopped / playstate=0 / position=0.000000
```

The legitimate REAPER evaluation/About dialog remained present after the controlled restart; no license or evaluation UI was bypassed or suppressed.

## Configuration admission

The active REAPER resource file was backed up before modification:

```text
/mnt/data/reaperctl-live-backups/reaper.ini.before-web-20260908T193640Z
```

Pre-change `reaper.ini` SHA-256:

```text
827be405ca781670546d7e3b6e54b575cb671002986c755d135a3343515310c2
```

The continuation added:

```text
csurf_cnt=1
csurf_0=HTTP 0 2307 '' 'index.html' 0 ''
```

Post-edit `reaper.ini` SHA-256 before restart:

```text
588d3381d12e41f679bbc1eb270650181a7676d0aa3152082fd48e6eb178bb94
```

Canonical project SHA-256 before and after the controlled REAPER restart remained identical:

```text
2ea85263d6dc125bf7739264956a1ee1a8074c2b42f69b606b5e9d8b7e9771f1
```

## Play verification

`reaperctl play --json`:

```text
target=play
changed=true
confirmed=true
action_id=1007
before=stopped, playstate=0, position=0.000000
after=playing, playstate=1
```

Independent `TRANSPORT` read while playing:

```text
TRANSPORT  1  0.501333  0  1.2.00  1.2.00
```

This proves the playhead actually advanced after the state-confirmed play action.

## Stop verification

`reaperctl stop --json`:

```text
target=stop
changed=true
confirmed=true
action_id=1016
before=playing, playstate=1, position=1.013333
after=stopped, playstate=0, position=0.000000
```

Final independent `TRANSPORT` read:

```text
TRANSPORT  0  0.000000  0  1.1.00  1.1.00
```

Result: **LIVE PASS** — deterministic session discovery, play, and stop were actually exercised against the canonical REAPER 7.79 workspace.

## Network-boundary observation

REAPER 7.79 was observed listening on `0.0.0.0:2307` for its Web Interface. `reaperctl` itself resolves the admitted local endpoint as `127.0.0.1:2307` and refuses non-loopback Web URLs unless `--allow-remote-web` is explicitly supplied. The server-side all-interface bind is therefore recorded as a hardening item and must not be described as loopback-only.
