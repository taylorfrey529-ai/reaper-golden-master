#!/usr/bin/env python3
"""Verify durable full-OS system-change manifests using only the Python standard library."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "MUTABILITY.json"
EVIDENCE = ROOT / "evidence" / "system-changes"
SHA_RE = re.compile(r"^[0-9a-f]{64}$")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def verify_manifest(path: Path, policy_sha: str) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "schema_version", "branch", "policy_sha256", "operation", "classification",
        "requested_change", "affected_paths", "affected_packages", "pre_state",
        "post_state", "services", "network_listeners", "rollback", "verification",
    }
    require(required <= set(data), f"{path}: missing required fields {sorted(required - set(data))}")
    require(data["schema_version"] == 1, f"{path}: unsupported schema_version")
    require(data["branch"] == "full-os-mutable-layer", f"{path}: wrong branch")
    require(data["policy_sha256"] == policy_sha, f"{path}: policy hash drift")
    require(data["classification"] in {"mutable", "candidate-required"}, f"{path}: invalid classification")
    require(isinstance(data["operation"], str) and data["operation"], f"{path}: missing operation")
    require(isinstance(data["requested_change"], str) and data["requested_change"], f"{path}: missing requested_change")

    for item in data["affected_paths"]:
        require(isinstance(item, dict), f"{path}: affected_paths item must be object")
        require(str(item.get("path", "")).startswith("/"), f"{path}: affected path must be absolute")
        require(item.get("classification") in {"mutable", "candidate-required"}, f"{path}: invalid path classification")
        for key in ("before_sha256", "after_sha256"):
            value = item.get(key)
            require(value is None or bool(SHA_RE.fullmatch(value)), f"{path}: invalid {key}")

    for item in data["affected_packages"]:
        require(isinstance(item, dict), f"{path}: affected_packages item must be object")
        require(isinstance(item.get("name"), str) and item["name"], f"{path}: package name missing")
        require(item.get("classification") in {"mutable", "candidate-required"}, f"{path}: invalid package classification")

    for state_name in ("pre_state", "post_state"):
        state = data[state_name]
        require(isinstance(state, dict), f"{path}: {state_name} must be object")
        inv = state.get("package_inventory_sha256")
        require(inv is None or bool(SHA_RE.fullmatch(inv)), f"{path}: invalid package inventory hash")

    services = data["services"]
    for key in ("added", "removed", "started", "stopped", "enabled", "disabled"):
        require(isinstance(services.get(key), list), f"{path}: services.{key} must be list")

    listeners = data["network_listeners"]
    for key in ("before", "after", "new_listeners"):
        require(isinstance(listeners.get(key), list), f"{path}: network_listeners.{key} must be list")

    rollback = data["rollback"]
    require(isinstance(rollback.get("available"), bool), f"{path}: rollback.available must be boolean")
    require(isinstance(rollback.get("artifacts"), list), f"{path}: rollback.artifacts must be list")

    verification = data["verification"]
    require(verification.get("result") in {"PASS", "FAIL", "BLOCKED"}, f"{path}: invalid verification result")
    require(isinstance(verification.get("golden_master_unchanged"), bool), f"{path}: golden_master_unchanged must be boolean")
    require(isinstance(verification.get("security_invariants_preserved"), bool), f"{path}: security_invariants_preserved must be boolean")

    if verification["result"] == "PASS":
        require(verification["golden_master_unchanged"] is True, f"{path}: PASS cannot change Golden Master")
        require(verification["security_invariants_preserved"] is True, f"{path}: PASS cannot weaken security invariants")
        if data["classification"] == "mutable":
            require(all(x["classification"] == "mutable" for x in data["affected_paths"]), f"{path}: mutable PASS contains candidate-required path")
            require(all(x["classification"] == "mutable" for x in data["affected_packages"]), f"{path}: mutable PASS contains candidate-required package")
            require(listeners["new_listeners"] == [], f"{path}: mutable PASS cannot silently add a network listener")


def main() -> int:
    if not POLICY.is_file():
        print("missing MUTABILITY.json", file=sys.stderr)
        return 2
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    if policy.get("schema_version") != 2 or policy.get("branch") != "full-os-mutable-layer":
        print("full-OS policy not active", file=sys.stderr)
        return 2
    policy_sha = sha256(POLICY)
    manifests = sorted(EVIDENCE.glob("*.json")) if EVIDENCE.is_dir() else []
    if not manifests:
        print("no system-change manifests found", file=sys.stderr)
        return 3
    try:
        for manifest in manifests:
            verify_manifest(manifest, policy_sha)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"system-change manifest verification failed: {exc}", file=sys.stderr)
        return 4
    print(f"System-change manifest verification PASSED ({len(manifests)} manifest(s), policy={policy_sha})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
