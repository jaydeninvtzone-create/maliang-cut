import importlib.util,json,socket,sys,tempfile,unittest,wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('asr_adapter',ROOT/'scripts/asr_local.py');a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
class AsrTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name);self.wav=self.base/'test.wav';self.write_wave()
        self.args=SimpleNamespace(audio=self.wav,model_dir=self.base/'model',out=self.base/'out',language='zh')
    def tearDown(self):self.temp.cleanup()
    def write_wave(self,rate=16000,channels=1,seconds=1):
        with wave.open(str(self.wav),'wb') as w:w.setparams((channels,2,rate,0,'NONE','not compressed'));w.writeframes(b'\0\0'*(rate*channels*seconds))
    def test_pcm_supported(self):self.assertEqual(a.read_pcm(self.wav)[1],1)
    def test_stereo_refused(self):
        self.write_wave(channels=2)
        with self.assertRaises(ValueError):a.read_pcm(self.wav)
    def test_long_audio_refused(self):
        self.write_wave(seconds=31)
        with self.assertRaises(ValueError):a.read_pcm(self.wav)
    def test_network_path_refused(self):
        with self.assertRaises(ValueError):a.local('https://example.com/audio.wav')
    def test_missing_dependency_has_no_output(self):
        with patch.object(a.importlib.util,'find_spec',return_value=None):
            with self.assertRaisesRegex(ValueError,'dependency missing'):a.asr(self.args)
        self.assertFalse(self.args.out.exists())
    def test_missing_weights_no_download(self):
        with self.assertRaisesRegex(ValueError,'never downloads'):a.model_files(self.args.model_dir)
    def test_wrong_model_hash_refused(self):
        self.args.model_dir.mkdir();(self.args.model_dir/'model.int8.onnx').write_bytes(b'wrong');(self.args.model_dir/'tokens.txt').write_text('wrong')
        with self.assertRaisesRegex(ValueError,'hashes differ'):a.model_files(self.args.model_dir)
    def test_existing_output_refused(self):
        self.args.out.mkdir();(self.args.out/'keep').write_text('keep')
        with self.assertRaises(ValueError):a.asr(self.args)
        self.assertEqual((self.args.out/'keep').read_text(),'keep')
    def test_python_network_guard_restored(self):
        original=socket.create_connection
        with a.python_network_disabled():
            with self.assertRaises(RuntimeError):socket.create_connection(('example.com',80))
        self.assertIs(socket.create_connection,original)
    def test_raw_tokens_and_text_are_not_rewritten(self):
        raw={'text':'不要，不要删掉。','tokens':['不','要','，','不','要','删','掉','。'],'timestamps':[0,.1,.2,.3,.4,.5,.6,.7]}
        class Result:
            text=raw['text']
            def __str__(self):return json.dumps(raw)
        class Stream:
            result=Result()
            def accept_waveform(self,*args):pass
        class Recognizer:
            def create_stream(self):return Stream()
            def decode_stream(self,*args):pass
        seen={}
        def factory(**kwargs):seen.update(kwargs);return Recognizer()
        engine=SimpleNamespace(__version__='1.13.8',OfflineRecognizer=SimpleNamespace(from_sense_voice=factory))
        with patch.object(a.importlib.util,'find_spec',return_value=SimpleNamespace(submodule_search_locations=[str(self.base)])),patch.object(a,'model_files',return_value=(self.base/'model',self.base/'tokens')),patch.object(a,'disable_native_telemetry',return_value=()),patch.dict(sys.modules,{'sherpa_onnx':engine}):
            result=a.asr(self.args)
        self.assertEqual(json.loads((self.args.out/'raw.json').read_text('utf-8')),raw)
        self.assertEqual((self.args.out/'transcript.txt').read_text('utf-8').strip(),raw['text'])
        self.assertFalse(seen['use_itn']);self.assertEqual(seen['num_threads'],1);self.assertEqual(seen['provider'],'cpu');self.assertFalse(result['semantic_deletions'])
if __name__=='__main__':unittest.main()
