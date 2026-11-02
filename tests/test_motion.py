import json,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import test_invariants as fixtures
m=fixtures.m;ROOT=fixtures.ROOT

class MotionTests(unittest.TestCase):
    tearDown=fixtures.PlanTests.tearDown
    check=fixtures.PlanTests.check
    def setUp(self):
        fixtures.PlanTests.setUp(self)
        self.p['clips'][0]['keyframes']={'uniform_scale':[{'time':0,'value':1},{'time':.6,'value':1.2},{'time':2,'value':1.2}]}
    def test_source_time_not_timeline_time(self):
        self.p['clips'][0]['speed']=2
        with self.assertRaises(ValueError):self.check()
    def test_duplicate_time(self):
        self.p['clips'][0]['keyframes']['uniform_scale'][1]['time']=0
        with self.assertRaises(ValueError):self.check()
    def test_alpha_range(self):
        self.p['clips'][0]['keyframes']={'alpha':[{'time':0,'value':1},{'time':1,'value':2}]}
        with self.assertRaises(ValueError):self.check()
    def test_missing_zero(self):
        self.p['clips'][0]['keyframes']['uniform_scale'][0]['time']=.1
        with self.assertRaises(ValueError):self.check()
    def test_unknown_property(self):
        self.p['clips'][0]['keyframes']={'made_up':[]}
        with self.assertRaises(ValueError):self.check()
    def test_unequal_scale(self):
        self.p['clips'][0]['transform']={'scale_x':1,'scale_y':2}
        with self.assertRaises(ValueError):self.check()
    def test_preview_refuses_motion(self):
        self.check()
        with patch.object(m,'probe',return_value=self.info):
            with self.assertRaisesRegex(ValueError,'Preview only'):
                m.preview(SimpleNamespace(plan=self.root/'plan.json',media_root=self.root,ffprobe='ffprobe',out=self.root/'out.mp4'))
    def test_real_backend_serialization_and_receipt(self):
        self.check()
        sys.path.insert(0,str(ROOT/'vendor'))
        import pyJianYingDraft as d
        material=d.VideoMaterial.__new__(d.VideoMaterial)
        material.material_id='fixture';material.path=str(self.root/'source.mp4');material.duration=5000000
        material.width=1920;material.height=1080;material.material_name='source.mp4'
        material.local_material_id='fixture-local';material.material_type='video'
        from pyJianYingDraft.local_materials import CropSettings
        material.crop_settings=CropSettings()
        with patch.object(m,'probe',return_value=self.info),patch.object(d,'VideoMaterial',return_value=material):
            out=self.root/'draft'
            m.build(SimpleNamespace(plan=self.root/'plan.json',media_root=self.root,ffprobe='ffprobe',out=out))
        content=json.loads((out/'draft_content.json').read_text('utf-8'))
        segment=content['tracks'][0]['segments'][0]
        frames=segment['common_keyframes'][0]['keyframe_list']
        self.assertEqual([f['time_offset'] for f in frames],[0,600000,2000000])
        receipt=json.loads((out/'maliang-build.json').read_text('utf-8'))
        self.assertEqual(receipt['shot_decisions'][0]['implemented_parameters']['keyframes'],self.p['clips'][0]['keyframes'])
        self.assertEqual(receipt['shot_decisions'][0]['visual_verification'],'PENDING')

if __name__=='__main__':unittest.main()
