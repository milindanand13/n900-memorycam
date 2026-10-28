"""Photo organization, migration safety and subsequent transfers without a phone."""
from contextlib import redirect_stdout
from datetime import date
import io
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import organize_photos as organize
import photo_library as library
import transfer_photos as transfer

JPEG = b"\xff\xd8\xff\xe0synthetic-photo"


class DateChecks(unittest.TestCase):
    def test_week_contains_the_recorded_capture_date(self):
        self.assertEqual(library.date_folders("20261022_001.jpg", date(2026, 10, 25)),
                         Path("2026-W43/2026-10-22"))
        self.assertEqual(library.date_folders("20270101_001.jpg", date(2027, 1, 2)),
                         Path("2026-W53/2027-01-01"))

    def test_bad_old_missing_and_future_dates_are_not_invented(self):
        for name in ("20090101_001.jpg", "20120712_001.jpg", "20260230_001.jpg", "me.png", "20271022_001.jpg"):
            self.assertEqual(library.date_folders(name, date(2026, 10, 25)), Path("Date-unverified"))

    def test_external_destination_is_explicit_and_nested_symlink_cannot_escape(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with self.assertRaises(ValueError):
                library.validate_root(root / "repo/photos", root / "repo")
            (root / "photos").mkdir()
            (root / "escape").mkdir()
            (root / "photos/Date-unverified").symlink_to(root / "escape", target_is_directory=True)
            with self.assertRaises(ValueError):
                library.photo_directory(root / "photos", "old.jpg")


class MigrationChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.private = self.root / "private"
        self.source = self.private / "inbox"
        self.source.mkdir(parents=True)
        self.photos = self.root / "Pictures/Personal/Nokia-N900"

    def tearDown(self):
        self.temp.cleanup()

    def test_verified_move_keeps_old_paths_working_and_repeat_run_is_safe(self):
        old = self.source / "20090119_004.jpg"
        recent = self.source / "20261022_001.jpg"
        old.write_bytes(JPEG)
        recent.write_bytes(JPEG + b"new")
        note = self.source / "notes.txt"
        note.write_text("keep")
        with organize.migration_lock(self.private):
            receipt, records = organize.migrate([self.source], self.photos, self.private)
        self.assertEqual(len(records), 2)
        self.assertTrue(json.loads(receipt.read_text())["complete"])
        for source in (old, recent):
            self.assertTrue(source.is_symlink())
            self.assertTrue(source.is_file())
        self.assertEqual(old.read_bytes(), JPEG)
        self.assertEqual(recent.read_bytes(), JPEG + b"new")
        self.assertEqual(note.read_text(), "keep")
        self.assertTrue((self.photos / "2026-W43/2026-10-22/20261022_001.jpg").is_file())
        self.assertTrue((self.photos / "Date-unverified/20090119_004.jpg").is_file())
        self.assertEqual(library.configured_root(self.private, self.root / "repo"), self.photos.resolve())
        organize.migrate([self.source], self.photos, self.private)
        self.assertEqual(len(list(self.photos.rglob("*.jpg"))), 2)

    def test_bad_photo_does_not_switch_configuration_or_remove_sources(self):
        good, bad = self.source / "20261022_001.jpg", self.source / "20261022_002.jpg"
        good.write_bytes(JPEG)
        bad.write_bytes(b"broken photo")
        with self.assertRaises(ValueError):
            organize.migrate([self.source], self.photos, self.private)
        self.assertFalse(good.is_symlink())
        self.assertEqual(good.read_bytes(), JPEG)
        self.assertFalse((self.private / "photo-library.json").exists())

    def test_corrupt_copy_is_rejected_before_any_source_is_replaced(self):
        source = self.source / "20261022_001.jpg"
        source.write_bytes(JPEG)
        with patch.object(organize.shutil, "copy2", side_effect=lambda src, dest: dest.write_bytes(b"corrupt")):
            with self.assertRaises(ValueError):
                organize.migrate([self.source], self.photos, self.private)
        self.assertFalse(source.is_symlink())
        self.assertEqual(source.read_bytes(), JPEG)
        self.assertFalse((self.private / "photo-library.json").exists())
        self.assertEqual(list(self.photos.rglob("*.part")), [])

    def test_filename_collision_preserves_both_photos(self):
        older = self.root / "other"
        older.mkdir()
        (older / "20261022_001.jpg").write_bytes(JPEG + b"a")
        (self.source / "20261022_001.jpg").write_bytes(JPEG + b"b")
        organize.migrate([older, self.source], self.photos, self.private)
        contents = {p.read_bytes() for p in self.photos.rglob("*.jpg")}
        self.assertEqual(contents, {JPEG + b"a", JPEG + b"b"})

    def test_migration_respects_the_scheduler_lock(self):
        with organize.migration_lock(self.private):
            with self.assertRaises(BlockingIOError), organize.migration_lock(self.private):
                self.fail("A second migration acquired the same lock")

    def test_future_pull_uses_week_and_date_and_skips_the_migrated_content(self):
        (self.source / "20261022_001.jpg").write_bytes(JPEG)
        organize.migrate([self.source], self.photos, self.private)
        incoming = JPEG + b"next-day"
        remote = {"20261022_001.jpg": JPEG, "20261023_001.jpg": incoming}
        key = self.root / "key"
        key.write_text("test placeholder")
        downloads = []

        def ssh(argv, **kwargs):
            if "stdout" in kwargs:
                name = argv[-1].split("/")[-1]
                downloads.append(name)
                kwargs["stdout"].write(remote[name])
                return subprocess.CompletedProcess(argv, 0)
            manifest = "".join("{}  ./{}\n".format(hashlib.md5(data).hexdigest(), name)
                               for name, data in remote.items())
            return subprocess.CompletedProcess(argv, 0, stdout=manifest)

        with patch.object(transfer, "PRIVATE", self.private), patch.object(transfer.subprocess, "run", side_effect=ssh), redirect_stdout(io.StringIO()):
            self.assertEqual(transfer.main(["--host", "phone.local", "--key", str(key)]), 0)
            self.assertEqual(transfer.main(["--host", "phone.local", "--key", str(key)]), 0)
        self.assertEqual(downloads, ["20261023_001.jpg"])
        saved = self.photos / "2026-W43/2026-10-23/20261023_001.jpg"
        self.assertEqual(saved.read_bytes(), incoming)
        self.assertEqual(len(list(self.photos.rglob("*.jpg"))), 2)


if __name__ == "__main__":
    unittest.main()
