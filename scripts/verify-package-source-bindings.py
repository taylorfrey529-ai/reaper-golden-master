#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BINDING = ROOT / "package-sources" / "reaper-debian-repo.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


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
        commit = repo["bound_bootstrap_commit"]
        require(isinstance(commit, str) and len(commit) == 40 and all(c in "0123456789abcdef" for c in commit), "invalid bound commit")
        require(repo["bootstrap_ci_run_id"] == "34293034792", "bootstrap CI run drift")
        require(repo["bootstrap_ci_conclusion"] == "success", "bootstrap CI must be successful")
        consumer = d["consumer"]
        require(consumer["repository"] == "taylorfrey529-ai/reaper-golden-master", "consumer repository drift")
        require(consumer["branch"] == "full-os-mutable-layer", "consumer branch drift")
        compat = d["compatibility"]
        require((compat["os"], compat["release"], compat["codename"], compat["architecture"]) == ("Debian GNU/Linux", "13", "trixie", "amd64"), "compatibility drift")
        transport = d["transport"]
        require(transport["github_access"] == "authenticated_private_snapshot_sync", "GitHub transport drift")
        require(transport["apt_access"] == "local_file_repository", "APT transport drift")
        require(transport["local_root"] == "/mnt/data/reaper-apt-repository", "local repository root drift")
        require(transport["github_credentials_in_apt_configuration_allowed"] is False, "GitHub credentials may not enter APT configuration")
        trust = d["trust"]
        require(trust["repository_signing_required"] is True, "repository signing must remain required")
        require(trust["signing_key_status"] == "pending-admission", "bootstrap signing state drift")
        require(trust["signing_key_fingerprint"] is None, "bootstrap must not claim a signing key")
        require(trust["signed_by_scope_required"] is True, "Signed-By scoping must remain required")
        require(trust["trust_root_installed_on_live_os"] is False, "bootstrap binding must not claim live trust-root installation")
        require(trust["trust_root_change_requires_candidate"] is True, "trust-root candidate gate missing")
        require(trust["unsigned_packages_allowed"] is False, "unsigned packages cannot be admitted")
        require(trust["unsigned_release_metadata_allowed"] is False, "unsigned Release metadata cannot be admitted")
        admission = d["admission"]
        require(admission["state"] == "bootstrap-bound", "admission state drift")
        require(admission["package_snapshot_admitted"] is False, "bootstrap cannot claim package snapshot admission")
        require(admission["apt_source_activation_admitted"] is False, "bootstrap cannot activate APT source")
        require(admission["pending_gate"] == "signing-key-admission-and-first-signed-snapshot", "pending gate drift")
    except (OSError, KeyError, json.JSONDecodeError, ValueError) as exc:
        print(f"package-source binding verification failed: {exc}", file=sys.stderr)
        return 1
    print("Private Debian repository binding verification PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
