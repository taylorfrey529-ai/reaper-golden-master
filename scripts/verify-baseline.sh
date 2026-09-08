#!/usr/bin/env bash
set -euo pipefail
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

required=(README.md BASELINE.json LINEAGE.md CONTINUATION.md)
for rel in "${required[@]}"; do
  [ -s "$ROOT/$rel" ] || { echo "MISSING $rel" >&2; exit 1; }
done

python3 - "$ROOT/BASELINE.json" <<'PY'
import json, sys
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text())
b = data["baseline"]
c = data["continuity_locks"]
p = data["policy"]

expected = {
    "golden_master": "GM-2026-09-08",
    "golden_master_id": "sha256:74a13a11fe232bca5bd8a320d11ee0c2e17ce5c2e53d76c74ee9714276a95b1f",
    "payload_bytes": 888467386,
    "recovery_authority_repository": "taylorfrey529-ai/reaper-is-free",
    "recovery_authority_proof_head": "6b76608974737e0b59818db94ecbc21018615794",
    "golden_master_admission_commit": "6cd104cbf70237be473b7eda5dca058dcd182069",
}
for key, value in expected.items():
    if b.get(key) != value:
        raise SystemExit(f"baseline regression: {key}={b.get(key)!r}, expected {value!r}")

locks = {
    "linux_audio_mode": 1,
    "interface": "apollo_spdif",
    "spdif_input_channels": 2,
    "spdif_output_channels": 2,
    "sample_rate_hz": 48000,
    "buffer_samples": 256,
    "buffer_count": 3,
    "project": "ASIO-Routing-Project",
    "tempo_bpm": 120,
    "time_signature": "4/4",
}
for key, value in locks.items():
    if c.get(key) != value:
        raise SystemExit(f"continuity lock regression: {key}={c.get(key)!r}, expected {value!r}")

if p.get("baseline_is_immutable") is not True:
    raise SystemExit("baseline immutability policy missing")
if p.get("silent_regression_allowed") is not False:
    raise SystemExit("silent regression policy invalid")

print("Reaper Golden Master baseline verification PASSED")
PY

grep -Fq 'GM-2026-09-08' "$ROOT/README.md"
grep -Fq '74a13a11fe232bca5bd8a320d11ee0c2e17ce5c2e53d76c74ee9714276a95b1f' "$ROOT/LINEAGE.md"
grep -Fq 'candidate Golden Master change' "$ROOT/CONTINUATION.md"

echo 'Continuation contract verification PASSED.'
