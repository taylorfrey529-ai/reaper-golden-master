# Live Secure Mutation Rehearsal — 2026-09-08

Scope: `mutable-restrictions-lifted` secure mutable continuation.

Branch source head under test:

```text
8c4da772f8b4aee7aa90c7afbeb8b08d3e69c1f0
```

Precondition CI:

```text
GitHub Actions run: 34287949659
Run number: 67
Conclusion: success
```

The live workspace is intentionally DNS-isolated, so a Git checkout from GitHub was not available inside the X11/REAPER environment. The live executor was staged from the branch mutation source and the exact repository `reaper-pan-drums.py` transform, with a minimal local core adapter supplying only baseline/path/process helper functions already covered by repository CI. This evidence therefore binds two proof classes separately:

1. exact repository-source regression/security proof from GitHub Actions;
2. real-workspace mutation/boot/rollback behavior from the live rehearsal.

No claim is made that the locally staged core adapter is the repository `reaperctl-core` byte-for-byte.

## Frozen invariants

```text
Golden Master: GM-2026-09-08
canonical project pre/post SHA-256:
2ea85263d6dc125bf7739264956a1ee1a8074c2b42f69b606b5e9d8b7e9771f1

REAPER runtime SHA-256:
cee99a74fdd9fc87974c96ea334a50afff4ca8d3121591aed218057bb38185e4

DISPLAY: :88
window title requirement:
ASIO-Routing-Project - REAPER v7.79 - EVALUATION LICENSE
```

Network enablement, REAPER-binary mutation, Golden Master mutation, recovery-authority mutation, path traversal, symlink escape, and license/evaluation bypass remained outside the permitted mutation surface.

## Live-session refusal gate

With canonical REAPER running, `mutate pan-drums` was invoked without `--live`.

Result:

```text
exit code: 2
stderr:
reaperctl: canonical REAPER is running; stop it before mutation or pass --live to explicitly accept live-session overwrite risk

project SHA before:
2ea85263d6dc125bf7739264956a1ee1a8074c2b42f69b606b5e9d8b7e9771f1

project SHA after refusal:
2ea85263d6dc125bf7739264956a1ee1a8074c2b42f69b606b5e9d8b7e9771f1
```

The refusal path did not mutate the canonical project.

## Safe mutation path

REAPER was stopped while X11/Openbox and Virtual Apollo remained available. The pan transform re-derived the same previously live-verified shell positions from `OH Stereo Test`:

```text
Kick Test   -0.06289279384260943
Snare Test  +0.06686060454210596
Tom 1 Test  -0.04173611454816717
```

Only three top-level shell `VOLPAN` lines changed:

```text
Kick Test
VOLPAN 1 0 -1 -1 1
-> VOLPAN 1 -0.062892794 -1 -1 1

Snare Test
VOLPAN 1 0 -1 -1 1
-> VOLPAN 1 0.066860605 -1 -1 1

Tom 1 Test
VOLPAN 1 0 -1 -1 1
-> VOLPAN 1 -0.041736115 -1 -1 1
```

Transform verification reported:

```text
overhead_unchanged: true
only_shell_volpan_changed: true
changed_byte_lines: 3
timing_fx_and_metadata_preserved: true
```

The canonical project moved from:

```text
before:
2ea85263d6dc125bf7739264956a1ee1a8074c2b42f69b606b5e9d8b7e9771f1

after mutation:
2bd9e8e26cd55f1775c8101c1f6ac4c547e9d5bddf9a6d3c1c53d928e622a561
```

The transaction used atomic replacement and post-write SHA verification.

Mutation receipt:

```text
/mnt/data/ubuntu-desktop-workspace/evidence/mutations/mutation-20260908T225838.596075Z-pan-drums.json
SHA-256:
153721b2ea27a6f5625e77c9543d056df821541fdae7b49b2c22d3b494eba4d3
```

Rollback artifact:

```text
/mnt/data/ubuntu-desktop-workspace/evidence/mutations/ASIO-Routing-Project.RPP.before-2ea85263d6dc125bf7739264956a1ee1a8074c2b42f69b606b5e9d8b7e9771f1.rpp
SHA-256:
2ea85263d6dc125bf7739264956a1ee1a8074c2b42f69b606b5e9d8b7e9771f1
```

## Mutated live boot

The mutated project was launched in the real `:88` REAPER environment.

Mapped window:

```text
ASIO-Routing-Project - REAPER v7.79 - EVALUATION LICENSE
```

The project remained byte-identical to the mutated candidate after REAPER boot:

```text
2bd9e8e26cd55f1775c8101c1f6ac4c547e9d5bddf9a6d3c1c53d928e622a561
```

No license/evaluation suppression or bypass occurred.

## Rollback verification

REAPER was stopped. The verified rollback artifact was restored with an atomic same-directory replacement.

Restored project SHA-256:

```text
2ea85263d6dc125bf7739264956a1ee1a8074c2b42f69b606b5e9d8b7e9771f1
```

REAPER was restarted on the restored canonical project. The mapped window again reported:

```text
ASIO-Routing-Project - REAPER v7.79 - EVALUATION LICENSE
```

After restart the canonical project remained exactly:

```text
2ea85263d6dc125bf7739264956a1ee1a8074c2b42f69b606b5e9d8b7e9771f1
```

REAPER runtime remained exactly:

```text
cee99a74fdd9fc87974c96ea334a50afff4ca8d3121591aed218057bb38185e4
```

Locked audio fields after rollback/restart:

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

The `apollo_pipe_sink.py` process was present after the final restart. No temporary `.mutation-*.RPP` candidate remained in the canonical project directory.

## Consolidated local rehearsal receipt

```text
/mnt/data/reaperctl-mutation-rehearsal/LIVE-MUTATION-REHEARSAL-R2-2026-09-08.json
SHA-256:
4ab73e58468daba010904227724133694ec4b1603130f2b26dfcac633efa0c8d
```

## Verdict

**PASS — live secure mutation/rollback behavior verified.**

This proves that the mutable branch can intentionally change canonical continuation project state while preserving the security boundary and exact rollback path. It does not promote a new Golden Master and does not alter `GM-2026-09-08`.

Next development gate: add a first-class receipt-driven rollback command before treating secure mutation as a normal production workflow.
