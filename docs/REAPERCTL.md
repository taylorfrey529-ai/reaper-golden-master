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
bin/reaperctl align-drums --analyze-only --json
bin/reaperctl align-drums --output-project /absolute/path/ASIO-Routing-Project-aligned.RPP --json
bin/reaperctl pan-drums --analyze-only --json
bin/reaperctl pan-drums --project /absolute/path/ASIO-Routing-Project-aligned.RPP --output-project /absolute/path/ASIO-Routing-Project-aligned-panned.RPP --json
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

The initial admitted stem contract is deliberately strict: exact track-name selection, `$track.wav` naming, filename-safe track names, WAV PCM, 48 kHz, stereo, 24-bit, whole-project bounds, an absent/empty output directory, and non-silent output unless `--allow-silent` is explicit.

The exporter uses a disposable RPP and disposable REAPER config. It opens REAPER's native Render-to-File surface, selects **Selected tracks (stems)**, confirms the native stem mode, renders only the expected files, verifies every file, and destroys the disposable process/config/project afterward. Headless persisted selection (`Nothing to render!`) and action `42230` (which resets stems to master mix) are explicitly rejected paths.

## Align drums to stereo overheads

`align-drums` implements the admitted overhead-anchored shell timing workflow while keeping the canonical project immutable.

```bash
bin/reaperctl align-drums --analyze-only --json

bin/reaperctl align-drums \
  --output-project /mnt/data/reaperctl-align/ASIO-Routing-Project-aligned.RPP \
  --json
```

The measurement stages preserve the admitted algorithm:

```text
2 kHz transient scan / 5 ms bins
up to 8 events / 120 ms minimum separation
8 kHz coarse derivative-energy correlation
+/-25 ms overhead search
96 kHz fine signed-derivative correlation
0.8 ms fine search radius
median + MAD outlier rejection
maximum admitted offset: 50 ms
minimum accepted score: 0.035
```

The initial continuation contract is intentionally strict: exactly one stereo OH WAVE track and simple single-WAVE-item shell tracks at 48 kHz / 24-bit with `POSITION=0`, `SOFFS=0`, and `PLAYRATE=1`.

Auto-detected shell names include kick, snare, tom, floor tom, and tokenized rack-tom names. The continuation fixes a historical false-positive bug: `rack` must be a token, so a name such as `8-Bar Drum Track - 120 BPM` is not misclassified merely because `track` contains the substring `rack`.

Application is non-destructive:

- analysis occurs from the source WAVs;
- a new output RPP is created;
- a disposable REAPER config receives the admitted `AI_Drum_Shell_Phase_Align` JSFX;
- only shell tracks receive the JSFX and `AI_DRUM_ALIGN_DELAY_MS` metadata;
- OH item/source/pan state is verified unchanged;
- shell item/source/pan state is verified unchanged;
- the canonical RPP hash is checked before and after;
- Tom 1 is explicitly reported as a self-anchor.

Latest live measurements:

```text
Kick Test   +0.000000 ms   4 accepted hits   OH L/1   score 0.999262
Snare Test  +0.302083 ms   2 accepted hits   robust median of 0.000000 / 0.604167 ms
Tom 1 Test  +0.000000 ms   5 accepted hits   OH L/1   score 0.999800   Tom 1 self-anchor
```

The verified aligned RPP SHA-256 is `57746c7b5a716304bd0e70d5afcf53f8441999c0065418cd9ff308fb881b25a1`; the canonical RPP remained `2ea85263d6dc125bf7739264956a1ee1a8074c2b42f69b606b5e9d8b7e9771f1`.

This command deliberately does **not** change pan or flip polarity. Timing alignment and pan placement remain separate continuity surfaces.

## Pan drum shells to the overhead image

`pan-drums` derives close-shell stereo placement from the fixed OH image while mechanically preserving the timing-alignment state.

```bash
bin/reaperctl pan-drums --analyze-only --json

bin/reaperctl pan-drums \
  --project /mnt/data/reaperctl-align/ASIO-Routing-Project-aligned.RPP \
  --output-project /mnt/data/reaperctl-align/ASIO-Routing-Project-aligned-panned.RPP \
  --json
```

The first admitted pan contract is intentionally conservative:

```text
reference: exactly one stereo OH WAVE track
shell source: mono 48 kHz / 24-bit WAVE
shell event scan: 2 kHz / 5 ms bins
maximum events: 8
minimum event separation: 120 ms
local OH anchor search: shell event -5 ms to +25 ms
stereo energy window: 2 ms pre / 18 ms post around the local OH anchor
pan mapping: inverse equal-power L/R amplitude ratio
robust combination: median + MAD rejection
minimum accepted shell hits: 2
```

`pan-drums` changes only the top-level track `VOLPAN` value for admitted shell tracks. It preserves the original RPP newline bytes, refuses an in-place edit, verifies the OH chunk is unchanged, verifies all unrelated tracks are unchanged, verifies media/item state is unchanged, and requires the raw byte-line diff to contain exactly one `VOLPAN` line per panned shell.

Latest overhead-derived placements:

```text
Kick Test   -0.062892794   6.289% left    4 / 4 accepted hits
Snare Test  +0.066860605   6.686% right   2 / 2 accepted hits
Tom 1 Test  -0.041736115   4.174% left    5 / 5 accepted hits
```

A stronger aligned-input fixture gate preserved all `AI_DRUM_ALIGN_DELAY_MS` and `AI_Drum_Shell_Phase_Align` state while changing exactly three CRLF-preserving `VOLPAN` lines. Actual REAPER 7.79 read-back returned the same four `D_PAN` values, including `OH Stereo Test = 0.000000000`.

The first implementation attempt was rejected because normal text I/O normalized CRLF line endings to LF. The admitted writer preserves original newline sequences and treats any extra byte-line change as failure.

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
- `evidence/LIVE-ALIGN-DRUMS-2026-09-08.md` — verified OH-anchored shell timing alignment.
- `evidence/LIVE-PAN-DRUMS-2026-09-08.md` — verified OH-image pan placement with byte-level pan-only diff and REAPER 7.79 read-back.

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
6. `align-drums` — **implemented and live-verified with Tom 1 self-anchor continuity**.
7. `pan-drums` — **implemented and live-verified against the fixed OH image**.
8. `screenshot` / `snapshot` / `backup` — next evidence/recovery increment.
