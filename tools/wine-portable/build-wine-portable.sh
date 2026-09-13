#!/usr/bin/env bash
set -euo pipefail

readonly WINE_VERSION="11.17"
readonly UPSTREAM_NAME="wine-${WINE_VERSION}-amd64-wow64.tar.xz"
readonly UPSTREAM_SHA256="3211db09086bc6fbd769c0286f27790b32d6fc6fb0bc610dad6b59796f07d462"
readonly UPSTREAM_URL="https://github.com/Kron4ek/Wine-Builds/releases/download/${WINE_VERSION}/${UPSTREAM_NAME}"
readonly PACKAGE_NAME="wine-${WINE_VERSION}-amd64-wow64-reaper-portable"
readonly SOURCE_DATE_EPOCH="1789257600"

workspace="${1:-${RUNNER_TEMP:-/tmp}/wine-portable-build}"
output="${2:-$PWD/dist}"
download_dir="$workspace/download"
extract_dir="$workspace/extract"
stage_parent="$workspace/stage"
stage="$stage_parent/$PACKAGE_NAME"

mkdir -p "$download_dir" "$extract_dir" "$stage/runtime" "$stage/bin" "$stage/docs" "$output"

curl --fail --location --retry 5 --retry-all-errors \
  --output "$download_dir/$UPSTREAM_NAME" "$UPSTREAM_URL"
printf '%s  %s\n' "$UPSTREAM_SHA256" "$download_dir/$UPSTREAM_NAME" | sha256sum --check --strict

tar -xJf "$download_dir/$UPSTREAM_NAME" -C "$extract_dir"
mapfile -t roots < <(find "$extract_dir" -mindepth 1 -maxdepth 1 -type d -print)
if [ "${#roots[@]}" -eq 1 ]; then
  runtime_root="${roots[0]}"
else
  runtime_root="$extract_dir"
fi
cp -a "$runtime_root"/. "$stage/runtime/"

cat > "$stage/bin/wine-portable" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)"
export PATH="$root/runtime/bin:$PATH"
if [ -z "${WINEPREFIX:-}" ]; then
  data_root="${XDG_DATA_HOME:-${HOME:?HOME is required}/.local/share}"
  export WINEPREFIX="$data_root/wine-prefixes/wine-11.17-wow64"
fi
mkdir -p "$WINEPREFIX"
exec "$root/runtime/bin/wine" "$@"
SH

cat > "$stage/bin/wineserver-portable" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)"
exec "$root/runtime/bin/wineserver" "$@"
SH

cat > "$stage/bin/install-wow-3980" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)"
media="${1:-/mnt/data/WoW-1.0.0.3980-enUS-media}"
installer="$media/Installer.exe"
export DISPLAY="${DISPLAY:-:88}"
export WINEPREFIX="${WINEPREFIX:-/mnt/data/wow-3980-prefix}"
export WINEDLLOVERRIDES="${WINEDLLOVERRIDES:-mscoree,mshtml=}"
if [ ! -f "$installer" ]; then
  printf 'Installer not found: %s\n' "$installer" >&2
  exit 66
fi
case "$WINEPREFIX" in
  /mnt/data/ubuntu-desktop-workspace/config/*)
    printf 'Refusing Wine prefix inside REAPER configuration: %s\n' "$WINEPREFIX" >&2
    exit 73
    ;;
esac
mkdir -p "$WINEPREFIX"
exec "$root/bin/wine-portable" "$installer"
SH

cat > "$stage/bin/verify-portable" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)"
runtime="$root/runtime"
[ "$(uname -m)" = "x86_64" ]
[ -x "$runtime/bin/wine" ]
[ -x "$runtime/bin/wineserver" ]
version="$($runtime/bin/wine --version)"
case "$version" in wine-11.17*) ;; *) printf 'Unexpected Wine version: %s\n' "$version" >&2; exit 1;; esac
find "$runtime" -type f -path '*/i386-windows/ntdll.dll' -print -quit | grep -q .
find "$runtime" -type f -path '*/x86_64-windows/ntdll.dll' -print -quit | grep -q .
if ldd "$runtime/bin/wine" 2>/dev/null | grep -q 'not found'; then
  ldd "$runtime/bin/wine" >&2
  exit 1
fi
printf 'PASS version=%s architecture=x86_64 wow64=i386+x86_64\n' "$version"
SH

chmod 0755 "$stage/bin/wine-portable" "$stage/bin/wineserver-portable" \
  "$stage/bin/install-wow-3980" "$stage/bin/verify-portable"

cat > "$stage/README.md" <<EOF
# Wine ${WINE_VERSION} WoW64 — REAPER workstation portable runtime

This package contains the non-staging Linux x86_64 WoW64 build from Kron4ek/Wine-Builds,
verified against the upstream SHA-256 digest and wrapped for an isolated World of Warcraft
1.0.0.3980 prefix. It does not modify REAPER projects or REAPER configuration.

## Verify

\`./bin/verify-portable\`

## Install World of Warcraft 1.0.0.3980

\`DISPLAY=:88 WINEPREFIX=/mnt/data/wow-3980-prefix ./bin/install-wow-3980 /mnt/data/WoW-1.0.0.3980-enUS-media\`

The prefix is deliberately separate from \`/mnt/data/ubuntu-desktop-workspace/config/REAPER\`.
The bundled legacy DirectX installer should not be installed globally.
EOF

cat > "$stage/docs/PROVENANCE.json" <<EOF
{
  "package": "$PACKAGE_NAME",
  "wine_version": "$WINE_VERSION",
  "architecture": "linux-x86_64",
  "wow64": true,
  "upstream_repository": "Kron4ek/Wine-Builds",
  "upstream_asset": "$UPSTREAM_NAME",
  "upstream_sha256": "$UPSTREAM_SHA256",
  "upstream_url": "$UPSTREAM_URL",
  "source_date_epoch": $SOURCE_DATE_EPOCH,
  "workflow_commit": "${GITHUB_SHA:-local}"
}
EOF

printf '%s  %s\n' "$UPSTREAM_SHA256" "$UPSTREAM_NAME" > "$stage/docs/UPSTREAM_SHA256SUMS"
(
  cd "$stage"
  find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
)

"$stage/bin/verify-portable"

archive="$output/$PACKAGE_NAME.tar.xz"
tar --sort=name --mtime="@$SOURCE_DATE_EPOCH" --owner=0 --group=0 --numeric-owner \
  -C "$stage_parent" -cJf "$archive" "$PACKAGE_NAME"
(cd "$output" && sha256sum "$(basename "$archive")" > "$(basename "$archive").sha256")
printf 'artifact=%s\n' "$archive"

