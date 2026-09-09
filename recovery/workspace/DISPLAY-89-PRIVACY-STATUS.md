# Display transport privacy hardening — NOT LIVE-VALIDATED

Base revision: `5622cce0f9ee899fb23d98ff30aae1377ba448da`.

This separate candidate is unpromoted. It is not approval to activate canonical
display :88, run acquire-candidate, or replace the admitted transport.

Changes follow the mit-magic-cookie-1 safeguards: secret-bearing xauth input
uses stdin, authority creation requires a private directory and refuses existing
targets, authentication rejection must be explicit and followed by an authorized
recheck, and listener family/address/ownership plus pathname and abstract Unix
socket evidence are required. Cleanup is checked before success is returned.

## Evidence

Six offline tests passed using:

```bash
python3 -m unittest discover -s tests -p test_display89_privacy.py -v
```

Python compilation and git diff whitespace checks passed. These checks do not
prove live X11 transport behavior or exhaustively validate the controller.

The live self-test exited 1 before starting a server: Xvfb, xauth, and xdpyinfo
are missing in the tested execution context. Dependency installation encountered
user/group permission restrictions. Preflight reported AF_UNIX denied (errno 1),
AF_INET creation/bind allowed, seccomp 2, and NoNewPrivs 1.

No IPv4/IPv6 listener on port 6089 remained. Canonical :88 was untouched.
No authentication PASS, live listener confinement PASS, or deployment readiness
is claimed. No real cookies, authority files, or runtime credentials are included.

## Remaining gate

In an authorized environment with the required dependencies, run the throwaway
self-test and inspect its full result, authorization failures, authenticated
recheck, IPv4/IPv6 listener ownership, pathname/abstract socket absence, and
cleanup. Review the broader acquisition path separately before promotion.
