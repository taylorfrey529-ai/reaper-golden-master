# Continuation Contract

This repository is the active evolution surface for the REAPER Golden Master system.

## Allowed work

Continuation work may include:

- REAPER project evolution;
- ReaScript and JSFX development;
- Virtual Apollo / `apollo_spdif` improvements;
- routing, monitoring, rendering, and capture automation;
- X11/Openbox session improvements;
- production workflow automation;
- regression, screenshot, audio, and live-session verification;
- plugin/DSP development;
- candidate future Golden Master preparation.

## Baseline-preserving changes

A normal continuation change must preserve:

```text
Golden Master: GM-2026-09-08
Golden Master ID: 74a13a11fe232bca5bd8a320d11ee0c2e17ce5c2e53d76c74ee9714276a95b1f
REAPER 7.79 Linux x86_64
X11 / Openbox on :88
ALSA linux_audio_mode=1
apollo_spdif
2-in / 2-out
48000 Hz
256 samples x 3
ASIO-Routing-Project
120 BPM / 4/4
```

The values above describe the inherited baseline. A future continuation may intentionally change one of them, but such a change must be declared as a **candidate Golden Master change** rather than silently overwriting the baseline record.

## Candidate workflow

When an intentional baseline change is made:

1. Create a candidate record under `candidates/<candidate-id>/`.
2. Record all changed continuity locks and runtime payload identities.
3. Compute SHA-256 for every affected payload.
4. Run repository regression.
5. Run live REAPER boot and behavior verification.
6. Read back any externally persisted binary payloads and re-hash them.
7. Promote the candidate only after the recovery authority repository has recorded it.

Until step 7 completes, the currently admitted Golden Master remains `GM-2026-09-08`.

## State vocabulary

- **Baseline** — immutable admitted Golden Master from which this repository continues.
- **Continuation** — active work that does not claim a new Golden Master identity.
- **Candidate** — proposed new recovery/runtime identity awaiting verification.
- **Promoted** — explicitly admitted new Golden Master with complete recovery evidence.

## Source of truth

For `GM-2026-09-08`, recovery truth remains in:

`https://github.com/taylorfrey529-ai/reaper-is-free`

This repository is the development successor, not a replacement for that historical authority.
