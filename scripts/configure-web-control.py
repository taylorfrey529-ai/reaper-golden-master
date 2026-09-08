#!/usr/bin/env python3
"""Safely admit one REAPER Web browser control surface into reaper.ini."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_PORT = 2307
DEFAULT_INTERFACE = "index.html"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_csurfs(lines: list[str], start: int, end: int) -> tuple[int | None, int, list[tuple[int, str]]]:
    cnt_i: int | None = None
    cnt = 0
    surfaces: list[tuple[int, str]] = []
    for i in range(start, end):
        m = re.match(r"^csurf_cnt=(\d+)$", lines[i])
        if m:
            cnt_i = i
            cnt = int(m.group(1))
        m = re.match(r"^csurf_(\d+)=(.*)$", lines[i])
        if m:
            surfaces.append((int(m.group(1)), m.group(2)))
    if surfaces:
        cnt = max(cnt, max(index for index, _ in surfaces) + 1)
    return cnt_i, cnt, surfaces


def plan(text: str, port: int, interface: str) -> dict[str, object]:
    lines = text.splitlines()
    try:
        section_i = lines.index("[reaper]")
    except ValueError as exc:
        raise ValueError("[reaper] section missing") from exc
    end = len(lines)
    for i in range(section_i + 1, len(lines)):
        if lines[i].startswith("[") and lines[i].endswith("]"):
            end = i
            break

    cnt_i, count, surfaces = parse_csurfs(lines, section_i + 1, end)
    http_surfaces = [(index, value) for index, value in surfaces if value.startswith("HTTP ")]
    requested = f"HTTP 0 {port} '' '{interface}' 0 ''"
    exact = [(index, value) for index, value in http_surfaces if value == requested]
    if exact:
        return {
            "changed": False,
            "existing_index": exact[0][0],
            "line": f"csurf_{exact[0][0]}={requested}",
            "text": text if text.endswith("\n") else text + "\n",
        }
    if http_surfaces:
        rendered = ", ".join(f"csurf_{index}={value}" for index, value in http_surfaces)
        raise ValueError(f"existing HTTP control surface differs from requested configuration: {rendered}")

    new_index = count
    new_line = f"csurf_{new_index}={requested}"
    insert_at = section_i + 1
    lines.insert(insert_at, new_line)
    if cnt_i is None:
        lines.insert(insert_at, f"csurf_cnt={new_index + 1}")
    else:
        for i, line in enumerate(lines):
            if re.match(r"^csurf_cnt=\d+$", line):
                lines[i] = f"csurf_cnt={new_index + 1}"
                break
    return {
        "changed": True,
        "existing_index": None,
        "line": new_line,
        "text": "\n".join(lines) + "\n",
    }


def reaper_is_running(reaper_binary: Path) -> bool:
    if not reaper_binary.is_file():
        return False
    try:
        result = subprocess.run(
            ["pgrep", "-f", f"^{re.escape(str(reaper_binary))} "],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return False
    return result.returncode == 0


def configure(
    ini: Path,
    backup_dir: Path,
    port: int,
    interface: str,
    apply: bool,
    reaper_binary: Path | None = None,
) -> dict[str, object]:
    if not ini.is_file():
        raise ValueError(f"reaper.ini not found: {ini}")
    before_hash = sha256(ini)
    original = ini.read_text(encoding="utf-8", errors="strict")
    result = plan(original, port, interface)
    output: dict[str, object] = {
        "ini": str(ini),
        "port": port,
        "interface": interface,
        "changed": result["changed"],
        "line": result["line"],
        "before_sha256": before_hash,
        "applied": False,
        "backup": None,
        "after_sha256": before_hash,
        "restart_required": bool(result["changed"]),
    }
    if not result["changed"] or not apply:
        return output
    if reaper_binary is not None and reaper_is_running(reaper_binary):
        raise ValueError(f"REAPER is running; stop it before applying reaper.ini changes: {reaper_binary}")

    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = backup_dir / f"reaper.ini.before-web-{stamp}"
    counter = 1
    while backup.exists():
        backup = backup_dir / f"reaper.ini.before-web-{stamp}.{counter}"
        counter += 1
    shutil.copy2(ini, backup)
    ini.write_text(str(result["text"]), encoding="utf-8")
    output["applied"] = True
    output["backup"] = str(backup)
    output["after_sha256"] = sha256(ini)
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ini", type=Path, required=True, help="Path to active REAPER reaper.ini")
    parser.add_argument("--backup-dir", type=Path, required=True, help="Directory for pre-change backup")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--interface", default=DEFAULT_INTERFACE)
    parser.add_argument("--reaper-binary", type=Path, help="When applying, refuse if this REAPER binary is currently running")
    parser.add_argument("--apply", action="store_true", help="Write the admitted configuration; default is plan/check only")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not 1 <= args.port <= 65535:
        print("configure-web-control: port must be 1..65535", file=sys.stderr)
        return 2
    if not re.fullmatch(r"[A-Za-z0-9_.-]+\.html", args.interface):
        print("configure-web-control: interface must be a simple .html basename", file=sys.stderr)
        return 2
    try:
        result = configure(args.ini, args.backup_dir, args.port, args.interface, args.apply, args.reaper_binary)
    except ValueError as exc:
        print(f"configure-web-control: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
