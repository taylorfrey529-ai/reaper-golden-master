#!/bin/bash
set -euo pipefail
ROOT_PREFIX=${ROOT_PREFIX:-}
REPO_ROOT=${REPO_ROOT:-/mnt/data/reaper-apt-repository}
FPR=EAE567EB437C007F46A58BDCA76356FF985B3F3B
KEY_SHA=7dc135b64febe59163cd293718cb02e2a2b3ad9ffe7ec01ecf9d9c93ec10e077
MANIFEST_SHA=51be57e06807e179f13da827fd0ca91041d384960866f6180682ff51faf19d56
KEY_SRC="$REPO_ROOT/keys/reaper-debian-repo.gpg"
MANIFEST="$REPO_ROOT/SNAPSHOT.sha256"
MANIFEST_SIG="$REPO_ROOT/SNAPSHOT.sha256.asc"
INRELEASE="$REPO_ROOT/dists/trixie/InRelease"
KEY_DST="$ROOT_PREFIX/etc/apt/keyrings/reaper-debian-repo.gpg"
SOURCE_DST="$ROOT_PREFIX/etc/apt/sources.list.d/reaper-debian-repo.sources"
for f in "$KEY_SRC" "$MANIFEST" "$MANIFEST_SIG" "$INRELEASE"; do
  [ -f "$f" ] && [ ! -L "$f" ] || { echo "candidate-install: missing or symlink: $f" >&2; exit 2; }
done
[ "$(sha256sum "$KEY_SRC" | awk '{print $1}')" = "$KEY_SHA" ] || { echo 'candidate-install: public key hash mismatch' >&2; exit 3; }
[ "$(sha256sum "$MANIFEST" | awk '{print $1}')" = "$MANIFEST_SHA" ] || { echo 'candidate-install: snapshot manifest hash mismatch' >&2; exit 3; }
ACTUAL_FPR=$(gpg --batch --show-keys --with-colons "$KEY_SRC" 2>/dev/null | awk -F: '$1=="fpr"{print $10; exit}')
[ "$ACTUAL_FPR" = "$FPR" ] || { echo "candidate-install: fingerprint mismatch: $ACTUAL_FPR" >&2; exit 3; }
gpgv --keyring "$KEY_SRC" "$MANIFEST_SIG" "$MANIFEST" >/dev/null 2>&1 || { echo 'candidate-install: snapshot signature invalid' >&2; exit 4; }
gpgv --keyring "$KEY_SRC" "$INRELEASE" >/dev/null 2>&1 || { echo 'candidate-install: InRelease signature invalid' >&2; exit 4; }
( cd "$REPO_ROOT"; sha256sum -c SNAPSHOT.sha256 >/dev/null ) || { echo 'candidate-install: snapshot member verification failed' >&2; exit 4; }
[ ! -e "$KEY_DST" ] && [ ! -L "$KEY_DST" ] || { echo "candidate-install: target already exists: $KEY_DST" >&2; exit 5; }
[ ! -e "$SOURCE_DST" ] && [ ! -L "$SOURCE_DST" ] || { echo "candidate-install: target already exists: $SOURCE_DST" >&2; exit 5; }
install -d -m 0755 "$(dirname "$KEY_DST")" "$(dirname "$SOURCE_DST")"
ktmp="$(dirname "$KEY_DST")/.reaper-debian-repo.gpg.$$"
stmp="$(dirname "$SOURCE_DST")/.reaper-debian-repo.sources.$$"
trap 'rm -f "$ktmp" "$stmp"' EXIT
install -m 0644 "$KEY_SRC" "$ktmp"
cat > "$stmp" <<EOT
Types: deb
URIs: file:$REPO_ROOT
Suites: trixie
Components: main
Architectures: amd64
Signed-By: /etc/apt/keyrings/reaper-debian-repo.gpg
EOT
chmod 0644 "$stmp"
mv "$ktmp" "$KEY_DST"
mv "$stmp" "$SOURCE_DST"
trap - EXIT
[ "$(sha256sum "$KEY_DST" | awk '{print $1}')" = "$KEY_SHA" ] || { echo 'candidate-install: installed key hash mismatch' >&2; exit 6; }
echo "candidate-install: PASS fingerprint=$FPR key=$KEY_DST source=$SOURCE_DST repo=$REPO_ROOT"
