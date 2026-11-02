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
    calls = []
    player_mode = 'playing'
    response = {'status': 200, 'content': [{'title': 'White Chicks', 'showType': 'movie',
        'streamingOptions': {'ph': [{'service': {'id': 'netflix'}, 'type': 'subscription',
                                    'link': 'https://www.netflix.com/title/60034587'}]}}]}

    def foreground(app):
        hass.states.async_set('remote.sony_xr_55x90l', 'on', {'current_activity': app})

    async def lookup(call):
        return response

    async def capture(call):
        calls.append((call.domain, call.service, dict(call.data)))

    async def player_read(call):
        await capture(call)
        marker = call.context.id if player_mode != 'stale' else 'previous-run'
        text = 'NOVA_NETFLIX_PLAYER_' + marker + '\n'
        if player_mode not in {'inactive', 'absent'}:
            text += 'state=PlaybackState {state=' + ('2' if player_mode == 'paused' else '3') + ', position=30000}'
        hass.states.async_set('media_player.android_tv_10_0_0_174', 'idle', {'adb_response': text})
        if player_mode == 'switch':
            foreground('launcher')

    hass.services.async_register('rest_command', 'netflix_title_search', lookup, supports_response=SupportsResponse.ONLY)
    for domain, name in [('media_player', 'play_media'), ('media_player', 'media_play'),
                         ('media_player', 'media_pause'), ('remote', 'send_command')]:
        hass.services.async_register(domain, name, capture)
    hass.services.async_register('androidtv', 'adb_command', player_read)
    helper = Script(hass, cv.SCRIPT_SCHEMA(no_delays(scripts['netflix_restart_from_playback']['sequence'])), 'Restart check', 'script')

    async def restart(call):
        return (await helper.async_run({}, call.context)).service_response

    hass.services.async_register('script', 'netflix_restart_from_playback', restart, supports_response=SupportsResponse.ONLY)
    script = Script(hass, cv.SCRIPT_SCHEMA(no_delays(scripts['play_netflix_title']['sequence'])), 'Netflix check', 'script')
    foreground('com.netflix.ninja')
    result = (await script.async_run({'query': 'White Chicks'}, Context())).service_response
    assert result['status'] == 'playback_requested' and result['play_command_sent'] is True
    assert [(domain, name) for domain, name, _ in calls] == [('remote', 'send_command'), ('media_player', 'play_media'), ('media_player', 'media_play')]
    assert calls[1][2]['media_content_id'] == 'https://www.netflix.com/watch/60034587?source=30'

    calls.clear()
    result = (await script.async_run({'query': 'White Chicks', 'from_start': True}, Context())).service_response
    assert result['status'] == 'restart_requested' and result['from_start'] is True and result['play_command_sent'] is True
    assert [(domain, name) for domain, name, _ in calls] == [('remote', 'send_command'), ('media_player', 'play_media'), ('media_player', 'media_play'), ('androidtv', 'adb_command'), ('media_player', 'media_pause'), ('remote', 'send_command'), ('remote', 'send_command')]
    assert calls[1][2]['media_content_id'] == 'https://www.netflix.com/watch/60034587?source=30'
    assert [data['command'] for domain, _, data in calls if domain == 'remote'] == ['HOME', ['BACK', 'BACK'], ['DPAD_DOWN', 'DPAD_CENTER']]
    assert result['restart_verified'] is False

    for player_mode in ['paused', 'stale', 'inactive', 'absent', 'switch']:
        foreground('com.netflix.ninja')
        calls.clear()
        result = (await helper.async_run({}, Context())).service_response
        assert result['status'] == 'needs_netflix_playback', (player_mode, result)
        assert not any(domain in {'remote', 'media_player'} for domain, _, _ in calls), (player_mode, calls)
        assert len(calls) <= 8
    foreground('launcher')
    calls.clear()
    result = (await helper.async_run({}, Context())).service_response
    assert result['status'] == 'needs_netflix_playback' and not calls
    result = (await script.async_run({'query': 'White Chicks'}, Context())).service_response
    assert result['status'] == 'needs_netflix_foreground' and result['play_command_sent'] is False
    assert not any(name in {'media_play', 'media_pause'} for _, name, _ in calls)
    response = {'status': 429, 'content': 'limited'}
    calls.clear()
    result = (await script.async_run({'query': 'White Chicks', 'from_start': True}, Context())).service_response
    assert result['status'] == 'failed' and not calls
    print('PASS normal movie Play unchanged; restart starts requested movie then fresh playing check → Pause → Back twice → Down/OK; stale/paused/inactive/missing/wrong-app states block navigation; lookup failures send no TV commands. Services mocked.')

asyncio.run(main())
