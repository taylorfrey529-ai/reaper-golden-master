# Display :88 cross-chat handoff

`:88` is treated as a logical REAPER monitor, not as a transferable PID or Unix-socket inode.

The continuity rule is **attach if the current chat can see the owning runtime; otherwise reconstruct the same logical display in the current runtime**.

## New-chat command

If the live workspace is already mounted:

```bash
/mnt/data/ubuntu-desktop-workspace/acquire-display-88.sh
```

From a repository checkout:

```bash
python3 recovery/workspace/reaper-display88ctl.py \
  --display 88 \
  --handoff-root /mnt/data/ubuntu-desktop-workspace/handoff/display-88 \
  acquire
```

The controller reports one of two successful modes:

- `attached-existing-runtime` — `:88` was already reachable and owned by the expected Xvfb.
- `reconstructed-in-current-runtime` — the old runtime was not reachable, so the controller restored the checkpoint overlay, started Xvfb/Openbox/desktop shell, relaunched the canonical REAPER project, and verified the real X11 window.

## Checkpoint

```bash
python3 recovery/workspace/reaper-display88ctl.py \
  --display 88 \
  --handoff-root /mnt/data/ubuntu-desktop-workspace/handoff/display-88 \
  checkpoint
```

Checkpoint root:

`/mnt/data/ubuntu-desktop-workspace/handoff/display-88/`

It contains a genuine `scrot` capture, X11 window tree, process ownership record, current project and `reaper.ini` overlay, SHA-256 manifest, and a handoff tarball. PIDs are advisory only.

## Sandbox preflight

```bash
python3 recovery/workspace/reaper-display88ctl.py --display 88 preflight
```

If `socket(AF_UNIX, ...)` is denied by the chat runtime, interactive Xvfb reconstruction is impossible there. The controller exits without claiming the monitor is active. The last real checkpoint frame remains usable for visual inspection. No TCP/VNC listener is opened as a workaround.

## Security and continuity locks

- Xvfb stays local: `-nolisten tcp`.
- No new network listener is introduced.
- The REAPER executable must retain its locked SHA-256.
- The current project hash is checkpointed dynamically so later approved project edits can travel with the logical monitor.
- The REAPER evaluation/license UI is preserved and verified by the canonical window title.
- `reaper.ini` is treated as mutable runtime configuration and is checkpointed rather than baseline-locked.
- The handoff directory remains under the admitted mutable workspace root.

## What is and is not transferred

The live Unix socket `/tmp/.X11-unix/X88`, the Xvfb PID, and REAPER process memory cannot be transferred across isolated chat runtimes. The handoff instead transfers the durable state needed to recreate the same logical monitor and validates the resulting real X11 session before calling it restored.
