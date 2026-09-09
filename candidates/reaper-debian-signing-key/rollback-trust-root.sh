#!/bin/bash
set -euo pipefail
ROOT_PREFIX=${ROOT_PREFIX:-}
REPO_ROOT=${REPO_ROOT:-/mnt/data/reaper-apt-repository}
KEY_SHA=7dc135b64febe59163cd293718cb02e2a2b3ad9ffe7ec01ecf9d9c93ec10e077
KEY_DST="$ROOT_PREFIX/etc/apt/keyrings/reaper-debian-repo.gpg"
SOURCE_DST="$ROOT_PREFIX/etc/apt/sources.list.d/reaper-debian-repo.sources"
[ -f "$KEY_DST" ] && [ ! -L "$KEY_DST" ] || { echo 'candidate-rollback: key target missing or symlink' >&2; exit 2; }
[ -f "$SOURCE_DST" ] && [ ! -L "$SOURCE_DST" ] || { echo 'candidate-rollback: source target missing or symlink' >&2; exit 2; }
[ "$(sha256sum "$KEY_DST" | awk '{print $1}')" = "$KEY_SHA" ] || { echo 'candidate-rollback: key drift; refusing removal' >&2; exit 3; }
expected=$(mktemp)
trap 'rm -f "$expected"' EXIT
cat > "$expected" <<EOT
Types: deb
URIs: file:$REPO_ROOT
Suites: trixie
Components: main
Architectures: amd64
Signed-By: /etc/apt/keyrings/reaper-debian-repo.gpg
EOT
cmp -s "$expected" "$SOURCE_DST" || { echo 'candidate-rollback: source drift; refusing removal' >&2; exit 3; }
rm -f "$SOURCE_DST"
rm -f "$KEY_DST"
echo "candidate-rollback: PASS restored=absent"
