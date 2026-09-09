#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BINDING = ROOT / "package-sources" / "reaper-debian-repo.json"
STATUS_INSTALL = ROOT / "os" / "install" / "install-reaper-workspace-status-package.sh"
STATUS_ROLLBACK = ROOT / "os" / "rollback" / "rollback-reaper-workspace-status-package.sh"
STATUS_MANIFEST = ROOT / "evidence" / "system-changes" / "SYSTEM-CHANGE-2026-09-08-reaper-workspace-status-package.json"
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
        require(d.get("schema_version") == 1 and d.get("source_kind") == "private_debian_repository", "binding schema drift")
        repo = d["repository"]
        require(repo["full_name"] == "taylorfrey529-ai/reaper-debian-repo", "repository name drift")
        require(repo["repository_id"] == "1362017734" and repo["visibility"] == "private" and repo["default_branch"] == "main", "repository authority drift")
        require(repo["bound_bootstrap_commit"] == "57afcc6dc995aae69bec1c663a2e4885b2ddc9c0", "bootstrap commit drift")
        require(repo["bootstrap_ci_run_id"] == "34293034792" and repo["bootstrap_ci_conclusion"] == "success", "bootstrap CI drift")
        require(repo["previous_snapshot_commit"] == "fcd3b1097c67dd57b5f9437ffa1952a784b61cd3", "previous snapshot commit drift")
        require(repo["previous_snapshot_ci_run_id"] == "34294140407" and repo["previous_snapshot_ci_conclusion"] == "success", "previous snapshot CI drift")
        require(repo["bound_snapshot_commit"] == "c38254474dd09a06c316423d4f1f6f3adaf79b46", "bound snapshot commit drift")
        require(repo["snapshot_ci_run_id"] == "34298118058" and repo["snapshot_ci_conclusion"] == "success", "snapshot CI drift")

        consumer = d["consumer"]
        require(consumer["repository"] == "taylorfrey529-ai/reaper-golden-master" and consumer["branch"] == "full-os-mutable-layer", "consumer drift")
        require(consumer["admitted_candidate_commit"] == "edee08555683c72d726345e94b404d17b32ab1aa", "trust-root candidate drift")
        require(consumer["candidate_ci_run_id"] == "34294605562" and consumer["candidate_ci_conclusion"] == "success", "candidate CI drift")
        require(consumer["owner_approved"] is True and consumer["policy"] == "MUTABILITY.json", "owner admission drift")

        compat = d["compatibility"]
        require((compat["os"], compat["release"], compat["codename"], compat["architecture"], compat["suite"], compat["component"]) ==
                ("Debian GNU/Linux", "13", "trixie", "amd64", "trixie", "main"), "compatibility drift")
        transport = d["transport"]
        require(transport["github_access"] == "authenticated_private_snapshot_sync" and transport["apt_access"] == "local_file_repository", "transport drift")
        require(transport["local_root"] == "/mnt/data/reaper-apt-repository" and transport["local_uri"] == "file:/mnt/data/reaper-apt-repository", "local repository drift")
        require(transport["github_credentials_in_apt_configuration_allowed"] is False, "GitHub credentials may not enter APT configuration")

        snap = d["snapshot"]
        require(snap["state"] == "admitted-private-snapshot" and snap["snapshot_id"] == "2026-09-09.2", "snapshot admission drift")
        require(snap["previous_snapshot_id"] == "2026-09-09.1", "previous snapshot id drift")
        require(snap["previous_snapshot_manifest_sha256"] == "51be57e06807e179f13da827fd0ca91041d384960866f6180682ff51faf19d56", "previous manifest drift")
        require(snap["snapshot_manifest_sha256"] == "9c14b692ade5ea52a3a8e0460e584cc363ae1cbd864cb6439f81b8753cf6f647", "snapshot manifest drift")
        packages = {p["name"]: p for p in snap["packages"]}
        require(set(packages) == {"reaper-workspace-status", "reaperctl"}, "snapshot package set drift")
        status = packages["reaper-workspace-status"]
        require((status["version"], status["architecture"], status["deb_sha256"], status["installed"]) ==
                ("1.0.0-1", "all", "a2f5fa8679720368b30377d10a541f8dd95cddfa9d8e5b39e6b433f0e346fe8b", True), "status package drift")
        ctl = packages["reaperctl"]
        require((ctl["version"], ctl["architecture"], ctl["deb_sha256"], ctl["installed"]) ==
                ("0.2.0-1", "all", "5fe9b91748c600e85623d8341a8ad619e62f7f80c5c4bfce40d3ac39e71361d9", False), "reaperctl package drift")
        require(ctl["source_repository"] == "taylorfrey529-ai/reaper-golden-master" and ctl["source_commit"] == "0e657d7f76665a1ea9b61f7426f8c82986d83c43", "reaperctl source provenance drift")
        require(ctl["build_commit"] == "466bef73a53f89e08fa8d07d9f166203d101c62f" and ctl["build_run_id"] == "34296813002", "reaperctl build provenance drift")

        trust = d["trust"]
        require(trust["repository_signing_required"] is True and trust["signing_key_status"] == "admitted-active", "signing state drift")
        require(trust["signing_key_fingerprint"] == "EAE567EB437C007F46A58BDCA76356FF985B3F3B", "signing fingerprint drift")
        require(trust["public_key_sha256"] == "7dc135b64febe59163cd293718cb02e2a2b3ad9ffe7ec01ecf9d9c93ec10e077", "public key drift")
        require(trust["trust_root_installed_on_live_os"] is True and trust["signed_by_scope_required"] is True, "trust-root state drift")
        require(trust["trust_root_path"] == "/etc/apt/keyrings/reaper-debian-repo.gpg" and trust["apt_source_path"] == "/etc/apt/sources.list.d/reaper-debian-repo.sources", "trust-root path drift")
        require(trust["apt_source_sha256"] == "1701fdeb0a0d68cc3f8da5b1a6058e4dc985e1f683101e9fba884bafb7aee9d2", "APT source drift")
        require(trust["trust_root_change_requires_candidate"] is True and trust["unsigned_packages_allowed"] is False and trust["unsigned_release_metadata_allowed"] is False, "trust invariant weakened")

        evidence = d["live_evidence"]
        require(evidence["local_repository_present"] is True, "local repo evidence missing")
        require(evidence["local_repository_snapshot_id"] == "2026-09-09.1", "live repo must remain prior snapshot before sync")
        require(evidence["local_repository_snapshot_manifest_sha256"] == "51be57e06807e179f13da827fd0ca91041d384960866f6180682ff51faf19d56", "live prior manifest drift")
        for key in ("package_inventory_sha256", "listener_inventory_sha256", "project_sha256", "reaper_sha256", "workspace_status_usr_local_sha256", "workspace_status_usr_bin_sha256"):
            require(valid_sha(evidence[key]), f"invalid live evidence hash: {key}")
        require(evidence["package_inventory_sha256"] == "2b265ff8b859e8413e82c37eda59c315621833713c3cae46635726a608ba228a", "package inventory drift")
        require(evidence["listener_inventory_sha256"] == "69b15352b7611ce5e030771733d63726b6392b86aa11d746b87531315ae64d0a", "listener drift")
        require(evidence["project_sha256"] == "2ea85263d6dc125bf7739264956a1ee1a8074c2b42f69b606b5e9d8b7e9771f1", "project drift")
        require(evidence["reaper_sha256"] == "cee99a74fdd9fc87974c96ea334a50afff4ca8d3121591aed218057bb38185e4", "REAPER drift")
        require(evidence["workspace_status_usr_local_sha256"] == evidence["workspace_status_usr_bin_sha256"] == "765bac01283962461cded9984a1bb3147df908a6e1d3302579e003153af791ed", "status utility drift")
        require(evidence["reaper_workspace_status_installed"] is True and evidence["reaperctl_installed"] is False, "live package-state drift")

        require(sha256(STATUS_INSTALL) == "6a203406c79076b398e56157dd91293e43b1badb8747b9e37b17d376f11263d7", "status installer drift")
        require(sha256(STATUS_ROLLBACK) == "46b33820bf5481a594159b2da48a20851f763293bb0a1579cac1c8f32c4a9c8f", "status rollback drift")
        m = json.loads(STATUS_MANIFEST.read_text(encoding="utf-8"))
        require(m["verification"]["result"] == "PASS" and m["verification"]["golden_master_unchanged"] is True and m["verification"]["security_invariants_preserved"] is True, "existing status package evidence invalid")

        admission = d["admission"]
        require(admission["state"] == "signed-snapshot-bound-pending-package-install", "admission state drift")
        require(admission["repository_snapshot_verified"] is True and admission["consumer_trust_root_admitted"] is True and admission["apt_source_activation_admitted"] is True, "admission prerequisites lost")
        require(admission["snapshot_sync_pending"] is True, "snapshot sync must remain pending before live transaction")
        require(admission["package_install_admitted"] is False and admission["package_install_verified"] is False and admission["rollback_rehearsed"] is False, "reaperctl install may not be pre-claimed")
        require(admission["pending_gate"] == "sync-snapshot-2026-09-09.2-and-install-reaperctl-0.2.0-1", "continuation cursor drift")
    except (OSError, KeyError, json.JSONDecodeError, ValueError) as exc:
        print(f"package-source binding verification failed: {exc}", file=sys.stderr)
        return 1
    print("Private Debian repository snapshot 2026-09-09.2 binding verification PASSED (reaperctl install pending)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
