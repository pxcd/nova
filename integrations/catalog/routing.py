"""Resolve named titles to subscribed PH services. Never controls a device."""

import base64
import json
from pathlib import Path
import re
import sys
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
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
    if type(request.get('from_start', False)) is not bool:
        raise ValueError('Invalid from_start.')
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
        return result('needs_clarification', 'Choose the title, year and type before selecting a service.', candidates=matches[:12])
    selected = matches[0]
    choices = selected['services']
    if not choices:
        if settings.get('kodi_fallback', False):
            if request.get('from_start'):
                return result('unsupported_request', 'Kodi fallback does not support a combined restart request. No command sent.', selected=selected)
            arguments = {'query': selected['title'], 'media_type': selected['media_type']}
            if selected['year'] is not None:
                arguments['year'] = int(selected['year'])
            if selected['media_type'] == 'series':
                if 'season' not in request:
                    return result('needs_episode', 'No configured streaming subscription offer found. Kodi POV is the fallback; ask for explicit season and episode before playback.', selected=selected, service='kodi', service_name='Kodi POV')
                arguments.update(season=int(request['season']), episode=int(request['episode']))
            return result('service_selected', 'No configured streaming subscription offer found. Kodi POV fallback selected; its catalog and sources are not verified by this lookup. Call the returned tool only for an authorized playback request.', selected=selected, service='kodi', service_name='Kodi POV', playback_tool='script__play_kodi_pov', playback_arguments=arguments)
        return result('unavailable', 'No PH subscription offer found on your configured services. No rentals, channels or Kodi fallback.', title=selected['title'])
    supported = [s for s in choices if not (request.get('from_start') and s in ('netflix', 'apple')) and not ('season' in request and s != 'netflix')]
    if not supported:
        return result('unsupported_request', 'Available services do not support the requested restart or numbered episode through the configured tools. Do not drop these settings.', candidates=matches)
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


def main():
    try:
        if len(sys.argv) != 2 or len(sys.argv[1]) > 4000:
            raise ValueError('Invalid request size.')
        request = json.loads(base64.b64decode(sys.argv[1], validate=True))
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
