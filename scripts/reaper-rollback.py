#!/usr/bin/env python3
"""Receipt-driven rollback for secure mutable REAPER continuation transactions."""
from __future__ import annotations

import argparse
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import stat
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "bin" / "reaperctl-core"
BASE = ROOT / "BASELINE.json"
MUTABILITY = ROOT / "MUTABILITY.json"


def _load(name: str, path: Path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    loader.exec_module(module)
    return module


core = _load("reaperctl_rollback_core", CORE)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


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


def confined_regular_file(path: Path, root: Path, label: str) -> Path:
    path = path.expanduser()
    root_real = root.expanduser().resolve()
    if path.is_symlink():
        raise ValueError(f"{label} symlink is not allowed: {path}")
    resolved = path.resolve()
    try:
        resolved.relative_to(root_real)
    except ValueError as exc:
        raise ValueError(f"{label} escapes permitted root: {resolved}") from exc
    if not resolved.is_file():
        raise ValueError(f"{label} not found: {resolved}")
    if not stat.S_ISREG(resolved.stat().st_mode):
        raise ValueError(f"{label} is not a regular file: {resolved}")
    return resolved


def canonical_project(path: Path, workspace: Path) -> Path:
    return confined_regular_file(path, workspace, "canonical project")


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
    _atomic_write(path, (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8"), 0o600)


def load_receipt(receipt_path: Path, rollback_root: Path, project: Path, policy_sha: str) -> tuple[Path, dict[str, Any], Path]:
    receipt = confined_regular_file(receipt_path, rollback_root, "mutation receipt")
    try:
        data = json.loads(receipt.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid mutation receipt JSON: {exc}") from exc
    if data.get("schema_version") != 1:
        raise ValueError(f"unsupported mutation receipt schema: {data.get('schema_version')!r}")
    for key in ("before_sha256", "after_sha256", "rollback_sha256", "mutability_policy_sha256"):
        if not _is_sha256(data.get(key)):
            raise ValueError(f"invalid or missing receipt hash: {key}")
    if data.get("mutability_policy_sha256") != policy_sha:
        raise ValueError("mutation receipt was created under a different mutability policy")
    if data.get("atomic_replace") is not True or data.get("postwrite_hash_verified") is not True or data.get("rollback_verified") is not True:
        raise ValueError("mutation receipt is not a verified secure-mutable transaction")
    receipt_project = Path(str(data.get("project", ""))).expanduser().resolve()
    if receipt_project != project:
        raise ValueError(f"mutation receipt targets a different project: {receipt_project}")
    rollback_value = data.get("rollback_artifact")
    if not isinstance(rollback_value, str) or not rollback_value:
        raise ValueError("mutation receipt missing rollback artifact")
    artifact = confined_regular_file(Path(rollback_value), rollback_root, "rollback artifact")
    artifact_sha = sha256(artifact)
    if artifact_sha != data["rollback_sha256"] or artifact_sha != data["before_sha256"]:
        raise RuntimeError("rollback artifact hash does not match mutation receipt")
    return receipt, data, artifact


def _preserve_current(project: Path, rollback_root: Path, current: bytes, current_sha: str, mode: int) -> Path:
    artifact = rollback_root / f"{project.name}.pre-rollback-{current_sha}.rpp"
    if artifact.exists():
        if artifact.is_symlink() or not artifact.is_file() or sha256(artifact) != current_sha:
            raise RuntimeError(f"pre-rollback artifact collision: {artifact}")
        return artifact
    _atomic_write(artifact, current, mode)
    if sha256(artifact) != current_sha:
        raise RuntimeError("pre-rollback artifact hash verification failed")
    return artifact


def execute_rollback(
    project: Path,
    receipt_path: Path,
    rollback_root: Path,
    policy_sha: str,
    live_reaper_pids: list[int] | None = None,
) -> dict[str, Any]:
    receipt, data, artifact = load_receipt(receipt_path, rollback_root, project, policy_sha)
    current = project.read_bytes()
    current_sha = hashlib.sha256(current).hexdigest()
    expected_after = data["after_sha256"]
    if current_sha != expected_after:
        raise RuntimeError(
            f"canonical project no longer matches mutation receipt after_sha256: current={current_sha}, expected={expected_after}"
        )
    mode = project.stat().st_mode
    pre_rollback = _preserve_current(project, rollback_root, current, current_sha, mode)
    if sha256(project) != current_sha:
        raise RuntimeError("canonical project changed while pre-rollback evidence was being prepared")
    target = artifact.read_bytes()
    target_sha = hashlib.sha256(target).hexdigest()
    replaced = False
    try:
        _atomic_write(project, target, mode)
        replaced = True
        if sha256(project) != data["before_sha256"]:
            raise RuntimeError("post-rollback hash verification failed")
    except Exception:
        if replaced:
            _atomic_write(project, current, mode)
            if sha256(project) != current_sha:
                raise RuntimeError("rollback failed and recovery of the mutated state also failed")
        raise
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    rollback_receipt = rollback_root / f"rollback-{timestamp}-{data.get('operation', 'mutation')}.json"
    record = {
        "schema_version": 1,
        "operation": data.get("operation"),
        "project": str(project),
        "source_mutation_receipt": str(receipt),
        "source_mutation_receipt_sha256": sha256(receipt),
        "from_sha256": current_sha,
        "to_sha256": target_sha,
        "expected_before_sha256": data["before_sha256"],
        "expected_after_sha256": data["after_sha256"],
        "rollback_artifact": str(artifact),
        "rollback_artifact_sha256": sha256(artifact),
        "pre_rollback_artifact": str(pre_rollback),
        "pre_rollback_artifact_sha256": sha256(pre_rollback),
        "mutability_policy_sha256": policy_sha,
        "atomic_replace": True,
        "postwrite_hash_verified": True,
        "live_reaper_override": bool(live_reaper_pids),
        "live_reaper_pids": list(live_reaper_pids or []),
        "result": "PASS",
    }
    _write_json_atomic(rollback_receipt, record)
    record["receipt"] = str(rollback_receipt)
    record["receipt_sha256"] = sha256(rollback_receipt)
    return record


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="reaperctl rollback", description=__doc__)
    parser.add_argument("--baseline", type=Path, default=Path(os.environ.get("REAPERCTL_BASELINE", BASE)))
    parser.add_argument("--mutability", type=Path, default=MUTABILITY)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--live", action="store_true", help="explicitly permit rollback while canonical REAPER is running")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        data = core.load_baseline(args.baseline)
        checks = core.static_checks(data)
        if not all(check.ok for check in checks):
            return int(core.render_checks(checks, args.json, "baseline"))
        load_mutability(args.mutability)
        paths = core.workspace_paths(data)
        project = canonical_project(paths["project"], paths["workspace"])
        rollback_root = (paths["workspace"] / "evidence" / "mutations").resolve()
        policy_sha = sha256(args.mutability)
        live_pids = core.discover_process_pids(paths["reaper"])
        if live_pids and not args.live:
            raise ValueError(
                "canonical REAPER is running; stop it before rollback or pass --live to explicitly accept live-session overwrite risk"
            )
        result = execute_rollback(project, args.receipt, rollback_root, policy_sha, live_pids if args.live else None)
    except ValueError as exc:
        print(f"reaperctl: {exc}", file=sys.stderr)
        return 2
    except RuntimeError as exc:
        print(f"reaperctl: {exc}", file=sys.stderr)
        return 4
    output = {"ok": True, "mode": "secure-rollback", "rollback": result}
    if args.json:
        print(json.dumps(output, indent=2))
    else:
        print("Secure project rollback: VERIFIED")
        print(f"Project: {project}")
        print(f"From: {result['from_sha256']}")
        print(f"To:   {result['to_sha256']}")
        print(f"Pre-rollback artifact: {result['pre_rollback_artifact']}")
        print(f"Receipt: {result['receipt']}")
        if result["live_reaper_override"]:
            print(f"Live REAPER override: yes ({result['live_reaper_pids']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
