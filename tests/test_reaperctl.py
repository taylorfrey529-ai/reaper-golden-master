from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin" / "reaperctl"
BASELINE = ROOT / "BASELINE.json"


class ReaperCtlTests(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(CLI), *args],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_baseline_json_reports_admitted_identity(self) -> None:
        result = self.run_cli("baseline", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["baseline"]["golden_master"], "GM-2026-09-08")
        self.assertEqual(
            data["baseline"]["golden_master_id"],
            "sha256:74a13a11fe232bca5bd8a320d11ee0c2e17ce5c2e53d76c74ee9714276a95b1f",
        )
        self.assertEqual(data["continuity_locks"]["linux_audio_mode"], 1)
        self.assertEqual(data["continuity_locks"]["interface"], "apollo_spdif")

    def test_static_health_passes(self) -> None:
        result = self.run_cli("health", "--static", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["ok"])
        self.assertEqual(report["scope"], "static")
        self.assertTrue(all(check["ok"] for check in report["checks"]))

    def test_static_health_rejects_audio_mode_regression(self) -> None:
        data = json.loads(BASELINE.read_text(encoding="utf-8"))
        data["continuity_locks"]["linux_audio_mode"] = 0
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "BASELINE.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            result = self.run_cli("--baseline", str(path), "health", "--static", "--json")
        self.assertEqual(result.returncode, 1)
        report = json.loads(result.stdout)
        lock_check = next(check for check in report["checks"] if check["name"] == "continuity_locks")
        self.assertFalse(lock_check["ok"])
        self.assertIn("linux_audio_mode", lock_check["detail"])

    def test_invalid_baseline_returns_usage_error_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "BASELINE.json"
            path.write_text("not-json", encoding="utf-8")
            result = self.run_cli("--baseline", str(path), "health", "--static")
        self.assertEqual(result.returncode, 2)
        self.assertIn("invalid baseline JSON", result.stderr)


if __name__ == "__main__":
    unittest.main()
