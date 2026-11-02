"""Run inside HA's Python environment. Shell and device actions are mocked."""
import asyncio
import json
import os
from pathlib import Path
import yaml
from homeassistant.core import Context, HomeAssistant, SupportsResponse
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.script import Script


async def main():
    hass = HomeAssistant('/tmp/nova-catalog-script-check')
    raw = yaml.safe_load(Path(os.environ.get('NOVA_CATALOG_SCRIPTS_PATH', '/config/scripts.yaml')).read_text())['find_netflix_by_performer']
    calls = []
    output = {'returncode': 0, 'stdout': json.dumps({'status': 'search_results', 'command_sent': False,
              'candidates': [{'title': 'Leo'}], 'selected': {'title': 'Leo'}})}
    async def shell(call):
        calls.append(dict(call.data))
        return output
    hass.services.async_register('shell_command', 'nova_catalog_discovery', shell,
                                 supports_response=SupportsResponse.ONLY)
    script = Script(hass, cv.SCRIPT_SCHEMA(raw['sequence']), 'Catalog check', 'script')
    result = (await script.async_run({'performer': 'Adam Sandler', 'choose_random': True}, Context())).service_response
    assert result['status'] == 'search_results' and result['command_sent'] is False
    assert calls[0]['request_payload'] == {'performer': 'Adam Sandler', 'content_kind': 'movie', 'choose_random': True}
    for invalid in [{'returncode': 1, 'stdout': '{}'}, {'returncode': 0, 'stdout': 'not json'},
                    {'returncode': 0, 'stdout': '[]'}, {'returncode': 0, 'stdout': '{}'}]:
        output = invalid
        result = (await script.async_run({'performer': 'Adam Sandler'}, Context())).service_response
        assert result['status'] == 'failed' and result['command_sent'] is False
    print('PASS discovery payload/defaults and structured failures; no device-control services registered or called.')

asyncio.run(main())
