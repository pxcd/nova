"""Run in HA's Python environment; all app and power services are mocked."""
import asyncio
import os
from pathlib import Path
import yaml
from homeassistant.core import HomeAssistant, Context, SupportsResponse
from homeassistant.helpers.script import Script
from homeassistant.helpers import config_validation as cv


async def main():
    hass = HomeAssistant('/tmp/nova-standby-tests')
    raw = yaml.safe_load(Path(os.environ.get('NOVA_APP_CONTROL_SCRIPTS_PATH', '/config/scripts.yaml')).read_text())
    sequence = raw['tv_standby']['sequence']
    for step in sequence:
        if 'wait_template' in step:
            step['timeout'] = 0
    calls = []
    failed_app = None
    power_works = True

    async def quit_app(call):
        app = call.data['app']
        calls.append(('quit', app))
        await asyncio.sleep(0)
        if app == failed_app:
            raise RuntimeError('Simulated app-stop failure')
        return dict(status='force_quit_confirmed', force_quit_verified=True)

    async def power_off(call):
        calls.append(('off', call.data['entity_id']))
        if power_works:
            hass.states.async_set('media_player.bravia_xr_55x90l', 'off')

    hass.services.async_register('script', 'force_quit_tv_app', quit_app, supports_response=SupportsResponse.ONLY)
    hass.services.async_register('media_player', 'turn_off', power_off)
    batch = Script(hass, cv.SCRIPT_SCHEMA(raw['force_quit_tv_apps']['sequence']), 'Quit apps test', 'script')

    async def quit_batch(call):
        return (await batch.async_run(dict(call.data), call.context)).service_response

    hass.services.async_register('script', 'force_quit_tv_apps', quit_batch, supports_response=SupportsResponse.ONLY)
    script = Script(hass, cv.SCRIPT_SCHEMA(sequence), 'TV standby test', 'script')

    async def run(data, initial='on'):
        calls.clear()
        hass.states.async_set('media_player.bravia_xr_55x90l', initial)
        return (await script.async_run(data, Context())).service_response

    result = await run({})
    assert result['status'] == 'standby_reported' and result['app_results'] == []
    assert calls == [('off', ['media_player.bravia_xr_55x90l'])], calls
    apps = ['Netflix', 'Apple TV', 'Prime Video', 'HBO Max']
    result = await run({'apps': apps})
    assert calls == [('quit', app) for app in apps] + [('off', ['media_player.bravia_xr_55x90l'])], calls
    assert [item['app'] for item in result['app_results']] == apps
    assert all(item['force_quit_verified'] for item in result['app_results'])
    assert result['standby_reported'] is True
    for bad in ['Netflix', None, {}, ['unknown'], ['Netflix', 'Netflix'], [True]]:
        result = await run({'apps': bad})
        assert result['status'] == 'invalid_apps' and not calls, (bad, result, calls)
    for selected in [[], ['HBO Max'], ['Prime Video', 'Netflix'], apps + ['Kodi']]:
        calls.clear()
        result = (await batch.async_run({'apps': selected}, Context())).service_response
        assert calls == [('quit', app) for app in selected], calls
        assert result['status'] == 'apps_stopped'
    failed_app = 'Apple TV'
    result = await run({'apps': apps})
    assert len(calls) == 5 and calls[-1][0] == 'off'
    assert result['app_results'][1]['force_quit_verified'] is False
    assert result['app_results'][2]['force_quit_verified'] is True
    failed_app = None
    power_works = False
    result = await run({})
    assert result['status'] == 'standby_unconfirmed' and result['standby_reported'] is False
    result = await run({}, initial='off')
    assert result['status'] == 'standby_reported' and len(calls) == 1
    print('PASS standby-only, ordered app stops, invalid inputs, app-stop failure continuation, unconfirmed power and already-off state. No TV actions.')


asyncio.run(main())
