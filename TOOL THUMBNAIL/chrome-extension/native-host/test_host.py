import base64
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from host import Files, read_message


class HostTests(unittest.TestCase):
    def test_crop_preserves_original_and_exact_top_rectangle(self):
        from PIL import Image
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            source = Path(tmp).resolve() / 'original.png'
            image = Image.new('RGB', (2048, 1536), 'red')
            image.paste('blue', (0, 1152, 2048, 1536))
            image.save(source)
            original = source.read_bytes()
            host = Files()
            result = host.crop_image(str(source), True)
            self.assertEqual(source.read_bytes(), original)
            with Image.open(result['filename']) as cropped:
                self.assertEqual(cropped.size, (2048, 1152))
                self.assertGreater(cropped.getpixel((100, 1151))[0], 240)
            self.assertEqual(host.crop_image(str(source), True)['filename'], result['filename'])
            self.assertEqual(len(list(Path(tmp).glob('*_16x9.jpg'))), 1)
            Image.new('RGB', (2050, 1538), 'green').save(source)
            result = host.crop_image(str(source), False)
            self.assertEqual(result['width'] * 9, result['height'] * 16)
            self.assertTrue(host.chunk(result['token'], 0)['length'] > 0)

    def test_paths_collision_and_bytes(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            host = Files()
            host.directory = Path(tmp).resolve()
            payload = b'\x89PNG\r\n\x1a\n' + b'test-image'
            data = 'data:image/png;base64,' + base64.b64encode(payload).decode()
            one = host.write('run_123/0001_01.png', data)
            two = host.write('run_123/0001_01.png', data)
            self.assertTrue(Path(one['filename']).is_absolute())
            self.assertNotEqual(one['filename'], two['filename'])
            self.assertEqual(Path(one['filename']).read_bytes(), payload)
            for path in ['../image.png', 'run_123/../../image.png', 'C:/image.png']:
                with self.assertRaises(ValueError):
                    host.write(path, data)
            with self.assertRaises(ValueError):
                host.write('run_123/0001_01.png', 'data:image/png;base64,YmFk')
            with self.assertRaises(ValueError):
                host.write('run_123/0001_01.jpg', data)

    def test_no_write_without_picker(self):
        with self.assertRaises(ValueError):
            Files().write('run_123/0001_01.png', '')

    def test_import_exact_download_and_reject_preview(self):
        from PIL import Image
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            host = Files()
            host.directory = Path(tmp).resolve()
            source = host.directory / 'download.webp'
            Image.new('RGB', (2048, 1152), 'red').save(source)
            result = host.import_image('run_123/0001_01.png', str(source))
            self.assertEqual((result['width'], result['height']), (2048, 1152))
            self.assertEqual(Path(result['filename']).suffix, '.webp')
            self.assertEqual(Path(result['filename']).read_bytes(), source.read_bytes())
            with self.assertRaisesRegex(ValueError, 'trùng dữ liệu'):
                host.import_image('run_123/0001_02.png', str(source))
            reader = Files()
            inspected = reader.inspect_image(str(source))
            self.assertEqual(inspected['sha256'], result['sha256'])
            data = reader.chunk(inspected['token'], 0)
            self.assertEqual(base64.b64decode(data['base64']), source.read_bytes())
            Image.new('RGB', (1024, 1024)).save(source)
            with self.assertRaisesRegex(ValueError, 'chưa đạt 2K'):
                host.import_image('run_123/0001_02.png', str(source))

    def test_chunk_limits_and_tokens(self):
        host = Files()
        host.payloads = {'valid': b'x' * 700000}
        first = host.chunk('valid', 0)
        second = host.chunk('valid', first['length'])
        self.assertEqual(len(base64.b64decode(first['base64'])) + len(base64.b64decode(second['base64'])), 700000)
        self.assertLess(len(json.dumps(first)), 1024 * 1024)
        for token, offset in [('invalid', 0), ('valid', -1), ('valid', 700000)]:
            with self.assertRaises(ValueError):
                host.chunk(token, offset)

    def test_protocol(self):
        encoded = json.dumps({'id': 'one', 'type': 'choose'}).encode()
        self.assertEqual(read_message(io.BytesIO(struct.pack('<I', len(encoded)) + encoded))['id'], 'one')
        self.assertIsNone(read_message(io.BytesIO()))
        for packet in [b'x', struct.pack('<I', 100) + b'{}', struct.pack('<I', 40 * 1024 * 1024)]:
            with self.assertRaises(ValueError):
                read_message(io.BytesIO(packet))


if __name__ == '__main__':
    unittest.main()
