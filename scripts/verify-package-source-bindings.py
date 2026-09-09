#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BINDING = ROOT / "package-sources" / "reaper-debian-repo.json"
SHA64 = set("0123456789abcdef")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def valid_sha(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in SHA64 for c in value)


def main() -> int:
    try:
        d = json.loads(BINDING.read_text(encoding="utf-8"))
        require(d.get("schema_version") == 1, "schema version drift")
        require(d.get("source_kind") == "private_debian_repository", "source kind drift")
        repo = d["repository"]
        require(repo["full_name"] == "taylorfrey529-ai/reaper-debian-repo", "repository name drift")
        require(repo["repository_id"] == "1362017734", "repository id drift")
        require(repo["visibility"] == "private", "repository must remain private")
        require(repo["default_branch"] == "main", "default branch drift")
        require(repo["bound_bootstrap_commit"] == "57afcc6dc995aae69bec1c663a2e4885b2ddc9c0", "bootstrap commit drift")
        require(repo["bootstrap_ci_run_id"] == "34293034792" and repo["bootstrap_ci_conclusion"] == "success", "bootstrap CI drift")
        require(repo["bound_snapshot_commit"] == "fcd3b1097c67dd57b5f9437ffa1952a784b61cd3", "snapshot commit drift")
        require(repo["snapshot_ci_run_id"] == "34294140407" and repo["snapshot_ci_conclusion"] == "success", "snapshot CI drift")

        consumer = d["consumer"]
        require(consumer["repository"] == "taylorfrey529-ai/reaper-golden-master", "consumer repository drift")
        require(consumer["branch"] == "full-os-mutable-layer", "consumer branch drift")
        require(consumer["admitted_from_candidate_branch"] == "candidate/reaper-debian-signing-key", "candidate branch drift")
        require(consumer["admitted_candidate_commit"] == "edee08555683c72d726345e94b404d17b32ab1aa", "candidate commit drift")
        require(consumer["candidate_ci_run_id"] == "34294605562" and consumer["candidate_ci_conclusion"] == "success", "candidate CI drift")
        require(consumer["owner_approved"] is True, "owner approval missing")
        require(consumer["policy"] == "MUTABILITY.json", "consumer policy drift")

        compat = d["compatibility"]
        require((compat["os"], compat["release"], compat["codename"], compat["architecture"], compat["suite"], compat["component"]) ==
                ("Debian GNU/Linux", "13", "trixie", "amd64", "trixie", "main"), "compatibility drift")
        transport = d["transport"]
        require(transport["github_access"] == "authenticated_private_snapshot_sync", "GitHub transport drift")
        require(transport["apt_access"] == "local_file_repository", "APT transport drift")
        require(transport["local_root"] == "/mnt/data/reaper-apt-repository", "local repository root drift")
        require(transport["local_uri"] == "file:/mnt/data/reaper-apt-repository", "local repository URI drift")
        require(transport["github_credentials_in_apt_configuration_allowed"] is False, "GitHub credentials may not enter APT configuration")

        snap = d["snapshot"]
        require(snap["state"] == "admitted-private-snapshot", "snapshot admission state drift")
        require(snap["snapshot_id"] == "2026-09-09.1", "snapshot id drift")
        require(snap["snapshot_manifest_sha256"] == "51be57e06807e179f13da827fd0ca91041d384960866f6180682ff51faf19d56", "snapshot manifest drift")
        require(snap["package_name"] == "reaper-workspace-status" and snap["package_version"] == "1.0.0-1", "package identity drift")
        require(snap["package_sha256"] == "a2f5fa8679720368b30377d10a541f8dd95cddfa9d8e5b39e6b433f0e346fe8b", "package hash drift")

        trust = d["trust"]
        require(trust["repository_signing_required"] is True, "repository signing must remain required")
        require(trust["signing_key_status"] == "admitted-active", "signing key state drift")
        require(trust["signing_key_fingerprint"] == "EAE567EB437C007F46A58BDCA76356FF985B3F3B", "signing fingerprint drift")
        require(trust["public_key_sha256"] == "7dc135b64febe59163cd293718cb02e2a2b3ad9ffe7ec01ecf9d9c93ec10e077", "public key hash drift")
        require(trust["signed_by_scope_required"] is True, "Signed-By scoping must remain required")
        require(trust["trust_root_installed_on_live_os"] is True, "admission must record live trust root")
        require(trust["trust_root_path"] == "/etc/apt/keyrings/reaper-debian-repo.gpg", "trust root path drift")
        require(trust["apt_source_path"] == "/etc/apt/sources.list.d/reaper-debian-repo.sources", "APT source path drift")
        require(trust["apt_source_sha256"] == "1701fdeb0a0d68cc3f8da5b1a6058e4dc985e1f683101e9fba884bafb7aee9d2", "APT source hash drift")
        require(trust["trust_root_change_requires_candidate"] is True, "future trust-root candidate gate missing")
        require(trust["trust_root_candidate_branch"] == "candidate/reaper-debian-signing-key", "trust-root candidate branch drift")
        require(trust["trust_root_candidate_commit"] == "edee08555683c72d726345e94b404d17b32ab1aa", "trust-root candidate commit drift")
        require(trust["unsigned_packages_allowed"] is False, "unsigned packages cannot be admitted")
        require(trust["unsigned_release_metadata_allowed"] is False, "unsigned Release metadata cannot be admitted")

        evidence = d["live_evidence"]
        require(evidence["local_repository_present"] is True, "local repository admission evidence missing")
        for key in ("package_inventory_sha256", "listener_inventory_sha256", "project_sha256", "reaper_sha256", "workspace_status_sha256", "apt_update_output_sha256", "apt_policy_output_sha256", "live_rollback_output_sha256", "live_reinstall_output_sha256"):
            require(valid_sha(evidence[key]), f"invalid live evidence hash: {key}")
        require(evidence["package_inventory_sha256"] == "1de03bf4d89b6b2c5d26def2f05ade72cb704a7bf81c887f87d4201d13aac018", "package inventory drift")
        require(evidence["listener_inventory_sha256"] == "69b15352b7611ce5e030771733d63726b6392b86aa11d746b87531315ae64d0a", "listener inventory drift")
        require(evidence["project_sha256"] == "2ea85263d6dc125bf7739264956a1ee1a8074c2b42f69b606b5e9d8b7e9771f1", "project hash drift")
        require(evidence["reaper_sha256"] == "cee99a74fdd9fc87974c96ea334a50afff4ca8d3121591aed218057bb38185e4", "REAPER hash drift")
        require(evidence["workspace_status_sha256"] == "765bac01283962461cded9984a1bb3147df908a6e1d3302579e003153af791ed", "workspace status hash drift")
        require(evidence["apt_candidate"] == "1.0.0-1", "APT candidate drift")
        require(evidence["package_installed"] is False, "trust-root admission may not claim package installation")

        admission = d["admission"]
        require(admission["state"] == "trust-root-admitted", "admission state drift")
        require(admission["repository_snapshot_verified"] is True, "repository snapshot must remain verified")
        require(admission["consumer_trust_root_admitted"] is True, "trust root must be admitted")
        require(admission["apt_source_activation_admitted"] is True, "APT source activation must be admitted")
        require(admission["package_install_admitted"] is False, "package install must remain a separate transaction")
        require(admission["pending_gate"] == "signed-package-install-reaper-workspace-status-1.0.0-1", "pending package gate drift")
    except (OSError, KeyError, json.JSONDecodeError, ValueError) as exc:
        print(f"package-source binding verification failed: {exc}", file=sys.stderr)
        return 1
    print("Private Debian repository admitted trust-root binding verification PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
