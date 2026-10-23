import json, pathlib, subprocess, sys, tempfile, unittest, wave
ROOT=pathlib.Path(__file__).resolve().parents[1]
SCRATCH=ROOT/'runs';SCRATCH.mkdir(exist_ok=True)
SCRIPT=ROOT/'musical-inference/scripts/monitor.py'
class MonitorTests(unittest.TestCase):
    def run_cli(self,*args):return subprocess.run([sys.executable,str(SCRIPT),*args],capture_output=True,text=True,timeout=15)
    def test_render(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temp:
            r=self.run_cli('--demo','--output',temp);self.assertEqual(r.returncode,0,r.stderr)
            data=json.loads((pathlib.Path(temp)/'result.json').read_text());self.assertFalse(data['measured_inference']);self.assertEqual(data['source'],'synthetic')
            with wave.open(str(pathlib.Path(temp)/'synthetic-demo.wav')) as w:
                self.assertEqual(w.getnframes(),32*5512);self.assertEqual(w.getnchannels(),2)
    def test_bounds(self):
        for args in [('--seconds','601'),('--seconds','0'),('--pid','-1'),('--demo','--play')]:self.assertNotEqual(self.run_cli(*args).returncode,0)
    def test_exclusive(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temp:
            (pathlib.Path(temp)/'.monitor.lock').write_text('test')
            self.assertNotEqual(self.run_cli('--demo','--output',temp).returncode,0)
            self.assertFalse((pathlib.Path(temp)/'result.json').exists())
if __name__=='__main__':
    r=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(MonitorTests))
    if not r.wasSuccessful():raise SystemExit(1)
    print('PASS synthesis, synthetic evidence, invalid inputs and exclusive output lock')
