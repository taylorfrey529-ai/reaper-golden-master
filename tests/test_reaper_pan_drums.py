from __future__ import annotations
import importlib.machinery, importlib.util, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PATH=ROOT/'scripts'/'reaper-pan-drums.py'
loader=importlib.machinery.SourceFileLoader('pan_test_module',str(PATH)); spec=importlib.util.spec_from_loader(loader.name,loader); mod=importlib.util.module_from_spec(spec); sys.modules[loader.name]=mod; loader.exec_module(mod)

class DummyOH:
    sr=48000
    def __init__(self,left,right): self.data=[left,right]; self.frames=min(len(left),len(right))

class PanTests(unittest.TestCase):
    def test_track_word_is_not_rack_tom(self):
        self.assertFalse(mod.is_shell_name('8-Bar Drum Track - 120 BPM'))
        self.assertTrue(mod.is_shell_name('Rack 1'))
        self.assertTrue(mod.is_tom1_name('Tom 1 Test'))

    def test_equal_energy_is_center(self):
        oh=DummyOH([1.0]*3000,[1.0]*3000)
        m=mod.pan_measurement(oh,0.02)
        self.assertIsNotNone(m)
        self.assertAlmostEqual(m['pan'],0.0,places=9)

    def test_more_right_energy_pans_right(self):
        oh=DummyOH([0.5]*3000,[1.0]*3000)
        m=mod.pan_measurement(oh,0.02)
        self.assertIsNotNone(m)
        self.assertGreater(m['pan'],0.0)

    def test_rewrite_preserves_crlf_and_changes_only_shell_volpan(self):
        text=(
            '<REAPER_PROJECT 0.1 "7.79/linux-x86_64" 0 0\r\n'
            '  <TRACK {1}\r\n    NAME "OH Stereo Test"\r\n    VOLPAN 1 0 -1 -1 1\r\n  >\r\n'
            '  <TRACK {2}\r\n    NAME "Kick Test"\r\n    VOLPAN 1 0 -1 -1 1\r\n  >\r\n'
            '  <TRACK {3}\r\n    NAME "Snare Test"\r\n    VOLPAN 1 0 -1 -1 1\r\n  >\r\n'
            '>\r\n')
        with tempfile.TemporaryDirectory() as tmp:
            src=Path(tmp)/'in.RPP'; out=Path(tmp)/'out.RPP'; src.write_bytes(text.encode())
            mod.rewrite_top_level_pans(src,out,[{'track':'Kick Test','pan':-0.125},{'track':'Snare Test','pan':0.25}],False)
            a=src.read_bytes().splitlines(keepends=True); b=out.read_bytes().splitlines(keepends=True)
            diffs=[(x,y) for x,y in zip(a,b) if x!=y]
            self.assertEqual(len(diffs),2)
            self.assertTrue(all(x.endswith(b'\r\n') and y.endswith(b'\r\n') for x,y in diffs))
            self.assertTrue(all(x.lstrip().startswith(b'VOLPAN ') and y.lstrip().startswith(b'VOLPAN ') for x,y in diffs))

if __name__=='__main__': unittest.main()
