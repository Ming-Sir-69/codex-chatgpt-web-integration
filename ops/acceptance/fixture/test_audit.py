import hashlib
from pathlib import Path
import tempfile
import unittest

from audit import audit


def digest(value):
    return hashlib.sha256(value).hexdigest()


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_valid_and_unlisted_files(self):
        (self.root / 'app.bin').write_bytes(b'payload')
        (self.root / 'other').write_bytes(b'ignored')
        self.assertEqual(audit(self.root, {'app.bin': digest(b'payload')}),
                         {'ok': True, 'missing': [], 'mismatched': []})
        self.assertEqual((self.root / 'app.bin').read_bytes(), b'payload')

    def test_missing_and_mismatched_sorted(self):
        (self.root / 'bad').write_bytes(b'bad')
        self.assertEqual(audit(self.root, {'z': digest(b'x'), 'bad': digest(b'good'), 'a': digest(b'y')}),
                         {'ok': False, 'missing': ['a', 'z'], 'mismatched': ['bad']})

    def test_empty(self):
        self.assertEqual(audit(self.root, {}), {'ok': True, 'missing': [], 'mismatched': []})

    def test_nested_and_unicode(self):
        (self.root / '构建').mkdir()
        (self.root / '构建/app').write_bytes(b'\x00\xff')
        self.assertTrue(audit(self.root, {'构建/app': digest(b'\x00\xff')})['ok'])

    def test_invalid_paths_and_digest(self):
        for path in ['../outside', '/absolute', '', 'dir/../app']:
            with self.subTest(path=path), self.assertRaises(ValueError):
                audit(self.root, {path: digest(b'x')})
        with self.assertRaises(ValueError):
            audit(self.root, {'app': 'not-a-hash'})

    def test_symlink_escape(self):
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / 'file'
            target.write_bytes(b'x')
            (self.root / 'escape').symlink_to(target)
            with self.assertRaises(ValueError):
                audit(self.root, {'escape': digest(b'x')})


if __name__ == '__main__':
    unittest.main()
