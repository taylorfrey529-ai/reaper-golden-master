#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAND = ROOT / "candidates" / "reaper-debian-signing-key"
BIND = ROOT / "package-sources" / "reaper-debian-repo.json"
EXPECTED = {
    "TRUST-ROOT-CANDIDATE.json": "7ea73c9ad53eeec3163ba434cb96f5d04e2a01a2c359f18e670f22b37320b0e6",
    "TECHNICAL-EVIDENCE.json": "a282a6715cd3dfe5b56326c59d174d7d15b42ac8b9bfb50dcee71c06bd4e020f",
    "install-trust-root.sh": "0757cadf2c3cbc24af6a0319819c1a69143e7bf89b8b9b4f33d9953d237152c7",
    "rollback-trust-root.sh": "9c71ee29ee50217ae71e52d59d176df2b474074ce9a8c46458404498d55a7061",
    "reaper-debian-repo.sources": "1701fdeb0a0d68cc3f8da5b1a6058e4dc985e1f683101e9fba884bafb7aee9d2",
}
FPR = "EAE567EB437C007F46A58BDCA76356FF985B3F3B"
SNAP_COMMIT = "fcd3b1097c67dd57b5f9437ffa1952a784b61cd3"
SNAP_RUN = "34294140407"
SNAP_MANIFEST = "51be57e06807e179f13da827fd0ca91041d384960866f6180682ff51faf19d56"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def require(ok: bool, msg: str) -> None:
    if not ok:
        raise ValueError(msg)


def classify(kind: str, value: str) -> dict:
    p = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "os-mutation-policy.py"), kind, value, "--json"],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    require(p.returncode in {0, 3}, f"classifier failed for {value}: {p.stderr.strip() or p.stdout.strip()}")
    return json.loads(p.stdout)


def main() -> int:
    try:
        for name, digest in EXPECTED.items():
            p = CAND / name
            require(p.is_file() and sha256(p) == digest, f"candidate artifact drift: {name}")
        c = json.loads((CAND / "TRUST-ROOT-CANDIDATE.json").read_text())
        e = json.loads((CAND / "TECHNICAL-EVIDENCE.json").read_text())
        b = json.loads(BIND.read_text())
        require(c["candidate"] == "reaper-debian-signing-key", "candidate id drift")
        require(c["candidate_branch"] == "candidate/reaper-debian-signing-key", "candidate branch drift")
        require(c["parent_commit"] == "8568d96ad01e7f320352b4830d242ba1397296f4", "parent drift")
        require(c["private_repository"]["bound_snapshot_commit"] == SNAP_COMMIT, "snapshot commit drift")
        require(c["private_repository"]["snapshot_ci_run_id"] == SNAP_RUN and c["private_repository"]["snapshot_ci_conclusion"] == "success", "snapshot CI drift")
        require(c["private_repository"]["snapshot_manifest_sha256"] == SNAP_MANIFEST, "snapshot manifest drift")
        require(c["signing_authority"]["fingerprint"] == FPR and c["signing_authority"]["secret_key_committed"] is False, "signing authority drift")
        require(c["live_trust_root_installed"] is False and c["live_apt_source_active"] is False, "candidate may not claim live activation")
        require(c["package_install_in_candidate"] is False, "candidate must not install package")
        require(c["owner_gate"] == "owner-approve-reaper-debian-signing-key-candidate", "owner gate drift")
        require(e["verdict"] == "TECHNICAL-PASS-OWNER-GATE-PENDING", "technical evidence verdict drift")
        require(e["private_repository_commit"] == SNAP_COMMIT and e["private_repository_ci_run_id"] == SNAP_RUN, "technical evidence source drift")
        require(e["isolated_apt"]["missing_key_rejected"] is True and e["isolated_apt"]["signed_by_update"] == "PASS", "isolated APT proof missing")
        require(e["sandbox_trust_root_rehearsal"]["install"] == "PASS" and e["sandbox_trust_root_rehearsal"]["rollback_drift_rejected"] is True and e["sandbox_trust_root_rehearsal"]["rollback_after_restoring_expected_bytes"] == "PASS", "sandbox rollback proof missing")
        require(e["protected_live_state"]["live_trust_root_installed"] is False and e["protected_live_state"]["live_apt_source_active"] is False, "technical evidence overclaims live state")
        require(b["repository"]["bound_snapshot_commit"] == SNAP_COMMIT and b["repository"]["snapshot_ci_run_id"] == SNAP_RUN and b["repository"]["snapshot_ci_conclusion"] == "success", "binding snapshot drift")
        require(b["trust"]["signing_key_status"] == "candidate-staged" and b["trust"]["signing_key_fingerprint"] == FPR, "binding signing state drift")
        require(b["trust"]["trust_root_installed_on_live_os"] is False, "binding may not claim live trust root")
        require(b["admission"]["state"] == "signed-snapshot-bound-candidate", "binding admission state drift")
        require(b["admission"]["consumer_trust_root_admitted"] is False and b["admission"]["apt_source_activation_admitted"] is False and b["admission"]["package_install_admitted"] is False, "binding overclaims admission")
        require(b["admission"]["pending_gate"] == "owner-approve-reaper-debian-signing-key-candidate", "binding owner gate drift")
        src = (CAND / "reaper-debian-repo.sources").read_text()
        require(src == "Types: deb\nURIs: file:/mnt/data/reaper-apt-repository\nSuites: trixie\nComponents: main\nArchitectures: amd64\nSigned-By: /etc/apt/keyrings/reaper-debian-repo.gpg\n", "APT source definition drift")
        for path in c["proposed_live_changes"]:
            require(classify("path", path)["classification"] == "candidate-required", f"proposed path unexpectedly ordinary-mutable: {path}")
        require(classify("package", "reaper-workspace-status")["classification"] == "mutable", "package should remain ordinary mutable after trust admission")
    except (OSError, KeyError, json.JSONDecodeError, ValueError) as exc:
        print(f"trust-root candidate verification failed: {exc}", file=sys.stderr)
        return 1
    print("REAPER Debian trust-root candidate verification PASSED; owner gate pending")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
