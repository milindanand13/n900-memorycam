"""Offline checks for the ranking in scripts/match_archive.py. Needs NumPy only; no model or photos."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
import match_archive as match  # noqa: E402


class RankingChecks(unittest.TestCase):
    def test_closest_first_scores_normalised_and_query_copy_excluded(self):
        records = [{'relative_path': name, 'sha256': checksum} for name, checksum in
                   [('unrelated', 'a'), ('match', 'b'), ('query-copy', 'query')]]
        result = match.ranking([1, 0], [[0, 1], [2, 0], [1, 0]], records, 'query')
        self.assertEqual([r['relative_path'] for r in result], ['match', 'unrelated'])
        self.assertAlmostEqual(result[0]['score'], 1.0)
        self.assertAlmostEqual(result[1]['score'], 0.0)

    def test_ties_are_ordered_by_path_so_runs_repeat(self):
        records = [{'relative_path': name, 'sha256': name} for name in ['b', 'a', 'c']]
        # Powers of two normalise to exactly 1.0, so all three scores tie exactly.
        result = match.ranking([1, 0], [[1, 0], [2, 0], [4, 0]], records, 'query')
        self.assertEqual(len({r['score'] for r in result}), 1)
        self.assertEqual([r['relative_path'] for r in result], ['a', 'b', 'c'])

    def test_invalid_features_rejected(self):
        record = [{'relative_path': 'candidate', 'sha256': 'a'}]
        for query, vectors in [([0, 0], [[1, 0]]), ([1, 0], [[0, 0]]),
                               ([float('nan'), 0], [[1, 0]]), ([1, 0], [[float('inf'), 0]])]:
            with self.subTest(query=query, vectors=vectors), self.assertRaises(ValueError):
                match.ranking(query, vectors, record, 'query')


class ArchiveChecks(unittest.TestCase):
    def test_exact_copies_counted_once(self):
        source = Path('/archive')
        paths = [source / 'a.jpg', source / 'trip' / 'a-copy.jpg', source / 'b.jpg']
        fake = {'a.jpg': 'x', 'a-copy.jpg': 'x', 'b.jpg': 'y'}
        records, duplicates = match.unique_images(paths, source, checksum=lambda p: fake[p.name])
        self.assertEqual([r['relative_path'] for r in records], ['a.jpg', 'b.jpg'])
        self.assertEqual(duplicates, [{'relative_path': 'trip/a-copy.jpg', 'sha256': 'x'}])

    def test_results_must_stay_in_private(self):
        self.assertTrue(match.inside_private(match.PRIVATE / 'matches' / 'run'))
        self.assertFalse(match.inside_private(match.REPO_ROOT / 'docs'))
        self.assertFalse(match.inside_private(match.PRIVATE / '..' / 'results'))


class ReviewChecks(unittest.TestCase):
    def test_page_keeps_css_braces_and_inserts_results(self):
        page = match.review_page(2, ['<figure>match</figure>'])
        self.assertIn('body{background:#171717', page)
        self.assertIn('2 unique archive photos', page)
        self.assertIn('<figure>match</figure>', page)


if __name__ == '__main__':
    unittest.main()
