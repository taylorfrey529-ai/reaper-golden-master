# Live overhead-image drum pan verification — 2026-09-08

Branch: `development/reaperctl`
Baseline: `GM-2026-09-08`
Canonical project: `ASIO-Routing-Project`
Canonical project SHA-256: `2ea85263d6dc125bf7739264956a1ee1a8074c2b42f69b606b5e9d8b7e9771f1`

## Continuity delta

This increment adds close-shell pan placement derived from the fixed stereo overhead image. It does not replace or mutate the admitted timing-alignment increment.

Frozen invariants:

- `OH Stereo Test` remains fixed and centered;
- shell media source, item position, length, source offset and play rate remain unchanged;
- timing alignment FX/metadata, when present, remain byte-preserved;
- polarity state remains unchanged;
- unrelated tracks and routing remain unchanged;
- the canonical RPP remains byte-identical.

## Pan measurement contract

The initial pan contract is deliberately strict:

```text
reference: exactly one stereo OH WAVE track
shell source: mono 48 kHz / 24-bit WAVE
shell event scan: 2 kHz / 5 ms bins
maximum events: 8
minimum event separation: 120 ms
local OH arrival search: shell event -5 ms to +25 ms
stereo energy window: 2 ms pre / 18 ms post around the local OH anchor
pan mapping: inverse equal-power L/R amplitude ratio
robust combination: median + MAD rejection
minimum accepted shell events: 2
```

The continuation keeps the token-aware `rack` matcher, so `8-Bar Drum Track - 120 BPM` is not treated as a rack tom.

## Live stereo-image results

```text
Kick Test
  pan: -0.062892794  (6.289% left)
  accepted shell events: 4 / 4
  pan MAD: 0.007326019

Snare Test
  pan: +0.066860605  (6.686% right)
  accepted shell events: 2 / 2
  pan MAD: 0.000611468

Tom 1 Test
  pan: -0.041736115  (4.174% left)
  accepted shell events: 5 / 5
  pan MAD: 0.009134491
  Tom 1 identity anchor: true
```

These are intentionally subtle placements because the stereo OH energy differences are subtle; no arbitrary wide-pan preset is introduced.

## Pan-only apply gate

Canonical-source pan output:

```text
/mnt/data/pan-dev/ASIO-Routing-Project-panned.RPP
SHA-256: 2bd9e8e26cd55f1775c8101c1f6ac4c547e9d5bddf9a6d3c1c53d928e622a561
```

After correcting a rejected newline-normalization attempt, the final writer preserves REAPER CRLF bytes. A stronger aligned-input fixture gate produced:

```text
aligned input SHA-256:
4ab0efaa151404c90f07c945a43c267ed419e651e75929214f11f9752c4b199e

aligned + panned output SHA-256:
b0eb1da9db48148a14a45b5e2465360dc5142dcff35803f4f2c4df39427fcea2

line count: 601 -> 601
CRLF lines: 601 -> 601
changed byte lines: 3
```

The three and only three changed lines were the top-level shell `VOLPAN` records:

```text
Kick Test   VOLPAN 1 0            -1 -1 1
         -> VOLPAN 1 -0.062892794 -1 -1 1

Snare Test  VOLPAN 1 0            -1 -1 1
         -> VOLPAN 1 0.066860605  -1 -1 1

Tom 1 Test  VOLPAN 1 0            -1 -1 1
         -> VOLPAN 1 -0.041736115 -1 -1 1
```

The aligned fixture retained the exact admitted timing markers:

```text
Kick Test    AI_DRUM_ALIGN_DELAY_MS 0.000000
Snare Test   AI_DRUM_ALIGN_DELAY_MS 0.302083
Tom 1 Test   AI_DRUM_ALIGN_DELAY_MS 0.000000
```

and retained each `AI_Drum_Shell_Phase_Align` RPP chunk.

## REAPER 7.79 read-back

The panned RPP was opened in actual REAPER 7.79 Linux x86_64 and queried through ReaScript. REAPER reported:

```text
OH Stereo Test  D_PAN =  0.000000000
Kick Test       D_PAN = -0.062892794
Snare Test      D_PAN =  0.066860605
Tom 1 Test      D_PAN = -0.041736115
```

The canonical project remained SHA-256 `2ea85263d6dc125bf7739264956a1ee1a8074c2b42f69b606b5e9d8b7e9771f1`.

## Rejected attempt

The first pan writer used normal text I/O. Python normalized REAPER's CRLF line endings to LF, making the semantic project equivalent but changing nearly every byte line. That attempt was rejected. The admitted writer reads/writes project bytes while preserving each original newline sequence and requires exactly one changed `VOLPAN` line per panned shell.

Result: **LIVE PASS** — stereo shell pan placement is derived from the fixed overhead image, read back correctly by REAPER 7.79, and mechanically preserves prior timing-alignment state.
