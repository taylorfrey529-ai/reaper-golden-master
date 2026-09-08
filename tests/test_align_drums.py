from __future__ import annotations
import importlib.machinery, importlib.util, math, struct, sys, tempfile, unittest, wave
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; SCRIPT=ROOT/'scripts'/'reaper-align-drums.py'
loader=importlib.machinery.SourceFileLoader('align_drums_test',str(SCRIPT)); spec=importlib.util.spec_from_loader(loader.name,loader); assert spec
align=importlib.util.module_from_spec(spec); sys.modules[loader.name]=align; loader.exec_module(align)

def pcm24(value:float)->bytes:
    v=max(-8388608,min(8388607,int(round(value*8388607))))
    if v<0:v+=1<<24
    return bytes((v&255,(v>>8)&255,(v>>16)&255))

def write_wave(path:Path,channels:list[list[float]],sr:int=48000):
    frames=len(channels[0]); raw=bytearray()
    for i in range(frames):
        for ch in channels: raw.extend(pcm24(ch[i]))
    with wave.open(str(path),'wb') as w:
        w.setnchannels(len(channels)); w.setsampwidth(3); w.setframerate(sr); w.writeframes(raw)

class AlignDrumsTests(unittest.TestCase):
    def test_shell_name_matching_does_not_treat_track_as_rack_tom(self):
        self.assertFalse(align.is_shell_name('8-Bar Drum Track - 120 BPM'))
        self.assertTrue(align.is_shell_name('Rack 1'))
        self.assertTrue(align.is_shell_name('Tom 1 Test'))
        self.assertTrue(align.is_shell_name('Kick Test'))

    def test_tom1_identity(self):
        self.assertTrue(align.is_tom1_name('Tom 1 Test'))
        self.assertTrue(align.is_tom1_name('Rack-01'))
        self.assertFalse(align.is_tom1_name('Tom 2'))

    def test_alignment_jsfx_preserves_non_destructive_pdc_contract(self):
        self.assertIn('slider1:0<-100,100,0.001>',align.JSFX_TEXT)
        self.assertIn('pdc_delay = -requested',align.JSFX_TEXT)
        self.assertIn('delaylen = requested',align.JSFX_TEXT)

    def test_zero_lag_wins_when_left_overhead_is_exact_shell(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); n=48000; shell=[0.0]*n
            # Four spaced, decaying transient bursts provide enough events for the admitted detector.
            for start,amp in [(9000,.8),(17000,.6),(25000,.45),(33000,.3)]:
                for i in range(240): shell[start+i]=amp*math.sin(2*math.pi*900*i/48000)*math.exp(-i/80)
            right=[0.0]*n; delay=48
            for i in range(n-delay): right[i+delay]=shell[i]
            sp=root/'shell.wav'; op=root/'oh.wav'; write_wave(sp,[shell]); write_wave(op,[shell,right])
            offset,events,kept=align.estimate_offset(align.Audio(sp),align.Audio(op))
        self.assertIsNotNone(offset)
        self.assertAlmostEqual(offset,0.0,places=6)
        self.assertGreaterEqual(len(kept),1)
        self.assertTrue(all(m['ch']==1 for m in kept))

    def test_dispatch_help_is_available(self):
        # Parser itself proves the continuation command contract without requiring live workspace files.
        parser=align.build_parser()
        with self.assertRaises(SystemExit) as cm: parser.parse_args(['--help'])
        self.assertEqual(cm.exception.code,0)

if __name__=='__main__':unittest.main()
