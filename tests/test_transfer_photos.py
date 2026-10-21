"""Offline checks for scripts/transfer_photos.py. No phone, SSH or real photos needed."""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
import transfer_photos as transfer  # noqa: E402

JPEG = b'\xff\xd8\xff\xe0' + b'fake jpeg body'
PNG = b'\x89PNG\r\n\x1a\n' + b'fake png body'


def md5(data):
    return hashlib.md5(data).hexdigest()


class ManifestChecks(unittest.TestCase):
    def test_valid_manifest_is_sorted_and_lowercased(self):
        a, b = 'A' * 32, 'b' * 32
        manifest = '{}  ./Camera/20261009_002.jpg\n{}  ./20261009_001.JPG\n'.format(a, b)
        self.assertEqual(transfer.parse_manifest(manifest),
                         [('20261009_001.JPG', b), ('Camera/20261009_002.jpg', 'a' * 32)])

    def test_unsafe_or_unexpected_lines_are_rejected(self):
        good = 'a' * 32
        bad_manifests = [
            good + '  ./../etc/passwd.jpg',        # climbs out of the photo folder
            good + '  ./notes.txt',                # not a photo
            good + '  ./photo one.jpg',            # unexpected character
            good + '  /home/user/photo.jpg',       # absolute path
            'abc  ./photo.jpg',                    # checksum too short
            good + '  ./a.jpg\n' + good + '  ./a.jpg',  # repeated path
        ]
        for manifest in bad_manifests:
            with self.subTest(manifest=manifest), self.assertRaises(ValueError):
                transfer.parse_manifest(manifest)


class PublishChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.inbox = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def part(self, data):
        path = self.inbox / '.incoming.part'
        path.write_bytes(data)
        return path

    def test_new_photo_gets_its_own_name(self):
        destination, status = transfer.publish_verified(self.part(JPEG), self.inbox, 'p.jpg', md5(JPEG))
        self.assertEqual((destination.name, status), ('p.jpg', 'transferred'))
        self.assertEqual(destination.read_bytes(), JPEG)
        self.assertFalse((self.inbox / '.incoming.part').exists())

    def test_same_content_already_saved_is_not_duplicated(self):
        (self.inbox / 'p.jpg').write_bytes(JPEG)
        destination, status = transfer.publish_verified(self.part(JPEG), self.inbox, 'p.jpg', md5(JPEG))
        self.assertEqual((destination.name, status), ('p.jpg', 'already_present'))
        self.assertEqual(sorted(p.name for p in self.inbox.iterdir()), ['p.jpg'])

    def test_reused_filename_never_overwrites_an_existing_photo(self):
        older = JPEG + b'older'
        (self.inbox / 'p.jpg').write_bytes(older)
        checksum = md5(JPEG)
        (self.inbox / 'p--{}.jpg'.format(checksum)).write_bytes(JPEG + b'also different')
        destination, status = transfer.publish_verified(self.part(JPEG), self.inbox, 'p.jpg', checksum)
        self.assertEqual(status, 'transferred')
        self.assertEqual(destination.name, 'p--{}-1.jpg'.format(checksum))
        self.assertEqual((self.inbox / 'p.jpg').read_bytes(), older)
        self.assertEqual(destination.read_bytes(), JPEG)


class ContentChecks(unittest.TestCase):
    def test_image_header_must_match_suffix(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'x'
            for data, name, expected in [(JPEG, 'a.jpg', True), (PNG, 'a.png', True),
                                         (PNG, 'a.jpg', False), (JPEG, 'a.png', False),
                                         (b'<html>', 'a.jpeg', False)]:
                path.write_bytes(data)
                with self.subTest(name=name, data=data[:4]):
                    self.assertEqual(transfer.has_image_header(path, name), expected)

    def test_local_photos_are_found_by_content_not_name(self):
        with tempfile.TemporaryDirectory() as folder:
            archive, inbox = Path(folder) / 'archive', Path(folder) / 'inbox'
            (archive / 'old').mkdir(parents=True)
            inbox.mkdir()
            (archive / 'old' / 'renamed.JPG').write_bytes(JPEG)
            (inbox / 'p.png').write_bytes(PNG)
            (inbox / 'notes.txt').write_bytes(b'not a photo')
            found = transfer.local_checksums((archive, inbox, Path(folder) / 'missing'))
            self.assertEqual(set(found), {md5(JPEG), md5(PNG)})

    def test_destinations_outside_private_are_refused(self):
        self.assertTrue(transfer.inside_private(transfer.PRIVATE / 'inbox'))
        self.assertFalse(transfer.inside_private(transfer.REPO_ROOT / 'inbox'))
        self.assertFalse(transfer.inside_private(transfer.PRIVATE / '..' / 'docs'))


if __name__ == '__main__':
    unittest.main()
