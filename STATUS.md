# Continuation Status

Current state: **promoted continuation — production controls, evidence/backup, and R2 clean-target restore are live-verified on `main`**

```text
Repository: taylorfrey529-ai/reaper-golden-master
Development branch: development/reaperctl
Baseline: GM-2026-09-08
Golden Master ID: 74a13a11fe232bca5bd8a320d11ee0c2e17ce5c2e53d76c74ee9714276a95b1f
Recovery authority: taylorfrey529-ai/reaper-is-free
Recovery authority proof head: 6b76608974737e0b59818db94ecbc21018615794
```

Live-verified continuation capabilities:

- immutable baseline and continuity-lock verification;
- live REAPER/X11/project discovery;
- state-confirmed transport control;
- verified 48 kHz stereo 24-bit render;
- native selected-track stem export;
- overhead-anchored drum timing alignment with Tom 1 self-anchor continuity;
- overhead-derived shell pan placement;
- real-X11 screenshot evidence;
- mutable-state snapshot manifest;
- deterministic continuation backup;
- deterministic clean-target `restore` over the exact admitted Golden Master REAPER runtime;
- reversible restore rehearsal proving the original live roots return unchanged.

## Drum continuation state

```text
OH Stereo Test
  timing: fixed reference
  pan: 0.000000000

Kick Test
  timing offset: +0.000000 ms
  pan: -0.062892794  (6.289% left)

Snare Test
  timing offset: +0.302083 ms
  pan: +0.066860605  (6.686% right)

Tom 1 Test
  timing offset: +0.000000 ms
  self-anchor: yes
  pan: -0.041736115  (4.174% left)
```

## Restore rehearsal history

### R1 — rejected

The original snapshot/backup successfully reconstructed all 35 mutable payload files plus the Golden Master REAPER runtime before boot, but clean desktop startup failed because `desktop_shell.py` assumed `workspace/assets/` already existed. The same gate also exposed stale-PID Xvfb lifecycle risk.

R1 remains historical rejected evidence:

```text
Snapshot ID:
sha256:84f80d3dc41d40e7bac286ae6d8085db124ec8b1b45be7bfb432d1272714abdf

Backup SHA-256:
95f2d7ca7ec1d2ca019a199e22bfd4be37fd9d42ae1ac7255fd04f696d4e9131
```

### R2 — live pass

Recovery fixes are versioned under `recovery/workspace/`:

```text
desktop_shell.py
fe9ec0d07212f7b079290d6d56d41e50f611f5208cfd1f2be9e3ee6d3c62c01d

start-desktop.sh
6a9675261b768a306afe6a5281b7d5704118d65ba2414ee0e0cf57c678b68a92

stop-desktop.sh
6508312f320c3e9665996965d54da75a8917551cbc64e3f592aa0170dd531642
```

R2 evidence package:

```text
Screenshot:
/mnt/data/reaperctl-evidence/reaper-live-2026-09-08-r2.png
SHA-256: 5f206b68807637649f538f4dabd98deb9a50e1dfa40f98aa88ff520feeb71a04

Snapshot:
/mnt/data/reaperctl-evidence/SNAPSHOT-2026-09-08-r2.json
SHA-256: 2be105e9362eb908a0949469429a0836b45c5e64f3f82a9bc43f29a01aa1b7c0
Snapshot ID: sha256:8067896bcf59f7e09ea66aa5227cc07026e8599638712379363d6e9b692d2f65
Inventory: 35 files / 6971470 bytes

Continuation backup:
/mnt/data/reaperctl-evidence/reaper-continuation-backup-2026-09-08-r2.tar.gz
SHA-256: a251950b052cfb0de75d2d0b7b13d1659bd35c0251fc630721246dbf0d91b0b0
bytes: 3014291
```

A second independent R2 backup build produced the identical archive SHA-256.

Golden Master runtime source:

```text
/mnt/data/audio.zip
SHA-256: 093f590ba02b0284dc676d7f8ae499ead6fd93316524f7872cfa3c6fda0660bd
```

Clean-target restore and boot passed with:

```text
REAPER runtime SHA-256:
cee99a74fdd9fc87974c96ea334a50afff4ca8d3121591aed218057bb38185e4

canonical project SHA-256:
2ea85263d6dc125bf7739264956a1ee1a8074c2b42f69b606b5e9d8b7e9771f1

Virtual Apollo device state SHA-256:
8dbe7191e99623be7c9024e5ac686c40c4ce4790c05d41494ea60af8f3affadc

DISPLAY: :88
resolution: 1440x900
window: ASIO-Routing-Project - REAPER v7.79 - EVALUATION LICENSE
Virtual Apollo pipe sink: active
```

The clean target did not contain `assets/wallpaper.png` before boot; the repaired desktop generated it successfully.

The locked audio settings were re-read after restore and passed exactly:

```text
alsa_indev=apollo_spdif
alsa_outdev=apollo_spdif
linux_audio_mode=1
linux_audio_bsize=256
linux_audio_bufs=3
linux_audio_nch_in=2
linux_audio_nch_out=2
linux_audio_srate=48000
```

Restored-boot screenshot:

```text
/mnt/data/reaperctl-restore-rehearsal-r2/restore-rehearsal-r2-boot.png
SHA-256: 91e84d54a69283688cd2a4f34936858ade2388b48c1c8871f99a46bd11570c34
resolution: 1440x900
```

Restore receipt:

```text
/mnt/data/reaperctl-restore-rehearsal-r2/RESTORE-REHEARSAL-R2-2026-09-08.json
SHA-256: 3b10f33f647ad8f953adb7f468336c5191f3aa44264bfa878b159eef02e83bb4
result: PASS
```

Exactly one snapshot-managed file drifted during first launch: REAPER added `faultyproject=<canonical RPP>` to `reaper.ini`. All locked ALSA fields remained unchanged, so this is classified as allowed launch-time runtime state, not a continuity regression.

After rehearsal, the original live roots were restored and restarted with the same protected project/runtime and repaired-desktop hashes.

## Restore command

`reaperctl restore` now performs isolated filesystem reconstruction and verification. It checks the embedded snapshot identity, exact archive membership, every payload size/hash/mode, Golden Master `audio.zip` identity, restored REAPER binary identity, and rejects path traversal. Partial targets are deleted on failure.

Detailed proof: `evidence/LIVE-RESTORE-REHEARSAL-2026-09-08.md`.

## Promotion gate

Technical continuation proof through clean-target restore completed on `development/reaperctl` at:

```text
52a1ee97a19053c1fb1e2754fcd4d2e77a22a4f6
```

Owner approval for the promotion gate was supplied separately after technical verification. `main` was then fast-forwarded from `2762c9e9ac5c888e9d335c4481e858c9ef5f0f05` to that exact verified continuation head without force.

Post-promotion GitHub Actions run `34287126542` / run #59 passed on `main` at the same exact head, including inherited Golden Master baseline verification, control-plane compilation, unit/regression tests, continuation command routing, and static health checks.

This promotion advances the **continuation repository state only**. It does not redefine, mutate, or replace `GM-2026-09-08`, its Golden Master ID, its recovery authority, or its exact runtime binary tier.

## Current gate

Promotion to `main` is complete and technically verified. No new runtime candidate has been admitted beyond the promoted R2 continuation state.

Next development cursor: **begin the next continuation transaction from the promoted `main` head while preserving all Golden Master and R2 recovery locks**.
