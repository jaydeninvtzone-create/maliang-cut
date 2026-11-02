"""Portable maliang-cut helpers. No app UI automation or paid service calls."""
import argparse, hashlib, json, math, os, re, shutil, subprocess, sys, tempfile, uuid
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0,str(Path(__file__).resolve().parent))
ROOT = Path(__file__).resolve().parents[1]

def dump(path, value):
    path=Path(path)
    with path.open('x',encoding='utf-8') as f: json.dump(value,f,ensure_ascii=False,indent=2)

def tool(value):
    found=shutil.which(value)
    if not found: raise ValueError('Executable not found: '+value)
    return found

def run(args):
    result=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',errors='replace')
    if result.returncode: raise ValueError(result.stderr[-3000:])
    return result.stdout

def probe(path, ffprobe='ffprobe'):
    return json.loads(run([tool(ffprobe),'-v','error','-show_streams','-show_format','-of','json',str(path)]))

def number(v, low, high, label):
    if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not low<=v<=high:
        raise ValueError('Invalid '+label)
    return v

def source_path(plan_path, name, media_root):
    if not isinstance(name,str) or not name: raise ValueError('Missing source')
    path=(plan_path.parent/name).resolve()
    if not path.is_relative_to(media_root.resolve()) or not path.is_file():
        raise ValueError('Source outside media root or missing')
    return path

def validate(plan_path,media_root,ffprobe='ffprobe'):
    plan_path=Path(plan_path).resolve(); media_root=Path(media_root).resolve()
    p=json.loads(plan_path.read_text('utf-8-sig'))
    if set(p)-{'version','name','canvas','clips','captions'}: raise ValueError('Unknown plan field')
    if p.get('version')!=2: raise ValueError('Plan version 2 required: review each shot choice and verification action; do not silently migrate old decisions')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',p.get('name','')): raise ValueError('Unsafe draft name')
    canvas=p['canvas']
    if set(canvas)!={'width','height','fps'}: raise ValueError('Invalid canvas keys')
    for k in ('width','height'):
        number(canvas[k],64,7680,k)
        if type(canvas[k]) is not int or canvas[k]%2: raise ValueError('Even integer dimensions required')
    number(canvas['fps'],1,60,'fps')
    if type(canvas['fps']) is not int: raise ValueError('Integer fps required')
    if not isinstance(p['clips'],list) or not p['clips']: raise ValueError('Clips required')
    tracks={}; ids=set(); cache={}; resolved=[]
    allowed={'id','source','in','out','at','speed','volume','track','spoken','purpose','method','reason','transform','decision'}
    for c in p['clips']:
        if set(c)-allowed: raise ValueError('Unknown clip field')
        cid=c.get('id')
        if not isinstance(cid,str) or not cid or cid in ids: raise ValueError('Duplicate/empty clip id')
        ids.add(cid)
        for key in ('purpose','method','reason'):
            if not isinstance(c.get(key),str) or not c[key].strip(): raise ValueError('Missing '+key)
        decision=c.get('decision')
        if not isinstance(decision,dict) or set(decision)-{'route','alternatives','comparison_not_needed','verification','native_gap'}:raise ValueError('Shot decision and verification required')
        if decision.get('route') not in ('native','external'):raise ValueError('Decision route must be native or external')
        if not isinstance(decision.get('verification'),str) or not decision['verification'].strip():raise ValueError('Missing shot-specific verification action')
        alternatives=decision.get('alternatives',[])
        if not isinstance(alternatives,list):raise ValueError('Alternatives must be a list')
        if not alternatives and (not isinstance(decision.get('comparison_not_needed'),str) or not decision['comparison_not_needed'].strip()):raise ValueError('Compare a meaningful alternative or explain why direct cut needs no comparison')
        for alternative in alternatives:
            if not isinstance(alternative,dict) or set(alternative)!={'method','tradeoff'} or any(not isinstance(alternative[k],str) or not alternative[k].strip() for k in ('method','tradeoff')):raise ValueError('Alternative needs method and concrete tradeoff')
            if alternative['method'].strip()==c['method'].strip():raise ValueError('Alternative repeats selected method')
        if decision['route']=='external' and (not isinstance(decision.get('native_gap'),str) or not decision['native_gap'].strip()):raise ValueError('External method needs a specific native gap')
        path=source_path(plan_path,c['source'],media_root)
        if path not in cache: cache[path]=probe(path,ffprobe)
        info=cache[path]
        if not any(s['codec_type']=='video' for s in info['streams']): raise ValueError('Video clip required')
        duration=float(info['format'].get('duration',0))
        start=number(c['in'],0,duration,'in'); end=number(c['out'],0,duration,'out')
        if end<=start: raise ValueError('Empty source range')
        at=number(c['at'],0,86400,'at'); speed=number(c.get('speed',1),.5,2,'speed')
        volume=number(c.get('volume',1),0,2,'volume')
        if type(c.get('spoken',False)) is not bool: raise ValueError('spoken must be boolean')
        if c.get('spoken') and (volume==0 or not any(s['codec_type']=='audio' for s in info['streams'])):
            raise ValueError('Spoken clip must retain an audio stream and nonzero volume')
        trans=c.get('transform',{})
        ranges={'scale_x':(.05,10),'scale_y':(.05,10),'transform_x':(-2,2),'transform_y':(-2,2),'rotation':(-360,360),'alpha':(0,1)}
        if set(trans)-set(ranges): raise ValueError('Unknown transform')
        for key,val in trans.items(): number(val,*ranges[key],key)
        track=c.get('track','main')
        if not isinstance(track,str) or not track: raise ValueError('Empty track')
        stop=at+(end-start)/speed
        tracks.setdefault(track,[]).append((at,stop,cid))
        resolved.append(dict(c,path=str(path),end_at=stop))
    if 'main' not in tracks: raise ValueError('Main track required')
    for name, intervals in tracks.items():
        last=0
        for at,stop,cid in sorted(intervals):
            if at<last-1e-5: raise ValueError('Overlap on '+name)
            if name=='main' and abs(at-last)>1e-5: raise ValueError('Gap on main')
            last=stop
    total=max(c['end_at'] for c in resolved)
    for cap in p.get('captions',[]):
        if set(cap)-{'text','at','duration','size','y'}: raise ValueError('Unknown caption field')
        if not isinstance(cap.get('text'),str) or not cap['text'].strip(): raise ValueError('Caption text required')
        number(cap['at'],0,total,'caption at');number(cap['duration'],.01,total,'caption duration')
        if cap['at']+cap['duration']>total+1e-5: raise ValueError('Caption outside timeline')
        number(cap.get('size',8),1,100,'caption size');number(cap.get('y',-.8),-1,1,'caption y')
    return p,resolved,total

def build(args):
    p,clips,total=validate(args.plan,args.media_root,args.ffprobe)
    out=args.out.resolve()
    if out.exists(): raise ValueError('Output exists; choose a new version directory')
    sys.path.insert(0,str(ROOT/'vendor'))
    import pyJianYingDraft as d
    out.parent.mkdir(parents=True,exist_ok=True)
    # Name supplied to library is the already validated plan name, not a user path.
    with tempfile.TemporaryDirectory(prefix='maliang-build-',dir=out.parent) as staging:
        draft=d.DraftFolder(staging).create_draft(p['name'],p['canvas']['width'],p['canvas']['height'],fps=p['canvas']['fps'],maintrack_adsorb=False)
        draft.content['name']=p['name']; draft.content['id']=str(uuid.uuid4()).upper()
        for name in dict.fromkeys(c.get('track','main') for c in clips):
            draft.append_track(d.TrackSpec(d.TrackType.video,name=name))
        for c in clips:
            segment=d.VideoSegment(d.VideoMaterial(c['path']),d.trange_seconds(c['at'],duration=c['end_at']-c['at']),source_timerange=d.trange_seconds(c['in'],duration=c['out']-c['in']),speed=c.get('speed',1),volume=c.get('volume',1),clip_settings=d.ClipSettings(**c.get('transform',{})))
            draft.add_segment(segment,c.get('track','main'))
        for i,c in enumerate(p.get('captions',[])):
            name='caption_'+str(i);draft.append_track(d.TrackSpec(d.TrackType.text,name=name))
            draft.add_segment(d.TextSegment(c['text'],d.trange_seconds(c['at'],duration=c['duration']),style=d.TextStyle(size=c.get('size',8),align=1),clip_settings=d.ClipSettings(transform_y=c.get('y',-.8))),name)
        draft.save()
        generated=Path(staging)/p['name']
        dump(generated/'maliang-plan.json',p)
        dump(generated/'maliang-build.json',{'status':'DRAFT_CREATED_NOT_NATIVE_VERIFIED','duration':total,'source_hashes':{c['id']:hashlib.sha256(Path(c['path']).read_bytes()).hexdigest() for c in clips},'native_opened':False,'native_exported':False,'draft_sha256':hashlib.sha256((generated/'draft_content.json').read_bytes()).hexdigest(),'source_files':[{'path':c['path'],'sha256':hashlib.sha256(Path(c['path']).read_bytes()).hexdigest()} for c in clips],'shot_decisions':[{'id':c['id'],'method':c['method'],'reason':c['reason'],'decision':c['decision'],'implemented_parameters':{'speed':c.get('speed',1),'volume':c.get('volume',1),'transform':c.get('transform',{})},'visual_verification':'PENDING'} for c in clips]})
        generated.rename(out)
    return {'draft':str(out),'duration':total,'status':'DRAFT_CREATED_NOT_NATIVE_VERIFIED'}

def preview(args):
    p,clips,total=validate(args.plan,args.media_root,args.ffprobe)
    if p.get('captions') or any(c.get('track','main')!='main' or c.get('transform') for c in clips):
        raise ValueError('Preview only supports untransformed main-track cuts without captions. Use native Jianying for this plan.')
    if args.out.exists():raise ValueError('Output exists')
    args.out.parent.mkdir(parents=True,exist_ok=True); ff=tool(args.ffmpeg)
    with tempfile.TemporaryDirectory(prefix='maliang-preview-',dir=args.out.parent) as temp:
        temp=Path(temp);w,h,fps=(p['canvas'][k] for k in ('width','height','fps'))
        pieces=[]
        for i,c in enumerate(sorted(clips,key=lambda x:x['at'])):
            dst=temp/f'{i}.mp4';speed=c.get('speed',1)
            info=probe(c['path'],args.ffprobe); audio=any(s['codec_type']=='audio' for s in info['streams'])
            vf=f"setpts=PTS/{speed},scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps}"
            cmd=[ff,'-v','error','-nostdin','-ss',str(c['in']),'-t',str(c['out']-c['in']),'-i',c['path']]
            if not audio:cmd+=['-f','lavfi','-i','anullsrc=r=48000:cl=stereo']
            cmd+=['-map','0:v:0','-map','0:a:0' if audio else '1:a:0','-vf',vf,'-af',f"atempo={speed},volume={c.get('volume',1)},aresample=48000",'-ac','2','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-t',str(c['end_at']-c['at']),str(dst)]
            run(cmd);pieces.append(dst)
        listing=temp/'concat.txt';listing.write_text(''.join("file '"+x.name+"'\n" for x in pieces),'utf-8')
        assembled=temp/'assembled.mp4'
        run([ff,'-v','error','-nostdin','-f','concat','-safe','1','-i',str(listing),'-c','copy','-movflags','+faststart',str(assembled)])
        # Atomic same-volume final move: existing outputs are never overwritten.
        if args.out.exists():raise ValueError('Output appeared during rendering')
        assembled.rename(args.out)
    return {'output':str(args.out),'expected_duration':total,'status':'ROUGH_PREVIEW_NOT_NATIVE_EXPORT'}

def verify(args):
    info=probe(args.media,args.ffprobe)
    run([tool(args.ffmpeg),'-v','error','-xerror','-nostdin','-i',str(args.media),'-f','null','-'])
    duration=float(info['format']['duration'])
    if args.duration is not None and abs(duration-args.duration)>.15:raise ValueError('Duration mismatch')
    return {'status':'TECHNICAL_DECODE_PASS_NOT_VISUAL_ACCEPTANCE','duration':duration,'streams':[{'type':s['codec_type'],'codec':s['codec_name'],'width':s.get('width'),'height':s.get('height')} for s in info['streams']],'sha256':hashlib.sha256(args.media.read_bytes()).hexdigest()}

def doctor(args):
    import importlib.util
    checks={}
    for name in ('ffmpeg','ffprobe'):
        value=getattr(args,name,name); executable=shutil.which(value)
        check={'available':False,'path':executable}
        if executable:
            try:
                result=subprocess.run([executable,'-version'],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=10)
                check['available']=result.returncode==0
                check['detail']=(result.stdout if result.returncode==0 else result.stderr)[:400]
            except (OSError,subprocess.TimeoutExpired) as e: check['detail']=str(e)
        if not check['available']:check['action']='Install '+name+' and add it to PATH, or pass --'+name+' with its executable path.'
        checks[name]=check
    dependencies={m:importlib.util.find_spec(m) is not None for m in ('pymediainfo','imageio')}
    python_ok=sys.version_info[:2]>=(3,12)
    ready=python_ok and all(c['available'] for c in checks.values()) and all(dependencies.values())
    actions=[]
    if not python_ok: actions.append('Use Python 3.12 or newer.')
    if not all(dependencies.values()):actions.append('Run this same Python interpreter with -m pip install -r '+str(ROOT/'requirements.txt'))
    return {'status':'LOCAL_PREREQUISITES_READY' if ready else 'LOCAL_PREREQUISITES_MISSING','python':sys.version.split()[0],'python_supported':python_ok,'tools':checks,'dependencies':dependencies,'actions':actions,'native_ui':'HOST_MUST_CHECK','native_export':'NOT_BUNDLED','optional_asr_dependency':importlib.util.find_spec('sherpa_onnx') is not None,'asr_weights':'USER_SUPPLIED_MODEL_DIR_REQUIRED','scope':'Checks executable startup and dependency discovery; does not open Jianying, import the draft backend, or validate model files.'}

def main():
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8',errors='replace')
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('doctor');p.add_argument('--ffmpeg',default='ffmpeg');p.add_argument('--ffprobe',default='ffprobe')
    p=sub.add_parser('inspect');p.add_argument('media',type=Path);p.add_argument('--ffprobe',default='ffprobe')
    for cmd in ('validate','build','preview'):
        p=sub.add_parser(cmd);p.add_argument('plan',type=Path);p.add_argument('--media-root',type=Path,required=True);p.add_argument('--ffprobe',default='ffprobe')
        if cmd!='validate':p.add_argument('--out',type=Path,required=True)
        if cmd=='preview':p.add_argument('--ffmpeg',default='ffmpeg')
    p=sub.add_parser('asr');p.add_argument('audio',type=Path);p.add_argument('--model-dir',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--language',choices=['zh','en','yue','ja','ko'],default='zh')
    p=sub.add_parser('register-draft');p.add_argument('draft',type=Path);p.add_argument('--draft-root',type=Path,required=True);p.add_argument('--media-root',type=Path,required=True)
    p=sub.add_parser('verify');p.add_argument('media',type=Path);p.add_argument('--ffmpeg',default='ffmpeg');p.add_argument('--ffprobe',default='ffprobe');p.add_argument('--duration',type=float)
    args=parser.parse_args()
    try:
        if args.command=='doctor':result=doctor(args)
        elif args.command=='asr':
            from asr_local import asr
            result=asr(args)
        elif args.command=='register-draft':
            from register_draft import register
            result=register(args)
        elif args.command=='inspect':result=probe(args.media,args.ffprobe)
        elif args.command=='validate':
            p,clips,total=validate(args.plan,args.media_root,args.ffprobe);result={'status':'PLAN_VALID','clips':len(clips),'duration':total}
        else:result=globals()[args.command](args)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        if args.command=='doctor' and result['status']=='LOCAL_PREREQUISITES_MISSING':return 1
    except (ValueError,OSError,KeyError,ImportError,RuntimeError) as e:
        print(json.dumps({'status':'FAILED','error':str(e)},ensure_ascii=False),file=sys.stderr);return 1
    return 0
if __name__=='__main__':sys.exit(main())
