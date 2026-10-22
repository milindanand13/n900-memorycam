"""Offline checks for scripts/auto_pull.py. No phone, network or SSH key needed."""
import fcntl
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
import auto_pull  # noqa: E402


class AutoPullChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.private = Path(self.temp.name) / 'private'
        self.calls = []

    def tearDown(self):
        self.temp.cleanup()

    def pull(self, code=0, error=None):
        def fake(argv):
            self.calls.append(argv)
            if error:
                raise error
            return code
        return fake

    def run_pull(self, home=True, **kwargs):
        return auto_pull.run('phone.local', Path('/key'), private=self.private,
                             is_home=lambda host: home, pull=self.pull(**kwargs))

    def last_log(self):
        return (self.private / 'auto-pull.log').read_text().splitlines()[-1]

    def test_phone_not_home_is_logged_and_not_an_error(self):
        self.assertEqual(self.run_pull(home=False), 0)
        self.assertEqual(self.calls, [])
        self.assertTrue(self.last_log().endswith('phone not home'))

    def test_phone_home_runs_the_checked_transfer_with_the_key(self):
        self.assertEqual(self.run_pull(), 0)
        self.assertEqual(self.calls, [['--host', 'phone.local', '--key', '/key']])
        self.assertTrue(self.last_log().endswith('transfer ok'))

    def test_failed_transfer_is_reported(self):
        self.assertEqual(self.run_pull(code=1), 1)
        self.assertTrue(self.last_log().endswith('transfer failed (exit 1)'))

    def test_refused_arguments_and_crashes_are_reported_not_raised(self):
        self.assertEqual(self.run_pull(error=SystemExit(2)), 1)
        self.assertTrue(self.last_log().endswith('transfer failed (exit 2)'))
        self.assertEqual(self.run_pull(error=RuntimeError('boom')), 1)
        self.assertTrue(self.last_log().endswith('transfer crashed: boom'))

    def test_second_run_is_skipped_while_one_is_active(self):
        self.private.mkdir()
        with (self.private / 'auto-pull.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertEqual(self.run_pull(), 2)
        self.assertEqual(self.calls, [])
        self.assertTrue(self.last_log().endswith('skipped: another run is active'))
        self.assertEqual(self.run_pull(), 0)  # lock released, runs normally

    def test_phone_is_home_only_when_the_connection_opens(self):
        class Conn:
            def close(self):
                pass

        def refuse(address, timeout):
            raise OSError('no route')

        no_wait = lambda seconds: None  # noqa: E731
        self.assertTrue(auto_pull.phone_is_home('h', connect=lambda address, timeout: Conn(), sleep=no_wait))
        self.assertFalse(auto_pull.phone_is_home('h', connect=refuse, sleep=no_wait))

    def test_a_missed_first_try_does_not_mean_the_phone_is_away(self):
        class Conn:
            def close(self):
                pass

        tries = []

        def wakes_on_second_try(address, timeout):
            tries.append(address)
            if len(tries) < 2:
                raise OSError('asleep')
            return Conn()

        self.assertTrue(auto_pull.phone_is_home('h', connect=wakes_on_second_try, sleep=lambda seconds: None))
        self.assertEqual(len(tries), 2)


if __name__ == '__main__':
    unittest.main()
