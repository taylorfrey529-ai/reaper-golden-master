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

```bash
bin/reaperctl screenshot \
  --output /mnt/data/reaperctl-evidence/reaper-live.png \
  --json
```

Admission requires:

- live X11 `:88` at exactly 1440x900;
- canonical `ASIO-Routing-Project - REAPER v7.79 - EVALUATION LICENSE` window mapped;
- exact REAPER binary SHA `cee99a74fdd9fc87974c96ea334a50afff4ca8d3121591aed218057bb38185e4`;
- non-uniform PNG pixel validation;
- canonical RPP SHA unchanged before/after capture.

The legitimate evaluation/license state is evidence and must not be suppressed or bypassed.

## Mutable-state snapshot

`snapshot` creates a machine-readable continuation manifest. It is **not a new Golden Master**.

```bash
bin/reaperctl snapshot \
  --screenshot /mnt/data/reaperctl-evidence/reaper-live.png \
  --output /mnt/data/reaperctl-evidence/SNAPSHOT.json \
  --json
```

The snapshot inventories and hashes the canonical RPP, all media actually referenced by it, project/routing files, desktop/Openbox/ALSA state, mutable REAPER configuration, Virtual Apollo implementation/configuration/device state, and optional live screenshot evidence.

Ephemeral PIDs/logs, rolling Apollo ear captures, temporary production artifacts, and the REAPER runtime tree are excluded. The exact REAPER runtime is bound by SHA-256 and remains recoverable from `GM-2026-09-08`.

The snapshot ID is SHA-256 over canonicalized manifest content before the `snapshot_id` field is added, so edits are detectable independently of pretty-print formatting.

## Deterministic continuation backup

`backup` packages a verified snapshot into a deterministic `tar.gz`.

```bash
bin/reaperctl backup \
  --snapshot /mnt/data/reaperctl-evidence/SNAPSHOT.json \
  --output /mnt/data/reaperctl-evidence/reaper-continuation-backup.tar.gz \
  --json
```

Before packaging, every live source file must still match its snapshot size and SHA-256. Archive members are sorted; uid/gid/mtime are normalized; the gzip header mtime is zeroed. Verification then checks exact archive membership, the embedded snapshot ID, backup manifest identity/count, and every payload member hash.

The live proof produced the same archive SHA-256 on two independent builds from the same snapshot.

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
- `evidence/LIVE-SNAPSHOT-BACKUP-2026-09-08.md` — recovery observation, real X11 screenshot proof, snapshot identity, and deterministic backup proof.

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
8. `screenshot` — **implemented and live-verified from real X11 pixels**.
9. `snapshot` — **implemented and live-verified as mutable-state manifest**.
10. `backup` — **implemented and live-verified as deterministic continuation package**.
11. continuation restore rehearsal — **next**: restore the package into a clean target over the admitted Golden Master runtime and prove byte/state equivalence.
