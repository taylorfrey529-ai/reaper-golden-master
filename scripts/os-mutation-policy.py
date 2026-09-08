#!/usr/bin/env python3
"""Classify proposed OS-layer paths and packages under the secure full-OS mutability contract."""
from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "MUTABILITY.json"


def load_policy(path: Path = DEFAULT_POLICY) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 2:
        raise ValueError("OS mutability policy requires schema_version=2")
    if data.get("branch") != "full-os-mutable-layer":
        raise ValueError("OS mutability policy is bound to the wrong branch")
    if data.get("mode") != "secure_mutable_continuation":
        raise ValueError("secure mutable continuation mode is not enabled")
    return data


def _normalize_abs(value: str) -> str:
    path = PurePosixPath(value)
    if not path.is_absolute():
        raise ValueError("path must be absolute")
    parts: list[str] = []
    for part in path.parts[1:]:
        if part in ("", "."):
            continue
        if part == "..":
            raise ValueError("path traversal is not allowed")
        parts.append(part)
    return "/" + "/".join(parts)


def _under(path: str, prefix: str) -> bool:
    if path == prefix:
        return True
    return path.startswith(prefix.rstrip("/") + "/")


def classify_path(policy: dict[str, Any], value: str) -> dict[str, Any]:
    path = _normalize_abs(value)
    os_layer = policy["os_mutable_layer"]
    protected_exact = set(os_layer.get("protected_exact_paths", []))
    protected_prefixes = list(os_layer.get("protected_path_prefixes", []))
    raw_exact = set(os_layer.get("raw_mutable_exact_paths", []))
    raw_prefixes = list(os_layer.get("raw_mutable_path_prefixes", []))

    if path in protected_exact:
        return {"kind": "path", "value": path, "classification": "candidate-required", "reason": "protected exact path"}
    for prefix in protected_prefixes:
        if _under(path, prefix):
            return {"kind": "path", "value": path, "classification": "candidate-required", "reason": f"protected path prefix {prefix}"}
    if path in raw_exact:
        return {"kind": "path", "value": path, "classification": "mutable", "reason": "admitted exact OS path"}
    for prefix in raw_prefixes:
        if _under(path, prefix):
            extra = None
            if prefix in {"/etc/systemd/system", "/etc/supervisor/conf.d"}:
                extra = "definition may change; service enablement and new listeners still require their explicit gates"
            result = {"kind": "path", "value": path, "classification": "mutable", "reason": f"admitted raw mutable prefix {prefix}"}
            if extra:
                result["guard"] = extra
            return result
    return {
        "kind": "path",
        "value": path,
        "classification": "candidate-required",
        "reason": "outside admitted raw mutable roots; use a verified package transaction or a separate candidate",
    }


def classify_package(policy: dict[str, Any], package: str) -> dict[str, Any]:
    package = package.strip()
    if not package or any(ch.isspace() for ch in package) or "/" in package:
        raise ValueError("package must be a single apt package name")
    os_layer = policy["os_mutable_layer"]
    blocked_exact = set(os_layer.get("blocked_core_packages", []))
    blocked_prefixes = tuple(os_layer.get("blocked_package_prefixes", []))
    if package in blocked_exact:
        return {"kind": "package", "value": package, "classification": "candidate-required", "reason": "protected core package"}
    if any(package.startswith(prefix) for prefix in blocked_prefixes):
        return {"kind": "package", "value": package, "classification": "candidate-required", "reason": "kernel/boot package family"}
    return {
        "kind": "package",
        "value": package,
        "classification": "mutable",
        "reason": "admitted apt package transaction",
        "guards": [
            "verified repository metadata and package signatures",
            "pre/post package inventory",
            "transaction log and rollback evidence",
            "no automatic service enablement",
            "no implicit new network listener",
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mutability", type=Path, default=DEFAULT_POLICY)
    sub = parser.add_subparsers(dest="kind", required=True)
    p_path = sub.add_parser("path")
    p_path.add_argument("value")
    p_path.add_argument("--json", action="store_true")
    p_pkg = sub.add_parser("package")
    p_pkg.add_argument("value")
    p_pkg.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        policy = load_policy(args.mutability)
        result = classify_path(policy, args.value) if args.kind == "path" else classify_package(policy, args.value)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"os-mutation-policy: {exc}")
        return 2
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"{result['classification']}: {result['value']} ({result['reason']})")
    return 0 if result["classification"] == "mutable" else 3


if __name__ == "__main__":
    raise SystemExit(main())
