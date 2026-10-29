import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys
import io
import base64
from PIL import Image
import integrated_app
sys.path.insert(0, str(Path(__file__).parent / 'chrome-extension' / 'native-host'))
import host


class IntegrationTests(unittest.TestCase):
    def test_stage_reference_real_file_and_invalid_image(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            with patch.object(host, '__file__', str(Path(temporary) / 'host.py')):
                output = io.BytesIO()
                Image.new('RGB', (3000, 1800), 'red').save(output, format='PNG')
                data = 'data:image/png;base64,' + base64.b64encode(output.getvalue()).decode()
                files = host.Files()
                staged = files.stage_reference(data)
                self.assertEqual(files.stage_reference(data)['path'], staged['path'])
                self.assertTrue(Path(staged['path']).is_file())
                with Image.open(staged['path']) as image:
                    self.assertEqual(image.format, 'JPEG')
                    self.assertEqual(max(image.size), 2048)
                with self.assertRaises(Exception):
                    files.stage_reference('data:image/jpeg;base64,aGVsbG8=')

    def test_reference_handoff_ack_and_path_bounds(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            root = Path(temporary)
            nctt = root / 'TOOL NCTT'
            (nctt / 'thumbnails').mkdir(parents=True)
            source = nctt / 'thumbnails' / 'sample.png'
            Image.new('RGB', (640, 360), 'blue').save(source)
            native = root / 'TOOL THUMBNAIL' / 'chrome-extension' / 'native-host'
            native.mkdir(parents=True)
            queue = native / 'nctt-job.json'
            with patch.object(integrated_app, 'NCTT', nctt), patch.object(integrated_app, 'QUEUE', queue), patch.object(host, '__file__', str(native / 'host.py')):
                job = integrated_app.write_job('Christmas jazz café', source, count=2)
                with self.assertRaises(ValueError):
                    integrated_app.write_job('do not overwrite pending')
                files = host.Files()
                received = files.nctt_job()['job']
                self.assertEqual(received['prompt'], 'Christmas jazz café')
                self.assertEqual(received['count'], 2)
                self.assertGreater(files.chunk(received['referenceImage']['token'], 0)['length'], 0)
                with self.assertRaises(ValueError):
                    files.nctt_job('incorrect-id')
                self.assertTrue(queue.exists())
                files.nctt_job(job['id'])
                self.assertFalse(queue.exists())
                outside = root / 'outside.png'
                Image.new('RGB', (10, 10)).save(outside)
                with self.assertRaises(ValueError):
                    integrated_app.write_job('outside', outside)
                integrated_app.write_job('prompt only')
                self.assertIsNone(files.nctt_job()['job']['reference'])


if __name__ == '__main__':
    unittest.main()
