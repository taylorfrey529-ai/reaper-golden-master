# Full OS Mutable Layer

Branch: `full-os-mutable-layer`

Parent secure-mutable branch: `mutable-restrictions-lifted`

Base commit:

```text
38cfea3c20227500e0db571f72a0d788ceac2705
```

This branch extends the proven REAPER continuation mutation/rollback model to an operating-system application/configuration layer while keeping the Golden Master, recovery authority, kernel/boot chain, authentication/privilege databases, package trust roots, REAPER runtime binary, and license/evaluation state protected.

## Mutable OS surfaces

Direct raw-file mutation is admitted under these prefixes:

```text
/usr/local
/opt
/etc/profile.d
/etc/systemd/system
/etc/supervisor/conf.d
/etc/xdg
/mnt/data/ubuntu-desktop-workspace
/mnt/data/graphics-workspace
/mnt/data/virtual-apollo
```

The following exact path is also admitted:

```text
/etc/environment
```

These surfaces cover locally installed applications and tools, custom toolchains, desktop/session components, environment configuration, service/process-supervisor definitions, and workspace system configuration.

## Package state

APT package state is mutable through verified package transactions.

A package transaction must retain:

- pre-transaction package inventory;
- post-transaction package inventory;
- package-manager transaction log;
- repository metadata/signature verification;
- system-change manifest;
- rollback/recovery evidence appropriate to the changed package set.

Package-owned files may legitimately land outside the raw mutable roots only through such a verified package-manager transaction. That does **not** turn their containing directories into unrestricted raw-write surfaces.

Package installation must not silently enable services. New network listeners require their own candidate/security review.

## Candidate-required surfaces

The following are not ordinary mutable-layer writes:

```text
/boot
/lib/modules
/usr/lib/modules
/etc/apt/trusted.gpg.d
/etc/apt/keyrings
/etc/pam.d
/etc/security
/etc/ssh
/root/.ssh
/etc/ssl/private
/etc/passwd
/etc/shadow
/etc/group
/etc/gshadow
/etc/sudoers
/etc/resolv.conf
/mnt/data/ubuntu-desktop-workspace/apps/REAPER/reaper
```

Changes touching kernel/bootloader state, authentication databases, privilege policy, package trust roots, the REAPER runtime binary, or a new network listener require a distinct candidate transaction. They are not silently admitted merely because this branch is OS-mutable.

Protected package families include kernel/boot packages such as `linux-image*`, `linux-headers*`, `linux-modules*`, `grub*`, `shim*`, and `systemd-boot*`.

Core package changes including `apt`, `dpkg`, `base-files`, `bash`, `coreutils`, `libc6`, `passwd`, `sudo`, `systemd`, `udev`, and `util-linux` also require a separate candidate.

## Classification before mutation

Use the policy classifier before a new class of OS change:

```bash
python3 scripts/os-mutation-policy.py path /usr/local/bin/my-tool --json
python3 scripts/os-mutation-policy.py path /etc/shadow --json
python3 scripts/os-mutation-policy.py package cmake --json
python3 scripts/os-mutation-policy.py package linux-image-amd64 --json
```

Classification results are:

- `mutable` — admitted by the current full-OS policy, subject to transaction evidence;
- `candidate-required` — not admitted for ordinary mutation; create and validate a separate candidate first.

A relative path, traversal attempt, or malformed package name is rejected.

## Security invariants

The branch does not permit:

- path traversal or symlink escape;
- implicit network enablement;
- package-signature bypass;
- trusted package-keyring mutation as a normal OS change;
- unverified external payload execution;
- authentication/privilege-policy mutation as a normal OS change;
- kernel/bootloader mutation as a normal OS change;
- Golden Master or recovery-authority mutation;
- REAPER evaluation/license bypass.

## Transaction evidence

Every admitted OS mutation must produce a system-change manifest. At minimum it records:

- branch and policy identity;
- operation/category;
- requested change;
- affected paths and/or packages;
- classifier results;
- pre-state hashes/inventory;
- post-state hashes/inventory;
- package transaction log when applicable;
- services/processes added, removed, started, stopped, enabled, or disabled;
- network listeners before/after;
- rollback/recovery artifacts;
- verification verdict.

The schema lives at `schemas/system-change-manifest.schema.json`.

## Relationship to the existing REAPER mutation layer

The previously live-verified project workflow remains intact:

```text
mutate -> receipt -> verify -> rollback
```

This branch adds OS-level mutability; it does not replace the existing RPP transaction safeguards.

`GM-2026-09-08` remains historical recovery authority and is not redefined by this branch.
