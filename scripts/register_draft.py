"""Register a newly generated owned draft while Jianying is completely closed."""
import csv,hashlib,json,os,re,shutil,subprocess,tempfile,time,uuid
from pathlib import Path

BOOL_FIELDS='cloud_draft_cover cloud_draft_sync draft_cloud_last_action_download draft_is_ai_shorts draft_is_cloud_temp_draft draft_is_infinite_canvas_draft draft_is_invisible draft_is_pippit_draft draft_is_web_article_video streaming_edit_draft_ready'.split()
STR_FIELDS='draft_cloud_purchase_info draft_cloud_template_id draft_cloud_tutorial_info draft_cloud_videocut_purchase_info draft_cover draft_fold_path draft_id draft_json_file draft_name draft_new_version draft_root_path draft_type draft_web_article_video_enter_from pippit_avatar_url pippit_extra_info pippit_id pippit_user_name tm_draft_cloud_completed'.split()
INT_FIELDS='draft_timeline_materials_size tm_draft_cloud_entry_id tm_draft_cloud_modified tm_draft_cloud_parent_entry_id tm_draft_cloud_space_id tm_draft_cloud_user_id tm_draft_create tm_draft_modified tm_draft_removed tm_duration'.split()
SOURCE_FILES={'draft_content.json','draft_meta_info.json','maliang-plan.json','maliang-build.json'}

def require_editor_closed():
    if os.name!='nt':raise ValueError('Native registration is currently supported on Windows only')
    r=subprocess.run(['tasklist.exe','/FO','CSV','/NH'],capture_output=True,text=True,timeout=15)
    if r.returncode:raise ValueError('Cannot verify editor process state')
    rows=list(csv.reader(r.stdout.splitlines()))
    if not rows or any(len(row)<2 for row in rows):raise ValueError('Unknown process inventory format')
    active=[row[0] for row in rows if row[0].lower().startswith(('jianying','capcut'))]
    if active:raise ValueError('Completely exit Jianying/CapCut before registration; no process will be killed')

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def check_index(data,root):
    if not isinstance(data,dict) or set(data)!={'all_draft_store','draft_ids','root_path'}:raise ValueError('Unknown root_meta_info schema; no write performed')
    if not isinstance(data['all_draft_store'],list) or not isinstance(data['root_path'],str):raise ValueError('Invalid index field types')
    if Path(data['root_path']).resolve()!=root:raise ValueError('Index root path mismatch')
    if type(data['draft_ids']) is int:
        if data['draft_ids']<0:raise ValueError('Negative opaque draft_ids value is unsupported')
        # Native observations include draft_ids=24 with 52 entries. Its integer semantics
        # are unknown: preserve it verbatim rather than infer a count or normalize it.
    elif isinstance(data['draft_ids'],list):
        if any(not isinstance(i,str) for i in data['draft_ids']):raise ValueError('Unsupported draft_ids list layout')
    else:raise ValueError('Unsupported draft_ids type')
    for item in data['all_draft_store']:
        if not isinstance(item,dict):raise ValueError('Unknown draft entry')
        for field in ('draft_id','draft_name','draft_fold_path'):
            if not isinstance(item.get(field),str):raise ValueError('Unknown draft entry identity')
        known=set(BOOL_FIELDS+STR_FIELDS+INT_FIELDS)
        if set(item)-known:raise ValueError('Unknown draft entry fields; no write performed')
        for field in item:
            expected=bool if field in BOOL_FIELDS else (str if field in STR_FIELDS else int)
            if type(item[field]) is not expected:raise ValueError('Unknown draft entry type')

def register(args):
    source=args.draft.resolve();root=args.draft_root.resolve();media_root=args.media_root.resolve()
    if not source.is_dir() or source==root or source.is_relative_to(root) or root.is_relative_to(source):raise ValueError('Source and native root must be independent directories')
    if not root.is_dir() or root.is_symlink():raise ValueError('Explicit existing native draft root required')
    if args.draft.is_symlink() or args.draft_root.is_symlink():raise ValueError('Symlink draft/root refused')
    items=list(source.iterdir())
    if {x.name for x in items}!=SOURCE_FILES or any(x.is_symlink() or not x.is_file() for x in items):raise ValueError('Only unmodified maliang-cut build output may be registered')
    receipt=json.loads((source/'maliang-build.json').read_text('utf-8-sig'))
    if receipt.get('status')!='DRAFT_CREATED_NOT_NATIVE_VERIFIED' or receipt.get('draft_sha256')!=sha(source/'draft_content.json'):
        raise ValueError('Build hash missing or changed; rebuild a fresh version, never register edited UI drafts through this helper')
    sources=receipt.get('source_files')
    if not isinstance(sources,list) or not sources:raise ValueError('Missing source file evidence')
    for entry in sources:
        path=Path(entry['path']).resolve()
        if not path.is_relative_to(media_root) or not path.is_file() or sha(path)!=entry['sha256']:raise ValueError('Source outside media root, missing, or changed')
    content=json.loads((source/'draft_content.json').read_text('utf-8-sig'));meta=json.loads((source/'draft_meta_info.json').read_text('utf-8-sig'))
    referenced={str(Path(v['path']).resolve()) for v in content.get('materials',{}).get('videos',[]) if v.get('path')}
    evidenced={str(Path(e['path']).resolve()) for e in sources}
    if referenced!=evidenced:raise ValueError('Draft media paths do not match build evidence')
    name=content.get('name','')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',name):raise ValueError('Unsafe draft name')
    ident=content.get('id')
    try:uuid.UUID(ident)
    except (ValueError,TypeError,AttributeError):raise ValueError('Draft needs a valid unique UUID')
    target=root/name
    if target.exists():raise ValueError('Native draft name already exists')
    require_editor_closed()
    index=root/'root_meta_info.json'
    if index.is_symlink() or not index.is_file():raise ValueError('Missing regular native root index')
    lock=root/'.maliang-register.lock';token=uuid.uuid4().hex
    with lock.open('x',encoding='ascii') as f:f.write(token)
    backup=None
    try:
        original=index.read_bytes();data=json.loads(original);check_index(data,root)
        if (isinstance(data['draft_ids'],list) and ident in data['draft_ids']) or any(x['draft_id']==ident or x['draft_name']==name or Path(x['draft_fold_path']).resolve()==target for x in data['all_draft_store']):raise ValueError('Native identity/name/path already registered')
        # Copy only our generated files; the source and all existing native projects remain untouched.
        with tempfile.TemporaryDirectory(prefix='.maliang-staging-',dir=root) as staging:
            staged=Path(staging)/name;staged.mkdir()
            for item in items:shutil.copy2(item,staged/item.name)
            if sha(staged/'draft_content.json')!=receipt['draft_sha256']:raise ValueError('Source changed during copy')
            now=int(time.time()*1000000);duration=round(float(receipt['duration'])*1000000)
            record={k:False for k in BOOL_FIELDS};record.update({k:'' for k in STR_FIELDS});record.update({k:0 for k in INT_FIELDS})
            record.update(draft_id=ident,draft_name=name,draft_fold_path=str(target),draft_root_path=str(root),draft_json_file=str(target/'draft_content.json'),tm_duration=duration,tm_draft_create=now,tm_draft_modified=now,draft_timeline_materials_size=sum(Path(path).stat().st_size for path in evidenced))
            meta.update(record)
            (staged/'draft_meta_info.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),'utf-8')
            backup_dir=root/'.maliang-register-backups'
            if backup_dir.is_symlink():raise ValueError('Backup directory symlink refused')
            backup_dir.mkdir(exist_ok=True)
            backup=backup_dir/('root_meta_info.'+token+'.json')
            with backup.open('xb') as f:f.write(original)
            # Existing entries are not cloned, redacted, reordered or rewritten individually.
            data['all_draft_store'].append(record)
            if isinstance(data['draft_ids'],list):data['draft_ids'].append(ident)
            # Nonnegative integer draft_ids is opaque and intentionally unchanged.
            updated=json.dumps(data,ensure_ascii=False,indent=2).encode('utf-8')
            pending=Path(staging)/'root_meta_info.pending.json';pending.write_bytes(updated)
            require_editor_closed()
            if index.read_bytes()!=original:raise ValueError('Concurrent index change; preserved backup, no index write')
            if target.exists():raise ValueError('Target appeared concurrently')
            staged.rename(target)
            # Last comparison is immediately before replacement. App must stay closed.
            require_editor_closed()
            if index.read_bytes()!=original:raise ValueError('Concurrent index change; owned draft left unregistered, no index write')
            pending.replace(index)
            if index.read_bytes()!=updated:raise ValueError('Index changed after replacement; inspect backup, do not overwrite newer data')
        return {'status':'REGISTERED_NOT_NATIVE_OPENED','draft':str(target),'draft_id':ident,'index_backup':str(backup),'native_opened':False,'native_exported':False}
    finally:
        if lock.exists() and lock.read_text('ascii')==token:lock.unlink()
