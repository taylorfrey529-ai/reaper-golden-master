# Reaper Golden Master Lineage

This repository continues from a separately admitted and byte-preserved recovery authority. It must never rewrite that authority by implication.

## Parent authority

```text
Repository: taylorfrey529-ai/reaper-is-free
Proof head: 6b76608974737e0b59818db94ecbc21018615794
Golden Master admission commit: 6cd104cbf70237be473b7eda5dca058dcd182069
Golden Master: GM-2026-09-08
Golden Master ID: 74a13a11fe232bca5bd8a320d11ee0c2e17ce5c2e53d76c74ee9714276a95b1f
Payload bytes: 888467386
```

The parent repository remains the recovery authority for that admitted baseline.

## Continuation rule

`reaper-golden-master` begins after the admitted baseline. Every change belongs to one of these states:

1. **Continuation change** — modifies active engineering or production behavior while preserving all baseline recovery locks.
2. **Candidate Golden Master change** — intentionally changes a baseline runtime, recovery payload, or continuity lock and therefore requires a new candidate identity.
3. **Promoted Golden Master** — a candidate that has passed exact-byte verification, repository regression, live boot/behavior verification, and explicit promotion.

A continuation change must never silently redefine `GM-2026-09-08`.

## Current baseline locks

```text
REAPER 7.79 Linux x86_64
X11 / Openbox
DISPLAY=:88
ALSA linux_audio_mode=1
apollo_spdif
2 input channels
2 output channels
48000 Hz
256 samples x 3 buffers
ASIO-Routing-Project
120 BPM
4/4
```

## Promotion discipline

When a future change affects the runtime or recovery identity:

- preserve `GM-2026-09-08` unchanged;
- create a new candidate identity;
- compute hashes for every required payload;
- verify downloaded/read-back bytes, not merely upload success;
- pass repository regression;
- boot and validate the live REAPER environment;
- record the new recovery authority in `reaper-is-free`;
- only then mark the candidate as promoted.

The continuation repository may evolve freely, but admitted Golden Masters are immutable historical anchors.
