# Live native selected-track stem export verification — 2026-09-08

Branch: `development/reaperctl`
Baseline: `GM-2026-09-08`
Canonical project: `ASIO-Routing-Project`

## Rejected paths

Two approaches were explicitly rejected before admission:

1. `-renderproject` with persisted `SEL 1` track state produced **Render Error: Nothing to render!**.
2. Native action `42230` (`File: Render project, using the most recent render settings, auto-close render dialog`) changed `RENDER_SETTINGS` from `2` (stems only) back to `0` (master mix) and produced `Master.wav`.

Neither behavior is used by the admitted exporter.

## Admitted path

The verified exporter creates a disposable copy of the canonical project and a disposable REAPER resource/config tree. A generated ReaScript:

- selects exact requested tracks in memory;
- sets `RENDER_SETTINGS=2` (native selected-track stems only);
- sets 48,000 Hz, stereo, whole-project bounds;
- sets output directory and `$track` naming;
- opens REAPER's current Render-to-File surface with action `40015`.

`reaperctl` then interacts only with that disposable REAPER 7.79 Render dialog. It requires the known 714×752 dialog geometry, selects the native **Selected tracks (stems)** source, confirms the project reports `RENDER_SETTINGS=2`, and activates the specific Render button. The disposable REAPER process/config/project are then destroyed after byte verification.

The canonical REAPER session and canonical RPP are not used as the render instance.

## Live CLI gate

The compact final implementation was executed for:

```text
Kick Test
Snare Test
```

Output directory:

```text
/mnt/data/reaperctl-stems-cli-live-final
```

Verified files:

```text
Kick Test.wav
  bytes: 4608690
  SHA-256: ed938c8d8eb345e9ef595980108f3365c7375b969f88b1dfbc927f6ace1bce20
  PCM WAV: 24-bit / stereo / 48000 Hz
  frames: 768000
  duration: 16.000000 s
  non-silent: true

Snare Test.wav
  bytes: 4608690
  SHA-256: 55c1174f90f45553ab61ca22642bb7adf4c598d648beaeb42c4598aac8fe1ade
  PCM WAV: 24-bit / stereo / 48000 Hz
  frames: 768000
  duration: 16.000000 s
  non-silent: true
```

Canonical project SHA-256 before and after:

```text
2ea85263d6dc125bf7739264956a1ee1a8074c2b42f69b606b5e9d8b7e9771f1
```

No `.reaperctl-stems-*.RPP` disposable project remained afterward.

Result: **LIVE PASS** — native selected-track stems were exported as exactly the requested two files, with strict 48 kHz/stereo/24-bit and byte-level verification, while the canonical project remained unchanged.
