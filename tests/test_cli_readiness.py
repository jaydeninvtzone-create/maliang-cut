import importlib.util,unittest,subprocess,io,contextlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('maliang',ROOT/'scripts/maliang.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class ReadinessTests(unittest.TestCase):
    def args(self):return SimpleNamespace(ffmpeg='custom-ffmpeg',ffprobe='custom-ffprobe')
    def test_ready_uses_explicit_paths(self):
        with patch.object(m.shutil,'which',side_effect=lambda x:x),patch('importlib.util.find_spec',return_value=object()),patch.object(m.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='version',stderr='')) as call:
            r=m.doctor(self.args())
            self.assertEqual(r['status'],'LOCAL_PREREQUISITES_READY')
            self.assertEqual(call.call_args_list[0].args[0],['custom-ffmpeg','-version'])
    def test_missing_dependency_has_action(self):
        with patch.object(m.shutil,'which',return_value=None),patch('importlib.util.find_spec',return_value=None):
            r=m.doctor(self.args());self.assertEqual(r['status'],'LOCAL_PREREQUISITES_MISSING');self.assertTrue(r['actions'])
    def test_timeout_does_not_pass(self):
        with patch.object(m.shutil,'which',return_value='tool'),patch('importlib.util.find_spec',return_value=object()),patch.object(m.subprocess,'run',side_effect=subprocess.TimeoutExpired('tool',10)):
            self.assertEqual(m.doctor(self.args())['status'],'LOCAL_PREREQUISITES_MISSING')
    def test_broken_executable_does_not_pass(self):
        with patch.object(m.shutil,'which',return_value='tool'),patch('importlib.util.find_spec',return_value=object()),patch.object(m.subprocess,'run',return_value=SimpleNamespace(returncode=1,stdout='',stderr='broken')):
            self.assertFalse(m.doctor(self.args())['tools']['ffmpeg']['available'])
    def test_cli_missing_exits_nonzero(self):
        with patch.object(m.sys,'argv',['maliang','doctor']),patch.object(m,'doctor',return_value={'status':'LOCAL_PREREQUISITES_MISSING'}),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(m.main(),1)
    def test_decode_error_rejected_with_xerror(self):
        args=SimpleNamespace(media=Path('example.mp4'),ffmpeg='ffmpeg',ffprobe='ffprobe',duration=None)
        with patch.object(m,'probe',return_value={'format':{'duration':'2'},'streams':[]}),patch.object(m,'tool',return_value='ffmpeg'),patch.object(m,'run',side_effect=ValueError('corrupt frame')) as call:
            with self.assertRaisesRegex(ValueError,'corrupt frame'):m.verify(args)
            self.assertIn('-xerror',call.call_args.args[0])
if __name__=='__main__':unittest.main()
