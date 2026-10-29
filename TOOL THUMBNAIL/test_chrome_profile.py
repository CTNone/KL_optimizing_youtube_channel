from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from chrome_profile import import_session, discover_profiles


class ProfileTests(unittest.TestCase):
    def test_discover_existing_profiles_only(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            root = Path(temporary)
            (root / 'Local State').write_text('{"profile":{"info_cache":{"Default":{"name":"Personal"},"Profile 1":{"name":"Work"},"Profile 9":{"name":"Deleted"}}}}')
            for name in ['Default', 'Profile 1', 'Profile 2', 'System Profile']:
                (root / name).mkdir()
                (root / name / 'Preferences').write_text('{}')
            found = discover_profiles(root)
            self.assertEqual([p['directory'] for p in found], ['Default', 'Profile 1', 'Profile 2'])
            self.assertEqual(found[1]['name'], 'Work')
            self.assertEqual(discover_profiles(root / 'missing'), [])

    def test_session_only_and_preserve_existing(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            root = Path(temporary)
            source = root / 'User Data' / 'Profile 1'
            source.mkdir(parents=True)
            (source.parent / 'Local State').write_text('{}')
            (source / 'Preferences').write_text('{}')
            (source / 'Network').mkdir()
            (source / 'Network' / 'Cookies').write_bytes(b'synthetic-session')
            (source / 'Login Data').write_bytes(b'synthetic-password')
            (source / 'History').write_bytes(b'synthetic-history')
            destination = root / 'tool' / 'chrome-profile'
            with patch('chrome_profile.chrome_running', return_value=False):
                import_session(source, destination)
                self.assertEqual((destination / 'Default/Network/Cookies').read_bytes(), b'synthetic-session')
                self.assertFalse((destination / 'Default/Login Data').exists())
                self.assertFalse((destination / 'Default/History').exists())
                self.assertTrue((source / 'Network/Cookies').exists())
                with self.assertRaises(ValueError):
                    import_session(source, destination)
            with patch('chrome_profile.chrome_running', return_value=True):
                with self.assertRaisesRegex(ValueError, 'Đóng'):
                    import_session(source, root / 'other')
                self.assertFalse((root / 'other').exists())


if __name__ == '__main__':
    unittest.main()
