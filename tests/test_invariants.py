import importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('maliang',ROOT/'scripts/maliang.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
rs=importlib.util.spec_from_file_location('release',ROOT/'tools/release.py');r=importlib.util.module_from_spec(rs);rs.loader.exec_module(r)
class PlanTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);(self.root/'source.mp4').write_bytes(b'fixture')
        self.p={'version':2,'name':'sample','canvas':{'width':1920,'height':1080,'fps':30},'clips':[{'id':'a','source':'source.mp4','in':0,'out':2,'at':0,'spoken':True,'purpose':'demo','method':'cut','reason':'retain the complete sentence','decision':{'route':'native','alternatives':[],'comparison_not_needed':'A direct source cut already expresses this sentence','verification':'Listen to the cut boundaries for missing consonants'}}]}
        self.info={'format':{'duration':'5'},'streams':[{'codec_type':'video'},{'codec_type':'audio'}]}
    def tearDown(self):self.tmp.cleanup()
    def check(self):
        path=self.root/'plan.json';path.write_text(json.dumps(self.p),'utf-8')
        with patch.object(m,'probe',return_value=self.info):return m.validate(path,self.root)
    def test_valid(self):self.assertEqual(self.check()[2],2)
    def test_escape(self):
        self.p['clips'][0]['source']='../outside.mp4'
        with self.assertRaises(ValueError):self.check()
    def test_spoken_muted(self):
        self.p['clips'][0]['volume']=0
        with self.assertRaises(ValueError):self.check()
    def test_gap(self):
        self.p['clips'][0]['at']=1
        with self.assertRaises(ValueError):self.check()
    def test_range(self):
        self.p['clips'][0]['out']=6
        with self.assertRaises(ValueError):self.check()
    def test_overlap(self):
        self.p['clips'].append(dict(self.p['clips'][0],id='b',at=1))
        with self.assertRaises(ValueError):self.check()
    def test_unknown_effect_rejected(self):
        self.p['clips'][0]['unimplemented_effect']='glow'
        with self.assertRaises(ValueError):self.check()
    def test_nan(self):
        self.p['clips'][0]['speed']=float('nan')
        with self.assertRaises(ValueError):self.check()
    def test_caption_outside(self):
        self.p['captions']=[{'text':'caption','at':1.5,'duration':1}]
        with self.assertRaises(ValueError):self.check()
    def test_missing_decision_rejected(self):
        del self.p['clips'][0]['decision']
        with self.assertRaises(ValueError):self.check()
    def test_external_without_native_gap_rejected(self):
        self.p['clips'][0]['decision']['route']='external'
        with self.assertRaises(ValueError):self.check()
    def test_empty_comparison_reason_rejected(self):
        self.p['clips'][0]['decision']['comparison_not_needed']=''
        with self.assertRaises(ValueError):self.check()
    def test_old_plan_version_refused(self):
        self.p['version']=1
        with self.assertRaises(ValueError):self.check()
    def test_no_native_controller(self):
        init=(ROOT/'vendor/pyJianYingDraft/__init__.py').read_text('utf-8')
        self.assertIn('ISWIN = False',init)
        self.assertFalse((ROOT/'vendor/pyJianYingDraft/jianying_controller.py').exists())
class ReleaseTests(unittest.TestCase):
    def test_unlisted_private_file_excluded(self):
        with tempfile.TemporaryDirectory() as temp:
            d=Path(temp);(d/'good.py').write_text('print(1)');(d/'private.txt').write_text('private')
            (d/'release-files.json').write_text(json.dumps(['good.py']))
            self.assertEqual([x[0] for x in r.inventory(d)],['good.py'])
    def test_secret_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            d=Path(temp);(d/'good.py').write_text('ghp_'+'a'*30);(d/'release-files.json').write_text(json.dumps(['good.py']))
            with self.assertRaises(ValueError):r.inventory(d)
    def test_traversal_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            d=Path(temp);(d/'release-files.json').write_text(json.dumps(['../outside.txt']))
            with self.assertRaises(ValueError):r.inventory(d)
if __name__=='__main__':unittest.main()
