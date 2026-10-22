#!/usr/bin/env python3
"""Pull new N900 photos when the phone is on the same Wi-Fi; do nothing otherwise.

Meant to be started by a scheduler, not by hand. It needs a dedicated, passwordless
SSH key whose public half is in the phone's /root/.ssh/authorized_keys:

    python3 scripts/auto_pull.py --host PHONE_HOSTNAME --key ~/.ssh/n900_memorycam

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
import sys
import time

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


def log_line(log, text):
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with log.open("a") as stream:
        stream.write("{} {}\n".format(stamp, text))


def run(host, key, private=transfer.PRIVATE, is_home=phone_is_home, pull=transfer.main):
    private.mkdir(parents=True, exist_ok=True)
    log = private / "auto-pull.log"
    with (private / "auto-pull.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            log_line(log, "skipped: another run is active")
            return 2
        if not is_home(host):
            log_line(log, "phone not home")
            return 0
        try:
            code = pull(["--host", host, "--key", str(key)])
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
    args = parser.parse_args(argv)
    return run(args.host, args.key.expanduser())


if __name__ == "__main__":
    sys.exit(main())
