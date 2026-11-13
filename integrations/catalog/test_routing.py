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

    def test_version_clarification_preserves_episode_and_automatic_preference(self):
        settings = dict(SETTINGS, kodi_fallback=True)
        rows = [title('Suits', ('netflix', 'prime'), 2011),
                title('Suits', ('prime',), 2018)]
        request = {'query': 'Suits', 'media_type': 'series', 'season': 2, 'episode': 3}
        clarification = resolve(request, settings, rows)
        self.assertEqual(clarification['status'], 'needs_clarification')
        self.assertEqual(clarification['request_context'], request)
        selected = resolve(dict(clarification['request_context'], year=2011), settings, rows)
        self.assertEqual(selected['service'], 'netflix')
        self.assertEqual(selected['playback_arguments']['season'], 2)
        self.assertEqual(selected['playback_arguments']['episode'], 3)
        self.assertNotEqual(selected['playback_tool'], 'script__play_kodi_pov')
        malformed = resolve({'query': 'Suits', 'year': 2011, 'episode_request': 'S2E3'}, settings, rows)
        self.assertEqual(malformed['status'], 'unsupported_request')
        self.assertIn('numeric season/episode', malformed['message'])
        self.assertNotIn('playback_tool', malformed)

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
        self.assertEqual(resolve(request, SETTINGS, [title()])['playback_arguments'], {'query':'Severance','year':2022,'start_playback':True,'season':1,'episode':2})

    def test_episode_selectors_exclude_movies_before_clarification(self):
        rows = [title('The Boys', ('prime',), 2019, 'series'),
                title('The Boys', (), 2024, 'movie'), title('The Boys', (), 1962, 'movie')]
        r = resolve({'query': 'The Boys', 'season': 2, 'episode': 2}, SETTINGS, rows)
        self.assertEqual(r['service'], 'prime')
        self.assertEqual(r['playback_arguments']['year'], 2019)
        self.assertEqual((r['playback_arguments']['season'], r['playback_arguments']['episode']), (2, 2))
        for selector in ({'season': 2, 'episode': 2}, {'latest_episode': True}, {'episode_request': 'the pilot'}):
            request = {'query': 'The Boys', **selector}
            with self.subTest(selector=selector):
                r = resolve(request, SETTINGS, rows[1:])
                self.assertEqual(r['status'], 'needs_title_correction')
                self.assertEqual(r['candidates'], [])
                r = resolve(request, SETTINGS, rows + [title('The Boys', (), 2025, 'series')])
                self.assertEqual(r['status'], 'needs_clarification')
                self.assertEqual([c['year'] for c in r['candidates']], [2019, 2025])
                self.assertEqual(r['request_context'], request)
                self.assertEqual(resolve(dict(request, media_type='movie'), SETTINGS, rows)['status'], 'unsupported_request')
        self.assertEqual(resolve({'query': 'The Boys'}, SETTINGS, rows)['status'], 'needs_clarification')
        self.assertEqual(resolve({'query': 'The Boys', 'media_type': 'movie', 'year': 2024}, SETTINGS, rows)['status'], 'unavailable')

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

    def test_latest_episode_is_preserved_for_kodi_fallback_only(self):
        settings = dict(SETTINGS, kodi_fallback=True)
        request = {'query': 'Example', 'media_type': 'series', 'latest_episode': True}
        r = resolve(request, settings, [title('Example', (), 2002, 'series')])
        self.assertEqual(r['playback_arguments'], {'query': 'Example', 'media_type': 'series', 'year': 2002, 'latest_episode': True})
        self.assertEqual(resolve(request, settings, [title('Example', ('netflix',), 2002, 'series')])['status'], 'unsupported_request')
        self.assertEqual(resolve(dict(request,media_type='movie'), settings, [title('Example', (), 2002, 'movie')])['status'], 'unsupported_request')
        with self.assertRaises(ValueError):
            validate(dict(request,season=1,episode=1), settings)

    def test_indirect_episode_returns_metadata_even_if_model_supplies_numbers(self):
        settings = dict(SETTINGS, kodi_fallback=True)
        description = 'play the first episode of the 2nd to the last season of south park'
        request = {'query': 'South Park', 'media_type': 'series', 'episode_request': description, 'season': 2, 'episode': 1}
        r = resolve(request, settings, [title('South Park', (), 1997, 'series')])
        self.assertEqual(r['status'], 'episode_lookup_required')
        self.assertEqual(r['metadata_tool'], 'script__browse_kodi_series')
        self.assertEqual(r['metadata_arguments'], {'query': 'South Park', 'year': 1997})
        self.assertEqual(r['episode_request'], description)
        self.assertNotIn('playback_tool', r)
        self.assertNotIn('playback_arguments', r)
        self.assertFalse(r['command_sent'])
        self.assertEqual(resolve(request, settings, [title('South Park', ('netflix',), 1997, 'series')])['status'], 'unsupported_request')
        self.assertEqual(resolve({'query':'South Park','season':2,'episode':1}, settings, [title('South Park', (),1997,'series')])['playback_arguments']['season'],2)
        with self.assertRaises(ValueError): validate(dict(request, episode_request=[]), settings)

    def test_numbered_episode_routes_to_all_native_services(self):
        request = {'query':'Example','season':1,'episode':2}
        for service in ['apple','hbo','prime']:
            r = resolve(request, SETTINGS, [title('Example',(service,),2022,'series')])
            self.assertEqual(r['service'], service)
            self.assertEqual((r['playback_arguments']['season'],r['playback_arguments']['episode']), (1,2))
            self.assertTrue(r['playback_arguments']['start_playback'])
            self.assertEqual(resolve(dict(request,from_start=True),SETTINGS,[title('Example',(service,),2022,'series')])['status'],'unsupported_request')

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
