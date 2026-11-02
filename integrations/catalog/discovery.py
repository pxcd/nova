"""Bounded, read-only Netflix PH performer discovery. No device-control calls."""

import base64
import fcntl
import hashlib
import json
import os
from pathlib import Path
import random
import re
import sys
import tempfile
import time
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API = 'https://api.movieofthenight.com/v4'
TTL = 3600
MAX_PAGES_PER_REQUEST = 3
MAX_TOTAL_PAGES = 12
MAX_RESULTS = 12


def normalize(value):
    value = unicodedata.normalize('NFKD', str(value)).casefold()
    return ''.join(c for c in value if c.isalnum())


def project(item, checked_at):
    """Retain credits and verified PH subscription links, never plots/artwork."""
    options = []
    for option in item.get('streamingOptions', {}).get('ph', []):
        if option.get('service', {}).get('id') != 'netflix' or option.get('type') != 'subscription':
            continue
        link = option.get('videoLink') or option.get('link', '')
        match = re.fullmatch(r'https://www\.netflix\.com/(?:watch|title)/([0-9]{6,10})/?', link)
        if match:
            options.append(match.group(1))
    ids = sorted(set(options))
    if len(ids) != 1 or not isinstance(item.get('title'), str):
        return None
    return {'title': item['title'], 'year': item.get('releaseYear', item.get('firstAirYear')),
            'media_type': item.get('showType'), 'cast': [c for c in item.get('cast', []) if isinstance(c, str)],
            'netflix_id': ids[0], 'checked_at': checked_at,
            'special_hint': bool(re.search(r'\bstand[ -]?up\b|\bcomedy special\b',
                                          str(item.get('overview', '')), re.IGNORECASE))}


def matching(items, performer, kind):
    wanted = normalize(performer)
    matches = {}
    for item in items:
        credit = next((c for c in item['cast'] if normalize(c) == wanted), None)
        if not credit:
            continue
        # This catalog calls stand-up specials "movies". Explicit overview cues or
        # performer-prefixed titles distinguish likely specials; not a formal taxonomy.
        special = item['special_hint'] or normalize(item['title']).startswith(wanted)
        if kind == 'movie' and (item['media_type'] != 'movie' or special):
            continue
        if kind == 'special' and (item['media_type'] != 'movie' or not special):
            continue
        if kind == 'series' and item['media_type'] != 'series':
            continue
        matches[item['netflix_id']] = {'title': item['title'], 'year': item['year'],
            'media_type': item['media_type'], 'matched_performer': credit,
            'cast_verified': True, 'available_on_requested_service': True,
            'netflix_id': item['netflix_id'], 'availability_checked_at': item['checked_at']}
    return list(matches.values())


class Catalog:
    def __init__(self, api_key, cache_dir, clock=time.time, monotonic=time.monotonic):
        self.api_key = api_key
        self.cache_dir = Path(cache_dir)
        self.clock = clock
        self.monotonic = monotonic
        self.deadline = 0
        self.requests = 0

    def load(self, name):
        try:
            value = json.loads((self.cache_dir / name).read_text())
            if 0 <= self.clock() - value['created_at'] < TTL:
                return value
        except (OSError, ValueError, KeyError, TypeError):
            pass
        return None

    def save(self, name, value):
        with tempfile.NamedTemporaryFile('w', dir=self.cache_dir, delete=False) as target:
            path = Path(target.name)
            try:
                json.dump(value, target)
                target.close()
                os.replace(path, self.cache_dir / name)
            finally:
                path.unlink(missing_ok=True)

    def get(self, endpoint, params):
        remaining = self.deadline - self.monotonic()
        if remaining <= 0:
            raise RuntimeError('Catalog search time budget reached.')
        self.requests += 1
        request = Request(API + endpoint + '?' + urlencode(params),
                          headers={'X-API-Key': self.api_key, 'Accept': 'application/json'})
        try:
            with urlopen(request, timeout=min(8, remaining)) as response:
                return json.load(response)
        except HTTPError as error:
            raise RuntimeError('Catalog HTTP ' + str(error.code) + '; search stopped.') from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise RuntimeError('Catalog request failed or timed out; search stopped.') from None

    def search(self, performer, kind, choose_random):
        self.deadline = self.monotonic() + 30
        self.requests = 0
        api_type = 'series' if kind == 'series' else 'movie'
        pool_name = 'netflix-ph-' + api_type + '-v1.json'
        pool = self.load(pool_name) or {'created_at': self.clock(), 'items': [],
                                      'pages': 0, 'cursor': None, 'complete': False}
        name = 'performer-' + hashlib.sha256((normalize(performer) + ':' + api_type).encode()).hexdigest() + '.json'
        direct = self.load(name)
        problems = []
        if direct is None:
            direct = {'created_at': self.clock(), 'items': []}
            try:
                rows = self.get('/shows/search/title', {'title': performer, 'country': 'ph',
                                'series_granularity': 'show', 'show_type': api_type})
                if not isinstance(rows, list):
                    raise RuntimeError('Unexpected catalog title-search response.')
                direct['items'] = [p for row in rows if (p := project(row, self.clock()))]
                self.save(name, direct)
            except RuntimeError as error:
                problems.append(str(error))
        found = matching(pool['items'] + direct['items'], performer, kind)
        for _ in range(MAX_PAGES_PER_REQUEST):
            if problems or pool['complete'] or pool['pages'] >= MAX_TOTAL_PAGES or len(found) >= 5:
                break
            params = {'country': 'ph', 'catalogs': 'netflix.subscription',
                      'show_type': api_type, 'series_granularity': 'show',
                      'order_by': 'popularity_alltime', 'order_direction': 'desc'}
            if pool['cursor']:
                params['cursor'] = pool['cursor']
            try:
                page = self.get('/shows/search/filters', params)
                if not isinstance(page, dict) or not isinstance(page.get('shows'), list) or not isinstance(page.get('hasMore'), bool):
                    raise RuntimeError('Unexpected catalog filter response.')
                cursor = page.get('nextCursor')
                if page['hasMore'] and (not isinstance(cursor, str) or not cursor or cursor == pool['cursor']):
                    raise RuntimeError('Catalog pagination did not advance; search stopped.')
                by_id = {item['netflix_id']: item for item in pool['items']}
                for row in page['shows']:
                    item = project(row, self.clock())
                    if item:
                        by_id[item['netflix_id']] = item
                pool.update(items=list(by_id.values()), pages=pool['pages'] + 1,
                            cursor=cursor, complete=not page['hasMore'])
                self.save(pool_name, pool)
                found = matching(pool['items'] + direct['items'], performer, kind)
            except RuntimeError as error:
                problems.append(str(error))
                break
        complete = pool['complete'] and not problems
        status = 'search_results' if found else ('no_matches' if complete else 'search_incomplete')
        shown = found[:MAX_RESULTS]
        selected = random.SystemRandom().choice(shown) if choose_random and shown else None
        return {'status': status, 'performer': performer, 'content_kind': kind, 'country': 'PH',
                'service': 'Netflix', 'command_sent': False, 'candidates': shown,
                'selected': selected, 'matching_count_in_checked_pool': len(found),
                'catalog_items_checked': len(pool['items']), 'catalog_pages_checked': pool['pages'],
                'search_complete': complete, 'requests_this_call': self.requests,
                'cache_max_age_seconds': TTL, 'errors': problems,
                'search_scope': 'complete_catalog' if complete else 'partial_catalog',
                'reply_hint': ("I checked a limited part of Netflix's PH catalog and did not find a verified match. "
                               "That does not mean no matching titles are available.") if status == 'search_incomplete' else '',
                'message': ('Choose only from these credit-verified Netflix PH subscription candidates. '
                            'This tool never plays anything. Revalidate the selected canonical title with the playback tool. '
                            'Results may be a bounded subset, not a full filmography. '
                            'If search_complete is false and candidates is empty, say the search was incomplete; '
                            'never claim no titles exist. Stand-up classification uses title/overview cues, not a formal catalog category.')}


def perform(request, catalog):
    if not isinstance(request, dict):
        raise ValueError('Expected an object request.')
    performer = request.get('performer')
    kind = request.get('content_kind', 'movie')
    choose_random = request.get('choose_random', False)
    if not isinstance(performer, str) or not 2 <= len(performer.strip()) <= 100 or not normalize(performer):
        raise ValueError('Provide a performer name between 2 and 100 characters.')
    if kind not in {'movie', 'special', 'series'} or not isinstance(choose_random, bool):
        raise ValueError('Choose movie, special or series, and a boolean choose_random.')
    return catalog.search(performer.strip(), kind, choose_random)


def main():
    try:
        if len(sys.argv) != 2 or len(sys.argv[1]) > 4000:
            raise ValueError('Invalid discovery request.')
        request = json.loads(base64.b64decode(sys.argv[1], validate=True))
        import yaml  # Existing HA dependency; credentials stay inside the VM.
        secret = yaml.safe_load(Path('/config/secrets.yaml').read_text())['streaming_availability_api_key']
        directory = Path('/config/.nova_catalog_cache')
        directory.mkdir(mode=0o700, exist_ok=True)
        with (directory / 'discovery.lock').open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError('Catalog discovery is busy; no playback command was sent.') from None
            result = perform(request, Catalog(secret, directory))
    except (ValueError, RuntimeError, OSError, KeyError, TypeError):
        result = {'status': 'failed', 'command_sent': False,
                  'message': 'Performer discovery could not complete. Check the request, API access, or try later. Do not infer unavailability.'}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
