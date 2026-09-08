import importlib.machinery, importlib.util, sys, unittest
from pathlib import Path
PATH=Path(__file__).resolve().parents[1]/'scripts'/'reaper-screenshot.py'
loader=importlib.machinery.SourceFileLoader('reaper_screenshot_test',str(PATH));spec=importlib.util.spec_from_loader(loader.name,loader);mod=importlib.util.module_from_spec(spec);sys.modules[loader.name]=mod;loader.exec_module(mod)

class ScreenshotTests(unittest.TestCase):
    def test_parse_dimensions(self):
        self.assertEqual(mod.parse_dimensions(' dimensions:    1440x900 pixels (380x238 millimeters)'),(1440,900))
    def test_window_classification_preserves_evaluation_state(self):
        titles=['Ubuntu Workspace Desktop','ASIO-Routing-Project - REAPER v7.79 - EVALUATION LICENSE','About REAPER v7.79/linux-x86_64 rev 06dd78 (Aug 17 2026)']
        state=mod.classify_reaper_windows(titles)
        self.assertTrue(state['evaluation_license_title']);self.assertTrue(state['about_window_present'])
    def test_non_evaluation_title_not_promoted(self):
        state=mod.classify_reaper_windows(['ASIO-Routing-Project - REAPER v7.79'])
        self.assertFalse(state['evaluation_license_title'])

if __name__=='__main__':unittest.main()
