#!/usr/bin/env python3
"""Securely apply allowlisted continuation transforms to the canonical REAPER project in place."""
from __future__ import annotations

import argparse
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "bin" / "reaperctl-core"
BASE = ROOT / "BASELINE.json"
MUTABILITY = ROOT / "MUTABILITY.json"
PAN = ROOT / "scripts" / "reaper-pan-drums.py"
ALIGN = ROOT / "scripts" / "reaper-align-drums.py"


def _load(name: str, path: Path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    loader.exec_module(module)
    return module


core = _load("reaperctl_mutate_core", CORE)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_mutability(path: Path = MUTABILITY) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid mutability policy: {exc}") from exc
    if data.get("mode") != "secure_mutable_continuation":
        raise ValueError("secure mutable continuation mode is not enabled")
    mutation = data.get("mutation_policy", {})
    security = data.get("security_invariants", {})
    candidate = data.get("candidate_boundary", {})
    for key in (
        "prewrite_backup_required",
        "atomic_replace_required",
        "postwrite_hash_required",
        "rollback_artifact_required",
    ):
        if mutation.get(key) is not True:
            raise ValueError(f"required mutation guard disabled: {key}")
    if mutation.get("silent_mutation_allowed") is not False:
        raise ValueError("silent mutation must remain disabled")
    for key in (
        "path_traversal_allowed",
        "symlink_escape_allowed",
        "remote_web_default_allowed",
        "network_enablement_implied",
        "reaper_binary_modification_allowed",
        "golden_master_record_modification_allowed",
        "recovery_authority_modification_allowed",
        "license_or_evaluation_bypass_allowed",
        "unverified_external_payload_execution_allowed",
    ):
        if security.get(key) is not False:
            raise ValueError(f"security invariant weakened: {key}")
    for key in (
        "baseline_lock_changes_require_candidate",
        "runtime_binary_change_requires_candidate",
        "promotion_requires_explicit_owner_approval",
    ):
        if candidate.get(key) is not True:
            raise ValueError(f"candidate boundary weakened: {key}")
    return data


def confined_project(project: Path, workspace: Path) -> Path:
    project = project.expanduser()
    workspace_real = workspace.expanduser().resolve()
    if project.is_symlink():
        raise ValueError(f"project symlink is not allowed: {project}")
    project_real = project.resolve()
    try:
        project_real.relative_to(workspace_real)
    except ValueError as exc:
        raise ValueError(f"project escapes workspace: {project_real}") from exc
    if not project_real.is_file():
        raise ValueError(f"canonical project not found: {project_real}")
    if not stat.S_ISREG(project_real.stat().st_mode):
        raise ValueError(f"canonical project is not a regular file: {project_real}")
    return project_real


def _atomic_write(path: Path, payload: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp, stat.S_IMODE(mode))
        os.replace(temp, path)
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
    _atomic_write(path, payload, 0o600)


def _backup_original(project: Path, rollback_root: Path, original: bytes, original_sha: str, mode: int) -> Path:
    rollback_root.mkdir(parents=True, exist_ok=True)
    backup = rollback_root / f"{project.name}.before-{original_sha}.rpp"
    if backup.exists():
        if backup.is_symlink() or not backup.is_file() or sha256(backup) != original_sha:
            raise RuntimeError(f"rollback artifact collision: {backup}")
        return backup
    _atomic_write(backup, original, mode)
    if sha256(backup) != original_sha:
        raise RuntimeError("rollback artifact hash verification failed")
    return backup


def _run_transform(operation: str, project: Path, candidate: Path, baseline: Path, tracks: list[str] | None, timeout: float) -> dict[str, Any]:
    if operation == "pan-drums":
        command = [sys.executable, str(PAN), "--baseline", str(baseline), "--project", str(project), "--output-project", str(candidate), "--overwrite", "--json"]
    elif operation == "align-drums":
        command = [sys.executable, str(ALIGN), "--baseline", str(baseline), "--output-project", str(candidate), "--overwrite", "--timeout", str(timeout), "--json"]
    else:
        raise ValueError(f"operation is not allowlisted: {operation}")
    for track in tracks or []:
        command.extend(["--track", track])
    try:
        proc = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=max(timeout + 10.0, 30.0), check=False)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"{operation} candidate generation timed out") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout)[-2000:]
        raise RuntimeError(f"{operation} candidate generation failed ({proc.returncode}): {detail}")
    try:
        report = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{operation} did not return valid JSON verification") from exc
    if report.get("ok") is not True or report.get("mode") != "applied":
        raise RuntimeError(f"{operation} candidate was not verified as applied")
    if not candidate.is_file() or candidate.stat().st_size == 0:
        raise RuntimeError(f"{operation} did not produce a candidate project")
    return report


def commit_candidate(project: Path, candidate: Path, rollback_root: Path, operation: str, policy_sha: str) -> dict[str, Any]:
    if candidate.is_symlink() or not candidate.is_file():
        raise ValueError("candidate project must be a regular non-symlink file")
    original = project.read_bytes()
    original_sha = hashlib.sha256(original).hexdigest()
    original_mode = project.stat().st_mode
    candidate_sha = sha256(candidate)
    if sha256(project) != original_sha:
        raise RuntimeError("canonical project changed before mutation commit")
    backup = _backup_original(project, rollback_root, original, original_sha, original_mode)
    os.chmod(candidate, stat.S_IMODE(original_mode))
    replaced = False
    try:
        os.replace(candidate, project)
        replaced = True
        if sha256(project) != candidate_sha:
            raise RuntimeError("post-write hash verification failed")
    except Exception:
        if replaced:
            _atomic_write(project, original, original_mode)
            if sha256(project) != original_sha:
                raise RuntimeError("mutation failed and rollback verification also failed")
        raise
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    receipt = rollback_root / f"mutation-{timestamp}-{operation}.json"
    record = {
        "schema_version": 1,
        "operation": operation,
        "project": str(project),
        "before_sha256": original_sha,
        "after_sha256": candidate_sha,
        "rollback_artifact": str(backup),
        "rollback_sha256": sha256(backup),
        "mutability_policy_sha256": policy_sha,
        "atomic_replace": True,
        "postwrite_hash_verified": True,
        "rollback_verified": True,
    }
    _write_json_atomic(receipt, record)
    record["receipt"] = str(receipt)
    record["receipt_sha256"] = sha256(receipt)
    return record


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="reaperctl mutate", description=__doc__)
    parser.add_argument("--baseline", type=Path, default=Path(os.environ.get("REAPERCTL_BASELINE", BASE)))
    parser.add_argument("--mutability", type=Path, default=MUTABILITY)
    sub = parser.add_subparsers(dest="operation", required=True)
    for name in ("pan-drums", "align-drums"):
        command = sub.add_parser(name)
        command.add_argument("--track", action="append", dest="tracks")
        command.add_argument("--json", action="store_true")
        if name == "align-drums":
            command.add_argument("--timeout", type=float, default=20.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        data = core.load_baseline(args.baseline)
        checks = core.static_checks(data)
        if not all(check.ok for check in checks):
            return int(core.render_checks(checks, getattr(args, "json", False), "baseline"))
        load_mutability(args.mutability)
        paths = core.workspace_paths(data)
        project = confined_project(paths["project"], paths["workspace"])
        policy_sha = sha256(args.mutability)
        rollback_root = paths["workspace"] / "evidence" / "mutations"
        fd, candidate_name = tempfile.mkstemp(prefix=f".{project.stem}.mutation-", suffix=project.suffix, dir=str(project.parent))
        os.close(fd)
        candidate = Path(candidate_name)
        try:
            report = _run_transform(args.operation, project, candidate, args.baseline, args.tracks, getattr(args, "timeout", 20.0))
            if sha256(project) != report.get("input_project_sha256", report.get("canonical_project_sha256")):
                raise RuntimeError("transform report does not bind the current canonical project")
            mutation = commit_candidate(project, candidate, rollback_root, args.operation, policy_sha)
        finally:
            try:
                candidate.unlink()
            except FileNotFoundError:
                pass
    except ValueError as exc:
        print(f"reaperctl: {exc}", file=sys.stderr)
        return 2
    except RuntimeError as exc:
        print(f"reaperctl: {exc}", file=sys.stderr)
        return 4
    result = {"ok": True, "mode": "secure-mutable", "transform": report, "mutation": mutation}
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Secure project mutation {args.operation}: VERIFIED")
        print(f"Project: {project}")
        print(f"Before: {mutation['before_sha256']}")
        print(f"After:  {mutation['after_sha256']}")
        print(f"Rollback: {mutation['rollback_artifact']}")
        print(f"Receipt:  {mutation['receipt']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
