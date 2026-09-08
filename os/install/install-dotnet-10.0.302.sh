#!/bin/bash
set -euo pipefail
ARCHIVE=${1:-/mnt/data/toolchains.zip}
EXPECTED_ARCHIVE=568650bc01243a4eee7abaa6512ef4ae58e34e1a11c0178b7f76acbe57fec711
EXPECTED_TREE=d0ba66b5979730d309518648260fb962c16d08db1ad7285ca1197f4562bcffc3
EXPECTED_FILES=4911
EXPECTED_BYTES=628335803
EXPECTED_DOTNET=55117d7d1f27537ee6e7a81b8b9f84f0b50c8cbd2d1d1e21684c31db1518230a
EXPECTED_WRAP=6a034df91a4a8ccd3791879f796bc804cbc04345633c2ab1bcaa335719a1f793
EXPECTED_PROFILE=a3722a299d8c0fc7b456964c16d589a95352f93a7f30dce55d7b0bd8ed92c36e
PREFIX=toolchains/dotnet/10.0.302/linux-x64/dotnet-sdk-10.0.302-linux-x64/
TARGET=/opt/dotnet-10.0.302
WRAP=/usr/local/bin/dotnet
PROFILE=/etc/profile.d/dotnet-10.0.302.sh

[ -f "$ARCHIVE" ] && [ ! -L "$ARCHIVE" ] || { echo 'install: archive missing or symlink' >&2; exit 2; }
ACTUAL_ARCHIVE=$(sha256sum "$ARCHIVE" | awk '{print $1}')
[ "$ACTUAL_ARCHIVE" = "$EXPECTED_ARCHIVE" ] || { echo "install: archive SHA mismatch $ACTUAL_ARCHIVE" >&2; exit 3; }
for p in "$TARGET" "$WRAP" "$PROFILE"; do [ ! -e "$p" ] || { echo "install: target already exists: $p" >&2; exit 4; }; done

python3 - "$ARCHIVE" "$PREFIX" "$EXPECTED_FILES" "$EXPECTED_BYTES" <<'PY'
from pathlib import PurePosixPath
import stat, sys, zipfile
archive,prefix,expected_files,expected_bytes=sys.argv[1],sys.argv[2],int(sys.argv[3]),int(sys.argv[4])
files=0; total=0
with zipfile.ZipFile(archive) as z:
    for info in z.infolist():
        if not info.filename.startswith(prefix):
            continue
        rel=info.filename[len(prefix):]
        if not rel:
            continue
        p=PurePosixPath(rel)
        if p.is_absolute() or '..' in p.parts:
            raise SystemExit('install: unsafe ZIP path')
        mode=(info.external_attr >> 16) & 0xFFFF
        if stat.S_ISLNK(mode):
            raise SystemExit('install: ZIP symlink rejected')
        if not info.is_dir():
            files += 1; total += info.file_size
if files != expected_files or total != expected_bytes:
    raise SystemExit(f'install: ZIP subtree inventory mismatch files={files} bytes={total}')
PY
unzip -t "$ARCHIVE" >/dev/null

TMP=$(mktemp -d /opt/.dotnet-10.0.302.extract.XXXXXX)
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT
cd "$TMP"
unzip -q "$ARCHIVE" "${PREFIX}*"
SRC="$TMP/$PREFIX"
[ -d "$SRC" ] || { echo 'install: extracted SDK subtree missing' >&2; exit 5; }
ACTUAL_TREE=$(python3 - "$SRC" <<'PY'
from pathlib import Path
import hashlib, stat, sys
root=Path(sys.argv[1]); h=hashlib.sha256()
for p in sorted(x for x in root.rglob('*') if x.is_file()):
    d=hashlib.sha256(p.read_bytes()).hexdigest(); rel=p.relative_to(root).as_posix(); mode=stat.S_IMODE(p.stat().st_mode)
    h.update(f'{rel}\t{mode:04o}\t{p.stat().st_size}\t{d}\n'.encode())
print(h.hexdigest())
PY
)
[ "$ACTUAL_TREE" = "$EXPECTED_TREE" ] || { echo "install: extracted tree mismatch $ACTUAL_TREE" >&2; exit 6; }
[ "$(sha256sum "$SRC/dotnet" | awk '{print $1}')" = "$EXPECTED_DOTNET" ] || { echo 'install: dotnet host mismatch' >&2; exit 6; }

mv "$SRC" "$TARGET"
install -d -m 0755 /usr/local/bin
cat > /usr/local/bin/.dotnet.install.$$ <<'SH'
#!/bin/sh
export DOTNET_ROOT=/opt/dotnet-10.0.302
exec /opt/dotnet-10.0.302/dotnet "$@"
SH
chmod 0755 /usr/local/bin/.dotnet.install.$$
mv /usr/local/bin/.dotnet.install.$$ "$WRAP"
cat > /etc/profile.d/.dotnet-10.0.302.install.$$ <<'SH'
export DOTNET_ROOT=/opt/dotnet-10.0.302
case ":$PATH:" in
  *:/opt/dotnet-10.0.302:*) ;;
  *) export PATH="/opt/dotnet-10.0.302:$PATH" ;;
esac
SH
chmod 0644 /etc/profile.d/.dotnet-10.0.302.install.$$
mv /etc/profile.d/.dotnet-10.0.302.install.$$ "$PROFILE"

[ "$(sha256sum "$WRAP" | awk '{print $1}')" = "$EXPECTED_WRAP" ] || { echo 'install: launcher hash mismatch' >&2; exit 7; }
[ "$(sha256sum "$PROFILE" | awk '{print $1}')" = "$EXPECTED_PROFILE" ] || { echo 'install: profile hash mismatch' >&2; exit 7; }
V=$(DOTNET_CLI_HOME="$TMP/home" DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1 DOTNET_NOLOGO=1 DOTNET_CLI_TELEMETRY_OPTOUT=1 "$WRAP" --version)
[ "$V" = '10.0.302' ] || { echo "install: unexpected SDK version $V" >&2; exit 8; }
echo "install: PASS dotnet=$V archive=$ACTUAL_ARCHIVE tree=$ACTUAL_TREE"
