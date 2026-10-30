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
        provenance = json.loads((assets / 'academy/provenance.json').read_text(encoding='utf-8'))
        records = provenance['records']
        rooms = ['minfa', 'xingfa', 'minsu', 'xingsu', 'xingzheng', 'shangjing', 'sanguo', 'lilun']
        seasonal = [f'academy-{season}{suffix}' for season in ('summer', 'autumn', 'winter')
                    for suffix in ('', '-portrait')]
        self.assertEqual(set(records), set(rooms + ['academy', 'academy-portrait'] + seasonal))
        for key, record in records.items():
            expected = (2880, 3840) if key.endswith('-portrait') else (3840, 2880)
            self.assertEqual(tuple(record['target']), expected)
            self.assertEqual(tuple(record['grid']), (3, 3) if key.endswith('-portrait') else (4, 2))
            self.assertEqual(len(record['tiles']), 9 if key.endswith('-portrait') else 8)
            if key == 'academy':        # 春季白天：12 处极简新地图是“地形原生块 + 建筑单体合成”，没有整图构图参考
                self.assertEqual(record['overlap_px'], 64)
                self.assertIn('composited', record['method'])
            else:
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
            self.assertEqual(art.builtin_asset('法考', f'beauty/page/train-{key}-night.webp'),
                             assets / f'beauty/page/train-{key}-night.webp')
            with Image.open(assets / f'academy/rooms/thumb-{key}.webp') as image:
                self.assertEqual(image.size, (640, 480))
        matrix = provenance['sceneMatrix']
        self.assertEqual(len(matrix), 24)
        self.assertEqual(len({v['sha256'] for v in matrix.values()}), 24)
        for state, record in matrix.items():
            file = paths.WEB_DIR.parent / record['file']
            self.assertTrue(file.is_file(), state)
            self.assertEqual(hashlib.sha256(file.read_bytes()).hexdigest(), record['sha256'])
            with Image.open(file) as image:
                self.assertEqual(list(image.size), record['size'])
        self.assertEqual(len(provenance['lighting']), 24)


if __name__ == '__main__':
    unittest.main()
