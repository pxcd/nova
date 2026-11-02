import copy
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from routing import resolve, search, validate

SETTINGS = {'subscriptions': ['netflix', 'hbo', 'apple', 'prime'],
            'preference': ['netflix', 'hbo', 'apple', 'prime']}


def title(name='Severance', services=('apple',), year=2022, kind='series'):
    return {'id': name + str(year), 'title': name, 'firstAirYear': year, 'showType': kind,
            'streamingOptions': {'ph': [{'service': {'id': s}, 'type': 'subscription',
                                       'link': 'https://example.com/title/1'} for s in services]}}


class RoutingTest(unittest.TestCase):
    def test_single_provider(self):
        r = resolve({'query': 'severance'}, SETTINGS, [title()])
        self.assertEqual(r['playback_tool'], 'script__play_apple_tv_title')
        self.assertEqual(r['playback_arguments'], {'query': 'Severance', 'year': 2022, 'start_playback': True})
        self.assertFalse(r['command_sent'])

    def test_preference_and_subscription_allowlist(self):
        settings = {'subscriptions': ['prime', 'hbo'], 'preference': ['hbo', 'prime']}
        r = resolve({'query': 'Severance'}, settings, [title(services=('netflix', 'prime', 'hbo'))])
        self.assertEqual(r['service'], 'hbo')

    def test_subscription_only_country_only_no_addons(self):
        for kind in ('rent', 'buy', 'addon', 'free'):
            row = title()
            row['streamingOptions']['ph'][0]['type'] = kind
            self.assertEqual(resolve({'query': 'Severance'}, SETTINGS, [row])['status'], 'unavailable')
        row = title()
        row['streamingOptions']['us'] = row['streamingOptions'].pop('ph')
        self.assertEqual(resolve({'query': 'Severance'}, SETTINGS, [row])['status'], 'unavailable')

    def test_unsupported_service_and_missing_link(self):
        for row in (title(services=('disney',)), title(services=())):
            self.assertEqual(resolve({'query': 'Severance'}, SETTINGS, [row])['status'], 'unavailable')
        row = title()
        row['streamingOptions']['ph'][0]['link'] = 'javascript:alert(1)'
        self.assertEqual(resolve({'query': 'Severance'}, SETTINGS, [row])['status'], 'unavailable')

    def test_ambiguity_not_resolved_by_availability(self):
        rows = [title('Mean Girls', ('prime',), 2004, 'movie'), title('Mean Girls', (), 2024, 'movie')]
        r = resolve({'query': 'Mean Girls'}, SETTINGS, rows)
        self.assertEqual(r['status'], 'needs_clarification')
        r = resolve({'query': 'Mean Girls', 'year': 2004}, SETTINGS, rows)
        self.assertEqual(r['playback_arguments']['year'], 2004)

    def test_movie_series_collision(self):
        rows = [title(kind='movie'), title(kind='series')]
        self.assertEqual(resolve({'query': 'Severance'}, SETTINGS, rows)['status'], 'needs_clarification')
        self.assertEqual(resolve({'query': 'Severance', 'media_type': 'series'}, SETTINGS, rows)['status'], 'unsupported_request')

    def test_netflix_hbo_remake_safety(self):
        for service in ('netflix', 'hbo'):
            rows = [title('Mean Girls', (service,), y, 'movie') for y in (2004, 2024)]
            r = resolve({'query': 'Mean Girls', 'year': 2004}, SETTINGS, rows)
            self.assertEqual(r['status'], 'unsupported_request')

    def test_restart_preserved_and_apple_not_supported(self):
        request = {'query': 'Severance', 'from_start': True}
        self.assertEqual(resolve(request, SETTINGS, [title()])['status'], 'unsupported_request')
        r = resolve(request, SETTINGS, [title(services=('apple', 'prime'))])
        self.assertTrue(r['playback_arguments']['from_start'])
        self.assertEqual(r['service'], 'prime')

    def test_netflix_combined_restart_is_not_routable(self):
        request = {'query': 'Severance', 'from_start': True}
        self.assertEqual(resolve(request, SETTINGS, [title(services=('netflix',))])['status'], 'unsupported_request')
        r = resolve(request, SETTINGS, [title(services=('netflix', 'prime'))])
        self.assertEqual(r['service'], 'prime')
        self.assertTrue(r['playback_arguments']['from_start'])
        request.update(season=1, episode=2)
        self.assertEqual(resolve(request, SETTINGS, [title(services=('netflix', 'prime'))])['status'], 'unsupported_request')

    def test_numbered_episode_preserved(self):
        request = {'query': 'Severance', 'season': 1, 'episode': 2, 'from_start': False}
        r = resolve(request, SETTINGS, [title(services=('netflix', 'hbo'))])
        self.assertEqual(r['playback_arguments'], dict(query='Severance', season=1, episode=2, from_start=False))
        self.assertEqual(resolve(request, SETTINGS, [title()])['status'], 'unsupported_request')

    def test_correction_candidates(self):
        r = resolve({'query': 'Sever ants'}, SETTINGS, [title()])
        self.assertEqual(r['status'], 'needs_title_correction')
        self.assertEqual(r['candidates'][0]['title'], 'Severance')
        self.assertNotIn('playback_tool', r)

    def test_original_title_and_duplicates(self):
        row = title('Other spelling')
        row['originalTitle'] = 'Severance'
        r = resolve({'query': 'Severance'}, SETTINGS, [row, copy.deepcopy(row)])
        self.assertEqual(r['status'], 'service_selected')
        self.assertEqual(r['playback_arguments']['query'], 'Other spelling')

    def test_kodi_fallback_only_after_confirmed_no_offer(self):
        settings = dict(SETTINGS, kodi_fallback=True)
        row = title('Example', (), 2004, 'movie')
        r = resolve({'query': 'Example'}, settings, [row])
        self.assertEqual(r['playback_tool'], 'script__play_kodi_pov')
        self.assertEqual(r['playback_arguments'], {'query': 'Example', 'media_type': 'movie', 'year': 2004})
        self.assertFalse(r['command_sent'])
        self.assertEqual(resolve({'query': 'Example'}, settings, [title('Example', ('prime',), 2004, 'movie')])['service'], 'prime')
        self.assertEqual(resolve({'query': 'Example'}, settings, [])['status'], 'needs_title_correction')
        self.assertEqual(resolve({'query': 'Example'}, settings, [row, title('Example', (), 2024, 'movie')])['status'], 'needs_clarification')
        with self.assertRaises(ValueError):
            resolve({'query': 'Example'}, settings, None)
        self.assertEqual(resolve({'query': 'Example', 'from_start': True}, settings, [row])['status'], 'unsupported_request')

    def test_kodi_series_requires_explicit_episode(self):
        settings = dict(SETTINGS, kodi_fallback=True)
        rows = [title('Example', (), 2022, 'series')]
        self.assertEqual(resolve({'query': 'Example'}, settings, rows)['status'], 'needs_episode')
        r = resolve({'query': 'Example', 'season': 2, 'episode': 3}, settings, rows)
        self.assertEqual(r['playback_arguments'], {'query': 'Example', 'year': 2022, 'media_type': 'series', 'season': 2, 'episode': 3})

    def test_input_validation(self):
        for data in ({'query': ''}, {'query': 'x', 'year': True}, {'query': 'x', 'season': 1},
                     {'query': 'x', 'season': 0, 'episode': 1}, {'query': 'x', 'from_start': 'true'},
                     {'query': 'x', 'media_type': 'person'}):
            with self.assertRaises(ValueError):
                validate(data, SETTINGS)
        with self.assertRaises(ValueError):
            validate({'query': 'x'}, {'subscriptions': ['netflix'], 'preference': ['hbo']})

    def test_integral_ha_selector_numbers(self):
        r = resolve({'query': 'Severance', 'season': 1.0, 'episode': 2.0}, SETTINGS, [title(services=('netflix',))])
        self.assertEqual(r['playback_arguments']['episode'], 2)
        self.assertIs(type(r['playback_arguments']['episode']), int)
        with self.assertRaises(ValueError):
            validate({'query': 'x', 'year': 2004.5}, SETTINGS)

    def test_bad_response(self):
        for rows in ({}, None, ['oops']):
            with self.assertRaises(ValueError):
                resolve({'query': 'x'}, SETTINGS, rows)

    def test_network_parameters_no_provider_filter(self):
        with patch('routing.urlopen') as fetch:
            fetch.return_value.__enter__.return_value.read.return_value = b'[]'
            self.assertEqual(search('A & B', 'test-key'), [])
            request = fetch.call_args.args[0]
            self.assertIn('title=A+%26+B&country=ph&series_granularity=show', request.full_url)
            self.assertNotIn('catalogs=', request.full_url)
            self.assertEqual(fetch.call_args.kwargs['timeout'], 12)
        with patch('routing.urlopen', side_effect=HTTPError('url', 429, '', {}, None)):
            with self.assertRaises(HTTPError):
                search('x', 'test-key')


if __name__ == '__main__':
    unittest.main()
