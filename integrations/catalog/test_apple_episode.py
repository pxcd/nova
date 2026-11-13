import json
import unittest
from routing import apple_episode

SHOW = 'umc.cmc.example'
LINK = 'https://tv.apple.com/ph/show/example/' + SHOW
EP = {'type': 'Episode', 'showId': SHOW, 'id': 'umc.cmc.ep', 'seasonNumber': 2,
      'episodeNumber': 3, 'title': 'Third',
      'url': 'https://tv.apple.com/ph/episode/third/umc.cmc.ep?showId=' + SHOW}


class AppleEpisodeTest(unittest.TestCase):
    def resolve(self, rows, **overrides):
        self.calls = []
        def fetch(url):
            self.calls.append(url)
            if url == LINK:
                data = {'data': [{'data': {'configuration': {'applicationProps': {
                    'storefront': {'storefrontId': 143474},
                    'requiredParamsMap': {'Default': {'sf': '143474'}}}}}}]}
                return '<script id="serialized-server-data">' + json.dumps(data) + '</script>'
            return json.dumps({'data': {'episodes': rows, 'totalEpisodeCount': 10}})
        return apple_episode(dict(show_link=LINK, season=2, episode=3) | overrides, fetch)

    def test_exact_identity_and_numbers(self):
        result = self.resolve([EP | {'seasonNumber': 1}, EP])
        self.assertEqual(result['title_link'], EP['url'])
        self.assertFalse(result['command_sent'])
        self.assertIn('nextToken=0%3A100', self.calls[-1])

    def test_wrong_show_or_episode_not_selected(self):
        for row in [EP | {'showId': 'wrong'}, EP | {'episodeNumber': 4}, EP | {'type': 'Movie'}]:
            self.assertEqual(self.resolve([row])['status'], 'episode_link_unavailable')

    def test_ambiguous_or_unsafe_link_rejected(self):
        for rows in [[EP, EP], [EP | {'url': 'https://evil.example/episode'}],
                     [EP | {'id': 'wrong'}], [EP | {'url': EP['url'].replace('/ph/', '/us/')}]]:
            with self.assertRaises(ValueError):
                self.resolve(rows)

    def test_input_validation_before_fetch(self):
        for overrides in [{'season': True}, {'episode': 0}, {'episode': 1.5},
                          {'show_link': LINK.replace('tv.apple.com', 'evil.example')}]:
            with self.assertRaises(ValueError):
                self.resolve([EP], **overrides)
            self.assertEqual(self.calls, [])


if __name__ == '__main__':
    unittest.main()
