from __future__ import annotations

import importlib.machinery
import importlib.util
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RENDER = ROOT / "scripts" / "reaper-render.py"
CLI = ROOT / "bin" / "reaperctl"

loader = importlib.machinery.SourceFileLoader("reaper_render_test_module", str(RENDER))
spec = importlib.util.spec_from_loader(loader.name, loader)
assert spec is not None
render = importlib.util.module_from_spec(spec)
sys.modules[loader.name] = render
loader.exec_module(render)


class ReaperRenderTests(unittest.TestCase):
    def test_patch_forces_48k_stereo_and_preserves_range_values(self) -> None:
        source = """<REAPER_PROJECT 0.1 \"7.79/linux-x86_64\" 174
  RENDER_FILE \"\"
  RENDER_PATTERN \"old\"
  RENDER_FMT 0 2 0
  RENDER_RANGE 3 1 2 3 4
>
"""
        patched = render.patch_render_project(source, Path("/tmp/output.wav"))
        self.assertIn('  RENDER_FILE "/tmp/output.wav"', patched)
        self.assertIn('  RENDER_PATTERN ""', patched)
        self.assertIn('  RENDER_FMT 0 2 48000', patched)
        self.assertIn('  RENDER_RANGE 1 1 2 3 4', patched)
        self.assertIn('  RENDER_FILE ""', source)

    def test_patch_rejects_non_wav(self) -> None:
        source = '  RENDER_FILE ""\n  RENDER_PATTERN ""\n  RENDER_FMT 0 2 0\n  RENDER_RANGE 1 0 0 0 1000\n'
        with self.assertRaisesRegex(ValueError, "wav"):
            render.patch_render_project(source, Path("/tmp/output.flac"))

    def test_wave_verifier_accepts_48k_stereo_24bit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ok.wav"
            with wave.open(str(path), "wb") as handle:
                handle.setnchannels(2)
                handle.setsampwidth(3)
                handle.setframerate(48000)
                handle.writeframes((b"\x01\x00\x00\xff\xff\xff") * 480)
            report = render.verify_rendered_wave(path)
        self.assertEqual(report["sample_rate_hz"], 48000)
        self.assertEqual(report["channels"], 2)
        self.assertEqual(report["sample_width_bytes"], 3)
        self.assertTrue(report["non_silent"])

    def test_wave_verifier_rejects_44100(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.wav"
            with wave.open(str(path), "wb") as handle:
                handle.setnchannels(2)
                handle.setsampwidth(3)
                handle.setframerate(44100)
                handle.writeframes((b"\x01\x00\x00\xff\xff\xff") * 441)
            with self.assertRaisesRegex(RuntimeError, "sample-rate regression"):
                render.verify_rendered_wave(path)

    def test_dispatcher_exposes_render_help(self) -> None:
        result = subprocess.run(
            [str(CLI), "render", "--help"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--output", result.stdout)
        self.assertIn("48 kHz", result.stdout)


if __name__ == "__main__":
    unittest.main()
