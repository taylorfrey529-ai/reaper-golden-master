# reaperctl

`reaperctl` is the deterministic control-plane CLI for the Reaper Golden Master continuation.

The control plane validates the immutable `GM-2026-09-08` baseline before it observes or drives the live DAW. Transport, production, evidence, and recovery actions are admitted only when their resulting state or output bytes can be verified.

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
bin/reaperctl screenshot --output /absolute/path/reaper-live.png --json
bin/reaperctl snapshot --screenshot /absolute/path/reaper-live.png --output /absolute/path/SNAPSHOT.json --json
bin/reaperctl backup --snapshot /absolute/path/SNAPSHOT.json --output /absolute/path/reaper-continuation-backup.tar.gz --json
bin/reaperctl restore --backup /absolute/path/reaper-continuation-backup.tar.gz --audio-zip /absolute/path/audio.zip --target /absolute/path/clean-target --json
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

The initial admitted stem contract is deliberately strict: exact track-name selection, `$track.wav` naming, filename-safe track names, WAV PCM, 48 kHz, stereo, 24-bit, whole-project bounds, an absent/empty output directory, and non-silent output unless `--allow-silent` is explicit.

The exporter uses a disposable RPP and disposable REAPER config. It opens REAPER's native Render-to-File surface, selects **Selected tracks (stems)**, confirms the native stem mode, renders only the expected files, verifies every file, and destroys the disposable process/config/project afterward. Headless persisted selection (`Nothing to render!`) and action `42230` (which resets stems to master mix) are explicitly rejected paths.

## Align drums to stereo overheads

`align-drums` implements the admitted overhead-anchored shell timing workflow while keeping the canonical project immutable.

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

Application is non-destructive: analysis occurs from source WAVs, a new output RPP is created, only shell tracks receive the dedicated alignment JSFX/metadata, OH state is verified unchanged, shell media/pan state is verified unchanged, and Tom 1 is explicitly reported as a self-anchor.

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

The first admitted pan contract uses a local OH direct-arrival search, 20 ms stereo energy window, inverse equal-power L/R mapping, and robust median/MAD combination. It requires one stereo OH WAVE track and mono 48 kHz / 24-bit shell sources.

`pan-drums` changes only the top-level track `VOLPAN` value for admitted shell tracks. It preserves original RPP newline bytes, refuses in-place editing, verifies the OH and unrelated track chunks are unchanged, and requires the raw byte-line diff to contain exactly one `VOLPAN` line per panned shell.

Latest overhead-derived placements:

```text
Kick Test   -0.062892794   6.289% left    4 / 4 accepted hits
Snare Test  +0.066860605   6.686% right   2 / 2 accepted hits
Tom 1 Test  -0.041736115   4.174% left    5 / 5 accepted hits
```

A stronger aligned-input fixture gate preserved all `AI_DRUM_ALIGN_DELAY_MS` and `AI_Drum_Shell_Phase_Align` state while changing exactly three CRLF-preserving `VOLPAN` lines. Actual REAPER 7.79 read-back returned the same values, including `OH Stereo Test = 0.000000000`.

The first pan writer attempt was rejected because normal text I/O normalized CRLF line endings to LF. The admitted writer preserves original newline sequences and treats any extra byte-line change as failure.

## Screenshot evidence

`screenshot` captures the **real X11 root display** and rejects a missing/stale GUI or blank output.

Admission requires live X11 `:88` at exactly 1440x900, the canonical REAPER 7.79 evaluation window, exact REAPER runtime identity, non-uniform PNG pixels, and unchanged canonical RPP bytes before/after capture. The legitimate evaluation/license state is evidence and must not be suppressed or bypassed.

## Mutable-state snapshot and deterministic backup

`snapshot` creates a machine-readable mutable continuation manifest; it is **not a new Golden Master**. It inventories and hashes the canonical RPP, referenced media, project/routing files, desktop/Openbox/ALSA state, mutable REAPER configuration, Virtual Apollo implementation/configuration/device state, and optional screenshot evidence.

`backup` packages a verified snapshot into deterministic `tar.gz` bytes. Every source file must still match the snapshot; archive membership, embedded snapshot identity, modes, sizes, and payload hashes are reverified. The REAPER runtime is excluded and remains bound to `GM-2026-09-08` by exact SHA-256.

## Deterministic clean-target restore

`restore` reconstructs a continuation into an **isolated target tree** from two authorities:

1. the verified continuation backup for mutable state;
2. the admitted Golden Master `audio.zip` for the exact REAPER 7.79 runtime.

```bash
bin/reaperctl restore \
  --backup /mnt/data/reaperctl-evidence/reaper-continuation-backup-2026-09-08-r2.tar.gz \
  --audio-zip /mnt/data/audio.zip \
  --target /mnt/data/reaperctl-restored \
  --json
```

Restore verification rejects path traversal, unexpected archive members, embedded snapshot tampering, member size/hash/mode drift, wrong Golden Master `audio.zip` bytes, and wrong REAPER runtime bytes. A failed restore removes the partial target.

The first live restore rehearsal, R1, was rejected because clean restoration did not recreate an empty `assets/` directory before `desktop_shell.py` attempted to generate `wallpaper.png`; it also exposed stale-PID Xvfb lifecycle risk. R2 repaired both defects. The exact repaired desktop files are versioned under `recovery/workspace/` and locked by regression hashes.

R2 live proof:

```text
Snapshot ID:
sha256:8067896bcf59f7e09ea66aa5227cc07026e8599638712379363d6e9b692d2f65

Continuation backup SHA-256:
a251950b052cfb0de75d2d0b7b13d1659bd35c0251fc630721246dbf0d91b0b0

Golden Master audio.zip SHA-256:
093f590ba02b0284dc676d7f8ae499ead6fd93316524f7872cfa3c6fda0660bd

Restored REAPER SHA-256:
cee99a74fdd9fc87974c96ea334a50afff4ca8d3121591aed218057bb38185e4

Restored project SHA-256:
2ea85263d6dc125bf7739264956a1ee1a8074c2b42f69b606b5e9d8b7e9771f1
```

The restored system booted on `:88` at 1440x900, regenerated the missing wallpaper asset from a clean tree, mapped the REAPER 7.79 **EVALUATION LICENSE** project window, retained all ALSA `apollo_spdif` / 48 kHz / 256x3 / 2x2 locks, and started the restored Virtual Apollo pipe sink.

One launch-time `reaper.ini` change was observed and classified: REAPER added only `faultyproject=<canonical RPP>`. Locked ALSA fields were unchanged; this is allowed runtime drift, not a continuity regression.

## Web control admission

`scripts/configure-web-control.py` safely admits the continuation Web surface. It is backup-first, idempotent, preserves non-HTTP surfaces, refuses a conflicting HTTP surface, and refuses to write while the specified REAPER binary is running.

REAPER 7.79 itself was observed listening on `0.0.0.0:2307` when the surface was configured; therefore the server is **not** described as loopback-only. `reaperctl` targets/refuses endpoints conservatively. Web control was not part of the R1/R2 captured mutable snapshots, so it was not invented as a restore requirement.

## Live evidence

- `evidence/LIVE-TRANSPORT-2026-09-08.md`
- `evidence/LIVE-RENDER-2026-09-08.md`
- `evidence/LIVE-STEMS-2026-09-08.md`
- `evidence/LIVE-ALIGN-DRUMS-2026-09-08.md`
- `evidence/LIVE-PAN-DRUMS-2026-09-08.md`
- `evidence/LIVE-SNAPSHOT-BACKUP-2026-09-08.md`
- `evidence/LIVE-RESTORE-REHEARSAL-2026-09-08.md`

## Development order

1. `baseline` / `health` — **implemented**.
2. `session` / `play` / `stop` — **implemented and live-verified**.
3. Web control admission — **implemented and live-verified separately**.
4. `render` — **implemented and live-verified at 48 kHz stereo PCM**.
5. `export-stems` — **implemented and live-verified using native selected-track stem semantics**.
6. `align-drums` — **implemented and live-verified with Tom 1 self-anchor continuity**.
7. `pan-drums` — **implemented and live-verified against the fixed OH image**.
8. `screenshot` — **implemented and live-verified from real X11 pixels**.
9. `snapshot` — **implemented and live-verified as mutable-state manifest**.
10. `backup` — **implemented and live-verified as deterministic continuation package**.
11. `restore` — **implemented and R2 live-verified from a clean target over the admitted Golden Master runtime**.
12. branch review/promotion gate — **next**; technical continuation proof is complete, but `main` remains untouched pending an explicit promotion decision.
