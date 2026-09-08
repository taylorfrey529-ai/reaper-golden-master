import hashlib, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
EXPECTED={
    'recovery/workspace/desktop_shell.py':'fe9ec0d07212f7b079290d6d56d41e50f611f5208cfd1f2be9e3ee6d3c62c01d',
    'recovery/workspace/start-desktop.sh':'6a9675261b768a306afe6a5281b7d5704118d65ba2414ee0e0cf57c678b68a92',
    'recovery/workspace/stop-desktop.sh':'6508312f320c3e9665996965d54da75a8917551cbc64e3f592aa0170dd531642',
}

class RecoveryWorkspaceTests(unittest.TestCase):
    def test_r2_recovery_bytes(self):
        for relative,expected in EXPECTED.items():
            path=ROOT/relative
            self.assertTrue(path.is_file(),relative)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),expected,relative)
    def test_asset_parent_creation_is_explicit(self):
        text=(ROOT/'recovery/workspace/desktop_shell.py').read_text()
        self.assertIn("WALLPAPER.parent.mkdir(parents=True, exist_ok=True)",text)
    def test_xvfb_pid_files_are_advisory(self):
        start=(ROOT/'recovery/workspace/start-desktop.sh').read_text()
        stop=(ROOT/'recovery/workspace/stop-desktop.sh').read_text()
        self.assertIn('existing_xvfb=$(pgrep -f',start)
        self.assertIn('# PID files are advisory',stop)
        self.assertIn('^Xvfb :${DISPLAY_NUM} ',stop)

if __name__=='__main__':unittest.main()
