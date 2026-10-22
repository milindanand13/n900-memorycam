#!/usr/bin/env python3
"""Copy every photo from the N900 that is not already on the Mac, checking each one.

First open a temporary SSH connection in your own terminal (you type the
phone's root password there; this script never sees it):

    mkdir -p private/ssh-session && chmod 700 private/ssh-session
    ssh -M -S private/ssh-session/control -fN \\
        -o HostKeyAlgorithms=+ssh-rsa root@PHONE_IP

Then, from the repository root:

    python3 scripts/transfer_photos.py --host PHONE_IP

Close the connection afterwards with:

    ssh -S private/ssh-session/control -O exit root@PHONE_IP

For unattended runs, pass --key with a dedicated passwordless key instead of
opening a connection first (see scripts/auto_pull.py).

Originals stay on the phone and local photos are never overwritten. Each file
is checked against the phone's MD5 and its image header before it gets its
final name. Photos already in the inbox or archive (by content, not by name)
are skipped. A receipt for every run is saved in private/transfers/.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import subprocess
import sys
import tempfile
from datetime import datetime, timezone


REPO_ROOT = Path(__file__).resolve().parent.parent
PRIVATE = REPO_ROOT / "private"
PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png"}
REMOTE_ROOT = "/home/user/MyDocs/DCIM"
PNG_HEADER = b"\x89PNG\r\n\x1a\n"
JPEG_HEADER = b"\xff\xd8\xff"


def md5_file(path):
    digest = hashlib.md5()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_manifest(value):
    """Turn the phone's `md5sum` output into sorted (relative path, checksum) pairs.

    Rejects anything unexpected rather than guessing: odd characters, paths that
    climb out of the photo folder, non-photo suffixes and repeated paths.
    """
    entries = []
    seen = set()
    for line in value.splitlines():
        match = re.fullmatch(r"([0-9a-fA-F]{32})  (\./[A-Za-z0-9_./-]+)", line)
        if not match:
            raise ValueError("Unexpected filename or checksum in the phone manifest.")
        checksum, source = match.groups()
        relative = source[2:]
        path = PurePosixPath(relative)
        if (
            not relative
            or path.is_absolute()
            or any(part in {"", ".", ".."} for part in relative.split("/"))
            or path.suffix.lower() not in PHOTO_EXTENSIONS
            or relative in seen
        ):
            raise ValueError("Unsafe or duplicate photo path in the phone manifest.")
        seen.add(relative)
        entries.append((relative, checksum.lower()))
    return sorted(entries)


def has_image_header(path, name):
    with path.open("rb") as stream:
        header = stream.read(8)
    if PurePosixPath(name).suffix.lower() == ".png":
        return header == PNG_HEADER
    return header.startswith(JPEG_HEADER)


def publish_verified(part, inbox, original_name, checksum):
    """Give a verified temporary file its final name without replacing any existing file.

    os.link fails if the name is taken, so there is no moment where an old photo
    is overwritten. A taken name with identical content counts as already present;
    a taken name with different content gets the checksum added to the new name.
    """
    original = Path(original_name)
    alternatives = [original.name, "{}--{}{}".format(original.stem, checksum, original.suffix)]
    attempt = 0
    while True:
        name = alternatives[attempt] if attempt < 2 else "{}--{}-{}{}".format(
            original.stem, checksum, attempt - 1, original.suffix
        )
        destination = inbox / name
        try:
            os.link(str(part), str(destination))
            part.unlink()
            return destination, "transferred"
        except FileExistsError:
            if destination.is_file() and not destination.is_symlink() and md5_file(destination) == checksum:
                part.unlink()
                return destination, "already_present"
            attempt += 1


def local_checksums(directories):
    """Map MD5 to path for every photo already saved locally."""
    found = {}
    for directory in directories:
        if directory.is_dir():
            for path in sorted(directory.rglob("*")):
                if path.is_file() and not path.is_symlink() and path.suffix.lower() in PHOTO_EXTENSIONS:
                    found.setdefault(md5_file(path), path)
    return found


def inside_private(path):
    return PRIVATE.resolve() in path.resolve().parents


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", required=True, help="Current N900 IP address")
    parser.add_argument("--socket", type=Path, default=PRIVATE / "ssh-session" / "control")
    parser.add_argument("--source-root", default=REMOTE_ROOT, help="Photo folder on the N900")
    parser.add_argument("--inbox", type=Path, default=PRIVATE / "inbox", help="Destination under private/")
    parser.add_argument("--archive", type=Path, default=PRIVATE / "archive",
                        help="Folder of already imported photos to skip (under private/)")
    parser.add_argument("--key", type=Path,
                        help="Passwordless SSH key; use instead of an open connection (--socket)")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.:-]*", args.host):
        parser.error("Use the phone's IP address or hostname.")

    remote_root = args.source_root.rstrip("/")
    if not remote_root.startswith(("/home/user/MyDocs/", "/media/")) or ".." in PurePosixPath(remote_root).parts:
        parser.error("Choose a photo folder in the phone's user storage.")
    inbox = args.inbox.resolve()
    archive = args.archive.resolve()
    if not inside_private(inbox) or not inside_private(archive):
        parser.error("Keep photo folders under private/, which git ignores.")
    logs = PRIVATE / "transfers"
    inbox.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)
    if args.key:
        if not args.key.is_file():
            parser.error("SSH key not found: {}".format(args.key))
        login = ["-i", str(args.key), "-o", "IdentitiesOnly=yes", "-o", "ControlPath=none",
                 "-o", "PubkeyAcceptedKeyTypes=+ssh-rsa"]
    else:
        login = ["-S", str(args.socket)]
    ssh = ["ssh"] + login + [
        "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-o", "HostKeyAlgorithms=+ssh-rsa",
        "-o", "StrictHostKeyChecking=yes", "-o", "ServerAliveInterval=15",
        "-o", "ServerAliveCountMax=3", "root@" + args.host,
    ]
    if not args.key:
        session_check = subprocess.run(
            ["ssh", "-S", str(args.socket), "-O", "check", "root@" + args.host],
            capture_output=True, text=True, timeout=15,
        )
        if session_check.returncode:
            print("Open the temporary SSH connection in your terminal first (see --help). No photos copied.",
                  file=sys.stderr)
            return 1

    batch = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    receipt_path = logs / (batch + "-receipt.json")
    receipt = {
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_root": remote_root,
        "complete": False,
        "photos": [],
    }
    try:
        manifest_command = (
            "cd " + shlex.quote(remote_root) + " || exit 1\n"
            "set -f\nIFS='\n'\n"
            "files=$(" + r"find . -type f \( -name '*.[jJ][pP][gG]' -o -name '*.[jJ][pP][eE][gG]' -o -name '*.[pP][nN][gG]' \)"
            + ") || exit 1\nfor f in $files; do md5sum \"$f\" || exit 1; done"
        )
        manifest = subprocess.run(
            ssh + [manifest_command], capture_output=True, text=True, check=True, timeout=120,
        ).stdout
        sources = parse_manifest(manifest)
        (logs / (batch + "-source-md5.txt")).write_text(manifest)
        receipt["phone_photo_count"] = len(sources)
        print("Found {} images in {} on the Nokia.".format(len(sources), remote_root), flush=True)

        local_by_checksum = local_checksums((archive, inbox))
        pending = [(source, checksum) for source, checksum in sources if checksum not in local_by_checksum]
        print("{} already present; {} to copy.".format(len(sources) - len(pending), len(pending)), flush=True)
        for source, expected in sources:
            if expected in local_by_checksum:
                destination = local_by_checksum[expected]
                status = "already_present"
            else:
                fd, part_name = tempfile.mkstemp(prefix=".n900-batch-", suffix=".part", dir=str(inbox))
                part = Path(part_name)
                try:
                    with os.fdopen(fd, "wb") as target:
                        subprocess.run(
                            ssh + ["cat " + shlex.quote(remote_root + "/" + source)],
                            stdout=target, check=True, timeout=300,
                        )
                    if md5_file(part) != expected:
                        raise ValueError("Checksum mismatch for {}. No final photo saved.".format(source))
                    if not has_image_header(part, source):
                        raise ValueError("Unexpected image contents for {}. No final photo saved.".format(source))
                    destination, status = publish_verified(part, inbox, PurePosixPath(source).name, expected)
                    local_by_checksum[expected] = destination
                    print("Verified: {} ({} bytes)".format(destination.name, destination.stat().st_size), flush=True)
                finally:
                    if part.exists():
                        part.unlink()
            receipt["photos"].append({
                "phone_path": source,
                "local_path": str(Path("private") / destination.relative_to(PRIVATE.resolve())),
                "md5": expected,
                "bytes": destination.stat().st_size,
                "status": status,
            })
        receipt["complete"] = True
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        receipt["error"] = str(error)
        print("Transfer stopped: {}".format(error), file=sys.stderr)
    finally:
        receipt["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")

    copied = sum(photo["status"] == "transferred" for photo in receipt["photos"])
    print("Copied and verified {} new photos. Receipt: {}".format(copied, receipt_path), flush=True)
    return 0 if receipt["complete"] else 1


if __name__ == "__main__":
    sys.exit(main())
