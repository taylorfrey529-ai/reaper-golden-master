# Live Receipt-Driven Rollback Rehearsal — 2026-09-08

Scope: `mutable-restrictions-lifted` secure mutable continuation.

Repository head under test:

```text
3a662e91a3fe719dad6b8212d9c2cac15ffa33f3
```

CI precondition:

```text
GitHub Actions run: 34289426039
Run number: 72
Conclusion: success
```

The repository head includes:

- `scripts/reaper-rollback.py`;
- `tests/test_reaper_rollback.py`;
- `bin/reaperctl rollback` routing;
- rollback compilation/routing in continuation CI.

The live environment remains DNS-isolated. The rollback executor was staged from the branch rollback source while the repository dispatcher/source/test surface was independently verified by GitHub Actions. The live harness retained the same minimal local core adapter used by the prior mutation rehearsal for baseline/path/process helper functions.

Local staged rollback source SHA-256:

```text
9819de0ea8b7a20632584e7e5564e6d85585a3989f34f41051fe035ef2392eb9
```

## Frozen invariants

```text
Golden Master: GM-2026-09-08
canonical project original SHA-256:
2ea85263d6dc125bf7739264956a1ee1a8074c2b42f69b606b5e9d8b7e9771f1

REAPER runtime SHA-256:
cee99a74fdd9fc87974c96ea334a50afff4ca8d3121591aed218057bb38185e4

DISPLAY: :88
required live window:
ASIO-Routing-Project - REAPER v7.79 - EVALUATION LICENSE
```

No Golden Master, recovery authority, runtime binary, network policy, or license/evaluation state was made mutable by this transaction.

## Running-REAPER refusal gate

Before changing any project bytes, `rollback` was invoked while canonical REAPER was running and without `--live`.

Result:

```text
exit code: 2
stderr:
reaperctl: canonical REAPER is running; stop it before rollback or pass --live to explicitly accept live-session overwrite risk

project SHA after refusal:
2ea85263d6dc125bf7739264956a1ee1a8074c2b42f69b606b5e9d8b7e9771f1
```

The refusal gate did not mutate the project.

## Fresh mutation

REAPER was stopped while X11/Openbox remained available. The existing secure mutation path was run again for `pan-drums`.

```text
before:
2ea85263d6dc125bf7739264956a1ee1a8074c2b42f69b606b5e9d8b7e9771f1

after:
2bd9e8e26cd55f1775c8101c1f6ac4c547e9d5bddf9a6d3c1c53d928e622a561
```

Mutation receipt:

```text
/mnt/data/ubuntu-desktop-workspace/evidence/mutations/mutation-20260908T231304.291157Z-pan-drums.json
SHA-256:
153721b2ea27a6f5625e77c9543d056df821541fdae7b49b2c22d3b494eba4d3
```

The mutation changed only the previously admitted three shell `VOLPAN` lines.

## Receipt-driven rollback

The new rollback command consumed that mutation receipt.

Required receipt gates included:

- receipt must be a regular non-symlink file under `workspace/evidence/mutations/`;
- receipt schema/hashes must be structurally valid;
- receipt mutability-policy hash must equal the active policy hash;
- receipt project path must equal the canonical project;
- rollback artifact must be confined to the mutation-evidence root;
- rollback artifact SHA must equal both `rollback_sha256` and `before_sha256`;
- canonical project must still equal the receipt `after_sha256`;
- the current mutated bytes are preserved before rollback;
- restoration is atomic and post-write SHA verified.

Successful transition:

```text
from:
2bd9e8e26cd55f1775c8101c1f6ac4c547e9d5bddf9a6d3c1c53d928e622a561

to:
2ea85263d6dc125bf7739264956a1ee1a8074c2b42f69b606b5e9d8b7e9771f1
```

Rollback receipt:

```text
/mnt/data/ubuntu-desktop-workspace/evidence/mutations/rollback-20260908T231317.037742Z-pan-drums.json
SHA-256:
8963d644459ae94244382a0dfaf97c35f455f720b8c47cd0dc8d92df7ad1ebae
```

The mutated pre-rollback state was retained as:

```text
/mnt/data/ubuntu-desktop-workspace/evidence/mutations/ASIO-Routing-Project.RPP.pre-rollback-2bd9e8e26cd55f1775c8101c1f6ac4c547e9d5bddf9a6d3c1c53d928e622a561.rpp
SHA-256:
2bd9e8e26cd55f1775c8101c1f6ac4c547e9d5bddf9a6d3c1c53d928e622a561
```

## Replay protection

The same mutation receipt was immediately submitted a second time after restoration.

Result:

```text
exit code: 4
stderr:
reaperctl: canonical project no longer matches mutation receipt after_sha256: current=2ea85263d6dc125bf7739264956a1ee1a8074c2b42f69b606b5e9d8b7e9771f1, expected=2bd9e8e26cd55f1775c8101c1f6ac4c547e9d5bddf9a6d3c1c53d928e622a561
```

The restored project remained unchanged. There is intentionally no force path that can reuse a stale receipt to overwrite later state.

## Final live boot

REAPER was restarted on the restored project.

```text
project SHA-256:
2ea85263d6dc125bf7739264956a1ee1a8074c2b42f69b606b5e9d8b7e9771f1

REAPER runtime SHA-256:
cee99a74fdd9fc87974c96ea334a50afff4ca8d3121591aed218057bb38185e4

window:
ASIO-Routing-Project - REAPER v7.79 - EVALUATION LICENSE
```

Locked audio state remained:

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

`apollo_pipe_sink.py` was present after restart and no `.ASIO-Routing-Project.mutation-*.RPP` candidate remained in the canonical project directory.

## Consolidated local receipt

```text
/mnt/data/reaperctl-mutation-rehearsal/LIVE-ROLLBACK-REHEARSAL-2026-09-08.json
SHA-256:
4a980ec588246f3067b52f232aa22c8b4f524440baf764801beba891f966f5b0
```

## Verdict

**PASS — receipt-driven secure rollback is live-verified.**

`reaperctl rollback --receipt <mutation-receipt>` is now suitable as the normal recovery half of the secure mutable workflow, subject to the same running-REAPER and security gates. This does not promote or redefine `GM-2026-09-08`.
