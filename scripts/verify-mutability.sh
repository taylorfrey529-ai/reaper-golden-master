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

if mutability.get("schema_version") != 1:
    raise SystemExit("unsupported mutability schema")
if mutability.get("branch") != "mutable-restrictions-lifted":
    raise SystemExit("mutability policy bound to wrong branch")
if mutability.get("mode") != "secure_mutable_continuation":
    raise SystemExit("secure mutable continuation mode missing")

required_mutable = {
    "continuation_project_state",
    "continuation_configuration",
    "virtual_apollo_runtime_state",
    "desktop_session_configuration",
    "derived_audio_outputs",
    "scripts_and_dsp",
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
}
mutation = mutability.get("mutation_policy", {})
for key in required_guards:
    if mutation.get(key) is not True:
        raise SystemExit(f"mutation guard disabled: {key}")
if mutation.get("silent_mutation_allowed") is not False:
    raise SystemExit("silent mutation must remain disabled")

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
):
    if security.get(key) is not False:
        raise SystemExit(f"security invariant weakened: {key}")

candidate = mutability.get("candidate_boundary", {})
for key in (
    "baseline_lock_changes_require_candidate",
    "runtime_binary_change_requires_candidate",
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

print("Secure mutable continuation verification PASSED")
PY
