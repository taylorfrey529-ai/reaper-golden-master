# Live screenshot / snapshot / continuation-backup verification — 2026-09-08

Branch: `development/reaperctl`
Baseline: `GM-2026-09-08`
Canonical project: `ASIO-Routing-Project`
Canonical project SHA-256: `2ea85263d6dc125bf7739264956a1ee1a8074c2b42f69b606b5e9d8b7e9771f1`

## Recovery observations before capture

The first screenshot attempt was correctly rejected as blank/uniform. Xvfb `:88` was reachable, but its root window had zero children: the X server existed while Openbox, the workspace shell, and REAPER were not mapped.

The existing workspace launchers were used to recover the desktop rather than reconstructing it. Two missing live runtime components were then discovered:

1. `/mnt/data/virtual-apollo` was absent. It was restored from the existing `linux-ububtu-vm-workspace-backup/virtual-apollo` authority.
2. `/mnt/data/ubuntu-desktop-workspace/apps/REAPER` was absent. REAPER 7.79 was restored from the admitted local `audio.zip` runtime payload.

Post-restore runtime checks:

```text
REAPER binary SHA-256:
cee99a74fdd9fc87974c96ea334a50afff4ca8d3121591aed218057bb38185e4

Canonical project SHA-256:
2ea85263d6dc125bf7739264956a1ee1a8074c2b42f69b606b5e9d8b7e9771f1

Audio payload SHA-256:
093f590ba02b0284dc676d7f8ae499ead6fd93316524f7872cfa3c6fda0660bd

audio.zip integrity: PASS
Virtual Apollo status: configured; playback tap IDLE
```

After recovery, the X11 tree contained:

```text
ASIO-Routing-Project - REAPER v7.79 - EVALUATION LICENSE
About REAPER v7.79/linux-x86_64 rev 06dd78 (Aug 17 2026)
```

The evaluation/license UI was preserved and detected. No suppression or bypass was performed.

## `reaperctl screenshot` live gate

The admitted capture is a real X11 root-display capture from `:88`.

```text
Output: /mnt/data/reaperctl-evidence/reaper-live-2026-09-08.png
Bytes: 124166
SHA-256: 089f064b40df266eac57369f9787a90ede45cff340057251ceb5527b3ca38c59
Resolution: 1440x900
Unique sampled colors: 1597
Pixel stddev: 47.4035 / 48.1049 / 47.2742
License state: evaluation
Canonical project SHA before/after:
2ea85263d6dc125bf7739264956a1ee1a8074c2b42f69b606b5e9d8b7e9771f1
```

The earlier black capture is explicitly rejected evidence:

```text
SHA-256: 26e314c88dc960b06e42599c6efcc3a6e009f9c9bc0c4f25bc3567fad5a14a22
Bytes: 3863
Reason: uniform/blank validation failure
```

## `reaperctl snapshot` live gate

The snapshot is a manifest of mutable continuation state. It does **not** claim to be a new Golden Master and does not duplicate the admitted REAPER runtime.

```text
Snapshot file: /mnt/data/reaperctl-evidence/SNAPSHOT-2026-09-08.json
Snapshot file bytes: 12826
Snapshot file SHA-256: 6078fea23d8a75116be5f0df97d02d4130b64fc08fcdfc356891036b63fc6a5f
Snapshot ID: sha256:84f80d3dc41d40e7bac286ae6d8085db124ec8b1b45be7bfb432d1272714abdf
Inventory: 35 files
Inventory bytes: 6983185
REAPER runtime embedded: no
```

Inventory scope includes:

- canonical RPP;
- every media file referenced by the canonical RPP;
- routing/project support files;
- X11/Openbox/desktop launch and verification files;
- REAPER mutable configuration required by this workspace;
- ALSA configuration;
- Virtual Apollo implementation/configuration/device state;
- the admitted live screenshot.

Explicit exclusions include PIDs, logs, rolling Apollo ear capture, temporary render/stem projects, and the REAPER runtime tree. The runtime is instead bound by exact SHA-256 and recovered from `GM-2026-09-08`.

## `reaperctl backup` live gate

The continuation backup is a deterministic `tar.gz` built from the verified snapshot.

```text
Archive: /mnt/data/reaperctl-evidence/reaper-continuation-backup-2026-09-08.tar.gz
Bytes: 3029201
SHA-256: 95f2d7ca7ec1d2ca019a199e22bfd4be37fd9d42ae1ac7255fd04f696d4e9131
Snapshot ID: sha256:84f80d3dc41d40e7bac286ae6d8085db124ec8b1b45be7bfb432d1272714abdf
Payload artifacts: 35
Payload bytes before compression: 6983185
Archive members: 37 (`BACKUP-MANIFEST.json`, `SNAPSHOT.json`, plus 35 payload files)
REAPER runtime embedded: no
```

Verification performed:

- snapshot self-ID recomputed and matched;
- every source file size/hash matched the snapshot before packaging;
- archive inventory matched exactly with no missing/extra members;
- embedded snapshot identity revalidated;
- embedded backup manifest identity/count revalidated;
- every extracted payload member was rehashed against the snapshot;
- `tar -tzf` passed;
- a second independent archive build from the same snapshot produced the exact same SHA-256 `95f2d7ca7ec1d2ca019a199e22bfd4be37fd9d42ae1ac7255fd04f696d4e9131`.

Result: **LIVE PASS** — real VM screenshot evidence, mutable-state snapshot, and deterministic continuation recovery package are verified without mutating `GM-2026-09-08` or the canonical RPP.
