"""Offline checks for scripts/transfer_photos.py. No phone, SSH or real photos needed."""
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

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


def listing_line(name, size, stamp='Oct 22 12:00'):
    return '-rw-r--r--    1 user     users      {} {} {}'.format(size, stamp, name)


class ListingChecks(unittest.TestCase):
    def test_names_and_sizes_are_read(self):
        text = listing_line('./b.jpg', 12) + '\n' + listing_line('./Camera/a.JPG', 5, 'Jan  1  2009') + '\n'
        self.assertEqual(transfer.parse_listing(text), (
            [('Camera/a.JPG', 5, 'Jan  1  2009'), ('b.jpg', 12, 'Oct 22 12:00')], []))

    def test_one_odd_file_is_skipped_not_fatal(self):
        text = '\n'.join([
            listing_line('./good.jpg', 10),
            listing_line('./photo one.jpg', 10),    # space
            listing_line('./notes.txt', 10),        # not a photo
            listing_line('./../etc/x.jpg', 10),     # climbs out
            listing_line('./good.jpg', 10),         # repeated
        ])
        entries, skipped = transfer.parse_listing(text)
        self.assertEqual([e[0] for e in entries], ['good.jpg'])
        self.assertEqual(len(skipped), 4)

    def test_something_that_is_not_a_listing_is_refused(self):
        with self.assertRaises(ValueError):
            transfer.parse_listing('d41d8cd98f00b204e9800998ecf8427e  ./a.jpg')
        self.assertEqual(transfer.parse_listing(''), ([], []))


class CacheChecks(unittest.TestCase):
    def test_unchanged_local_files_are_not_hashed_again(self):
        with tempfile.TemporaryDirectory() as folder:
            photo = Path(folder) / 'p.jpg'
            photo.write_bytes(JPEG)
            cache = {}
            with patch.object(transfer, 'md5_file', wraps=transfer.md5_file) as hashed:
                transfer.local_checksums((Path(folder),), cache)
                found = transfer.local_checksums((Path(folder),), cache)
                self.assertEqual(hashed.call_count, 1)
                self.assertEqual(set(found), {md5(JPEG)})
                photo.write_bytes(JPEG + b'edited')
                self.assertEqual(set(transfer.local_checksums((Path(folder),), cache)), {md5(JPEG + b'edited')})
                self.assertEqual(hashed.call_count, 2)
            photo.unlink()
            transfer.local_checksums((Path(folder),), cache)
            self.assertEqual(cache, {})

    def test_damaged_cache_file_means_start_over(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'cache.json'
            path.write_text('{"phone": ')
            self.assertEqual(transfer.load_cache(path), {'phone': {}, 'local': {}})
            transfer.save_cache(path, {'phone': {'a.jpg': [1, 'x', 'y']}, 'local': {}})
            self.assertEqual(transfer.load_cache(path)['phone'], {'a.jpg': [1, 'x', 'y']})


class FakePhone:
    """Stands in for ssh: answers listing, checksum and download commands from a dict of files."""

    def __init__(self, files, listing_works=True):
        self.files, self.listing_works = files, listing_works
        self.checksummed, self.downloaded = [], []

    def __call__(self, argv, **kwargs):
        command = argv[-1]
        if 'stdout' in kwargs:
            name = command.split('/')[-1].strip("'")
            self.downloaded.append(name)
            kwargs['stdout'].write(self.files[name])
            return subprocess.CompletedProcess(argv, 0)
        if 'ls -l' in command:
            if not self.listing_works:
                return subprocess.CompletedProcess(argv, 0, stdout=''.join(
                    '{}  ./{}\n'.format(md5(data), name) for name, data in self.files.items()))
            return subprocess.CompletedProcess(argv, 0, stdout=''.join(
                listing_line('./' + name, len(data)) + '\n' for name, data in self.files.items()))
        if 'for f in' in command:
            names = list(self.files)
        else:
            names = [part.strip("'")[2:] for part in command.split('md5sum ')[1].split()]
        self.checksummed.extend(names)
        return subprocess.CompletedProcess(argv, 0, stdout=''.join(
            '{}  ./{}\n'.format(md5(self.files[name]), name) for name in names))


class RunChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.private = Path(self.temp.name) / 'private'
        self.key = Path(self.temp.name) / 'key'
        self.key.write_text('placeholder')

    def tearDown(self):
        self.temp.cleanup()

    def run_transfer(self, phone):
        with patch.object(transfer, 'PRIVATE', self.private), \
                patch.object(transfer.subprocess, 'run', side_effect=phone), redirect_stdout(io.StringIO()):
            return transfer.main(['--host', 'phone.local', '--key', str(self.key)])

    def receipts(self):
        return sorted((self.private / 'transfers').glob('*-receipt.json'))

    def test_odd_file_on_phone_does_not_stop_other_photos(self):
        # The fake phone lists both files; the odd name must be skipped and never downloaded.
        phone = FakePhone({'20261023_001.jpg': JPEG, 'photo one.jpg': JPEG + b'odd'})
        self.assertEqual(self.run_transfer(phone), 0)
        self.assertEqual(phone.downloaded, ['20261023_001.jpg'])
        self.assertEqual([p.name for p in (self.private / 'inbox').iterdir()], ['20261023_001.jpg'])
        receipt = json.loads(self.receipts()[0].read_text())
        self.assertTrue(receipt['complete'])
        self.assertEqual(len(receipt['skipped_phone_files']), 1)

    def test_known_photos_are_not_checksummed_or_receipted_again(self):
        phone = FakePhone({'20261023_001.jpg': JPEG})
        self.assertEqual(self.run_transfer(phone), 0)
        self.assertEqual(phone.checksummed, ['20261023_001.jpg'])
        self.assertEqual(len(self.receipts()), 1)
        phone.files['20261024_001.jpg'] = JPEG + b'new'
        phone.checksummed.clear()
        self.assertEqual(self.run_transfer(phone), 0)
        self.assertEqual(phone.checksummed, ['20261024_001.jpg'])
        self.assertEqual(len(self.receipts()), 2)
        phone.checksummed.clear()
        self.assertEqual(self.run_transfer(phone), 0)
        self.assertEqual(phone.checksummed, [])
        self.assertEqual(len(self.receipts()), 2)  # nothing new, so no new receipt

    def test_unreadable_listing_falls_back_to_checksumming_everything(self):
        phone = FakePhone({'20261023_001.jpg': JPEG}, listing_works=False)
        self.assertEqual(self.run_transfer(phone), 0)
        self.assertEqual(phone.downloaded, ['20261023_001.jpg'])

    def test_corrupted_download_leaves_no_photo_and_fails(self):
        phone = FakePhone({'20261023_001.jpg': JPEG})
        original = phone.__call__

        def corrupt(argv, **kwargs):
            if 'stdout' in kwargs:
                kwargs['stdout'].write(JPEG + b'damaged in transit')
                return subprocess.CompletedProcess(argv, 0)
            return original(argv, **kwargs)

        self.assertEqual(self.run_transfer(corrupt), 1)
        inbox = self.private / 'inbox'
        self.assertEqual(list(inbox.iterdir()), [])
        self.assertFalse(json.loads(self.receipts()[0].read_text())['complete'])


if __name__ == '__main__':
    unittest.main()
