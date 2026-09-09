#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BINDING = ROOT / "package-sources" / "reaper-debian-repo.json"
INSTALL = ROOT / "os" / "install" / "install-reaper-workspace-status-package.sh"
ROLLBACK = ROOT / "os" / "rollback" / "rollback-reaper-workspace-status-package.sh"
MANIFEST = ROOT / "evidence" / "system-changes" / "SYSTEM-CHANGE-2026-09-08-reaper-workspace-status-package.json"
SHA64 = set("0123456789abcdef")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def valid_sha(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in SHA64 for c in value)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    try:
        d = json.loads(BINDING.read_text(encoding="utf-8"))
        require(d.get("schema_version") == 1, "schema version drift")
        require(d.get("source_kind") == "private_debian_repository", "source kind drift")

        repo = d["repository"]
        require(repo["full_name"] == "taylorfrey529-ai/reaper-debian-repo", "repository name drift")
        require(repo["repository_id"] == "1362017734", "repository id drift")
        require(repo["visibility"] == "private" and repo["default_branch"] == "main", "repository authority drift")
        require(repo["bound_bootstrap_commit"] == "57afcc6dc995aae69bec1c663a2e4885b2ddc9c0", "bootstrap commit drift")
        require(repo["bootstrap_ci_run_id"] == "34293034792" and repo["bootstrap_ci_conclusion"] == "success", "bootstrap CI drift")
        require(repo["bound_snapshot_commit"] == "fcd3b1097c67dd57b5f9437ffa1952a784b61cd3", "snapshot commit drift")
        require(repo["snapshot_ci_run_id"] == "34294140407" and repo["snapshot_ci_conclusion"] == "success", "snapshot CI drift")

        consumer = d["consumer"]
        require(consumer["repository"] == "taylorfrey529-ai/reaper-golden-master" and consumer["branch"] == "full-os-mutable-layer", "consumer drift")
        require(consumer["admitted_from_candidate_branch"] == "candidate/reaper-debian-signing-key", "candidate branch drift")
        require(consumer["admitted_candidate_commit"] == "edee08555683c72d726345e94b404d17b32ab1aa", "candidate commit drift")
        require(consumer["candidate_ci_run_id"] == "34294605562" and consumer["candidate_ci_conclusion"] == "success", "candidate CI drift")
        require(consumer["owner_approved"] is True and consumer["policy"] == "MUTABILITY.json", "owner admission drift")

        compat = d["compatibility"]
        require((compat["os"], compat["release"], compat["codename"], compat["architecture"], compat["suite"], compat["component"]) ==
                ("Debian GNU/Linux", "13", "trixie", "amd64", "trixie", "main"), "compatibility drift")
        transport = d["transport"]
        require(transport["github_access"] == "authenticated_private_snapshot_sync", "GitHub transport drift")
        require(transport["apt_access"] == "local_file_repository", "APT transport drift")
        require(transport["local_root"] == "/mnt/data/reaper-apt-repository" and transport["local_uri"] == "file:/mnt/data/reaper-apt-repository", "local repository drift")
        require(transport["github_credentials_in_apt_configuration_allowed"] is False, "GitHub credentials may not enter APT configuration")

        snap = d["snapshot"]
        require(snap["state"] == "admitted-private-snapshot" and snap["snapshot_id"] == "2026-09-09.1", "snapshot admission drift")
        require(snap["snapshot_manifest_sha256"] == "51be57e06807e179f13da827fd0ca91041d384960866f6180682ff51faf19d56", "snapshot manifest drift")
        require((snap["package_name"], snap["package_version"], snap["package_architecture"]) == ("reaper-workspace-status", "1.0.0-1", "all"), "package identity drift")
        require(snap["package_sha256"] == "a2f5fa8679720368b30377d10a541f8dd95cddfa9d8e5b39e6b433f0e346fe8b", "package hash drift")
        require(snap["package_payload_sha256"] == "765bac01283962461cded9984a1bb3147df908a6e1d3302579e003153af791ed", "package payload drift")

        trust = d["trust"]
        require(trust["repository_signing_required"] is True and trust["signing_key_status"] == "admitted-active", "signing state drift")
        require(trust["signing_key_fingerprint"] == "EAE567EB437C007F46A58BDCA76356FF985B3F3B", "signing fingerprint drift")
        require(trust["public_key_sha256"] == "7dc135b64febe59163cd293718cb02e2a2b3ad9ffe7ec01ecf9d9c93ec10e077", "public key drift")
        require(trust["signed_by_scope_required"] is True and trust["trust_root_installed_on_live_os"] is True, "trust-root state drift")
        require(trust["trust_root_path"] == "/etc/apt/keyrings/reaper-debian-repo.gpg", "trust-root path drift")
        require(trust["apt_source_path"] == "/etc/apt/sources.list.d/reaper-debian-repo.sources", "APT source path drift")
        require(trust["apt_source_sha256"] == "1701fdeb0a0d68cc3f8da5b1a6058e4dc985e1f683101e9fba884bafb7aee9d2", "APT source hash drift")
        require(trust["trust_root_change_requires_candidate"] is True, "future trust-root candidate gate missing")
        require(trust["unsigned_packages_allowed"] is False and trust["unsigned_release_metadata_allowed"] is False, "signature invariant weakened")

        evidence = d["live_evidence"]
        for key in (
            "trust_root_admission_package_inventory_sha256", "package_pre_inventory_sha256",
            "package_post_inventory_sha256", "package_rollback_inventory_sha256",
            "listener_inventory_sha256", "project_sha256", "reaper_sha256",
            "workspace_status_usr_local_sha256", "workspace_status_usr_bin_sha256",
            "apt_update_output_sha256", "apt_install_output_sha256",
            "apt_purge_rehearsal_output_sha256", "guarded_rollback_output_sha256",
            "guarded_reinstall_output_sha256", "install_script_sha256", "rollback_script_sha256",
        ):
            require(valid_sha(evidence[key]), f"invalid evidence hash: {key}")
        require(evidence["package_pre_inventory_sha256"] == "c82d5c8c3a85896e1f0fabac3adc5ec5d54a54fee4703ca73a5e6867d302f3a3", "pre-package inventory drift")
        require(evidence["package_post_inventory_sha256"] == "2b265ff8b859e8413e82c37eda59c315621833713c3cae46635726a608ba228a", "post-package inventory drift")
        require(evidence["package_rollback_inventory_sha256"] == evidence["package_pre_inventory_sha256"], "rollback did not restore pre-package inventory")
        require(evidence["listener_inventory_sha256"] == "69b15352b7611ce5e030771733d63726b6392b86aa11d746b87531315ae64d0a", "listener inventory drift")
        require(evidence["project_sha256"] == "2ea85263d6dc125bf7739264956a1ee1a8074c2b42f69b606b5e9d8b7e9771f1", "project hash drift")
        require(evidence["reaper_sha256"] == "cee99a74fdd9fc87974c96ea334a50afff4ca8d3121591aed218057bb38185e4", "REAPER hash drift")
        require(evidence["workspace_status_usr_local_sha256"] == "765bac01283962461cded9984a1bb3147df908a6e1d3302579e003153af791ed", "usr-local payload drift")
        require(evidence["workspace_status_usr_bin_sha256"] == evidence["workspace_status_usr_local_sha256"], "installed payload differs from approved utility")
        require(evidence["package_installed"] is True, "package install not recorded")
        require((evidence["installed_package_name"], evidence["installed_package_version"], evidence["installed_package_architecture"]) ==
                ("reaper-workspace-status", "1.0.0-1", "all"), "installed package metadata drift")
        require(sha256(INSTALL) == evidence["install_script_sha256"] == "6a203406c79076b398e56157dd91293e43b1badb8747b9e37b17d376f11263d7", "installer byte drift")
        require(sha256(ROLLBACK) == evidence["rollback_script_sha256"] == "46b33820bf5481a594159b2da48a20851f763293bb0a1579cac1c8f32c4a9c8f", "rollback byte drift")

        m = json.loads(MANIFEST.read_text(encoding="utf-8"))
        require(m["operation"] == "install-signed-reaper-workspace-status-package" and m["classification"] == "mutable", "package manifest drift")
        require(m["pre_state"]["package_inventory_sha256"] == evidence["package_pre_inventory_sha256"], "manifest pre-inventory drift")
        require(m["post_state"]["package_inventory_sha256"] == evidence["package_post_inventory_sha256"], "manifest post-inventory drift")
        require(m["verification"]["result"] == "PASS" and m["verification"]["golden_master_unchanged"] is True and m["verification"]["security_invariants_preserved"] is True, "package verification evidence invalid")

        admission = d["admission"]
        require(admission["state"] == "signed-package-installed", "admission state drift")
        require(admission["repository_snapshot_verified"] is True, "repository snapshot verification lost")
        require(admission["consumer_trust_root_admitted"] is True and admission["apt_source_activation_admitted"] is True, "trust admission lost")
        require(admission["package_install_admitted"] is True and admission["package_install_verified"] is True, "package admission incomplete")
        require(admission["rollback_rehearsed"] is True, "rollback rehearsal missing")
        require(admission["pending_gate"] == "next-signed-package-or-os-transaction", "continuation cursor drift")
    except (OSError, KeyError, json.JSONDecodeError, ValueError) as exc:
        print(f"package-source binding verification failed: {exc}", file=sys.stderr)
        return 1
    print("Private Debian repository signed package binding verification PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
