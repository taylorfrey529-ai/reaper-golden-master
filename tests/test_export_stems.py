from __future__ import annotations
import importlib.machinery, importlib.util, sys, tempfile, unittest, wave
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; SCRIPT=ROOT/'scripts'/'reaper-export-stems.py'
l=importlib.machinery.SourceFileLoader('stems_test',str(SCRIPT)); s=importlib.util.spec_from_loader(l.name,l); assert s
stems=importlib.util.module_from_spec(s); sys.modules[l.name]=stems; l.exec_module(stems)
class Tests(unittest.TestCase):
    def test_names_and_targets(self):
        stems.valid_names(['Kick Test','Snare Test'])
        self.assertEqual(stems.expected(['Kick Test'],Path('/tmp/x')),[Path('/tmp/x/Kick Test.wav')])
        with self.assertRaises(ValueError): stems.valid_names(['bad/name'])
    def test_lua_uses_native_stem_dialog_not_recent_render_action(self):
        x=stems.lua(['Kick Test','Snare Test'],Path('/tmp/o'),Path('/tmp/s'))
        self.assertIn("'RENDER_SETTINGS',2,true",x); self.assertIn('Main_OnCommand(40015,0)',x); self.assertNotIn('42230',x)
    def test_status(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'s'; p.write_text('settings=2.0\nerror=\n'); stems.wait_stem_mode(p,.2)
    def test_wav_48k(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.wav'
            with wave.open(str(p),'wb') as w: w.setnchannels(2); w.setsampwidth(3); w.setframerate(48000); w.writeframes(b'\x01\0\0\xff\xff\xff'*480)
            r=stems.verify_wav(p,False); self.assertEqual(r['sample_rate_hz'],48000); self.assertTrue(r['non_silent'])
    def test_wav_rejects_44100(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.wav'
            with wave.open(str(p),'wb') as w: w.setnchannels(2); w.setsampwidth(3); w.setframerate(44100); w.writeframes(b'\x01\0\0\xff\xff\xff'*441)
            with self.assertRaisesRegex(RuntimeError,'sample-rate'): stems.verify_wav(p,False)
    def test_isolated_config_disables_web(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); r=root/'r'; r.mkdir(); (r/'reaper.ini').write_text("[reaper]\ncsurf_cnt=1\ncsurf_0=HTTP 0 2307 '' 'index.html' 0 ''\n")
            q=root/'q'; q.mkdir(); home=stems.isolated_config(r,q); text=(home/'REAPER'/'reaper.ini').read_text(); self.assertIn('csurf_cnt=0',text); self.assertNotIn('csurf_0=',text)
if __name__=='__main__': unittest.main()
