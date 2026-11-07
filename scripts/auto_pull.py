#!/usr/bin/env python3
"""Pull new N900 photos when the phone is on the same Wi-Fi; do nothing otherwise.

Meant to be started by a scheduler, not by hand. It needs a dedicated, passwordless
SSH key whose public half is in the phone's /root/.ssh/authorized_keys:

    python3 scripts/auto_pull.py --host PHONE_HOSTNAME --key ~/.ssh/n900_memorycam [--mac PHONE_WIFI_MAC]

With --mac the phone is first looked up by its Wi-Fi hardware address on whatever network
the Mac is on (home, hotspot, a friend's Wi-Fi), and the SSH key is still checked under
PHONE_HOSTNAME. Without it, or if the lookup fails, PHONE_HOSTNAME is used as before.

If the phone does not answer on SSH port 22 (three tries, ten seconds apart) the run is logged as "phone not home"
and exits 0, so an absent phone is not an error. Otherwise it runs the same checked
copy as scripts/transfer_photos.py (originals stay on the phone, nothing is
overwritten, every file is MD5-checked). Only one run can happen at a time. One line
per run is appended to private/auto-pull.log; full receipts go to private/transfers/.

Exit codes: 0 done or phone not home, 1 transfer failed, 2 another run is active.
"""

import argparse
import fcntl
from datetime import datetime, timezone
from pathlib import Path
import socket
import subprocess
import sys
import time

import lan_find
import transfer_photos as transfer


def phone_is_home(host, port=22, timeout=5, attempts=3, pause=10,
                  connect=socket.create_connection, sleep=time.sleep):
    """True if something answers on the phone's SSH port.

    A phone in Wi-Fi power saving can miss the first try, so ask a few times.
    """
    for attempt in range(attempts):
        if attempt:
            sleep(pause)
        try:
            connect((host, port), timeout).close()
            return True
        except OSError:
            pass
    return False


def mac_gateway():
    """The Mac's default gateway, so "phone not home" logs show whether the Mac itself was home."""
    try:
        out = subprocess.run(["route", "-n", "get", "default"], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return next((line.split(":", 1)[1].strip() for line in out.splitlines() if "gateway:" in line), "none")


def log_line(log, text):
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with log.open("a") as stream:
        stream.write("{} {}\n".format(stamp, text))


def run(host, key, private=transfer.PRIVATE, is_home=phone_is_home, pull=transfer.main,
        gateway=mac_gateway, mac=None, find=lan_find.find):
    private.mkdir(parents=True, exist_ok=True)
    log = private / "auto-pull.log"
    with (private / "auto-pull.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            log_line(log, "skipped: another run is active")
            return 2
        address = (find(mac, 22) if mac else None) or host
        if not is_home(address):
            log_line(log, "phone not home (mac gateway {})".format(gateway()))
            return 0
        extra = ["--host-key-alias", host] if address != host else []
        try:
            code = pull(["--host", address, "--key", str(key)] + extra)
        except SystemExit as error:  # argparse refusals, such as a missing key
            code = error.code if isinstance(error.code, int) else 1
        except Exception as error:  # keep the scheduler's log readable
            log_line(log, "transfer crashed: {}".format(error))
            return 1
        log_line(log, "transfer ok" if code == 0 else "transfer failed (exit {})".format(code))
        return 0 if code == 0 else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", required=True, help="N900 hostname or IP address")
    parser.add_argument("--key", required=True, type=Path, help="Dedicated passwordless SSH key")
    parser.add_argument("--mac", help="Phone's Wi-Fi MAC address, to find it on any network")
    args = parser.parse_args(argv)
    return run(args.host, args.key.expanduser(), mac=args.mac)


if __name__ == "__main__":
    sys.exit(main())
