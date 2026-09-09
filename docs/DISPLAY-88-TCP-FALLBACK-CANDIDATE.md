# Display :88 authenticated loopback TCP fallback candidate

Candidate: `display-88-tcp-fallback-v1`

Branch: `candidate/display-88-tcp-fallback`

Base: `5140c3ca15fe2c2112790996f74769a66aa0bca7`

## Purpose

The admitted cross-chat controller reconstructs `:88` through a local AF_UNIX socket. Some chat execution sandboxes deny `socket(AF_UNIX, SOCK_STREAM, 0)` with `EPERM`, so the admitted controller correctly exits 73 instead of claiming success.

This candidate adds a second transport for that exact condition. It does not replace the admitted transport and it does not activate automatically.

## Security model

Direct `Xvfb -listen tcp` is rejected because this X server build binds wildcard IPv4 and IPv6 listeners. The candidate instead:

1. creates an IPv4 TCP listener itself;
2. binds exactly `127.0.0.1:(6000 + display)`;
3. passes that already-bound socket to Xvfb using the systemd `LISTEN_FDS` protocol;
4. starts Xvfb with both its Unix and self-created TCP transports disabled;
5. requires a fresh Xauthority MIT-MAGIC-COOKIE-1 credential stored mode `0600`;
6. never includes the Xauthority cookie in the cross-chat checkpoint;
7. uses `DISPLAY=127.0.0.1:88` for Openbox, the desktop shell, REAPER, and inspection tools.

For canonical `:88`, the candidate listener would therefore be `127.0.0.1:6088` only.

## Fail-closed routing

The candidate is scoped to the following decision path:

```text
existing admitted :88 reachable
    -> use admitted AF_UNIX path

AF_UNIX available but :88 absent
    -> use admitted AF_UNIX reconstruction

AF_UNIX denied
    -> probe AF_INET loopback bind
       -> denied: exit blocked
       -> allowed: authenticated loopback TCP candidate may reconstruct
```

The candidate activation path deliberately refuses to run when AF_UNIX is available. This prevents the new listener from becoming the normal transport.

## Candidate commands

Non-mutating sandbox probe:

```bash
python3 recovery/workspace/reaper-display88-tcp-candidate.py preflight --display 88
```

Throwaway transport security self-test; it refuses canonical `:88`:

```bash
python3 recovery/workspace/reaper-display88-tcp-candidate.py selftest --display 89
```

Candidate acquisition interface after admission/owner approval:

```bash
recovery/workspace/acquire-display-88-tcp-candidate.sh
```

## Verified development evidence

A throwaway `:89` test proved:

- authenticated `xdpyinfo` succeeds over `127.0.0.1:89`;
- unauthenticated `xdpyinfo` is denied;
- `/tmp/.X11-unix/X89` is absent;
- the only X11 listener is IPv4 loopback `127.0.0.1:6089`;
- Xauthority mode is `0600`;
- Xvfb receives the pre-bound listener as inherited fd 3 rather than binding wildcard TCP itself.

A direct stock-Xvfb TCP test was also performed and rejected as the deployment design because it bound `0.0.0.0:6089` and IPv6 `*:6089`.

## Remaining gate

This candidate has not been promoted into `full-os-mutable-layer` and canonical `:88` has not been converted to TCP. The existing mutability contract states that any new network listener requires candidate handling, explicit security review, and explicit owner approval.

Before promotion, the AF_UNIX-denied target chat must run the non-mutating `preflight` command and prove `af_inet.allowed=true`. If AF_INET is also denied there, in-chat X11 reconstruction remains impossible and the logical monitor must be hosted by a persistent external runtime.
