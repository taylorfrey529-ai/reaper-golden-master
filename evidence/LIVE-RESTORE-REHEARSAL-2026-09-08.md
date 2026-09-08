# Live continuation restore rehearsal — 2026-09-08

Branch: `development/reaperctl`
Baseline: `GM-2026-09-08`
Golden Master ID: `sha256:74a13a11fe232bca5bd8a320d11ee0c2e17ce5c2e53d76c74ee9714276a95b1f`

## Scope

This gate proves that the mutable continuation backup can be restored over the exact admitted REAPER 7.79 runtime, booted from canonical paths on X11/Openbox, and returned to the pre-rehearsal live roots without changing protected project/runtime bytes.

The rehearsal used a reversible filesystem swap so the restored tree occupied the actual canonical paths during boot:

```text
/mnt/data/ubuntu-desktop-workspace
/mnt/data/virtual-apollo
DISPLAY=:88
```

The original live roots were renamed intact, restored after the rehearsal, restarted, and rehashed.

## R1 — rejected

The first clean restore used:

```text
snapshot ID:
sha256:84f80d3dc41d40e7bac286ae6d8085db124ec8b1b45be7bfb432d1272714abdf

continuation backup SHA-256:
95f2d7ca7ec1d2ca019a199e22bfd4be37fd9d42ae1ac7255fd04f696d4e9131
```

Pre-boot reconstruction passed all 35 manifest files plus the exact REAPER runtime, but desktop startup failed. The failure was real and was not promoted:

```text
FileNotFoundError:
/mnt/data/ubuntu-desktop-workspace/assets/wallpaper.png
```

`desktop_shell.py` attempted to generate `assets/wallpaper.png` without first creating the `assets/` parent directory. The rehearsal also exposed a lifecycle weakness: stale/missing PID files could leave the real `Xvfb :88` process alive while startup attempted to create another display server.

R1 verdict: **REJECTED**.

## Recovery fixes

Three mutable workspace files were corrected and then frozen by SHA-256:

```text
recovery/workspace/desktop_shell.py
fe9ec0d07212f7b079290d6d56d41e50f611f5208cfd1f2be9e3ee6d3c62c01d

recovery/workspace/start-desktop.sh
6a9675261b768a306afe6a5281b7d5704118d65ba2414ee0e0cf57c678b68a92

recovery/workspace/stop-desktop.sh
6508312f320c3e9665996965d54da75a8917551cbc64e3f592aa0170dd531642
```

The desktop shell now creates the wallpaper parent directory before generating the wallpaper. Startup discovers the actual Xvfb/Openbox/desktop processes rather than trusting PID files blindly. Shutdown treats PID files as advisory and also targets only the exact workspace/display process identities.

The repaired live session was tested by deleting `assets/`, stopping the desktop, confirming no orphan `Xvfb :88` remained, restarting from zero, regenerating `wallpaper.png`, and reopening the canonical REAPER evaluation project.

## R2 snapshot and backup

A new screenshot/snapshot/backup was created after the recovery fixes.

Real live screenshot:

```text
/mnt/data/reaperctl-evidence/reaper-live-2026-09-08-r2.png
bytes: 110755
SHA-256: 5f206b68807637649f538f4dabd98deb9a50e1dfa40f98aa88ff520feeb71a04
resolution: 1440x900
```

R2 snapshot:

```text
/mnt/data/reaperctl-evidence/SNAPSHOT-2026-09-08-r2.json
bytes: 12776
SHA-256: 2be105e9362eb908a0949469429a0836b45c5e64f3f82a9bc43f29a01aa1b7c0
Snapshot ID: sha256:8067896bcf59f7e09ea66aa5227cc07026e8599638712379363d6e9b692d2f65
Inventory: 35 files / 6971470 bytes
REAPER runtime embedded: no
```

R2 deterministic continuation backup:

```text
/mnt/data/reaperctl-evidence/reaper-continuation-backup-2026-09-08-r2.tar.gz
bytes: 3014291
SHA-256: a251950b052cfb0de75d2d0b7b13d1659bd35c0251fc630721246dbf0d91b0b0
```

A second independent build from the same R2 snapshot produced the identical archive SHA-256.

Golden Master runtime source used by the restore:

```text
/mnt/data/audio.zip
SHA-256: 093f590ba02b0284dc676d7f8ae499ead6fd93316524f7872cfa3c6fda0660bd
```

The exact restored REAPER binary remained:

```text
cee99a74fdd9fc87974c96ea334a50afff4ca8d3121591aed218057bb38185e4
```

## R2 clean restore gate

Pre-boot clean-target verification passed:

```text
continuation artifacts: 35
continuation artifact bytes: 6971470
all sizes: exact
all SHA-256 values: exact
all recorded modes: exact
REAPER runtime SHA-256: exact
```

The clean restored tree deliberately did not contain `assets/wallpaper.png` before first boot. Startup created the parent directory and regenerated the wallpaper successfully.

Live boot then passed:

```text
DISPLAY: :88
resolution: 1440x900
window: ASIO-Routing-Project - REAPER v7.79 - EVALUATION LICENSE
license state: evaluation
Virtual Apollo pipe sink: active
```

Locked REAPER audio configuration was re-read from the restored `reaper.ini` and passed exactly:

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

The restored Virtual Apollo `.asoundrc` matched its restored authority copy byte-for-byte, and opening the REAPER playback device launched the restored `apollo_pipe_sink.py` process.

Restored protected hashes:

```text
canonical project:
2ea85263d6dc125bf7739264956a1ee1a8074c2b42f69b606b5e9d8b7e9771f1

REAPER runtime:
cee99a74fdd9fc87974c96ea334a50afff4ca8d3121591aed218057bb38185e4

Virtual Apollo device state:
8dbe7191e99623be7c9024e5ac686c40c4ce4790c05d41494ea60af8f3affadc
```

Real restored-boot screenshot:

```text
/mnt/data/reaperctl-restore-rehearsal-r2/restore-rehearsal-r2-boot.png
bytes: 110716
SHA-256: 91e84d54a69283688cd2a4f34936858ade2388b48c1c8871f99a46bd11570c34
validated: 1440x900 / non-uniform real X11 pixels
```

Restore receipt:

```text
/mnt/data/reaperctl-restore-rehearsal-r2/RESTORE-REHEARSAL-R2-2026-09-08.json
bytes: 2041
SHA-256: 3b10f33f647ad8f953adb7f468336c5191f3aa44264bfa878b159eef02e83bb4
result: PASS
```

## Post-boot drift classification

Exactly one snapshot-managed file changed during the restored boot:

```text
workspace/config/REAPER/reaper.ini
pre-boot SHA-256: 502dd9e54544f4581e41965bd79d9230f8d8025eaef395013c0f0656e1f8f83c
post-boot SHA-256: ab7c182d176250c952cd634d8a83d29d829bd1d06e208ead0adfeeae1be8b39b
```

The only semantic addition was REAPER's runtime recovery marker:

```text
faultyproject=/mnt/data/ubuntu-desktop-workspace/projects/ASIO-Routing-Project/ASIO-Routing-Project.RPP
```

All locked ALSA fields remained unchanged. This is classified as **allowed launch-time runtime drift**, not a baseline or continuation-lock regression.

## Return-to-original verification

After the restored session was stopped, the original live roots were put back, restarted, and verified. The protected project/runtime bytes and all three repaired desktop files returned exactly:

```text
project SHA-256:
2ea85263d6dc125bf7739264956a1ee1a8074c2b42f69b606b5e9d8b7e9771f1

runtime SHA-256:
cee99a74fdd9fc87974c96ea334a50afff4ca8d3121591aed218057bb38185e4

desktop_shell.py:
fe9ec0d07212f7b079290d6d56d41e50f611f5208cfd1f2be9e3ee6d3c62c01d

start-desktop.sh:
6a9675261b768a306afe6a5281b7d5704118d65ba2414ee0e0cf57c678b68a92

stop-desktop.sh:
6508312f320c3e9665996965d54da75a8917551cbc64e3f592aa0170dd531642
```

## Restore command

The continuation now includes `scripts/reaper-restore.py` / `reaperctl restore`. It verifies the embedded snapshot identity, exact archive membership, member sizes/hashes/modes, Golden Master `audio.zip` SHA-256, and restored REAPER binary identity before admitting an isolated restore target. It rejects path traversal and deletes a partially restored target on failure.

Result: **LIVE PASS — R2 clean-target restore and boot verified.**
