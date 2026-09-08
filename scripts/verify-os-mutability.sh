#!/usr/bin/env bash
set -euo pipefail
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

[ -s "$ROOT/MUTABILITY.json" ] || { echo "MISSING MUTABILITY.json" >&2; exit 1; }
[ -s "$ROOT/BASELINE.json" ] || { echo "MISSING BASELINE.json" >&2; exit 1; }

python3 - "$ROOT/MUTABILITY.json" "$ROOT/BASELINE.json" <<'PY'
import json
import sys
from pathlib import Path

mutability = json.loads(Path(sys.argv[1]).read_text())
baseline = json.loads(Path(sys.argv[2]).read_text())

if mutability.get("schema_version") != 2:
    raise SystemExit("unsupported OS mutability schema")
if mutability.get("branch") != "full-os-mutable-layer":
    raise SystemExit("OS mutability policy bound to wrong branch")
if mutability.get("parent_branch") != "mutable-restrictions-lifted":
    raise SystemExit("OS mutability policy lost parent branch provenance")
if mutability.get("base_commit") != "38cfea3c20227500e0db571f72a0d788ceac2705":
    raise SystemExit("OS mutable branch base commit changed")
if mutability.get("mode") != "secure_mutable_continuation":
    raise SystemExit("secure mutable continuation mode missing")

required_mutable = {
    "continuation_project_state",
    "continuation_configuration",
    "virtual_apollo_runtime_state",
    "desktop_session_configuration",
    "derived_audio_outputs",
    "scripts_and_dsp",
    "os_application_layer",
    "installed_package_state",
    "toolchains",
    "system_applications",
    "desktop_components",
    "environment_configuration",
    "service_process_supervision",
    "workspace_system_configuration",
}
mutable = mutability.get("mutable_surfaces", {})
for key in required_mutable:
    if mutable.get(key) is not True:
        raise SystemExit(f"required mutable surface disabled: {key}")

required_guards = {
    "prewrite_backup_required",
    "atomic_replace_required",
    "postwrite_hash_required",
    "rollback_artifact_required",
    "system_change_manifest_required",
    "package_transaction_log_required",
    "pretransaction_package_inventory_required",
    "posttransaction_package_inventory_required",
}
mutation = mutability.get("mutation_policy", {})
for key in required_guards:
    if mutation.get(key) is not True:
        raise SystemExit(f"OS mutation guard disabled: {key}")
if mutation.get("silent_mutation_allowed") is not False:
    raise SystemExit("silent mutation must remain disabled")

os_layer = mutability.get("os_mutable_layer", {})
required_raw_prefixes = {
    "/usr/local",
    "/opt",
    "/etc/profile.d",
    "/etc/systemd/system",
    "/etc/supervisor/conf.d",
    "/etc/xdg",
    "/mnt/data/ubuntu-desktop-workspace",
    "/mnt/data/graphics-workspace",
    "/mnt/data/virtual-apollo",
}
if not required_raw_prefixes.issubset(set(os_layer.get("raw_mutable_path_prefixes", []))):
    raise SystemExit("required raw mutable OS roots missing")
if "/etc/environment" not in set(os_layer.get("raw_mutable_exact_paths", [])):
    raise SystemExit("/etc/environment not admitted as exact mutable path")
if os_layer.get("package_state_mutable") is not True:
    raise SystemExit("package state not mutable")
if os_layer.get("package_owned_files_outside_raw_roots_via_verified_transaction_only") is not True:
    raise SystemExit("package-owned files outside raw roots are not transaction-confined")
if os_layer.get("admitted_package_manager") != "apt":
    raise SystemExit("unexpected package manager")
for key in (
    "package_signature_verification_required",
    "package_repository_metadata_verification_required",
):
    if os_layer.get(key) is not True:
        raise SystemExit(f"package trust guard disabled: {key}")
for key in (
    "package_service_autostart_allowed",
    "package_kernel_or_bootloader_changes_allowed",
):
    if os_layer.get(key) is not False:
        raise SystemExit(f"unsafe package behavior enabled: {key}")

required_protected_prefixes = {
    "/boot",
    "/lib/modules",
    "/usr/lib/modules",
    "/etc/apt/trusted.gpg.d",
    "/etc/apt/keyrings",
    "/etc/pam.d",
    "/etc/security",
    "/etc/ssh",
    "/root/.ssh",
    "/etc/ssl/private",
}
if not required_protected_prefixes.issubset(set(os_layer.get("protected_path_prefixes", []))):
    raise SystemExit("protected OS roots weakened")
required_protected_exact = {
    "/etc/passwd",
    "/etc/shadow",
    "/etc/group",
    "/etc/gshadow",
    "/etc/sudoers",
    "/etc/resolv.conf",
    "/mnt/data/ubuntu-desktop-workspace/apps/REAPER/reaper",
}
if not required_protected_exact.issubset(set(os_layer.get("protected_exact_paths", []))):
    raise SystemExit("protected exact paths weakened")

blocked_prefixes = set(os_layer.get("blocked_package_prefixes", []))
for prefix in ("linux-image", "linux-headers", "linux-modules", "grub", "shim", "systemd-boot"):
    if prefix not in blocked_prefixes:
        raise SystemExit(f"kernel/boot package block missing: {prefix}")
blocked_core = set(os_layer.get("blocked_core_packages", []))
for package in ("apt", "dpkg", "base-files", "bash", "coreutils", "libc6", "passwd", "sudo", "systemd", "udev", "util-linux"):
    if package not in blocked_core:
        raise SystemExit(f"core package block missing: {package}")

security = mutability.get("security_invariants", {})
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
    "kernel_or_bootloader_modification_allowed",
    "authentication_database_modification_allowed",
    "privilege_policy_modification_allowed",
    "package_signature_bypass_allowed",
    "trusted_package_keyring_modification_allowed",
    "security_policy_weakening_allowed",
    "implicit_network_listener_enablement_allowed",
):
    if security.get(key) is not False:
        raise SystemExit(f"security invariant weakened: {key}")

candidate = mutability.get("candidate_boundary", {})
for key in (
    "baseline_lock_changes_require_candidate",
    "runtime_binary_change_requires_candidate",
    "kernel_or_bootloader_change_requires_candidate",
    "authentication_or_privilege_change_requires_candidate",
    "package_trust_root_change_requires_candidate",
    "new_network_listener_requires_candidate",
    "promotion_requires_explicit_owner_approval",
):
    if candidate.get(key) is not True:
        raise SystemExit(f"candidate boundary weakened: {key}")

base = baseline.get("baseline", {})
if base.get("golden_master") != "GM-2026-09-08":
    raise SystemExit("Golden Master identity changed")
if base.get("golden_master_id") != "sha256:74a13a11fe232bca5bd8a320d11ee0c2e17ce5c2e53d76c74ee9714276a95b1f":
    raise SystemExit("Golden Master ID changed")
if base.get("recovery_authority_repository") != "taylorfrey529-ai/reaper-is-free":
    raise SystemExit("recovery authority changed")

print("Secure full OS mutable-layer verification PASSED")
PY
