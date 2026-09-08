#!/usr/bin/env python3
"""Verified 48 kHz stereo PCM render command for the Reaper Golden Master continuation."""

from __future__ import annotations

import argparse
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import wave
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORE_PATH = ROOT / "bin" / "reaperctl-core"
DEFAULT_BASELINE = ROOT / "BASELINE.json"
RENDER_SAMPLE_RATE = 48000
RENDER_CHANNELS = 2
RENDER_SAMPLE_WIDTH = 3


def _load_core():
    loader = importlib.machinery.SourceFileLoader("reaperctl_render_core", str(CORE_PATH))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError(f"cannot load {CORE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


core = _load_core()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def patch_render_project(text: str, target: Path) -> str:
    if target.suffix.lower() != ".wav":
        raise ValueError("initial render contract supports .wav output only")
    escaped_target = str(target.resolve()).replace("\\", "/").replace('"', '\\"')

    def replace_one(pattern: str, replacement: str, source: str) -> str:
        updated, count = re.subn(pattern, replacement, source, count=1, flags=re.MULTILINE)
        if count != 1:
            raise ValueError(f"project render field missing or ambiguous: {pattern}")
        return updated

    patched = text
    patched = replace_one(r'^  RENDER_FILE .*$', f'  RENDER_FILE "{escaped_target}"', patched)
    patched = replace_one(r'^  RENDER_PATTERN .*$', '  RENDER_PATTERN ""', patched)
    patched = replace_one(
        r'^  RENDER_FMT .*$',
        f'  RENDER_FMT 0 {RENDER_CHANNELS} {RENDER_SAMPLE_RATE}',
        patched,
    )
    match = re.search(r'^  RENDER_RANGE (\d+)(.*)$', patched, flags=re.MULTILINE)
    if match is None:
        raise ValueError("project render range field missing")
    patched = patched[:match.start()] + f'  RENDER_RANGE 1{match.group(2)}' + patched[match.end():]
    return patched


def verify_rendered_wave(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"render output missing: {path}")
    size = path.stat().st_size
    if size <= 44:
        raise RuntimeError(f"render output is empty or truncated: {path}")
    try:
        with wave.open(str(path), "rb") as handle:
            channels = handle.getnchannels()
            sample_rate = handle.getframerate()
            sample_width = handle.getsampwidth()
            frames = handle.getnframes()
            compression = handle.getcomptype()
            non_silent = False
            while True:
                raw = handle.readframes(65536)
                if not raw:
                    break
                if any(raw):
                    non_silent = True
                    break
    except (wave.Error, EOFError) as exc:
        raise RuntimeError(f"render output is not a readable PCM WAVE file: {exc}") from exc

    if channels != RENDER_CHANNELS:
        raise RuntimeError(f"render channel regression: {channels}, expected {RENDER_CHANNELS}")
    if sample_rate != RENDER_SAMPLE_RATE:
        raise RuntimeError(f"render sample-rate regression: {sample_rate}, expected {RENDER_SAMPLE_RATE}")
    if sample_width != RENDER_SAMPLE_WIDTH:
        raise RuntimeError(f"render sample-width regression: {sample_width}, expected {RENDER_SAMPLE_WIDTH}")
    if compression != "NONE":
        raise RuntimeError(f"render compression regression: {compression}")
    if frames <= 0:
        raise RuntimeError("render contains no audio frames")
    if not non_silent:
        raise RuntimeError("render contains only digital silence")

    return {
        "path": str(path),
        "size_bytes": size,
        "sha256": file_sha256(path),
        "channels": channels,
        "sample_rate_hz": sample_rate,
        "sample_width_bytes": sample_width,
        "frames": frames,
        "duration_seconds": frames / sample_rate,
        "non_silent": non_silent,
    }


def render_project(data: dict[str, Any], output: Path, *, overwrite: bool, timeout: float) -> dict[str, Any]:
    paths = core.workspace_paths(data)
    project: Path = paths["project"]
    reaper: Path = paths["reaper"]
    if not project.is_file():
        raise ValueError(f"canonical project missing: {project}")
    if not reaper.is_file():
        raise ValueError(f"REAPER binary missing: {reaper}")

    output = output.expanduser().resolve()
    if output.suffix.lower() != ".wav":
        raise ValueError("render output must use .wav")
    if output.exists() and not overwrite:
        raise ValueError(f"render output already exists; use --overwrite: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)

    project_before = file_sha256(project)
    original = project.read_text(encoding="utf-8", errors="strict")
    patched = patch_render_project(original, output)
    temp_path: Path | None = None
    artifact: dict[str, Any] | None = None
    if output.exists() and overwrite:
        output.unlink()

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".RPP",
            prefix=".reaperctl-render-",
            dir=project.parent,
            delete=False,
        ) as temp:
            temp.write(patched)
            temp_path = Path(temp.name)

        env = os.environ.copy()
        env["HOME"] = os.environ.get("REAPER_GM_HOME", str(paths["workspace"] / "home"))
        env["XDG_CONFIG_HOME"] = os.environ.get(
            "REAPER_GM_XDG_CONFIG_HOME", str(paths["workspace"] / "config")
        )
        env["DISPLAY"] = str(paths["display"])
        try:
            proc = subprocess.run(
                [str(reaper), "-newinst", "-nosplash", "-renderproject", str(temp_path)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"REAPER render timed out after {timeout:.1f}s") from exc
        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "").strip()[-2000:]
            raise RuntimeError(f"REAPER render exited {proc.returncode}: {tail}")
        artifact = verify_rendered_wave(output)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)

    project_after = file_sha256(project)
    if project_after != project_before:
        raise RuntimeError(
            "canonical project changed during render: "
            f"before={project_before} after={project_after}"
        )
    assert artifact is not None
    return {
        "ok": True,
        "canonical_project": str(project),
        "canonical_project_sha256_before": project_before,
        "canonical_project_sha256_after": project_after,
        "render": artifact,
        "reaper_exit_code": 0,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="reaperctl render", description=__doc__)
    parser.add_argument(
        "--baseline",
        type=Path,
        default=Path(os.environ.get("REAPERCTL_BASELINE", DEFAULT_BASELINE)),
    )
    parser.add_argument("--output", type=Path, required=True, help="Explicit .wav output path")
    parser.add_argument("--overwrite", action="store_true", help="Allow replacement of an existing output file")
    parser.add_argument("--timeout", type=float, default=60.0, help="Seconds allowed for REAPER command-line render")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        data = core.load_baseline(args.baseline)
    except ValueError as exc:
        print(f"reaperctl: {exc}", file=sys.stderr)
        return 2
    checks = core.static_checks(data)
    if not all(check.ok for check in checks):
        return int(core.render_checks(checks, args.json, "baseline"))
    try:
        report = render_project(data, args.output, overwrite=args.overwrite, timeout=args.timeout)
    except ValueError as exc:
        print(f"reaperctl: {exc}", file=sys.stderr)
        return 2
    except RuntimeError as exc:
        print(f"reaperctl: {exc}", file=sys.stderr)
        return 4

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        artifact = report["render"]
        print("Render: VERIFIED")
        print(f"Output: {artifact['path']}")
        print(
            f"Format: {artifact['channels']}ch / {artifact['sample_rate_hz']} Hz / "
            f"{artifact['sample_width_bytes'] * 8}-bit PCM"
        )
        print(f"Duration: {artifact['duration_seconds']:.6f}s")
        print(f"Bytes: {artifact['size_bytes']}")
        print(f"SHA-256: {artifact['sha256']}")
        print(f"Canonical project unchanged: {report['canonical_project_sha256_before']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
