from __future__ import annotations

import hashlib
import importlib.machinery
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "reaper-rollback.py"
BASELINE = ROOT / "BASELINE.json"
MUTABILITY = ROOT / "MUTABILITY.json"

loader = importlib.machinery.SourceFileLoader("reaper_rollback_test_module", str(SCRIPT))
spec = importlib.util.spec_from_loader(loader.name, loader)
assert spec is not None
rollback = importlib.util.module_from_spec(spec)
sys.modules[loader.name] = rollback
loader.exec_module(rollback)


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def make_receipt(root: Path, project: Path, before: bytes, after: bytes, policy_sha: str) -> tuple[Path, Path]:
    rollback_root = root / "evidence" / "mutations"
    rollback_root.mkdir(parents=True)
    artifact = rollback_root / f"{project.name}.before-{digest(before)}.rpp"
    artifact.write_bytes(before)
    receipt = rollback_root / "mutation-test-pan-drums.json"
    receipt.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "operation": "pan-drums",
                "project": str(project.resolve()),
                "before_sha256": digest(before),
                "after_sha256": digest(after),
                "rollback_artifact": str(artifact.resolve()),
                "rollback_sha256": digest(before),
                "mutability_policy_sha256": policy_sha,
                "atomic_replace": True,
                "postwrite_hash_verified": True,
                "rollback_verified": True,
            }
        ),
        encoding="utf-8",
    )
    return receipt, artifact


class ReaperRollbackTests(unittest.TestCase):
    def test_successful_receipt_rollback_restores_before_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            project = workspace / "project.rpp"
            before = b"before-state\n"
            after = b"after-state\n"
            project.write_bytes(after)
            policy_sha = "a" * 64
            receipt, _ = make_receipt(workspace, project, before, after, policy_sha)
            rollback_root = workspace / "evidence" / "mutations"

            result = rollback.execute_rollback(project, receipt, rollback_root, policy_sha)

            self.assertEqual(project.read_bytes(), before)
            self.assertEqual(result["from_sha256"], digest(after))
            self.assertEqual(result["to_sha256"], digest(before))
            self.assertEqual(result["result"], "PASS")
            pre_rollback = Path(result["pre_rollback_artifact"])
            self.assertEqual(pre_rollback.read_bytes(), after)
            self.assertEqual(rollback.sha256(pre_rollback), digest(after))
            rollback_receipt = Path(result["receipt"])
            self.assertTrue(rollback_receipt.is_file())
            record = json.loads(rollback_receipt.read_text(encoding="utf-8"))
            self.assertTrue(record["atomic_replace"])
            self.assertTrue(record["postwrite_hash_verified"])

    def test_stale_current_project_is_rejected_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            project = workspace / "project.rpp"
            before = b"before\n"
            after = b"after\n"
            later = b"later-edit\n"
            project.write_bytes(later)
            policy_sha = "b" * 64
            receipt, _ = make_receipt(workspace, project, before, after, policy_sha)
            rollback_root = workspace / "evidence" / "mutations"

            with self.assertRaises(RuntimeError):
                rollback.execute_rollback(project, receipt, rollback_root, policy_sha)
            self.assertEqual(project.read_bytes(), later)

    def test_tampered_rollback_artifact_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            project = workspace / "project.rpp"
            before = b"before\n"
            after = b"after\n"
            project.write_bytes(after)
            policy_sha = "c" * 64
            receipt, artifact = make_receipt(workspace, project, before, after, policy_sha)
            artifact.write_bytes(b"tampered\n")
            rollback_root = workspace / "evidence" / "mutations"

            with self.assertRaises(RuntimeError):
                rollback.execute_rollback(project, receipt, rollback_root, policy_sha)
            self.assertEqual(project.read_bytes(), after)

    def test_receipt_outside_mutation_evidence_root_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            project = workspace / "project.rpp"
            before = b"before\n"
            after = b"after\n"
            project.write_bytes(after)
            rollback_root = workspace / "evidence" / "mutations"
            rollback_root.mkdir(parents=True)
            artifact = rollback_root / "before.rpp"
            artifact.write_bytes(before)
            outside = workspace / "outside-receipt.json"
            outside.write_text("{}", encoding="utf-8")

            with self.assertRaises(ValueError):
                rollback.load_receipt(outside, rollback_root, project, "d" * 64)

    def test_main_refuses_running_reaper_without_live_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            project = workspace / "project.rpp"
            project.write_bytes(b"current\n")
            paths = {
                "workspace": workspace,
                "project": project,
                "reaper": workspace / "reaper",
            }
            with mock.patch.object(rollback.core, "workspace_paths", return_value=paths), mock.patch.object(
                rollback.core, "discover_process_pids", return_value=[4242]
            ):
                code = rollback.main(
                    [
                        "--baseline",
                        str(BASELINE),
                        "--mutability",
                        str(MUTABILITY),
                        "--receipt",
                        str(workspace / "evidence" / "mutations" / "unused.json"),
                    ]
                )
            self.assertEqual(code, 2)
            self.assertEqual(project.read_bytes(), b"current\n")


if __name__ == "__main__":
    unittest.main()
