#!/usr/bin/env python3
"""Upgrade the existing nightly Mac photo-pull job to also check every two minutes.

Run with the same Python used by the installed LaunchAgent. No sudo is needed.
--prepare-only writes a private preview without changing the installed job.
"""

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent.parent
LABEL = "com.milind.memorycam.autopull"


def upgraded(existing, interval=120):
    """Preserve the verified host/key/nightly slots and add arrival polling."""
    if existing.get("Label") != LABEL:
        raise ValueError("This is not the Memorycam photo-pull job.")
    if type(interval) is not int or interval < 60:
        raise ValueError("Check at most once per minute.")
    args = list(existing.get("ProgramArguments", []))
    # Accept an already upgraded job, so reinstalling does not nest wrappers.
    if args[:2] == ["/usr/bin/caffeinate", "-i"]:
        args = args[2:]
    if len(args) < 6 or Path(args[1]).name != "auto_pull.py":
        raise ValueError("Expected the existing auto_pull.py job with host and key.")
    if "--host" not in args or "--key" not in args:
        raise ValueError("The existing job must specify a phone host and SSH key.")
    result = dict(existing)
    result.pop("Program", None)
    result["ProgramArguments"] = ["/usr/bin/caffeinate", "-i"] + args
    result["StartInterval"] = interval
    result["RunAtLoad"] = True
    return result


def atomic_write(path, data):
    """Finish the complete private file before replacing its previous version."""
    fd, name = tempfile.mkstemp(prefix=".memorycam-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def install(agent, data, original, domain, run=subprocess.run):
    """Replace and reload one job, restoring the previous job on load failure."""
    service = domain + "/" + LABEL
    current = run(["launchctl", "print", service], capture_output=True, text=True)
    if current.returncode == 0 and "state = running" in current.stdout:
        raise ValueError("A photo pull is active. Wait for it to finish and retry.")
    # Write first. A permission refusal must leave the running schedule alone.
    atomic_write(agent, data)
    try:
        if current.returncode == 0:
            run(["launchctl", "bootout", service], check=True, capture_output=True)
        run(["launchctl", "bootstrap", domain, str(agent)], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        atomic_write(agent, original)
        restored = run(["launchctl", "print", service], capture_output=True)
        if restored.returncode != 0:
            run(["launchctl", "bootstrap", domain, str(agent)], check=True, capture_output=True)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", type=Path, default=Path.home() / "Library/LaunchAgents" / (LABEL + ".plist"))
    parser.add_argument("--interval", type=int, default=120)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        original = args.agent.read_bytes()
        updated = upgraded(plistlib.loads(original), args.interval)
        data = plistlib.dumps(updated)
        for item in (updated["ProgramArguments"][2], updated["ProgramArguments"][3]):
            if not Path(item).is_file():
                raise ValueError("The installed Python or photo-pull script is missing.")
        private = ROOT / "private" / "autopull-setup"
        private.mkdir(parents=True, exist_ok=True, mode=0o700)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        atomic_write(private / (stamp + "-previous.plist"), original)
        prepared = private / (LABEL + ".plist")
        atomic_write(prepared, data)
        print("Prepared:", prepared)
        if args.prepare_only:
            return 0
        install(args.agent, data, original, "gui/" + str(os.getuid()))
        print("Installed: checks every {} seconds while awake, at login, and at the existing nightly slots.".format(args.interval))
        return 0
    except (OSError, ValueError, plistlib.InvalidFileException, subprocess.SubprocessError) as error:
        print("Not installed: {}".format(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
