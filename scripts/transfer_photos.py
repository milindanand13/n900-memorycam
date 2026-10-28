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
final name. Photos already in the inbox, archive or configured Pictures library
(by content, not by name) are skipped. After organize_photos.py completes, new
copies use week/date folders in that library. Receipts stay in private/transfers/.
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

import photo_library


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


def clean_path(source):
    """Return a phone photo path relative to the photo folder, or raise ValueError if unsafe."""
    if not re.fullmatch(r"\./[A-Za-z0-9_./-]+", source):
        raise ValueError("Unexpected filename in the phone manifest.")
    relative = source[2:]
    path = PurePosixPath(relative)
    if (
        not relative
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in relative.split("/"))
        or path.suffix.lower() not in PHOTO_EXTENSIONS
    ):
        raise ValueError("Unsafe photo path in the phone manifest.")
    return relative


def parse_manifest(value):
    """Turn the phone's `md5sum` output into sorted (relative path, checksum) pairs.

    Rejects anything unexpected rather than guessing: odd characters, paths that
    climb out of the photo folder, non-photo suffixes and repeated paths.
    """
    entries = []
    seen = set()
    for line in value.splitlines():
        match = re.fullmatch(r"([0-9a-fA-F]{32})  (.+)", line)
        if not match:
            raise ValueError("Unexpected filename or checksum in the phone manifest.")
        checksum, source = match.groups()
        relative = clean_path(source)
        if relative in seen:
            raise ValueError("Unsafe or duplicate photo path in the phone manifest.")
        seen.add(relative)
        entries.append((relative, checksum.lower()))
    return sorted(entries)


LISTING_LINE = re.compile(r"[-][-rwxsStT]{9}\s+\d+\s+\S+\s+\S+\s+(\d+)\s+(\S+\s+\S+\s+\S+)\s+(.+)")


def parse_listing(value):
    """Turn the phone's `ls -l` output into sorted (path, size, date text) triples plus skipped lines.

    A photo with an odd name is skipped and reported, so one stray file cannot stop
    every other photo. Output that is not an `ls -l` listing at all raises ValueError.
    """
    entries, skipped, seen, recognised = [], [], set(), False
    for line in value.splitlines():
        match = LISTING_LINE.fullmatch(line.strip())
        if match:
            recognised = True
            size, stamp, source = match.groups()
            try:
                relative = clean_path(source)
            except ValueError:
                relative = None
            if relative and relative not in seen:
                seen.add(relative)
                entries.append((relative, int(size), stamp))
                continue
        skipped.append(line[:200])
    if skipped and not recognised:
        raise ValueError("The phone's file listing was not in the expected format.")
    return sorted(entries), skipped


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


def local_checksums(directories, cache=None):
    """Map MD5 to path for every photo already saved locally.

    `cache` (path -> [size, mtime_ns, md5]) lets unchanged files skip rehashing.
    It is updated in place to describe exactly the files found this time.
    """
    old = {} if cache is None else dict(cache)
    seen = {}
    found = {}
    for directory in directories:
        if directory.is_dir():
            for path in sorted(directory.rglob("*")):
                if path.is_file() and not path.is_symlink() and path.suffix.lower() in PHOTO_EXTENSIONS:
                    info = path.stat()
                    entry = old.get(str(path))
                    if entry and entry[:2] == [info.st_size, info.st_mtime_ns]:
                        checksum = entry[2]
                    else:
                        checksum = md5_file(path)
                    seen[str(path)] = [info.st_size, info.st_mtime_ns, checksum]
                    found.setdefault(checksum, path)
    if cache is not None:
        cache.clear()
        cache.update(seen)
    return found


def load_cache(path):
    """Read the remembered checksums; a missing or damaged file just means starting over."""
    try:
        data = json.loads(path.read_text())
        return {"phone": dict(data["phone"]), "local": dict(data["local"])}
    except (OSError, ValueError, KeyError, TypeError):
        return {"phone": {}, "local": {}}


def save_cache(path, cache):
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(cache))
    os.replace(str(temporary), str(path))


def remote_files_command(remote_root, per_file):
    """Shell script for the phone: run `per_file` on every photo under the photo folder."""
    return (
        "cd " + shlex.quote(remote_root) + " || exit 1\n"
        "set -f\nIFS='\n'\n"
        "files=$(" + r"find . -type f \( -name '*.[jJ][pP][gG]' -o -name '*.[jJ][pP][eE][gG]' -o -name '*.[pP][nN][gG]' \)"
        + ") || exit 1\nfor f in $files; do " + per_file + " || exit 1; done"
    )


def read_phone(ssh, remote_root, remembered):
    """Return ([(path, md5)], skipped lines, what to remember) for the photos on the phone.

    Lists names and sizes (cheap), then asks the phone for the checksum of only the
    photos not remembered from an earlier run. If the listing is not understood, it
    falls back to checksumming every photo, as the first version did.
    """
    try:
        listing, skipped = parse_listing(subprocess.run(
            ssh + [remote_files_command(remote_root, 'ls -l "$f"')],
            capture_output=True, text=True, check=True, timeout=120).stdout)
    except ValueError:
        manifest = subprocess.run(
            ssh + [remote_files_command(remote_root, 'md5sum "$f"')],
            capture_output=True, text=True, check=True, timeout=120).stdout
        return parse_manifest(manifest), [], {}
    checksums = {}
    wanted = []
    for path, size, stamp in listing:
        entry = remembered.get(path)
        if entry and entry[:2] == [size, stamp]:
            checksums[path] = entry[2]
        else:
            wanted.append(path)
    for start in range(0, len(wanted), 100):
        batch = wanted[start:start + 100]
        command = "cd " + shlex.quote(remote_root) + " || exit 1\nmd5sum " + " ".join(shlex.quote("./" + n) for n in batch)
        output = subprocess.run(ssh + [command], capture_output=True, text=True, check=True,
                                timeout=120 + 60 * len(batch)).stdout
        checksums.update(parse_manifest(output))
    sizes = {path: (size, stamp) for path, size, stamp in listing}
    if set(checksums) != set(sizes):
        raise ValueError("The phone did not return a checksum for every photo.")
    return (sorted(checksums.items()), skipped,
            {path: [sizes[path][0], sizes[path][1], checksum] for path, checksum in checksums.items()})


def inside_private(path):
    return PRIVATE.resolve() in path.resolve().parents


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", required=True, help="Current N900 IP address")
    parser.add_argument("--socket", type=Path, default=PRIVATE / "ssh-session" / "control")
    parser.add_argument("--source-root", default=REMOTE_ROOT, help="Photo folder on the N900")
    parser.add_argument("--inbox", type=Path, help="Override under private/; otherwise use the configured photo library")
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
    try:
        library = photo_library.configured_root(PRIVATE, REPO_ROOT)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error("Invalid photo-library configuration: {}".format(error))
    inbox = (args.inbox or library or PRIVATE / "inbox").resolve()
    archive = args.archive.resolve()
    organized = library is not None and inbox == library
    if (not organized and not inside_private(inbox)) or not inside_private(archive):
        parser.error("Use the configured photo library or a folder under private/.")
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
    sources = []
    try:
        cache_path = PRIVATE / "md5-cache.json"
        cache = load_cache(cache_path)
        sources, skipped, cache["phone"] = read_phone(ssh, remote_root, cache["phone"])
        receipt["phone_photo_count"] = len(sources)
        print("Found {} images in {} on the Nokia.".format(len(sources), remote_root), flush=True)
        if skipped:
            receipt["skipped_phone_files"] = skipped[:50]
            print("Skipped {} phone files with unusual names or listings: {}".format(
                len(skipped), "; ".join(skipped[:3])), flush=True)

        local_by_checksum = local_checksums((archive, inbox) + ((library,) if library else ()), cache["local"])
        save_cache(cache_path, cache)
        pending = [(source, checksum) for source, checksum in sources if checksum not in local_by_checksum]
        print("{} already present; {} to copy.".format(len(sources) - len(pending), len(pending)), flush=True)
        for source, expected in sources:
            if expected in local_by_checksum:
                destination = local_by_checksum[expected]
                status = "already_present"
            else:
                target_folder = photo_library.photo_directory(inbox, source) if organized else inbox
                fd, part_name = tempfile.mkstemp(prefix=".n900-batch-", suffix=".part", dir=str(target_folder))
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
                    destination, status = publish_verified(part, target_folder, PurePosixPath(source).name, expected)
                    local_by_checksum[expected] = destination
                    print("Verified: {} ({} bytes)".format(destination.name, destination.stat().st_size), flush=True)
                finally:
                    if part.exists():
                        part.unlink()
            receipt["photos"].append({
                "phone_path": source,
                "local_path": str(destination.resolve()) if library else str(Path("private") / destination.relative_to(PRIVATE.resolve())),
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
        copied = sum(photo["status"] == "transferred" for photo in receipt["photos"])
        # A check that found nothing new and went fine would only add clutter every two minutes.
        wrote = copied or not receipt["complete"]
        if wrote:
            receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
            (logs / (batch + "-source-md5.txt")).write_text(
                "".join("{}  ./{}\n".format(checksum, source) for source, checksum in sources))

    print("Copied and verified {} new photos.{}".format(copied, " Receipt: {}".format(receipt_path) if wrote else ""),
          flush=True)
    return 0 if receipt["complete"] else 1


if __name__ == "__main__":
    sys.exit(main())
