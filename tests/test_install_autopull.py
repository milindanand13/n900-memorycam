"""Schedule upgrades and rollback, without touching launchd or real user files."""
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import install_autopull as setup


class ScheduleChecks(unittest.TestCase):
    def existing(self):
        return {"Label": setup.LABEL,
                "ProgramArguments": ["/python", "/repo/scripts/auto_pull.py", "--host", "phone.local", "--key", "/key"],
                "StartCalendarInterval": [{"Hour": 1, "Minute": 0}, {"Hour": 1, "Minute": 15}],
                "StandardOutPath": "/private/log"}

    def test_upgrade_preserves_existing_connection_and_nightly_checks(self):
        old = self.existing()
        new = plistlib.loads(plistlib.dumps(setup.upgraded(old)))
        self.assertEqual(new["StartInterval"], 120)
        self.assertTrue(new["RunAtLoad"])
        self.assertEqual(new["StartCalendarInterval"], old["StartCalendarInterval"])
        self.assertEqual(new["StandardOutPath"], old["StandardOutPath"])
        self.assertEqual(new["ProgramArguments"][2:], old["ProgramArguments"])
        self.assertNotIn("StartInterval", old)
        self.assertEqual(setup.upgraded(new), new)

    def test_refuses_wrong_job_and_aggressive_polling(self):
        for value in ({}, {"Label": setup.LABEL}, dict(self.existing(), Label="another.job")):
            with self.assertRaises(ValueError):
                setup.upgraded(value)
        with self.assertRaises(ValueError):
            setup.upgraded(self.existing(), 1)

    def test_bootstrap_failure_restores_previous_file_and_schedule(self):
        calls = []

        def run(argv, **kwargs):
            calls.append(argv)
            if argv[1] == "print":
                return subprocess.CompletedProcess(argv, 0 if len(calls) == 1 else 1, stdout="state = not running")
            if argv[1] == "bootstrap" and len(calls) == 3:
                raise subprocess.CalledProcessError(5, argv)
            return subprocess.CompletedProcess(argv, 0)

        with tempfile.TemporaryDirectory() as folder:
            agent = Path(folder) / "job.plist"
            agent.write_bytes(b"old")
            with self.assertRaises(subprocess.CalledProcessError):
                setup.install(agent, b"new", b"old", "gui/123", run=run)
            self.assertEqual(agent.read_bytes(), b"old")
        self.assertEqual([c[1] for c in calls], ["print", "bootout", "bootstrap", "print", "bootstrap"])

    def test_active_transfer_is_not_interrupted(self):
        with tempfile.TemporaryDirectory() as folder:
            agent = Path(folder) / "job.plist"
            agent.write_bytes(b"old")
            with self.assertRaises(ValueError):
                setup.install(agent, b"new", b"old", "gui/123",
                              run=lambda *a, **kw: subprocess.CompletedProcess(a, 0, stdout="state = running"))
            self.assertEqual(agent.read_bytes(), b"old")

    def test_write_refusal_leaves_loaded_schedule_alone(self):
        calls = []

        def run(argv, **kwargs):
            calls.append(argv)
            return subprocess.CompletedProcess(argv, 0, stdout="state = not running")

        with patch.object(setup, "atomic_write", side_effect=PermissionError("blocked")):
            with self.assertRaises(PermissionError):
                setup.install(Path("/job.plist"), b"new", b"old", "gui/123", run=run)
        self.assertEqual([c[1] for c in calls], ["print"])


if __name__ == "__main__":
    unittest.main()
