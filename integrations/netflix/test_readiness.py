"""Run in HA with staged YAML. All device services are mocked."""
import asyncio
import json
import os
import re
from pathlib import Path
import yaml
from homeassistant.core import Context, HomeAssistant, SupportsResponse
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.script import Script


def immediate(value):
    if isinstance(value, list):
        return [immediate(v) for v in value if not (isinstance(v, dict) and 'delay' in v)]
    if isinstance(value, dict):
        result = {k: immediate(v) for k, v in value.items()}
        if 'wait_template' in result:
            result['timeout'] = '00:00:00'
        return result
    return value


async def main():
    hass = HomeAssistant('/tmp/nova-netflix-readiness-check')
    raw = yaml.safe_load(Path(os.environ.get('NOVA_SCRIPTS_PATH', '/config/scripts.yaml')).read_text())
    calls = []
    waking, home, launching = True, True, True
    ready, playing = True, True
    probe_count = 0
    frozen = False
    samples = []
    response = {'status': 200, 'content': [{'title': 'Example', 'showType': 'movie',
        'streamingOptions': {'ph': [{'service': {'id': 'netflix'}, 'type': 'subscription',
                                    'link': 'https://www.netflix.com/watch/12345678'}]}}]}

    def state(app='com.netflix.ninja', on=True):
        hass.states.async_set('remote.sony_xr_55x90l', 'on' if on else 'off', {'current_activity': app})
        hass.states.async_set('media_player.sony_xr_55x90l_2', 'on' if on else 'unavailable')

    async def lookup(call):
        return response

    async def capture(call):
        calls.append((call.domain, call.service, dict(call.data)))
        if call.service == 'turn_on' and waking:
            state('launcher')
        if call.service == 'send_command' and home:
            state('launcher')
        if call.service == 'play_media' and launching:
            state()

    async def probe(call):
        nonlocal probe_count
        if samples:
            r, p, pos = samples.pop(0)
            calls.append(('script', 'probe', dict(call.data)))
            return {'ready': r, 'playing': p, 'position_ms': pos}
        probe_count += 1
        calls.append(('script', 'probe', dict(call.data)))
        return {'ready': ready, 'playing': playing, 'position_ms': 10 if frozen else probe_count * 1000}

    hass.services.async_register('rest_command', 'netflix_title_search', lookup, supports_response=SupportsResponse.ONLY)
    hass.services.async_register('script', 'netflix_readiness_probe', probe, supports_response=SupportsResponse.ONLY)
    for domain, name in [('remote', 'send_command'), ('media_player', 'turn_on'),
                         ('media_player', 'play_media'), ('media_player', 'media_play')]:
        hass.services.async_register(domain, name, capture)
    script = Script(hass, cv.SCRIPT_SCHEMA(immediate(raw['play_netflix_title']['sequence'])), 'Launch check', 'script')

    async def run(**kwargs):
        calls.clear()
        return (await script.async_run({'query': 'Example', **kwargs}, Context())).service_response

    state(on=False)
    result = await run()
    assert result['status'] == 'playback_reported' and result['media_session_playing'], (result, calls)
    assert not result['playback_verified'] and not result['title_verified']
    assert calls[0][1] == 'turn_on'
    assert sum(c[1] == 'media_play' for c in calls) == 1
    assert all(c[2].get('command') in (None, 'HOME') for c in calls)

    state(on=False); waking = False
    result = await run()
    assert result['status'] == 'needs_tv_ready' and len(calls) == 1
    waking = True; state(); home = False
    result = await run()
    assert result['status'] == 'needs_tv_ready' and len(calls) == 1
    home = True; launching = False
    result = await run()
    assert result['status'] == 'needs_netflix_foreground'
    assert not any(c[1] in ('probe', 'media_play') for c in calls)

    launching = True; ready = playing = False
    result = await run()
    assert result['status'] == 'needs_netflix_ready' and result['play_command_sent']
    assert sum(c[1] == 'media_play' for c in calls) == 1
    ready = True
    result = await run()
    assert result['status'] == 'needs_netflix_ready' and result['play_command_sent']
    assert sum(c[1] == 'probe' for c in calls) == 6
    assert sum(c[1] == 'media_play' for c in calls) == 2
    playing = True; frozen = True
    result = await run()
    assert result['status'] == 'needs_netflix_ready' and not result['playback_advancing']
    assert sum(c[1] == 'media_play' for c in calls) == 1
    samples[:] = [(False, False, None), (True, True, 1115), (True, False, 10), (True, True, 1000), (True, True, 2100)]
    result = await run()
    assert result['status'] == 'playback_reported' and result['playback_advancing']
    assert result['resume_retry_sent'] and sum(c[1] == 'media_play' for c in calls) == 2
    result = await run(from_start=True)
    assert result['status'] == 'unsupported_restart' and not calls
    response = {'status': 500, 'content': []}
    result = await run()
    assert result['status'] == 'failed' and not calls

    # Exercise the real probe template separately, including stale/malformed ADB output.
    probe_script = Script(hass, cv.SCRIPT_SCHEMA(immediate(raw['netflix_readiness_probe']['sequence'])), 'Probe check', 'script')
    native = {'status': 'ready', 'package': 'com.netflix.ninja', 'state_before': 3, 'position_before_ms': 1000}
    fresh = True
    async def adb(call):
        command = call.data['command']
        assert 'NovaSeek inspect' in command and 'seek-one-second' not in command
        marker = command.split('; echo ', 1)[1]
        payload = native if isinstance(native, str) else json.dumps(native)
        hass.states.async_set('media_player.android_tv_10_0_0_174', 'idle',
            {'adb_response': 'NOVA_SEEK_RESULT=' + payload + '\n' + (marker if fresh else 'STALE')})
    hass.services.async_register('androidtv', 'adb_command', adb)
    async def check():
        return (await probe_script.async_run({'wait_seconds': 0}, Context())).service_response
    state()
    assert (await check()) == {'ready': True, 'playing': True, 'position_ms': 1000}
    native['state_before'] = 2
    assert (await check()) == {'ready': True, 'playing': False, 'position_ms': 1000}
    native['package'] = 'com.wbd.stream'
    assert (await check()) == {'ready': False, 'playing': False, 'position_ms': None}
    native = 'invalid JSON'
    assert (await check()) == {'ready': False, 'playing': False, 'position_ms': None}
    native = {'status': 'ready', 'package': 'com.netflix.ninja', 'state_before': 3, 'position_before_ms': 1000}; fresh = False
    assert (await check()) == {'ready': False, 'playing': False, 'position_ms': None}
    print('PASS wake/Home/foreground gates, bounded readiness and playback polling, no blind OK, no false title verification, fresh read-only native probe and malformed/stale output rejection; no TV actions.')


asyncio.run(main())
