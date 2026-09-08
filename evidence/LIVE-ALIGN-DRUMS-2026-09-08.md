# Live overhead-anchored drum alignment verification — 2026-09-08

Branch: `development/reaperctl`
Baseline: `GM-2026-09-08`
Canonical project: `ASIO-Routing-Project`
Canonical project SHA-256: `2ea85263d6dc125bf7739264956a1ee1a8074c2b42f69b606b5e9d8b7e9771f1`

## Authority recovered

The continuation was derived from the admitted `reaper-is-free` workflow:

- `AI_Phase_align_drum_shells_to_overheads.lua`
- `AI_Drum_Shell_Phase_Align`

The admitted workflow keeps the OH reference fixed, performs a local shell-to-OH correlation, robustly combines accepted hit lags, and applies the result only through the dedicated non-destructive shell JSFX. Tom 1 remains explicitly tagged as a self-anchor.

A continuation bug fix was required: the historical name matcher searched for the substring `rack`, which also occurs inside the word `track`. The continuation now uses token-aware `rack` matching, so `8-Bar Drum Track - 120 BPM` is not falsely treated as a rack tom.

## Measurement contract

The continuation analyzer preserves the admitted measurement stages:

```text
transient scan: 2000 Hz / 5 ms bins
maximum events: 8
minimum event gap: 120 ms
coarse correlation: 8000 Hz
coarse shell window: 6 ms pre / 24 ms post
OH search radius: +/-25 ms
fine correlation: 96000 Hz
fine shell window: 4 ms pre / 10 ms post
fine search radius: 0.8 ms
maximum admitted offset: 50 ms
minimum accepted correlation score: 0.035
robust combination: median + MAD rejection
```

Initial continuation scope is intentionally strict: one stereo OH WAVE track plus simple single-WAVE-item shell tracks at 48 kHz / 24-bit with item `POSITION=0`, `SOFFS=0`, and `PLAYRATE=1`.

## Live measurements

OH reference:

```text
OH Stereo Test
```

Measured shell results:

```text
Kick Test
  offset: +0.000000 ms
  accepted hits: 4 / 4
  dominant OH channel: L/1
  average fine-correlation score: 0.999262

Snare Test
  offset: +0.302083 ms
  accepted hits: 2 / 2
  hit 1: +0.000000 ms, OH L/1, score 0.974624
  hit 2: +0.604167 ms, OH R/2, score 0.975020
  robust median: +0.302083 ms

Tom 1 Test
  offset: +0.000000 ms
  accepted hits: 5 / 5
  dominant OH channel: L/1
  average fine-correlation score: 0.999800
  Tom 1 self-anchor: true
```

Independent direct waveform correlation also confirmed that the close shells match OH L at zero samples while OH R contains later arrivals of approximately 1.000 ms for kick, 0.604 ms for snare, and 1.396 ms for Tom 1.

## Disposable apply gate

The implementation created a new aligned RPP rather than modifying the canonical project:

```text
/mnt/data/reaperctl-align-live/ASIO-Routing-Project-aligned.RPP
```

Output project SHA-256:

```text
57746c7b5a716304bd0e70d5afcf53f8441999c0065418cd9ff308fb881b25a1
```

Applied shell markers:

```text
Kick Test    AI_DRUM_ALIGN_DELAY_MS 0.000000
Snare Test   AI_DRUM_ALIGN_DELAY_MS 0.302083
Tom 1 Test   AI_DRUM_ALIGN_DELAY_MS 0.000000
```

All three shell tracks contain `JS: utility/AI_Drum_Shell_Phase_Align`.

Verification passed:

- canonical RPP SHA-256 remained `2ea85263d6dc125bf7739264956a1ee1a8074c2b42f69b606b5e9d8b7e9771f1`;
- the OH track received no alignment FX;
- OH media source, item position, item length, source offset, play rate, and pan were unchanged;
- shell media sources, item positions, lengths, source offsets, play rates, and pans were unchanged;
- only shell alignment FX/metadata were added.

## Scope boundary

This increment preserves the admitted workflow's behavior: it performs timing/phase-by-delay alignment and **does not flip polarity or change pan**. Inverse-polarity correlation is reported rather than automatically inverted. Stereo pan matching is therefore a separate continuation increment and must be verified independently rather than silently added to this alignment pass.

Result: **LIVE PASS** — overhead-anchored, non-destructive shell timing alignment is implemented on a disposable project with Tom 1 self-anchor continuity and canonical-project preservation.
