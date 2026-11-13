"""Resolve named titles to subscribed PH services. Never controls a device."""

import base64
import json
from pathlib import Path
import re
import sys
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, parse_qs
from urllib.request import Request, urlopen

SERVICES = {
    'netflix': ('Netflix', 'script__play_netflix_title'),
    'hbo': ('HBO Max', 'script__play_hbo_title'),
    'apple': ('Apple TV+', 'script__play_apple_tv_title'),
    'prime': ('Prime Video', 'script__play_prime_video_title'),
}


def normalize(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', value).casefold() if c.isalnum())


def result(status, message, **data):
    return dict(status=status, country='PH', command_sent=False, message=message, **data)


def whole_number(value, minimum, maximum):
    return type(value) in (int, float) and minimum <= value <= maximum and int(value) == value


def validate(request, settings):
    if not isinstance(request, dict) or not isinstance(settings, dict):
        raise ValueError('Expected request and settings objects.')
    if type(settings.get('kodi_fallback', False)) is not bool:
        raise ValueError('Invalid Kodi fallback setting.')
    query = request.get('query')
    if not isinstance(query, str) or not 1 <= len(query.strip()) <= 200 or not normalize(query):
        raise ValueError('Provide a title.')
    subscriptions = settings.get('subscriptions')
    preference = settings.get('preference')
    for values in (subscriptions, preference):
        if not isinstance(values, list) or not values or any(not isinstance(v, str) or v not in SERVICES for v in values) or len(set(values)) != len(values):
            raise ValueError('Configure supported subscriptions and preference once each.')
    if set(subscriptions) != set(preference):
        raise ValueError('Preference must order all configured subscriptions.')
    if 'year' in request and (not whole_number(request['year'], 1800, 2200)):
        raise ValueError('Invalid release year.')
    if 'media_type' in request and request['media_type'] not in ('movie', 'series'):
        raise ValueError('Invalid media type.')
    description = request.get('episode_request')
    if description is not None and (not isinstance(description, str) or not 1 <= len(description.strip()) <= 500):
        raise ValueError('Invalid episode description.')
    if type(request.get('from_start', False)) is not bool:
        raise ValueError('Invalid from_start.')
    if type(request.get('latest_episode', False)) is not bool:
        raise ValueError('Invalid latest_episode.')
    if request.get('latest_episode') and any(k in request for k in ('season', 'episode')):
        raise ValueError('Choose latest episode or explicit episode numbers.')
    if 'season' in request or 'episode' in request:
        if any(not whole_number(request.get(k), 1, 999) for k in ('season', 'episode')):
            raise ValueError('Supply both season and episode as positive integers.')


def usable_services(item, subscriptions):
    found = set()
    for offer in item.get('streamingOptions', {}).get('ph', []):
        service = offer.get('service', {}).get('id')
        link = offer.get('link') or offer.get('videoLink')
        if service in subscriptions and offer.get('type') == 'subscription' and isinstance(link, str) and re.match(r'^https://[^/\s]+/', link):
            found.add(service)
    return found


def resolve(request, settings, rows):
    validate(request, settings)
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError('Invalid catalog response.')
    wanted = normalize(request['query'])
    episode_requested = 'season' in request or bool(request.get('latest_episode') or request.get('episode_request'))
    if episode_requested and request.get('media_type') == 'movie':
        return result('unsupported_request', 'Episode selection requires a series, but media_type was movie. Correct the tool arguments; nothing was played.')
    matches = []
    candidates = []
    seen = set()
    for item in rows:
        title = item.get('title')
        if not isinstance(title, str) or not title:
            continue
        year = item.get('releaseYear', item.get('firstAirYear'))
        kind = item.get('showType')
        if kind not in ('movie', 'series'):
            continue
        if episode_requested and kind != 'series':
            continue
        services = usable_services(item, settings['subscriptions'])
        candidate = dict(title=title, year=year, media_type=kind,
                         services=[s for s in settings['preference'] if s in services])
        identity = (item.get('id', title), year, kind)
        if identity in seen:
            continue
        seen.add(identity)
        candidates.append(candidate)
        names = [normalize(n) for n in (title, item.get('originalTitle')) if isinstance(n, str)]
        if wanted not in names or ('year' in request and year != request['year']) or ('media_type' in request and kind != request['media_type']):
            continue
        matches.append(candidate)
    if not matches:
        return result('needs_title_correction', 'No exact title/year/type match. Use a clear catalog correction once or ask which title; nothing was played.', candidates=candidates[:12])
    # Availability must not silently resolve distinct remakes or movie/series collisions.
    if len(matches) != 1:
        return result('needs_clarification', 'Clarify only which title/version the user means using these candidates. Do not ask for a service: subscription preference is configured. Preserve the original episode/settings in the follow-up, then rerun this resolver with the clarified title/year/type; it selects the service automatically.', candidates=matches[:12],
                      request_context={key: request[key] for key in ('query', 'year', 'media_type', 'season', 'episode', 'episode_request', 'latest_episode', 'from_start') if key in request})
    selected = matches[0]
    if (request.get('latest_episode') or request.get('episode_request')) and selected['media_type'] != 'series':
        return result('unsupported_request', 'Episode selection requires a series. Nothing was played.', selected=selected)
    choices = selected['services']
    if not choices:
        if settings.get('kodi_fallback', False):
            if request.get('from_start'):
                return result('unsupported_request', 'Kodi fallback does not support a combined restart request. No command sent.', selected=selected)
            arguments = {'query': selected['title'], 'media_type': selected['media_type']}
            if selected['year'] is not None:
                arguments['year'] = int(selected['year'])
            if selected['media_type'] == 'series':
                if request.get('episode_request'):
                    metadata_arguments = {'query': selected['title']}
                    if selected['year'] is not None:
                        metadata_arguments['year'] = int(selected['year'])
                    return result('episode_lookup_required', 'Kodi fallback selected, but the episode is described indirectly. Inspect actual season/episode metadata before playback. Supplied numeric season/episode arguments are not authoritative for this description; no playback tool is returned. Set prepare_playback=true only for an authorized playback request.',
                                  selected=selected, service='kodi', service_name='Kodi POV',
                                  episode_request=request['episode_request'],
                                  metadata_tool='script__browse_kodi_series', metadata_arguments=metadata_arguments)
                if request.get('latest_episode'):
                    arguments['latest_episode'] = True
                elif 'season' not in request:
                    return result('needs_episode', 'No configured streaming subscription offer found. Kodi POV is the fallback; ask for explicit season and episode before playback.', selected=selected, service='kodi', service_name='Kodi POV')
                else:
                    arguments.update(season=int(request['season']), episode=int(request['episode']))
            return result('service_selected', 'No configured streaming subscription offer found. Kodi POV fallback selected; its catalog and sources are not verified by this lookup. Call the returned tool only for an authorized playback request.', selected=selected, service='kodi', service_name='Kodi POV', playback_tool='script__play_kodi_pov', playback_arguments=arguments)
        return result('unavailable', 'No PH subscription offer found on your configured services. No rentals, channels or Kodi fallback.', title=selected['title'])
    supported = [s for s in choices if not request.get('latest_episode') and not request.get('episode_request') and not (request.get('from_start') and s in ('netflix', 'apple')) and not ('season' in request and request.get('from_start'))]
    if not supported:
        return result('unsupported_request', 'The submitted indirect/latest episode or combined restart settings cannot be routed as supplied. Explicit numeric season and episode ARE supported on Netflix, HBO Max, Apple TV+ and Prime Video. If the conversation already supplies absolute numbers (including SxEy), rerun this resolver with numeric season/episode and omit episode_request. Otherwise clarify only the unsupported episode/restart setting. Do not ask the user to choose a service or offer manual navigation. Do not switch to Kodi while a configured subscription offer exists; do not claim the apps lack episode deep links.', candidates=matches)
    service = supported[0]
    # All playback tools re-resolve by title; only Apple/Prime can also filter year.
    collisions = [c for c in candidates if normalize(c['title']) == normalize(selected['title'])
                  and service in c['services']
                  and (c['year'], c['media_type']) != (selected['year'], selected['media_type'])]
    if collisions and (service in ('netflix', 'hbo') or any(c['year'] == selected['year'] for c in collisions)):
        return result('unsupported_request', 'The playback tool cannot safely distinguish these same-name versions on this service. No command sent.', candidates=matches)
    arguments = {'query': selected['title']}
    if service in ('apple', 'prime') and selected['year'] is not None:
        arguments['year'] = int(selected['year'])
    if service != 'netflix':
        arguments['start_playback'] = True
    if service != 'apple':
        arguments['from_start'] = request.get('from_start', False)
    if 'season' in request:
        arguments.update(season=int(request['season']), episode=int(request['episode']))
    return result('service_selected', 'Read-only lookup finished. Call the returned playback tool exactly once only for a play request. It rechecks availability; this result is not playback.',
                  selected=selected, service=service, service_name=SERVICES[service][0],
                  playback_tool=SERVICES[service][1], playback_arguments=arguments)


def search(query, key):
    url = 'https://api.movieofthenight.com/v4/shows/search/title?' + urlencode({'title': query.strip(), 'country': 'ph', 'series_granularity': 'show'})
    with urlopen(Request(url, headers={'X-API-Key': key, 'Accept': 'application/json'}), timeout=12) as response:
        return json.load(response)


def apple_episode(request, fetch=None):
    """Fill catalog link gaps using Apple's public PH episode metadata."""
    season, episode = request.get('season'), request.get('episode')
    link = request.get('show_link', '')
    match = re.fullmatch(r'https://tv[.]apple[.]com/ph/show/[A-Za-z0-9%._~-]+/(umc[.]cmc[.][A-Za-z0-9]+)/?', link)
    if not match or not all(whole_number(n, 1, 999) for n in (season, episode)):
        raise ValueError('Invalid Apple episode request.')
    show_id = match[1]

    def public_fetch(url):
        with urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=8) as response:
            if urlsplit(response.url).hostname != urlsplit(url).hostname:
                raise ValueError('Unexpected metadata redirect.')
            body = response.read(4_000_001)
            if len(body) > 4_000_000:
                raise ValueError('Metadata response too large.')
            return body.decode('utf-8')

    fetch = fetch or public_fetch
    page = fetch(link)
    embedded = re.search(r'<script[^>]+id="serialized-server-data"[^>]*>(.*?)</script>', page, re.S)
    if not embedded:
        raise ValueError('Apple page metadata missing.')
    data = json.loads(embedded[1])
    if not isinstance(data, dict) or not isinstance(data.get('data'), list) or not data['data']:
        raise ValueError('Invalid Apple page metadata.')
    props = data['data'][0]['data']['configuration']['applicationProps']
    if props['storefront']['storefrontId'] != 143474:
        raise ValueError('Unexpected Apple storefront.')
    params = dict(props['requiredParamsMap']['Default'])
    params['sf'] = '143474'
    # Bounded public metadata lookup; never invent an episode from array position.
    for offset in range(0, 300, 100):
        url = 'https://uts-api.itunes.apple.com/uts/v3/shows/' + show_id + '/episodes?'
        payload = json.loads(fetch(url + urlencode(params | {'nextToken': f'{offset}:100'})))['data']
        if not isinstance(payload.get('episodes'), list) or any(not isinstance(e, dict) for e in payload['episodes']):
            raise ValueError('Invalid Apple episode list.')
        if not whole_number(payload.get('totalEpisodeCount'), 0, 100000):
            raise ValueError('Invalid Apple episode count.')
        matches = [e for e in payload['episodes'] if e.get('showId') == show_id
                   and e.get('type') == 'Episode' and e.get('seasonNumber') == season
                   and e.get('episodeNumber') == episode]
        if len(matches) > 1:
            raise ValueError('Ambiguous Apple episode metadata.')
        if matches:
            item = matches[0]
            episode_link = item.get('url', '')
            pattern = r'https://tv[.]apple[.]com/ph/episode/[A-Za-z0-9%._~-]+/(umc[.]cmc[.][A-Za-z0-9]+)[?]showId=(umc[.]cmc[.][A-Za-z0-9]+)'
            target = re.fullmatch(pattern, episode_link)
            if not target or target[1] != item.get('id') or target[2] != show_id:
                raise ValueError('Invalid Apple episode link.')
            return result('episode_resolved', 'Exact episode found in Apple PH metadata.',
                          title_link=episode_link, episode_title=item.get('title', ''),
                          season=int(season), episode=int(episode))
        if offset + 100 >= payload['totalEpisodeCount']:
            break
    return result('episode_link_unavailable', 'No exact episode link found in the bounded Apple metadata lookup; this does not prove regional unavailability.')


def main():
    try:
        if len(sys.argv) != 2 or len(sys.argv[1]) > 4000:
            raise ValueError('Invalid request size.')
        request = json.loads(base64.b64decode(sys.argv[1], validate=True))
        if not isinstance(request, dict):
            raise ValueError('Expected a request object.')
        if request.get('action') == 'apple_episode':
            print(json.dumps(apple_episode(request), ensure_ascii=False))
            return
        import yaml  # Already installed in Home Assistant.
        settings = yaml.safe_load(Path('/config/nova_services.yaml').read_text())
        validate(request, settings)
        key = yaml.safe_load(Path('/config/secrets.yaml').read_text())['streaming_availability_api_key']
        output = resolve(request, settings, search(request['query'], key))
    except (ValueError, TypeError, KeyError, OSError, HTTPError, URLError):
        output = result('failed', 'Service lookup failed. Check configuration/API access; do not infer unavailability or send playback commands.')
    print(json.dumps(output, ensure_ascii=False))


if __name__ == '__main__':
    main()
