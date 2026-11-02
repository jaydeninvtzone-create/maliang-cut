import hashlib,importlib.util,json,tempfile,unittest,uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('registration',ROOT/'scripts/register_draft.py');r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
class RegisterTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name);self.native=self.base/'native';self.native.mkdir();self.source=self.base/'draft';self.source.mkdir();self.media=self.base/'media';self.media.mkdir();(self.media/'source.mp4').write_bytes(b'owned-media')
        self.ident=str(uuid.uuid4());self.content={'id':self.ident,'name':'sample','materials':{'videos':[{'path':str(self.media/'source.mp4')}]}}
        self.original={'root_path':str(self.native),'draft_ids':['existing-id'],'all_draft_store':[{'draft_id':'existing-id','draft_name':'original','draft_fold_path':str(self.native/'original'),'draft_cloud_purchase_info':'preserve-existing-value'}]}
        self.index=self.native/'root_meta_info.json';self.index.write_text(json.dumps(self.original),'utf-8')
        (self.native/'original').mkdir();(self.native/'original/keep.txt').write_text('keep')
        (self.source/'draft_content.json').write_text(json.dumps(self.content),'utf-8');(self.source/'draft_meta_info.json').write_text('{}');(self.source/'maliang-plan.json').write_text('{}')
        self.receipt={'status':'DRAFT_CREATED_NOT_NATIVE_VERIFIED','duration':1,'draft_sha256':r.sha(self.source/'draft_content.json'),'source_files':[{'path':str(self.media/'source.mp4'),'sha256':r.sha(self.media/'source.mp4')}]}
        (self.source/'maliang-build.json').write_text(json.dumps(self.receipt),'utf-8')
        self.args=SimpleNamespace(draft=self.source,draft_root=self.native,media_root=self.media)
    def tearDown(self):self.temp.cleanup()
    def run_register(self):
        with patch.object(r,'require_editor_closed'):return r.register(self.args)
    def test_success_preserves_existing_and_backs_up(self):
        before=self.index.read_bytes();result=self.run_register();after=json.loads(self.index.read_bytes())
        self.assertEqual(after['all_draft_store'][0],self.original['all_draft_store'][0]);self.assertEqual(after['draft_ids'],['existing-id',self.ident])
        self.assertEqual(Path(result['index_backup']).read_bytes(),before);self.assertEqual((self.native/'original/keep.txt').read_text(),'keep');self.assertTrue((self.source/'draft_content.json').exists())
        self.assertFalse((self.native/'.maliang-register.lock').exists())
    def test_opaque_integer_24_preserved_with_52_entries(self):
        self.original['draft_ids']=24
        self.original['all_draft_store']=[{'draft_id':str(i),'draft_name':'existing_'+str(i),'draft_fold_path':str(self.native/('existing_'+str(i)))} for i in range(52)]
        self.index.write_text(json.dumps(self.original),'utf-8')
        self.run_register();after=json.loads(self.index.read_bytes())
        self.assertIs(type(after['draft_ids']),int);self.assertEqual(after['draft_ids'],24)
        self.assertEqual(len(after['all_draft_store']),53);self.assertEqual(after['all_draft_store'][:52],self.original['all_draft_store'])
    def test_negative_integer_refused(self):
        self.original['draft_ids']=-1;self.index.write_text(json.dumps(self.original),'utf-8')
        before=self.index.read_bytes()
        with self.assertRaises(ValueError):self.run_register()
        self.assertEqual(self.index.read_bytes(),before)
    def test_unknown_count_types_refused(self):
        for value in (True,False,'1',1.0,None,{}):
            with self.subTest(value=value):
                self.original['draft_ids']=value;self.index.write_text(json.dumps(self.original),'utf-8')
                with self.assertRaises(ValueError):self.run_register()
    def test_running_editor_refused_without_writes(self):
        before=self.index.read_bytes()
        with patch.object(r,'require_editor_closed',side_effect=ValueError('running')):
            with self.assertRaises(ValueError):r.register(self.args)
        self.assertEqual(before,self.index.read_bytes());self.assertFalse((self.native/'sample').exists())
    def test_existing_target_refused(self):
        (self.native/'sample').mkdir()
        with self.assertRaises(ValueError):self.run_register()
    def test_duplicate_uuid_refused(self):
        data=dict(self.original,draft_ids=[self.ident]);self.index.write_text(json.dumps(data),'utf-8')
        with self.assertRaises(ValueError):self.run_register()
    def test_unknown_schema_refused(self):
        self.index.write_text(json.dumps(dict(self.original,new_layout={})),encoding='utf-8')
        with self.assertRaises(ValueError):self.run_register()
    def test_unknown_entry_field_refused(self):
        self.original['all_draft_store'][0]['unknown']='x';self.index.write_text(json.dumps(self.original),'utf-8')
        with self.assertRaises(ValueError):self.run_register()
    def test_changed_source_refused(self):
        (self.media/'source.mp4').write_bytes(b'changed')
        with self.assertRaises(ValueError):self.run_register()
    def test_changed_draft_refused(self):
        (self.source/'draft_content.json').write_text('{}')
        with self.assertRaises(ValueError):self.run_register()
    def test_concurrent_index_preserved(self):
        calls=[0]
        def race():
            calls[0]+=1
            if calls[0]==2:self.index.write_text(json.dumps(dict(self.original,draft_ids=['concurrent'])),'utf-8')
        with patch.object(r,'require_editor_closed',side_effect=race):
            with self.assertRaises(ValueError):r.register(self.args)
        self.assertEqual(json.loads(self.index.read_bytes())['draft_ids'],['concurrent']);self.assertFalse((self.native/'sample').exists())
    def test_lock_refused(self):
        (self.native/'.maliang-register.lock').write_text('other-writer')
        with self.assertRaises(FileExistsError):self.run_register()
        self.assertEqual((self.native/'.maliang-register.lock').read_text(),'other-writer')
if __name__=='__main__':unittest.main()
