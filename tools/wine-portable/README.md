# Portable Wine WoW64 artifact branch

This branch assembles a deterministic, regression-checked Wine 11.17 Linux x86_64
WoW64 runtime for the REAPER workstation. The upstream release asset is immutable by
digest: `3211db09086bc6fbd769c0286f27790b32d6fc6fb0bc610dad6b59796f07d462`.

The build verifies the upstream archive, preserves both i386 and x86_64 Windows modules,
adds an isolated WoW 1.0.0.3980 launcher, produces a complete internal checksum manifest,
and uploads the deterministic `.tar.xz` plus its SHA-256 companion file.

No REAPER project or configuration file is modified by the build or launcher.

