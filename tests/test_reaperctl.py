from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin" / "reaperctl"
BASELINE = ROOT / "BASELINE.json"

loader = importlib.machinery.SourceFileLoader("reaperctl_module", str(CLI))
spec = importlib.util.spec_from_loader(loader.name, loader)
assert spec is not None
reaperctl = importlib.util.module_from_spec(spec)
sys.modules[loader.name] = reaperctl
loader.exec_module(reaperctl)


class FakeReaperHandler(BaseHTTPRequestHandler):
    state = 0
    action_log: list[int] = []

    def do_GET(self) -> None:  # noqa: N802
        command = self.path.removeprefix("/_/").rstrip(";")
        if command == "TRANSPORT":
            body = f"TRANSPORT\t{type(self).state}\t1.250\t0\t0:01.250\t1.2.00\n"
            self.send_response(200)
            self.end_headers()
            self.wfile.write(body.encode())
            return
        if command == "1007":
            type(self).state = 1
            type(self).action_log.append(1007)
            self.send_response(200)
            self.end_headers()
            return
        if command == "1016":
            type(self).state = 0
            type(self).action_log.append(1016)
            self.send_response(200)
            self.end_headers()
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return


class FakeReaperServer:
    def __enter__(self) -> str:
        FakeReaperHandler.state = 0
        FakeReaperHandler.action_log = []
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeReaperHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        return f"http://{host}:{port}"

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


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

    def test_discovers_web_interface_from_reaper_ini(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reaper.ini"
            path.write_text("[reaper]\ncsurf_cnt=1\ncsurf_0=HTTP 0 8080 '' 'index.html' 0 ''\n", encoding="utf-8")
            self.assertEqual(reaperctl.discover_web_url_from_ini(path), "http://127.0.0.1:8080")

    def test_transport_parser(self) -> None:
        state = reaperctl.parse_transport_response("TRANSPORT\t1\t12.5\t1\t0:12.500\t4.1.00\n")
        self.assertEqual(state.playstate, 1)
        self.assertEqual(state.label, "playing")
        self.assertEqual(state.position_seconds, 12.5)
        self.assertTrue(state.repeat)

    def test_play_and_stop_are_state_confirmed_and_idempotent(self) -> None:
        with FakeReaperServer() as url:
            play = reaperctl.drive_transport(url, "play")
            self.assertTrue(play["confirmed"])
            self.assertTrue(play["changed"])
            self.assertEqual(play["action_id"], 1007)
            self.assertEqual(play["after"]["label"], "playing")

            play_again = reaperctl.drive_transport(url, "play")
            self.assertTrue(play_again["confirmed"])
            self.assertFalse(play_again["changed"])
            self.assertIsNone(play_again["action_id"])

            stop = reaperctl.drive_transport(url, "stop")
            self.assertTrue(stop["confirmed"])
            self.assertTrue(stop["changed"])
            self.assertEqual(stop["action_id"], 1016)
            self.assertEqual(stop["after"]["label"], "stopped")
            self.assertEqual(FakeReaperHandler.action_log, [1007, 1016])

    def test_remote_web_is_not_loopback(self) -> None:
        self.assertFalse(reaperctl.is_loopback_web_url("http://192.0.2.4:8080"))
        self.assertTrue(reaperctl.is_loopback_web_url("http://127.0.0.1:8080"))


if __name__ == "__main__":
    unittest.main()
