"""Optional offline short-PCM ASR adapter. No weights, downloads, or semantic edits."""
import array,ctypes,hashlib,importlib.util,json,os,socket,sys,tempfile,time,wave
from pathlib import Path
from contextlib import contextmanager
MODEL_SHA='c71f0ce00bec95b07744e116345e33d8cbbe08cef896382cf907bf4b51a2cd51'
TOKENS_SHA='f449eb28dc567533d7fa59be34e2abca8784f771850c78a47fb731a31429a1dc'

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def local(path):
    raw=str(path)
    if '://' in raw or raw.startswith(('\\\\','//')):raise ValueError('ASR requires explicit local files, not URLs or network shares')
    return Path(path).expanduser().resolve()

def read_pcm(path):
    path=local(path)
    if not path.is_file():raise ValueError('ASR audio file is missing')
    if path.stat().st_size>2_000_000:raise ValueError('ASR accepts at most 30 seconds of 16k mono PCM WAV')
    try:
        with wave.open(str(path),'rb') as w:
            if (w.getnchannels(),w.getsampwidth(),w.getframerate(),w.getcomptype())!=(1,2,16000,'NONE'):raise ValueError('ASR requires 16kHz mono 16-bit uncompressed PCM WAV; convert a working copy first')
            frames=w.getnframes()
            if not 0<frames<=480000:raise ValueError('ASR supports nonempty inputs up to 30 seconds per call')
            raw=w.readframes(frames)
            if len(raw)!=frames*2:raise ValueError('Truncated PCM input')
    except wave.Error as e:raise ValueError('Invalid PCM WAV: '+str(e)) from e
    values=array.array('h');values.frombytes(raw)
    if sys.byteorder!='little':values.byteswap()
    return [v/32768.0 for v in values],frames/16000

def model_files(folder):
    folder=local(folder);model=folder/'model.int8.onnx';tokens=folder/'tokens.txt'
    if not model.is_file() or not tokens.is_file():raise ValueError('Provide an existing SenseVoiceSmall int8 2024-07-17 model directory containing model.int8.onnx and tokens.txt; this command never downloads weights')
    if sha(model)!=MODEL_SHA or sha(tokens)!=TOKENS_SHA:raise ValueError('Model/token hashes differ from the supported int8 2024-07-17 pair; no inference started')
    return model,tokens

@contextmanager
def python_network_disabled():
    old={name:getattr(socket,name) for name in ('socket','create_connection','getaddrinfo')}
    def deny(*args,**kwargs):raise RuntimeError('Network calls disabled in local ASR adapter')
    try:
        for name in old:setattr(socket,name,deny)
        yield
    finally:
        for name,value in old.items():setattr(socket,name,value)

def disable_native_telemetry(package_dir):
    if os.name!='nt':raise ValueError('This ASR adapter is currently validated for Windows only')
    ptr=ctypes.c_void_p;fn=ctypes.WINFUNCTYPE
    class ApiPrefix(ctypes.Structure):
        _fields_=[('CreateStatus',ptr),('GetErrorCode',ptr),('GetErrorMessage',ptr),('CreateEnv',fn(ptr,ctypes.c_int,ctypes.c_char_p,ctypes.POINTER(ptr))),('CreateEnvWithCustomLogger',ptr),('EnableTelemetryEvents',ptr),('DisableTelemetryEvents',fn(ptr,ptr))]
    class ApiBase(ctypes.Structure):
        _fields_=[('GetApi',fn(ctypes.POINTER(ApiPrefix),ctypes.c_uint32)),('GetVersionString',fn(ctypes.c_char_p))]
    dll=ctypes.WinDLL(str(package_dir/'lib/onnxruntime.dll'));dll.OrtGetApiBase.argtypes=[];dll.OrtGetApiBase.restype=ctypes.POINTER(ApiBase)
    base=dll.OrtGetApiBase().contents
    if base.GetVersionString()!=b'1.28.2':raise ValueError('Unsupported bundled ONNX Runtime version; expected 1.28.2')
    api=base.GetApi(28).contents;env=ptr()
    if api.CreateEnv(3,b'maliang-asr-local',ctypes.byref(env)) or not env.value:raise ValueError('Could not create local ORT environment')
    if api.DisableTelemetryEvents(env):raise ValueError('Could not disable native telemetry')
    return dll,base,api,env

def asr(args):
    output=local(args.out)
    if output.exists():raise ValueError('ASR output exists; choose a fresh directory')
    samples,duration=read_pcm(args.audio)
    spec=importlib.util.find_spec('sherpa_onnx')
    if spec is None:raise ValueError('Optional ASR dependency missing: install requirements-asr.txt into the Python running this command; no installation or download was attempted')
    model,tokens=model_files(args.model_dir)
    if not spec.submodule_search_locations:raise ValueError('Unexpected ASR package layout')
    package_dir=Path(next(iter(spec.submodule_search_locations)))
    started=time.perf_counter()
    with python_network_disabled():
        telemetry_guard=disable_native_telemetry(package_dir)
        import sherpa_onnx
        if sherpa_onnx.__version__!='1.13.8':raise ValueError('Unsupported sherpa-onnx version; expected 1.13.8')
        recognizer=sherpa_onnx.OfflineRecognizer.from_sense_voice(model=str(model),tokens=str(tokens),num_threads=1,provider='cpu',language=args.language,use_itn=False)
        stream=recognizer.create_stream();stream.accept_waveform(16000,samples);recognizer.decode_stream(stream)
        raw=json.loads(str(stream.result));text=stream.result.text
        if not isinstance(text,str) or raw.get('text')!=text:raise ValueError('Inconsistent raw ASR response')
    timestamps=raw.get('timestamps',[]);raw_tokens=raw.get('tokens',[])
    timing_usable=isinstance(timestamps,list) and isinstance(raw_tokens,list) and len(timestamps)==len(raw_tokens) and len(timestamps)>0 and all(type(t) in (float,int) and 0<=t<=duration+.5 for t in timestamps)
    receipt={'status':'RAW_ASR_COMPLETED_NOT_TRANSCRIPT_ACCEPTED','engine':'sherpa-onnx 1.13.8','model':'SenseVoiceSmall int8 2024-07-17','model_license':'FunASR Model Open Source License Agreement v1.1; separate from adapter Apache-2.0','provider':'cpu','threads':1,'language':args.language,'use_itn':False,'input_sha256':sha(local(args.audio)),'audio_seconds':duration,'elapsed_seconds':round(time.perf_counter()-started,3),'token_start_times_available':timing_usable,'timestamp_scope':'Raw model token start estimates only; no end times, forced alignment, validated word boundaries, diarization or final SRT','semantic_deletions':False,'text_rewritten':False,'python_network_guard':True,'native_telemetry_disabled':True,'network_scope':'Process-level safeguards; not an OS network sandbox or packet-capture proof'}
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.maliang-asr-',dir=output.parent) as temp:
        staging=Path(temp)/'result';staging.mkdir()
        (staging/'raw.json').write_text(json.dumps(raw,ensure_ascii=False,indent=2),'utf-8');(staging/'transcript.txt').write_text(text+'\n','utf-8');(staging/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),'utf-8')
        if output.exists():raise ValueError('ASR output appeared concurrently')
        staging.rename(output)
    return dict(receipt,output=str(output))
