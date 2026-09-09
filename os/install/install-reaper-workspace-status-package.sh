#!/bin/bash
set -euo pipefail
PKG=reaper-workspace-status
VER=1.0.0-1
SRC=/etc/apt/sources.list.d/reaper-debian-repo.sources
KEY=/etc/apt/keyrings/reaper-debian-repo.gpg
REPO=/mnt/data/reaper-apt-repository
DEB="$REPO/pool/main/r/reaper-workspace-status/reaper-workspace-status_1.0.0-1_all.deb"
FPR=EAE567EB437C007F46A58BDCA76356FF985B3F3B
KEY_SHA=7dc135b64febe59163cd293718cb02e2a2b3ad9ffe7ec01ecf9d9c93ec10e077
SRC_SHA=1701fdeb0a0d68cc3f8da5b1a6058e4dc985e1f683101e9fba884bafb7aee9d2
MANIFEST_SHA=51be57e06807e179f13da827fd0ca91041d384960866f6180682ff51faf19d56
DEB_SHA=a2f5fa8679720368b30377d10a541f8dd95cddfa9d8e5b39e6b433f0e346fe8b
PAYLOAD_SHA=765bac01283962461cded9984a1bb3147df908a6e1d3302579e003153af791ed
for p in "$SRC" "$KEY" "$REPO/SNAPSHOT.sha256" "$REPO/SNAPSHOT.sha256.asc" "$REPO/dists/trixie/InRelease" "$DEB"; do
  [ -f "$p" ] && [ ! -L "$p" ] || { echo "install-package: missing or symlink: $p" >&2; exit 2; }
done
[ "$(sha256sum "$KEY" | awk '{print $1}')" = "$KEY_SHA" ] || { echo 'install-package: key hash drift' >&2; exit 3; }
[ "$(sha256sum "$SRC" | awk '{print $1}')" = "$SRC_SHA" ] || { echo 'install-package: source config drift' >&2; exit 3; }
[ "$(sha256sum "$REPO/SNAPSHOT.sha256" | awk '{print $1}')" = "$MANIFEST_SHA" ] || { echo 'install-package: snapshot manifest drift' >&2; exit 3; }
[ "$(sha256sum "$DEB" | awk '{print $1}')" = "$DEB_SHA" ] || { echo 'install-package: deb drift' >&2; exit 3; }
actual_fpr=$(gpg --batch --show-keys --with-colons "$KEY" 2>/dev/null | awk -F: '$1=="fpr"{print $10; exit}')
[ "$actual_fpr" = "$FPR" ] || { echo 'install-package: signing fingerprint drift' >&2; exit 3; }
gpgv --keyring "$KEY" "$REPO/SNAPSHOT.sha256.asc" "$REPO/SNAPSHOT.sha256" >/dev/null 2>&1 || { echo 'install-package: snapshot signature invalid' >&2; exit 4; }
gpgv --keyring "$KEY" "$REPO/dists/trixie/InRelease" >/dev/null 2>&1 || { echo 'install-package: InRelease signature invalid' >&2; exit 4; }
( cd "$REPO" && sha256sum -c SNAPSHOT.sha256 >/dev/null ) || { echo 'install-package: snapshot member verification failed' >&2; exit 4; }
if dpkg-query -W -f='${Status}' "$PKG" 2>/dev/null | grep -q 'install ok installed'; then
  echo 'install-package: package already installed' >&2
  exit 5
fi
[ ! -e /usr/bin/reaper-workspace-status ] && [ ! -L /usr/bin/reaper-workspace-status ] || { echo 'install-package: /usr/bin target already exists' >&2; exit 5; }
apt-get -o Dir::Etc::sourcelist="$SRC" -o Dir::Etc::sourceparts='-' -o APT::Get::List-Cleanup=0 -o Acquire::Retries=0 -o Dpkg::Use-Pty=0 update >/dev/null
DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends -o Dir::Etc::sourcelist="$SRC" -o Dir::Etc::sourceparts='-' -o Acquire::Retries=0 -o Dpkg::Use-Pty=0 install "$PKG=$VER" >/dev/null
state=$(dpkg-query -W -f='${Status}\t${Version}\t${Architecture}' "$PKG")
[ "$state" = $'install ok installed\t1.0.0-1\tall' ] || { echo "install-package: installed metadata drift: $state" >&2; exit 6; }
[ "$(sha256sum /usr/bin/reaper-workspace-status | awk '{print $1}')" = "$PAYLOAD_SHA" ] || { echo 'install-package: installed payload drift' >&2; exit 6; }
echo "install-package: PASS package=$PKG version=$VER fingerprint=$FPR"
