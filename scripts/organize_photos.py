#!/usr/bin/env python3
"""Move existing Nokia photos into Pictures, then route future pulls there.

Photo bytes are copied and verified before old files become compatibility
symlinks. Non-photo files and phone originals are never changed. Re-running is
safe: content already in the library is reused, without replacing any photo.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

import photo_library
import transfer_photos as transfer


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def save_json(path, value):
    fd, name = tempfile.mkstemp(prefix=".organize-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


@contextmanager
def migration_lock(private):
    with (private / "auto-pull.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def migrate(roots, library, private):
    """Caller holds the auto-pull lock for the whole migration/config switch."""
    library.mkdir(parents=True, exist_ok=True, mode=0o700)
    sources = sorted({p for root in roots if root.is_dir() for p in root.rglob("*")
                      if p.is_file() and not p.is_symlink()
                      and p.suffix.lower() in transfer.PHOTO_EXTENSIONS})
    known = transfer.local_checksums((library,))
    records = []
    # Complete the verified copy of every source before changing any old file.
    for source in sources:
        expected_sha = sha256(source)
        checksum = transfer.md5_file(source)
        if not transfer.has_image_header(source, source.name):
            raise ValueError("Unexpected photo contents: " + str(source))
        destination = known.get(checksum)
        if destination is None:
            folder = photo_library.photo_directory(library, source.name)
            fd, name = tempfile.mkstemp(prefix=".organize-", suffix=".part", dir=str(folder))
            os.close(fd)
            part = Path(name)
            try:
                shutil.copy2(source, part)
                if sha256(part) != expected_sha:
                    raise ValueError("Copy verification failed: " + str(source))
                destination, _ = transfer.publish_verified(part, folder, source.name, checksum)
                known[checksum] = destination
            finally:
                part.unlink(missing_ok=True)
        if sha256(destination) != expected_sha or sha256(source) != expected_sha:
            raise ValueError("Photo changed during migration: " + str(source))
        records.append({"source": str(source), "destination": str(destination),
                        "sha256": expected_sha, "md5": checksum, "bytes": source.stat().st_size})

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    receipt_path = private / "transfers" / (stamp + "-organization.json")
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt = {"complete": False, "library": str(library), "photos": records}
    save_json(receipt_path, receipt)
    # Links keep old experiment paths working without keeping duplicate bytes.
    # Make each replacement atomic, after rechecking its verified destination.
    for record in records:
        source, destination = Path(record["source"]), Path(record["destination"])
        if sha256(source) != record["sha256"] or sha256(destination) != record["sha256"]:
            raise ValueError("Photo changed before path switch: " + str(source))
        fd, name = tempfile.mkstemp(prefix=".photo-link-", dir=str(source.parent))
        os.close(fd)
        os.unlink(name)
        try:
            os.symlink(str(destination), name)
            os.replace(name, source)
        finally:
            if os.path.lexists(name):
                os.unlink(name)
    save_json(private / "photo-library.json", {"root": str(library), "layout": "iso-week/date-v1"})
    receipt["complete"] = True
    save_json(receipt_path, receipt)
    return receipt_path, records


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", type=Path, default=photo_library.DEFAULT_LIBRARY)
    parser.add_argument("--source", type=Path, action="append", help="Additional existing Nokia photo folder")
    args = parser.parse_args(argv)
    private = transfer.PRIVATE.resolve()
    try:
        library = photo_library.validate_root(args.library, transfer.REPO_ROOT)
        roots = [private / "inbox", private / "archive", private / "nokia-images",
                 Path.home() / "Pictures" / "Nokia"] + (args.source or [])
        for root in roots:
            root = root.resolve()
            if root == library or library in root.parents or root in library.parents:
                raise ValueError("Source and destination folders must be separate.")
        private.mkdir(parents=True, exist_ok=True)
        with migration_lock(private):
            receipt, records = migrate(roots, library, private)
        print("Organized and verified {} photos. Future transfers now use {}".format(len(records), library))
        print("Receipt:", receipt)
        return 0
    except (OSError, ValueError) as error:
        print("Organization not completed: {}".format(error), file=sys.stderr)
        print("Verified copies are preserved; rerunning can finish a partial migration.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
