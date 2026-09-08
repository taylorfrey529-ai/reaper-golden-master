# Secure Mutable Continuation

This document applies to the `mutable-restrictions-lifted` branch of `taylorfrey529-ai/reaper-golden-master`.

The purpose of this branch is to permit intentional continuation-state mutation without weakening the security, Golden Master, recovery-authority, or license/evaluation boundaries.

## Invariants that remain locked

The following remain protected:

- `GM-2026-09-08` identity and Golden Master record;
- recovery authority in `taylorfrey529-ai/reaper-is-free`;
- REAPER 7.79 runtime binary identity unless a separately declared candidate is created;
- path-traversal and symlink-escape rejection;
- no implicit network enablement;
- no license/evaluation bypass;
- no execution of unverified external payloads;
- no silent mutation;
- owner-controlled promotion for future Golden Master admission.

`MUTABILITY.json` is the branch-local policy contract and `scripts/verify-mutability.sh` enforces these invariants in CI.

## Secure mutation

The first admitted in-place mutation operations are:

```bash
bin/reaperctl mutate pan-drums --json
bin/reaperctl mutate align-drums --json
```

The command does not weaken the underlying transforms. It first creates and verifies a disposable candidate project, then applies the candidate to the canonical RPP only through the secure mutation transaction.

A successful mutation requires:

1. canonical project confinement to the workspace;
2. no project symlink;
3. inherited Golden Master baseline health;
4. active secure mutability policy;
5. REAPER stopped unless `--live` is explicitly supplied;
6. verified transform output bound to the current canonical-project SHA;
7. verified pre-write rollback artifact;
8. a second canonical-project SHA check before replacement;
9. atomic same-directory replacement;
10. post-write SHA verification;
11. durable mutation receipt.

The normal production path is to stop REAPER before mutation. `--live` exists only as an explicit risk acknowledgement and is recorded in the receipt; it is not implied by this branch.

## Mutation receipt

A mutation receipt is written under:

```text
/mnt/data/ubuntu-desktop-workspace/evidence/mutations/
```

It binds at least:

- operation;
- canonical project path;
- `before_sha256`;
- `after_sha256`;
- rollback artifact path and SHA;
- active mutability-policy SHA;
- atomic-replace/post-write verification;
- live-REAPER override state.

The receipt is the authority for a later rollback transaction.

## Receipt-driven rollback

Use:

```bash
bin/reaperctl rollback \
  --receipt /mnt/data/ubuntu-desktop-workspace/evidence/mutations/mutation-<timestamp>-<operation>.json \
  --json
```

Rollback is fail-closed. It requires:

1. the receipt is a regular non-symlink file inside the mutation-evidence root;
2. receipt schema and SHA fields are valid;
3. receipt mutability-policy SHA equals the active policy SHA;
4. receipt project equals the current canonical project;
5. rollback artifact is a regular confined file;
6. rollback artifact SHA equals both the receipt `rollback_sha256` and `before_sha256`;
7. canonical project still equals receipt `after_sha256`;
8. REAPER is stopped unless `--live` is explicitly supplied;
9. current mutated bytes are preserved as a pre-rollback artifact;
10. restoration uses atomic replacement and post-write SHA verification;
11. a rollback receipt is written.

There is deliberately **no force option**. If the canonical project has changed since the mutation receipt was created, rollback refuses instead of overwriting later work.

A successfully consumed mutation receipt therefore cannot be replayed immediately: after restoration, the canonical project equals `before_sha256`, not the receipt's required `after_sha256`.

## Live proof

Live secure mutation proof:

```text
evidence/LIVE-MUTATION-REHEARSAL-2026-09-08.md
```

Live receipt-driven rollback proof:

```text
evidence/LIVE-ROLLBACK-REHEARSAL-2026-09-08.md
```

The rollback rehearsal proved:

```text
mutated project:
2bd9e8e26cd55f1775c8101c1f6ac4c547e9d5bddf9a6d3c1c53d928e622a561

restored project:
2ea85263d6dc125bf7739264956a1ee1a8074c2b42f69b606b5e9d8b7e9771f1

REAPER runtime:
cee99a74fdd9fc87974c96ea334a50afff4ca8d3121591aed218057bb38185e4
```

The final restored system remapped the legitimate REAPER 7.79 `EVALUATION LICENSE` window and retained all locked ALSA / `apollo_spdif` settings.

## Production transaction rule

For ordinary mutable production work:

```text
verify baseline + mutability policy
-> stop REAPER
-> mutate
-> retain mutation receipt
-> boot/verify the changed project
-> continue if approved
OR
-> stop REAPER
-> rollback using that exact receipt
-> boot/verify the restored project
```

A rollback receipt and pre-rollback artifact preserve evidence of the reversed state. Neither mutation nor rollback changes the admitted Golden Master identity.
