"""Offline checks for the rule in scripts/daily_choice.py. Needs NumPy only; no model or real photos."""
from datetime import date
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
import daily_choice as daily  # noqa: E402

DAY = date(2026, 10, 24)


def candidate(name, scene, problems=()):
    return {'name': name, 'path': name, 'scene': scene, 'problems': list(problems)}


class RuleChecks(unittest.TestCase):
    def test_usable_photo_beats_a_higher_scoring_unusable_one(self):
        chosen = daily.pick([candidate('a', 0.1, ['blurry']), candidate('b', 0.0), candidate('c', -0.1)])
        self.assertEqual(chosen['name'], 'b')

    def test_all_unusable_still_gives_one_photo(self):
        chosen = daily.pick([candidate('a', 0.1, ['blurry']), candidate('b', 0.2, ['too dark'])])
        self.assertEqual(chosen['name'], 'b')
        self.assertIsNone(daily.pick([]))

    def test_tie_goes_to_the_later_photo(self):
        self.assertEqual(daily.pick([candidate('20261024_002.jpg', 0.5), candidate('20261024_001.jpg', 0.5)])['name'],
                         '20261024_002.jpg')

    def test_quality_limits(self):
        self.assertEqual(daily.photo_problems(daily.MIN_BLUR, daily.MIN_BRIGHTNESS), [])
        self.assertEqual(daily.photo_problems(1.0, 1.0), ['blurry', 'too dark'])

    def test_only_near_black_photos_are_too_dark(self):
        self.assertEqual(daily.photo_problems(100.0, 10.0), [])
        self.assertEqual(daily.photo_problems(100.0, 7.9), ['too dark'])

    def test_dark_photo_is_lifted_and_a_bright_one_is_left_alone(self):
        dark = np.full((4, 4, 3), 20, dtype=np.uint8)
        pixels, was_lifted = daily.lifted(dark)
        self.assertTrue(was_lifted)
        self.assertAlmostEqual(float(pixels.mean()), daily.BRIGHTEN_BELOW, delta=2.0)
        bright = np.full((4, 4, 3), 200, dtype=np.uint8)
        pixels, was_lifted = daily.lifted(bright)
        self.assertFalse(was_lifted)
        self.assertTrue((pixels == bright).all())
        black, was_lifted = daily.lifted(np.zeros((4, 4, 3), dtype=np.uint8))
        self.assertTrue(was_lifted)
        self.assertLess(float(black.mean()), daily.BRIGHTEN_BELOW)    # lift is capped, so no invented detail

    def test_dark_penalty_shrinks_to_nothing(self):
        self.assertAlmostEqual(daily.dark_penalty(0.0), daily.DARK_PENALTY)
        self.assertEqual(daily.dark_penalty(daily.DARK_FULL), 0.0)
        self.assertEqual(daily.dark_penalty(200.0), 0.0)
        self.assertGreater(daily.dark_penalty(20.0), daily.dark_penalty(50.0))

    def test_near_copy_drops_the_earlier_shot_only(self):
        self.assertEqual(daily.near_copies([[1, 0], [0, 1], [1, 0.01]]), {0})
        self.assertEqual(daily.near_copies([[1, 0], [0, 1]]), set())

    def test_scene_score_prefers_scene_prompts(self):
        scores = daily.scene_scores([[1, 0], [0, 1]], scene=[[1, 0]], not_scene=[[0, 1]])
        self.assertGreater(scores[0], scores[1])

    def test_invalid_features_rejected(self):
        with self.assertRaises(ValueError):
            daily.near_copies([[0, 0], [1, 0]])


class ChoiceChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.scores = {}

    def add(self, name, scene=0.0, blur=100.0, brightness=100.0, content=None, folder=None):
        folder = self.root / (folder or name[:8])
        folder.mkdir(exist_ok=True)
        (folder / name).write_bytes((content or name).encode())
        self.scores[name] = (scene, blur, brightness)

    def choose_by_name(self, day=DAY, used=()):
        """Like choose, but the scene score comes from self.scores, in the order of the paths."""
        names = []

        def embed(paths):
            names[:] = [p.name for p in paths]
            return [[1.0 if j == i else 0.0 for j in range(len(paths))] for i in range(len(paths))]

        return daily.choose_photo(self.root, day, set(used), lambda p: self.scores[p.name][1:], embed,
                                  lambda vectors: [self.scores[n][0] for n in names])

    def test_only_that_days_photos_compete(self):
        self.add('20261023_001.jpg', scene=0.9)
        self.add('20261024_001.jpg', scene=0.1)
        self.add('20261024_002.jpg', scene=0.2)
        self.add('20261025_001.jpg', scene=0.8)
        result = self.choose_by_name()
        self.assertEqual(result['source'], 'today')
        self.assertEqual(result['chosen'], '20261024/20261024_002.jpg')
        self.assertEqual({c['name'] for c in result['considered']}, {'20261024_001.jpg', '20261024_002.jpg'})

    def test_a_lit_photo_beats_a_slightly_better_scoring_dark_one(self):
        self.add('20261024_001.jpg', scene=0.057, brightness=20.0)
        self.add('20261024_002.jpg', scene=0.050, brightness=100.0)
        self.assertEqual(self.choose_by_name()['chosen'], '20261024/20261024_002.jpg')

    def test_dark_photos_can_still_win_when_nothing_lit_is_close(self):
        self.add('20261024_001.jpg', scene=0.057, brightness=20.0)
        self.add('20261024_002.jpg', scene=0.0, brightness=100.0)
        self.assertEqual(self.choose_by_name()['chosen'], '20261024/20261024_001.jpg')

    def test_single_unusable_photo_is_still_used_and_flagged(self):
        self.add('20261024_001.jpg', blur=1.0)
        result = self.choose_by_name()
        self.assertEqual(result['chosen'], '20261024/20261024_001.jpg')
        self.assertEqual(result['used_despite_problems'], ['blurry'])

    def test_no_photo_day_uses_best_unused_past_photo(self):
        self.add('20261020_001.jpg', scene=0.5)
        self.add('20261021_001.jpg', scene=0.3)
        self.add('20261022_001.jpg', scene=0.9, blur=1.0)     # unusable, so skipped while others are usable
        self.add('20261026_001.jpg', scene=1.0)               # future-dated: never a stand-in
        self.add('20250101_001.jpg', scene=1.0, folder='Date-unverified')
        result = self.choose_by_name()
        self.assertEqual(result['source'], 'stand-in')
        self.assertEqual(result['chosen'], '20261020/20261020_001.jpg')

    def test_listed_wrong_clock_dates_count_as_their_real_day(self):
        self.add('20090113_001.jpg', scene=0.5, folder='Date-unverified')
        self.add('20090118_001.jpg', scene=0.9, folder='Date-unverified')     # not listed: stays unverified
        result = self.choose_by_name(day=date(2026, 9, 23))
        self.assertEqual((result['source'], result['chosen']), ('today', 'Date-unverified/20090113_001.jpg'))
        self.add('20090119_001.jpg', scene=0.1, folder='Date-unverified')
        self.add('20260929_001.jpg', scene=0.2)
        result = self.choose_by_name(day=date(2026, 9, 29))
        self.assertEqual({c['name'] for c in result['considered']}, {'20090119_001.jpg', '20260929_001.jpg'})
        self.assertEqual(result['chosen'], '20260929/20260929_001.jpg')

    def test_listed_wrong_clock_photo_can_be_a_stand_in_but_unlisted_cannot(self):
        self.add('20090101_001.jpg', scene=0.5, folder='Date-unverified')
        self.add('20090118_001.jpg', scene=0.9, folder='Date-unverified')
        self.add('20090119_001.jpg', scene=0.1, folder='Date-unverified')
        result = self.choose_by_name()
        self.assertEqual(result['source'], 'stand-in')
        self.assertEqual(result['chosen'], 'Date-unverified/20090101_001.jpg')
        self.assertEqual({c['name'] for c in result['considered']}, {'20090101_001.jpg', '20090119_001.jpg'})

    def test_stand_in_skips_photos_already_chosen_and_identical_copies(self):
        self.add('20261020_001.jpg', scene=0.5, content='same')
        self.add('20261021_001.jpg', scene=0.4, content='same')   # byte-identical copy of the first
        self.add('20261022_001.jpg', scene=0.1)
        first_hash = daily.match.sha256(self.root / '20261020' / '20261020_001.jpg')
        result = self.choose_by_name(used=[first_hash])
        self.assertEqual(result['chosen'], '20261022/20261022_001.jpg')
        self.assertEqual(len(result['considered']), 1)

    def test_nothing_left_is_reported_not_invented(self):
        self.add('20261020_001.jpg')
        digest = daily.match.sha256(self.root / '20261020' / '20261020_001.jpg')
        result = self.choose_by_name(used=[digest])
        self.assertEqual((result['source'], result['chosen']), ('none', None))
        self.assertEqual(self.choose_by_name(day=date(2026, 10, 1))['chosen'], None)


class LedgerChecks(unittest.TestCase):
    def test_records_accumulate_and_missing_ledger_is_empty(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'daily-choice.json'
            self.assertEqual(daily.load_ledger(path), [])
            daily.record_choice({'date': '2026-10-24', 'sha256': 'a'}, path)
            daily.record_choice({'date': '2026-10-25', 'sha256': 'b'}, path)
            self.assertEqual([c['sha256'] for c in daily.load_ledger(path)], ['a', 'b'])
            self.assertFalse(path.with_suffix('.tmp').exists())


if __name__ == '__main__':
    unittest.main()
