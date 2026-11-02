import asyncio
import os
import yaml
from homeassistant.core import HomeAssistant, Context, SupportsResponse
from homeassistant.helpers.script import Script
from homeassistant.helpers import config_validation as cv


def no_delays(value):
    if isinstance(value, list):
        return [no_delays(item) for item in value if not (isinstance(item, dict) and 'delay' in item)]
    if isinstance(value, dict):
        result = {key: no_delays(item) for key, item in value.items()}
        if 'wait_template' in result:
            result['timeout'] = '00:00:00'
        return result
    return value


async def main():
    hass = HomeAssistant('/tmp/netflix-restart-check')
    scripts = yaml.safe_load(open(os.environ.get('NOVA_SCRIPTS_PATH', '/config/scripts.yaml')))
    calls, lookups = [], []
    response = {'status': 200, 'content': [{'title': 'White Chicks', 'showType': 'movie',
        'streamingOptions': {'ph': [{'service': {'id': 'netflix'}, 'type': 'subscription',
                                    'link': 'https://www.netflix.com/title/60034587'}]}}]}

    def foreground(app):
        hass.states.async_set('remote.sony_xr_55x90l', 'on', {'current_activity': app})

    async def lookup(call):
        lookups.append(dict(call.data))
        return response

    async def capture(call):
        calls.append((call.domain, call.service, dict(call.data)))

    hass.services.async_register('rest_command', 'netflix_title_search', lookup, supports_response=SupportsResponse.ONLY)
    for domain, name in [('media_player', 'play_media'), ('media_player', 'media_play'),
                         ('media_player', 'media_pause'), ('remote', 'send_command')]:
        hass.services.async_register(domain, name, capture)
    script = Script(hass, cv.SCRIPT_SCHEMA(no_delays(scripts['play_netflix_title']['sequence'])), 'Netflix check', 'script')
    helper = Script(hass, cv.SCRIPT_SCHEMA(scripts['netflix_restart_from_playback']['sequence']), 'Disabled restart check', 'script')
    foreground('com.netflix.ninja')
    result = (await script.async_run({'query': 'White Chicks'}, Context())).service_response
    assert result['status'] == 'playback_requested' and result['play_command_sent'] is True
    assert [(domain, name) for domain, name, _ in calls] == [('remote', 'send_command'), ('media_player', 'play_media'), ('media_player', 'media_play')]
    assert calls[1][2]['media_content_id'] == 'https://www.netflix.com/watch/60034587?source=30'

    for app in ['com.netflix.ninja', 'launcher']:
        foreground(app)
        calls.clear(); lookups.clear()
        result = (await script.async_run({'query': 'White Chicks', 'from_start': True}, Context())).service_response
        assert result['status'] == 'unsupported_restart' and result['command_sent'] is False
        assert not calls and not lookups
        result = (await helper.async_run({}, Context())).service_response
        assert result['status'] == 'unsupported_restart' and result['command_sent'] is False
        assert not calls and not lookups

    result = (await script.async_run({'query': 'White Chicks'}, Context())).service_response
    assert result['status'] == 'needs_netflix_foreground' and result['play_command_sent'] is False
    assert not any(name in {'media_play', 'media_pause'} for _, name, _ in calls)
    response = {'status': 429, 'content': 'limited'}
    calls.clear()
    result = (await script.async_run({'query': 'White Chicks'}, Context())).service_response
    assert result['status'] == 'failed' and not calls
    print('PASS normal watch link + Play preserved; restart and legacy helper send no lookup/device commands in any foreground state; wrong-app and lookup failures block Play. Services mocked.')

asyncio.run(main())
