"""Run in HA against staged scripts; no TV actions registered or performed."""
import asyncio
import json
import os
from pathlib import Path
import yaml
from homeassistant.core import Context, HomeAssistant, SupportsResponse
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.script import Script


async def main():
    hass = HomeAssistant('/tmp/nova-routing-script-check')
    path = os.environ.get('NOVA_CATALOG_SCRIPTS_PATH', '/config/scripts.yaml')
    raw = yaml.safe_load(Path(path).read_text())['resolve_streaming_title']
    calls = []
    output = {'returncode': 0, 'stdout': json.dumps({'status': 'service_selected',
              'command_sent': False, 'service': 'netflix'})}

    async def shell(call):
        calls.append(dict(call.data))
        return output

    hass.services.async_register('shell_command', 'nova_service_routing', shell,
                                 supports_response=SupportsResponse.ONLY)
    script = Script(hass, cv.SCRIPT_SCHEMA(raw['sequence']), 'Routing check', 'script')
    response = (await script.async_run({'query': 'White Chicks'}, Context())).service_response
    assert response['status'] == 'service_selected' and response['command_sent'] is False
    assert calls[-1]['request_payload'] == {'query': 'White Chicks', 'from_start': False}
    await script.async_run({'query': 'Severance', 'media_type': 'series', 'year': None,
                            'season': None, 'episode': None, 'from_start': None}, Context())
    assert calls[-1]['request_payload'] == {'query': 'Severance', 'media_type': 'series', 'from_start': False}
    request = {'query': 'Brooklyn Nine-Nine', 'season': 1, 'episode': 2,
               'from_start': True, 'year': 2013, 'media_type': 'series'}
    await script.async_run(request, Context())
    assert calls[-1]['request_payload'] == request
    for invalid in ({'returncode': 1, 'stdout': '{}'}, {'returncode': 0, 'stdout': 'bad json'},
                    {'returncode': 0, 'stdout': '[]'}, {'returncode': 0, 'stdout': '{}'}):
        output = invalid
        response = (await script.async_run({'query': 'White Chicks'}, Context())).service_response
        assert response['status'] == 'failed' and response['command_sent'] is False
    print('PASS routing payload/defaults, settings preservation and structured shell failures; no TV calls.')


asyncio.run(main())
