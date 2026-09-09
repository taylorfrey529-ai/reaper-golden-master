#!/bin/bash
set -euo pipefail
PKG=reaper-workspace-status
VER=1.0.0-1
SRC=/etc/apt/sources.list.d/reaper-debian-repo.sources
KEY=/etc/apt/keyrings/reaper-debian-repo.gpg
REPO=/mnt/data/reaper-apt-repository
FPR=EAE567EB437C007F46A58BDCA76356FF985B3F3B
KEY_SHA=7dc135b64febe59163cd293718cb02e2a2b3ad9ffe7ec01ecf9d9c93ec10e077
SRC_SHA=1701fdeb0a0d68cc3f8da5b1a6058e4dc985e1f683101e9fba884bafb7aee9d2
PAYLOAD_SHA=765bac01283962461cded9984a1bb3147df908a6e1d3302579e003153af791ed
[ -f "$SRC" ] && [ ! -L "$SRC" ] || { echo 'rollback-package: source missing or symlink' >&2; exit 2; }
[ -f "$KEY" ] && [ ! -L "$KEY" ] || { echo 'rollback-package: key missing or symlink' >&2; exit 2; }
[ "$(sha256sum "$KEY" | awk '{print $1}')" = "$KEY_SHA" ] || { echo 'rollback-package: key hash drift' >&2; exit 3; }
[ "$(sha256sum "$SRC" | awk '{print $1}')" = "$SRC_SHA" ] || { echo 'rollback-package: source config drift' >&2; exit 3; }
actual_fpr=$(gpg --batch --show-keys --with-colons "$KEY" 2>/dev/null | awk -F: '$1=="fpr"{print $10; exit}')
[ "$actual_fpr" = "$FPR" ] || { echo 'rollback-package: signing fingerprint drift' >&2; exit 3; }
state=$(dpkg-query -W -f='${Status}\t${Version}\t${Architecture}' "$PKG" 2>/dev/null || true)
[ "$state" = $'install ok installed\t1.0.0-1\tall' ] || { echo "rollback-package: package state drift: $state" >&2; exit 3; }
[ -f /usr/bin/reaper-workspace-status ] && [ ! -L /usr/bin/reaper-workspace-status ] || { echo 'rollback-package: installed payload missing or symlink' >&2; exit 3; }
[ "$(sha256sum /usr/bin/reaper-workspace-status | awk '{print $1}')" = "$PAYLOAD_SHA" ] || { echo 'rollback-package: installed payload drift' >&2; exit 3; }
DEBIAN_FRONTEND=noninteractive apt-get -y -o Dir::Etc::sourcelist="$SRC" -o Dir::Etc::sourceparts='-' -o Acquire::Retries=0 -o Dpkg::Use-Pty=0 purge "$PKG" >/dev/null
if dpkg-query -W -f='${Status}' "$PKG" 2>/dev/null | grep -q 'install ok installed'; then
  echo 'rollback-package: package still installed' >&2
  exit 6
fi
[ ! -e /usr/bin/reaper-workspace-status ] && [ ! -L /usr/bin/reaper-workspace-status ] || { echo 'rollback-package: /usr/bin payload remains' >&2; exit 6; }
echo "rollback-package: PASS restored=package-absent trust-root-preserved"
