# Live REAPER render verification — 2026-09-08

Branch: `development/reaperctl`
Baseline: `GM-2026-09-08`
Canonical project: `ASIO-Routing-Project`

## Rejected exploratory result

The first command-line render inherited an unsafe render default and produced:

```text
WAV PCM 24-bit stereo
sample rate: 44100 Hz
size: 4234290 bytes
duration: 16.0 s
SHA-256: da4ae27162d095f9af0083fbd59c63291cba7e705e06679d0ccbe6e57aba4f85
```

Because the Golden Master audio continuity lock is 48,000 Hz, this result was **rejected** and never admitted as the render implementation.

## Direct temporary-RPP proof

A copy of the canonical RPP was placed temporarily in the same project directory and only its render fields were changed to an absolute WAV target, stereo, 48 kHz, and entire-project bounds. REAPER 7.79 rendered it with exit code 0. The canonical project SHA-256 remained unchanged:

```text
2ea85263d6dc125bf7739264956a1ee1a8074c2b42f69b606b5e9d8b7e9771f1
```

## Actual reaperctl render live gate

The implemented CLI was run against the canonical project:

```bash
reaperctl render \
  --output /mnt/data/reaperctl-renders/ASIO-Routing-Project-reaperctl-live-48k.wav \
  --json
```

The command returned `ok=true` and independently verified:

```text
Output: /mnt/data/reaperctl-renders/ASIO-Routing-Project-reaperctl-live-48k.wav
REAPER exit code: 0
Container: RIFF/WAVE
Encoding: Microsoft PCM
Sample width: 24 bit
Channels: 2
Sample rate: 48000 Hz
Frames: 768000
Duration: 16.000000 s
Size: 4608690 bytes
Non-silent: true
SHA-256: 44ef543f74070a04b65690487ba0bb65638be0926c43935a8a4f3548f09041cd
```

Independent file inspection confirmed the same format and SHA-256.

Canonical project hash before and after the CLI render:

```text
2ea85263d6dc125bf7739264956a1ee1a8074c2b42f69b606b5e9d8b7e9771f1
```

No `.reaperctl-render-*.RPP` temporary file remained afterward.

Result: **LIVE PASS** — `reaperctl render` preserves the canonical project and produces a byte-verified, non-silent, 48 kHz stereo 24-bit PCM master.
