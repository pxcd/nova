import copy
import tempfile
import unittest
from pathlib import Path
from discovery import Catalog, matching, perform, project


def movie(title='Murder Mystery', cast=None, country='ph', kind='subscription', show_type='movie', id='80242619'):
    return {'title': title, 'showType': show_type, 'releaseYear': 2019,
            'cast': cast if cast is not None else ['Adam Sandler', 'Jennifer Aniston'],
            'overview': 'A fictional synopsis that must not be exported.',
            'streamingOptions': {country: [{'service': {'id': 'netflix'}, 'type': kind,
                                           'link': 'https://www.netflix.com/title/' + id}]}}


class FakeCatalog(Catalog):
    def __init__(self, directory, direct=None, pages=None):
        self.now = 1000
        super().__init__('unused-test-key', directory, clock=lambda: self.now, monotonic=lambda: 0)
        self.direct = direct or []
        self.pages = pages or []
        self.calls = []

    def get(self, endpoint, params):
        self.requests += 1
        self.calls.append((endpoint, dict(params)))
        result = self.direct if endpoint.endswith('/title') else self.pages.pop(0)
        if isinstance(result, Exception):
            raise result
        return copy.deepcopy(result)


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    def catalog(self, **kwargs):
        return FakeCatalog(self.directory.name, **kwargs)

    def test_credit_and_subscription_validation(self):
        valid = project(movie(), 1000)
        self.assertEqual(matching([valid], 'ADAM SANDLER', 'movie')[0]['title'], 'Murder Mystery')
        self.assertEqual(matching([valid], 'Tom Cruise', 'movie'), [])
        self.assertIsNone(project(movie(country='us'), 1000))
        self.assertIsNone(project(movie(kind='rent'), 1000))
        bad = movie(); bad['streamingOptions']['ph'][0]['link'] = 'https://example.com/watch/80242619'
        self.assertIsNone(project(bad, 1000))
        self.assertNotIn('overview', valid)

    def test_movie_special_and_series_are_separate(self):
        items = [project(movie(), 1000), project(movie('Adam Sandler: 100% Fresh', id='80200001'), 1000),
                 project(movie('A Series', show_type='series', id='80200002'), 1000)]
        self.assertEqual([x['title'] for x in matching(items, 'Adam Sandler', 'movie')], ['Murder Mystery'])
        self.assertEqual([x['title'] for x in matching(items, 'Adam Sandler', 'special')], ['Adam Sandler: 100% Fresh'])
        self.assertEqual([x['title'] for x in matching(items, 'Adam Sandler', 'series')], ['A Series'])

    def test_discovers_on_later_page_and_random_only_from_verified_pool(self):
        c = self.catalog(pages=[{'shows': [movie('Unrelated', cast=['Other Actor'])], 'hasMore': True, 'nextCursor': 'page2'},
                                {'shows': [movie(), movie('Wrong country', country='us')], 'hasMore': False}])
        result = perform({'performer': 'Adam Sandler', 'choose_random': True}, c)
        self.assertEqual(result['selected']['title'], 'Murder Mystery')
        self.assertTrue(result['search_complete'])
        self.assertFalse(result['command_sent'])
        self.assertEqual(c.calls[-1][1]['cursor'], 'page2')
        self.assertEqual(c.calls[-1][1]['catalogs'], 'netflix.subscription')
        self.assertEqual(result['requests_this_call'], 3)
        self.assertNotIn('A fictional synopsis', str(result))
        self.assertNotIn('overview', result['candidates'][0])

    def test_empty_partial_scan_never_claims_unavailable(self):
        c = self.catalog(pages=[{'shows': [], 'hasMore': True, 'nextCursor': str(i)} for i in range(3)])
        r = perform({'performer': 'Adam Sandler'}, c)
        self.assertEqual(r['status'], 'search_incomplete')
        self.assertFalse(r['search_complete'])
        self.assertIsNone(r['selected'])
        self.assertEqual(r['requests_this_call'], 4)

    def test_complete_empty_scan_has_scoped_no_matches(self):
        c = self.catalog(pages=[{'shows': [], 'hasMore': False}])
        r = perform({'performer': 'Adam Sandler'}, c)
        self.assertEqual(r['status'], 'no_matches')
        self.assertTrue(r['search_complete'])

    def test_cache_reuses_complete_catalog_and_preserves_age(self):
        c = self.catalog(pages=[{'shows': [movie()], 'hasMore': False}])
        perform({'performer': 'Adam Sandler'}, c)
        c.calls.clear(); c.now += 300
        r = perform({'performer': 'Adam Sandler', 'choose_random': True}, c)
        self.assertEqual(c.calls, [])
        self.assertEqual(r['selected']['availability_checked_at'], 1000)
        self.assertEqual(r['requests_this_call'], 0)
        c.now += 3601; c.pages = [{'shows': [], 'hasMore': False}]
        r = perform({'performer': 'Adam Sandler'}, c)
        self.assertEqual(r['status'], 'no_matches')
        self.assertEqual(r['requests_this_call'], 2)

    def test_api_error_stops_search_without_false_unavailability(self):
        c = self.catalog(direct=RuntimeError('Catalog HTTP 429; search stopped.'))
        r = perform({'performer': 'Adam Sandler'}, c)
        self.assertEqual(r['status'], 'search_incomplete')
        self.assertEqual(r['requests_this_call'], 1)
        self.assertIn('429', r['errors'][0])

    def test_pagination_loop_does_not_exhaust_quota(self):
        c = self.catalog(pages=[{'shows': [], 'hasMore': True, 'nextCursor': 'same'},
                                {'shows': [], 'hasMore': True, 'nextCursor': 'same'}])
        r = perform({'performer': 'Adam Sandler'}, c)
        self.assertEqual(r['requests_this_call'], 3)
        self.assertEqual(r['status'], 'search_incomplete')
        self.assertIn('did not advance', r['errors'][0])

    def test_shared_cache_page_cap_prevents_further_scan(self):
        c = self.catalog()
        c.save('netflix-ph-movie-v1.json', {'created_at': c.now, 'items': [],
               'pages': 12, 'cursor': 'later', 'complete': False})
        r = perform({'performer': 'Adam Sandler'}, c)
        self.assertEqual(r['status'], 'search_incomplete')
        self.assertEqual([endpoint for endpoint, _ in c.calls], ['/shows/search/title'])
        self.assertEqual(r['catalog_pages_checked'], 12)

    def test_performer_titled_specials_avoid_catalog_scan(self):
        c = self.catalog(direct=[movie('Jo Koy: Special ' + str(i), cast=['Jo Koy'], id=str(80200000+i)) for i in range(6)])
        r = perform({'performer': 'jokoy', 'content_kind': 'special', 'choose_random': True}, c)
        self.assertEqual(len(r['candidates']), 6)
        self.assertEqual(r['requests_this_call'], 1)
        self.assertEqual(r['selected']['matched_performer'], 'Jo Koy')

    def test_validation_prevents_requests(self):
        c = self.catalog()
        for request in [None, {}, {'performer': ''}, {'performer': '../'}, {'performer': 'Adam Sandler', 'content_kind': 'music'}, {'performer': 'Adam Sandler', 'choose_random': 'yes'}]:
            with self.assertRaises(ValueError):
                perform(request, c)
        self.assertEqual(c.calls, [])

    def test_ambiguous_links_are_rejected(self):
        row = movie(); other = copy.deepcopy(row['streamingOptions']['ph'][0]);other['link'] = 'https://www.netflix.com/title/80000001';row['streamingOptions']['ph'].append(other)
        self.assertIsNone(project(row, 1000))


if __name__ == '__main__':
    unittest.main()
