# R2 workspace recovery fixtures

These files are the exact mutable desktop bytes admitted by the successful 2026-09-08 R2 clean-target restore rehearsal.

They are **continuation recovery fixtures**, not a replacement for `GM-2026-09-08` and not a duplicate REAPER runtime. The exact REAPER 7.79 runtime remains owned by the Golden Master and is restored separately from the admitted `audio.zip` payload.

```text
desktop_shell.py
SHA-256 fe9ec0d07212f7b079290d6d56d41e50f611f5208cfd1f2be9e3ee6d3c62c01d

start-desktop.sh
SHA-256 6a9675261b768a306afe6a5281b7d5704118d65ba2414ee0e0cf57c678b68a92

stop-desktop.sh
SHA-256 6508312f320c3e9665996965d54da75a8917551cbc64e3f592aa0170dd531642
```

R1 exposed two clean-restore defects:

1. `desktop_shell.py` assumed `assets/` already existed before generating `assets/wallpaper.png`.
2. desktop lifecycle control could trust stale PID files and leave the real `Xvfb :88` process alive.

R2 fixes both:

- the desktop creates the wallpaper parent directory explicitly;
- startup verifies the actual expected Xvfb process when a display is already reachable;
- shutdown treats PID files as advisory and also targets only exact workspace/display processes.

Regression tests lock these three files to the hashes above. See `evidence/LIVE-RESTORE-REHEARSAL-2026-09-08.md` for the rejected R1 and successful R2 live proof.
