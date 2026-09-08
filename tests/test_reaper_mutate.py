from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "reaper-mutate.py"
MUTABILITY = ROOT / "MUTABILITY.json"

loader = importlib.machinery.SourceFileLoader("reaper_mutate_test_module", str(SCRIPT))
spec = importlib.util.spec_from_loader(loader.name, loader)
assert spec is not None
mutate = importlib.util.module_from_spec(spec)
sys.modules[loader.name] = mutate
loader.exec_module(mutate)


class ReaperMutateTests(unittest.TestCase):
    def test_policy_loads_with_security_guards_enabled(self) -> None:
        data = mutate.load_mutability(MUTABILITY)
        self.assertEqual(data["mode"], "secure_mutable_continuation")
        self.assertFalse(data["mutation_policy"]["silent_mutation_allowed"])
        self.assertFalse(data["security_invariants"]["path_traversal_allowed"])
        self.assertFalse(data["security_invariants"]["license_or_evaluation_bypass_allowed"])

    def test_confined_project_rejects_outside_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            workspace.mkdir()
            outside = root / "outside.rpp"
            outside.write_text("outside", encoding="utf-8")
            with self.assertRaises(ValueError):
                mutate.confined_project(outside, workspace)

    def test_confined_project_rejects_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            workspace.mkdir()
            real = workspace / "real.rpp"
            real.write_text("real", encoding="utf-8")
            link = workspace / "link.rpp"
            try:
                link.symlink_to(real)
            except OSError:
                self.skipTest("symlinks unavailable")
            with self.assertRaises(ValueError):
                mutate.confined_project(link, workspace)

    def test_commit_candidate_creates_verified_rollback_and_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            workspace.mkdir()
            project = workspace / "project.rpp"
            candidate = workspace / "candidate.rpp"
            rollback = workspace / "evidence" / "mutations"
            project.write_bytes(b"before-state\n")
            candidate.write_bytes(b"after-state\n")
            os.chmod(project, 0o640)

            result = mutate.commit_candidate(
                project,
                candidate,
                rollback,
                "pan-drums",
                "policy-sha",
            )

            self.assertEqual(project.read_bytes(), b"after-state\n")
            self.assertFalse(candidate.exists())
            backup = Path(result["rollback_artifact"])
            receipt = Path(result["receipt"])
            self.assertEqual(backup.read_bytes(), b"before-state\n")
            self.assertEqual(mutate.sha256(backup), result["before_sha256"])
            self.assertEqual(mutate.sha256(project), result["after_sha256"])
            self.assertTrue(receipt.is_file())
            receipt_data = json.loads(receipt.read_text(encoding="utf-8"))
            self.assertTrue(receipt_data["atomic_replace"])
            self.assertTrue(receipt_data["postwrite_hash_verified"])
            self.assertTrue(receipt_data["rollback_verified"])
            self.assertEqual(receipt_data["mutability_policy_sha256"], "policy-sha")

    def test_backup_collision_with_wrong_bytes_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project.rpp"
            candidate = root / "candidate.rpp"
            rollback = root / "rollback"
            project.write_bytes(b"before\n")
            candidate.write_bytes(b"after\n")
            original_sha = mutate.sha256(project)
            rollback.mkdir()
            collision = rollback / f"{project.name}.before-{original_sha}.rpp"
            collision.write_bytes(b"tampered\n")
            with self.assertRaises(RuntimeError):
                mutate.commit_candidate(project, candidate, rollback, "pan-drums", "policy-sha")
            self.assertEqual(project.read_bytes(), b"before\n")


if __name__ == "__main__":
    unittest.main()
