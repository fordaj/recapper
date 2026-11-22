import unittest
from pathlib import Path
import tempfile

from recapper.model import Project, MediaAsset, Track, Clip, RenderSettings
from recapper.render import RenderPipeline


class TestTimelineCompiler(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.tmp = Path(self.td.name)
        self.proj = Project(
            name='Test',
            media=[
                MediaAsset(id='m1', type='image', name='i1', path='i1.jpg'),
                MediaAsset(id='m2', type='image', name='i2', path='i2.jpg'),
            ],
            tracks=[Track(id='V1', kind='visual', label='V1', order=0), Track(id='A1', kind='audio', label='A1', order=1)],
            clips=[],
            render=RenderSettings(width=320, height=240, fps=24),
        )

    def tearDown(self):
        self.td.cleanup()

    def test_compiles_title_clip(self):
        self.proj.clips.append(Clip(id='c1', track_id='V1', type='title', name='T', start=0, duration=2, params={'title':'Hi'}))
        plan = RenderPipeline(self.proj, self.tmp/'.recapper.json').compile_visual_plan()
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0].operation, 'title-slide')

    def test_inserts_gap(self):
        self.proj.clips.append(Clip(id='c1', track_id='V1', type='title', name='T', start=2, duration=2, params={'title':'Hi'}))
        plan = RenderPipeline(self.proj, self.tmp/'.recapper.json').compile_visual_plan()
        self.assertEqual(plan[0].operation, 'gap-black')
        self.assertAlmostEqual(plan[0].duration, 2.0)
        self.assertEqual(plan[1].operation, 'title-slide')

    def test_maps_composition(self):
        self.proj.clips.append(Clip(id='c1', track_id='V1', type='composition', name='C', start=0, duration=2, params={'compLeft':'m1','compRight':'m2'}))
        plan = RenderPipeline(self.proj, self.tmp/'.recapper.json').compile_visual_plan()
        self.assertEqual(plan[0].operation, 'images-to-side-by-side-video')
        self.assertEqual(plan[0].inputs['left_image'], 'm1')

    def test_sorts_by_start(self):
        self.proj.clips.append(Clip(id='c2', track_id='V1', type='title', name='B', start=2, duration=1, params={'title':'B'}))
        self.proj.clips.append(Clip(id='c1', track_id='V1', type='title', name='A', start=0, duration=2, params={'title':'A'}))
        plan = RenderPipeline(self.proj, self.tmp/'.recapper.json').compile_visual_plan()
        self.assertEqual([p.clip_id for p in plan], ['c1','c2'])


if __name__ == '__main__':
    unittest.main()
