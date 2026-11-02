"""Run in HA's Python environment; the ADB transport is mocked."""
import asyncio
import json
import os
from pathlib import Path
import yaml
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.script import Script


async def main():
    hass = HomeAssistant('/tmp/nova-current-restart-check')
    path = os.environ.get('NOVA_RESTART_SCRIPTS_PATH', '/config/scripts.yaml')
    raw = yaml.safe_load(Path(path).read_text())['restart_current_netflix']['sequence']
    calls = []
    mode = 'valid'
    good = {'status': 'seek_confirmed', 'package': 'com.netflix.ninja', 'state_before': 3,
            'target_position_ms': 1000, 'command_sent': True, 'seek_verified': True,
            'position_after_ms': 88, 'state_after': 3}

    async def adb(call):
        calls.append(dict(call.data))
        marker = call.context.id if mode != 'stale' else 'previous-run'
        data = dict(good)
        if mode == 'not_ready':
            data = {'status': 'not_ready', 'command_sent': False, 'seek_verified': False}
        if mode == 'wrong_package': data['package'] = 'other.app'
        if mode == 'paused': data['state_before'] = 2
        if mode == 'wrong_target': data['target_position_ms'] = 0
        if mode == 'not_at_start': data['position_after_ms'] = 100000
        if mode == 'unverified': data['seek_verified'] = False
        if mode == 'no_command': data['command_sent'] = False
        text = 'NOVA_CURRENT_RESTART_' + marker + '\n'
        if mode != 'missing':
            text += 'NOVA_SEEK_RESULT=' + (json.dumps(data) if mode != 'bad_json' else 'broken') + '\n'
        if mode == 'duplicate': text += 'NOVA_SEEK_RESULT=' + json.dumps(data) + '\n'
        hass.states.async_set('media_player.android_tv_10_0_0_174', 'idle', {'adb_response': text})

    hass.services.async_register('androidtv', 'adb_command', adb)
    script = Script(hass, cv.SCRIPT_SCHEMA(raw), 'Current Netflix restart', 'script')
    hass.states.async_set('remote.sony_xr_55x90l', 'on', {'current_activity': 'com.netflix.ninja'})
    result = (await script.async_run({'position_seconds': 1}, Context())).service_response
    assert result['status'] == 'restart_confirmed' and result['restart_verified'] is True
    assert result['position_after_ms'] == 88 and len(calls) == 1
    assert 'NovaSeek seek-one-second' in calls[0]['command']
    assert not any(word in calls[0]['command'] for word in ['BACK', 'DPAD', 'am start', 'force-stop', 'REWIND'])
    for mode in ['stale', 'missing', 'bad_json', 'duplicate', 'wrong_package', 'paused',
                 'wrong_target', 'not_at_start', 'unverified', 'no_command', 'not_ready']:
        calls.clear()
        result = (await script.async_run({'position_seconds': 1}, Context())).service_response
        assert result['restart_verified'] is False, (mode, result)
        assert result['status'] != 'restart_confirmed' and len(calls) == 1
    for value in [0, 2, 1.5, True, '1', None]:
        calls.clear()
        result = (await script.async_run({'position_seconds': value}, Context())).service_response
        assert result['status'] == 'invalid_position' and not calls
    hass.states.async_set('remote.sony_xr_55x90l', 'on', {'current_activity': 'other.app'})
    calls.clear()
    result = (await script.async_run({'position_seconds': 1}, Context())).service_response
    assert result['status'] == 'needs_netflix_playback' and not calls
    print('PASS current-only seek validation, fresh marker, position/target/package/playing-state checks, malformed/stale result handling and wrong foreground rejection; no navigation/playback-launch services exist in this test.')

asyncio.run(main())
