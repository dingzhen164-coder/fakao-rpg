"""法考学院正式美术的随包路径、原生尺寸和分块来源记录。"""
import hashlib
import json
import unittest
from pathlib import Path

from PIL import Image

from rpg import art, paths


class AcademyArtTest(unittest.TestCase):
    def test_native_scenes_and_packaged_room_mapping(self):
        assets = paths.WEB_DIR / 'assets'
        records = json.loads((assets / 'academy/provenance.json').read_text(encoding='utf-8'))['records']
        rooms = ['minfa', 'xingfa', 'minsu', 'xingsu', 'xingzheng', 'shangjing', 'sanguo', 'lilun']
        self.assertEqual(set(records), set(rooms + ['academy', 'academy-portrait']))
        for key, record in records.items():
            expected = (2880, 3840) if key == 'academy-portrait' else (3840, 2880)
            self.assertEqual(tuple(record['target']), expected)
            self.assertEqual(tuple(record['grid']), (3, 3) if key == 'academy-portrait' else (4, 2))
            self.assertEqual(len(record['tiles']), 9 if key == 'academy-portrait' else 8)
            self.assertEqual(record['reference']['role'], 'composition-and-low-frequency-tone-only')
            for tile in record['tiles']:
                self.assertGreaterEqual(tile['native'][0], tile['w'])
                self.assertGreaterEqual(tile['native'][1], tile['h'])
                self.assertEqual(len(tile['sha256']), 64)
            file = paths.WEB_DIR.parent / record['output']
            self.assertTrue(file.is_file(), file)
            self.assertEqual(file.stat().st_size, record['bytes'])
            self.assertEqual(hashlib.sha256(file.read_bytes()).hexdigest(), record['sha256'])
            with Image.open(file) as image:
                self.assertEqual(image.size, expected)
                image.verify()
        for key in rooms:
            rel = f'beauty/page/train-{key}.webp'
            self.assertEqual(art.builtin_asset('法考', rel), assets / rel)
            with Image.open(assets / f'academy/rooms/thumb-{key}.webp') as image:
                self.assertEqual(image.size, (640, 480))


if __name__ == '__main__':
    unittest.main()
