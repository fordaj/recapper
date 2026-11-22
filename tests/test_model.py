import unittest
from recapper.model import Project, MediaAsset, Track, Clip, RenderSettings, CLIP_TYPE_OPERATIONS


class TestModel(unittest.TestCase):
    def test_default_project_valid(self):
        p = Project.default('Demo')
        p.validate(strict_media=False)
        self.assertEqual(p.name, 'Demo')
        self.assertEqual(len(p.tracks), 2)

    def test_clip_type_mapping(self):
        self.assertEqual(CLIP_TYPE_OPERATIONS['title'], 'title-slide')
        self.assertEqual(CLIP_TYPE_OPERATIONS['image'], 'image-to-video')
        self.assertEqual(CLIP_TYPE_OPERATIONS['composition'], 'images-to-side-by-side-video')
        self.assertEqual(CLIP_TYPE_OPERATIONS['video'], 'normalize-video')
        self.assertEqual(CLIP_TYPE_OPERATIONS['audio'], 'audio-track')

    def test_round_trip(self):
        p = Project.default('RoundTrip')
        p.media.append(MediaAsset(id='m1', type='image', name='img', path='img.jpg'))
        p.clips.append(Clip(id='c1', track_id='V1', type='title', name='T', start=0, duration=2, params={'title':'Hi'}))
        p.validate(strict_media=True)
        d = p.to_dict()
        p2 = Project.from_dict(d)
        p2.validate(strict_media=True)
        self.assertEqual(p2.clips[0].params['title'], 'Hi')

    def test_strict_media_validation(self):
        p = Project.default('X')
        p.clips.append(Clip(id='c1', track_id='V1', type='image', name='I', start=0, duration=1, media_id='missing'))
        with self.assertRaises(ValueError):
            p.validate(strict_media=True)
        p.validate(strict_media=False)


if __name__ == '__main__':
    unittest.main()
