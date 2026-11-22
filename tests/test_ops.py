import unittest
from unittest import mock
from pathlib import Path
import tempfile

from recapper.ops import registry
from recapper.ops.base import RenderContext


class TestRegistry(unittest.TestCase):
    def test_builtins_registered(self):
        names = [o.name for o in registry.list()]
        for expected in ['title-slide','image-to-video','images-to-side-by-side-video','normalize-video','audio-track']:
            self.assertIn(expected, names)

    def test_clip_type_mappings(self):
        m = registry.clip_type_mappings()
        self.assertEqual(m['title'], 'title-slide')
        self.assertEqual(m['image'], 'image-to-video')
        self.assertEqual(m['composition'], 'images-to-side-by-side-video')

    def test_schema_has_fields(self):
        op = registry.get('title-slide')
        s = op.schema()
        self.assertEqual(s['name'], 'title-slide')
        self.assertTrue(any(p['name']=='title' for p in s['params']))


class TestOperationBuild(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.tmp = Path(self.td.name)
        self.ctx = RenderContext(project_dir=self.tmp, temp_dir=self.tmp/'tmp', output_dir=self.tmp/'out', render_settings={'width':320,'height':240,'fps':24})
        self.ctx.temp_dir.mkdir(parents=True, exist_ok=True)
        self.ctx.output_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.td.cleanup()

    @mock.patch('recapper.ops.title_slide.run_ffmpeg')
    @mock.patch('recapper.ops.title_slide.which', return_value='/usr/bin/ffmpeg')
    @mock.patch('recapper.ops.title_slide.resolve_font', return_value='/tmp/font.ttf')
    def test_title_slide_builds_command(self, _font, _which, run_ffmpeg):
        op = registry.get('title-slide')
        res = op.build({}, {'title':'Hello','subtitle':'World','duration':2,'width':320,'height':240,'fps':24,'color':'black'}, self.ctx)
        self.assertTrue(res.outputs)
        cmd = res.commands[0]
        self.assertEqual(cmd[0], '/usr/bin/ffmpeg')
        joined = ' '.join(cmd)
        self.assertIn('drawtext', joined)
        self.assertIn('anullsrc', joined)
        run_ffmpeg.assert_called_once()

    @mock.patch('recapper.ops.image_to_video.run_ffmpeg')
    @mock.patch('recapper.ops.image_to_video.which', return_value='/usr/bin/ffmpeg')
    def test_image_to_video_builds_command(self, _which, run_ffmpeg):
        img = self.tmp/'img.jpg'
        img.write_bytes(b'fake')
        op = registry.get('image-to-video')
        res = op.build({'image': str(img)}, {'duration':2,'width':320,'height':240,'fps':24}, self.ctx)
        cmd = res.commands[0]
        joined = ' '.join(cmd)
        self.assertIn('-loop', joined)
        self.assertIn('scale=', joined)
        run_ffmpeg.assert_called_once()

    @mock.patch('recapper.ops.side_by_side.run_ffmpeg')
    @mock.patch('recapper.ops.side_by_side.which', return_value='/usr/bin/ffmpeg')
    def test_side_by_side_builds_command(self, _which, run_ffmpeg):
        left = self.tmp/'l.jpg'; left.write_bytes(b'l')
        right = self.tmp/'r.jpg'; right.write_bytes(b'r')
        op = registry.get('images-to-side-by-side-video')
        res = op.build({'left_image': str(left), 'right_image': str(right)}, {'duration':2,'width':320,'height':240,'fps':24}, self.ctx)
        joined = ' '.join(res.commands[0])
        self.assertIn('hstack', joined)
        run_ffmpeg.assert_called_once()


if __name__ == '__main__':
    unittest.main()
