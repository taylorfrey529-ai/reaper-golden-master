# Display transport privacy review — NOT LIVE-VALIDATED

Rebuilt 2026-09-09 from candidate revision
`5622cce0f9ee899fb23d98ff30aae1377ba448da` after the previous unpublished patch
was lost. This is new implementation work, not recovery of that exact patch.

## Scope

Only preflight and throwaway display self-testing are enabled. Canonical :88
self-testing is refused and acquire-candidate is explicitly disabled. No live
desktop, package installation, repository trust change, or promotion is claimed.

The controller sends secret-bearing xauth commands through private stdin,
requires an owned private authority directory, refuses existing/symlink targets,
suppresses xauth diagnostics, and publishes authority files without overwriting.
Self-testing requires explicit authorization rejection followed by an authorized
recheck; enabled, empty host access rules; exact IPv4 loopback listener and process
ownership evidence; no IPv6 listener; absent pathname and abstract Unix sockets;
authority ownership/mode checks; and cleanup before returning success.

## Verification in this chat

Seven offline regression tests passed:

```sh
python3 -m unittest discover -s tests -p test_display89_privacy.py -v
```

These tests cover cookie argv exclusion, redaction, existing-file preservation,
symlink refusal, private-directory enforcement, canonical/acquisition blocking,
and rejection of absent, wildcard, or IPv6 listener evidence. They do not replace
live verification or a complete concurrency/security audit.

The self-test exited 1 before server startup: Xvfb, xauth, and xdpyinfo were
missing from PATH. The extracted Xvfb binary additionally lacks libXfont2.so.2.
Openbox is absent. APT fails at its required user/group transitions; no sandbox
or package-signature controls were disabled.

Preflight: AF_UNIX denied with errno 1; AF_INET socket creation and loopback bind
allowed with errno null; Seccomp 2; NoNewPrivs 1. The preflight listener scope is
intended policy, not observed server evidence. No live authentication PASS is
claimed. No server was started, and canonical :88 was untouched.

## Persistent sources

All six GM-2026-09-08 payloads match their recorded identities. The sixth backup
is 6,456,501 bytes, SHA-256
`c67b69e513484e0a5870bd7f55a34a280b3b771b7a5b825cc9ef5bfb932bb31a`;
all 62 internal checksummed files pass. It restores project, audio, configuration,
desktop source, and historical screenshots, but supplies no missing X11 binaries.

## Remaining gates

Supply verified Ubuntu 24.04 amd64 dependencies for Xvfb, xauth, x11-utils,
x11-xserver-utils, and Openbox, including their dependencies and fonts. Preserve
signed package metadata and package hashes when preparing an offline bundle on
an authorized compatible host. Do not install the Debian 13 package snapshot as
an assumed Ubuntu dependency source.

Run the bounded self-test with those tools and review complete listener,
authentication, ownership, and cleanup results. A separate acquisition review
and live-state transaction are required before enabling a desktop. Historical
screenshots and results from another runtime are not current display evidence.
