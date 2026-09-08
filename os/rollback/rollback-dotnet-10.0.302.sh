#!/bin/bash
set -euo pipefail
TARGET=/opt/dotnet-10.0.302
WRAP=/usr/local/bin/dotnet
PROFILE=/etc/profile.d/dotnet-10.0.302.sh
EXPECTED_TREE=d0ba66b5979730d309518648260fb962c16d08db1ad7285ca1197f4562bcffc3
EXPECTED_WRAP=6a034df91a4a8ccd3791879f796bc804cbc04345633c2ab1bcaa335719a1f793
EXPECTED_PROFILE=a3722a299d8c0fc7b456964c16d589a95352f93a7f30dce55d7b0bd8ed92c36e
[ -d "$TARGET" ] || { echo 'rollback: target missing' >&2; exit 3; }
[ -f "$WRAP" ] && [ ! -L "$WRAP" ] || { echo 'rollback: launcher missing/symlink' >&2; exit 3; }
[ -f "$PROFILE" ] && [ ! -L "$PROFILE" ] || { echo 'rollback: profile missing/symlink' >&2; exit 3; }
ACTUAL_WRAP=$(sha256sum "$WRAP" | awk '{print $1}')
ACTUAL_PROFILE=$(sha256sum "$PROFILE" | awk '{print $1}')
[ "$ACTUAL_WRAP" = "$EXPECTED_WRAP" ] || { echo 'rollback: launcher drift' >&2; exit 4; }
[ "$ACTUAL_PROFILE" = "$EXPECTED_PROFILE" ] || { echo 'rollback: profile drift' >&2; exit 4; }
ACTUAL_TREE=$(python3 - "$TARGET" <<'PY'
from pathlib import Path
import hashlib, stat, sys
root=Path(sys.argv[1]); h=hashlib.sha256()
for p in sorted(x for x in root.rglob('*') if x.is_file()):
    d=hashlib.sha256(p.read_bytes()).hexdigest(); rel=p.relative_to(root).as_posix(); mode=stat.S_IMODE(p.stat().st_mode)
    h.update(f'{rel}\t{mode:04o}\t{p.stat().st_size}\t{d}\n'.encode())
print(h.hexdigest())
PY
)
[ "$ACTUAL_TREE" = "$EXPECTED_TREE" ] || { echo "rollback: toolchain tree drift $ACTUAL_TREE" >&2; exit 4; }
rm -rf --one-file-system "$TARGET"
rm -f "$WRAP" "$PROFILE"
echo 'rollback: PASS'
