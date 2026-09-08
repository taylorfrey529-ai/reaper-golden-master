# Reaper Golden Master

`reaper-golden-master` is the active continuation repository for the byte-preserved REAPER 7.79 production system admitted by [`taylorfrey529-ai/reaper-is-free`](https://github.com/taylorfrey529-ai/reaper-is-free).

## Baseline

```text
Golden Master: GM-2026-09-08
Golden Master ID: 74a13a11fe232bca5bd8a320d11ee0c2e17ce5c2e53d76c74ee9714276a95b1f
Golden Master payload bytes: 888467386
Recovery authority repository: taylorfrey529-ai/reaper-is-free
Recovery authority proof head: 6b76608974737e0b59818db94ecbc21018615794
Golden Master admission commit: 6cd104cbf70237be473b7eda5dca058dcd182069
```

This repository does **not** redefine or mutate `GM-2026-09-08`. It begins from that admitted baseline and records all subsequent development as continuation state.

## Continuity locks inherited from the baseline

```text
REAPER: 7.79 Linux x86_64
Desktop: X11 / Openbox
Display: :88
Audio backend: ALSA (linux_audio_mode=1)
Interface: apollo_spdif
S/PDIF: stereo 2-in / 2-out
Sample rate: 48000 Hz
Buffer: 256 samples x 3
Project: ASIO-Routing-Project
Tempo: 120 BPM / 4/4
```

Never silently regress the admitted baseline. A changed runtime or recovery payload becomes a candidate for a **new** Golden Master and must pass explicit verification before promotion.

## Repository roles

- **`reaper-is-free`** — immutable recovery/continuity authority for admitted Golden Masters.
- **`reaper-golden-master`** — active engineering, production, automation, testing, and evolution after the admitted baseline.

See [`LINEAGE.md`](LINEAGE.md), [`BASELINE.json`](BASELINE.json), and [`CONTINUATION.md`](CONTINUATION.md) for the machine-readable and operational continuation contract.
