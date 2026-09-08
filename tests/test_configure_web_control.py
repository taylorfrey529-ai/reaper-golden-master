from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "configure-web-control.py"
spec = importlib.util.spec_from_file_location("configure_web_control", SCRIPT)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class ConfigureWebControlTests(unittest.TestCase):
    def test_plan_adds_first_surface(self) -> None:
        result = module.plan("[reaper]\nfoo=bar\n", 2307, "index.html")
        self.assertTrue(result["changed"])
        self.assertIn("csurf_cnt=1", result["text"])
        self.assertIn("csurf_0=HTTP 0 2307 '' 'index.html' 0 ''", result["text"])

    def test_plan_is_idempotent(self) -> None:
        text = "[reaper]\ncsurf_cnt=1\ncsurf_0=HTTP 0 2307 '' 'index.html' 0 ''\n"
        result = module.plan(text, 2307, "index.html")
        self.assertFalse(result["changed"])
        self.assertEqual(result["text"], text)

    def test_plan_refuses_different_http_surface(self) -> None:
        text = "[reaper]\ncsurf_cnt=1\ncsurf_0=HTTP 0 8080 '' 'index.html' 0 ''\n"
        with self.assertRaisesRegex(ValueError, "existing HTTP control surface differs"):
            module.plan(text, 2307, "index.html")

    def test_plan_preserves_non_http_surface_and_uses_next_index(self) -> None:
        text = "[reaper]\ncsurf_cnt=1\ncsurf_0=OSC 0 9000 127.0.0.1 9001 1024 10\n"
        result = module.plan(text, 2307, "index.html")
        self.assertTrue(result["changed"])
        self.assertIn("csurf_cnt=2", result["text"])
        self.assertIn("csurf_1=HTTP 0 2307 '' 'index.html' 0 ''", result["text"])
        self.assertIn("csurf_0=OSC 0 9000 127.0.0.1 9001 1024 10", result["text"])

    def test_apply_creates_backup_and_changes_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ini = root / "reaper.ini"
            backups = root / "backups"
            ini.write_text("[reaper]\nfoo=bar\n")
            before = module.sha256(ini)
            result = module.configure(ini, backups, 2307, "index.html", True)
            self.assertTrue(result["applied"])
            self.assertNotEqual(result["after_sha256"], before)
            backup = Path(str(result["backup"]))
            self.assertTrue(backup.is_file())
            self.assertEqual(module.sha256(backup), before)
            self.assertIn("csurf_0=HTTP 0 2307 '' 'index.html' 0 ''", ini.read_text())


if __name__ == "__main__":
    unittest.main()
