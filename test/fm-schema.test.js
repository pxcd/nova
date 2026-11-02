import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { normalizeFmRequest } from '../fm-schema.js';
const tools = JSON.parse(await readFile(new URL('./fixtures/ha-tool-schemas.json', import.meta.url)));
const tool = (request, name) => request.tools.find(t => t.function.name === name).function.parameters;
test('actual HA schemas are narrowed to Apple-compatible, HA-valid representations', () => {
  const request = { model: 'system', tools, messages: [{ role: 'user', content: 'hello' }], stream: true };
  const before = structuredClone(request); const result = normalizeFmRequest(request);
  assert.deepEqual(request, before);
  assert.equal(result.tools.length, 32);
  assert.deepEqual(result.tools.map(t => t.function.name), tools.map(t => t.function.name));
  assert.deepEqual(result.messages, request.messages); assert.equal(result.stream, true);
  assert.equal(tool(result, 'homeassistant__GetLiveContext').properties.domain.type, 'array');
  assert.equal(tool(result, 'media_player__HassSetVolumeRelative').properties.volume_step.type, 'integer');
  assert.equal(tool(result, 'media_player__HassSetVolumeRelative').properties.volume_step.minimum, -100);
  for (const name of ['media_player__HassMediaPlayerMute', 'media_player__HassMediaPlayerUnmute']) {
    assert.equal(tool(result, name).properties.is_volume_muted.type, 'boolean');
  }
  assert.deepEqual(tool(result, 'script__play_kodi_pov'), tool(request, 'script__play_kodi_pov'));
});
test('unknown unions fail visibly instead of being silently changed', () => {
  const request = { tools: [{ function: { name: 'new_tool', parameters: { type: 'object', properties: { value: { anyOf: [{ type: 'string' }, { type: 'integer' }] } } } } }] };
  assert.throws(() => normalizeFmRequest(request), /new_tool.value/);
});
test('unknown untyped fields fail visibly', () => {
  assert.throws(() => normalizeFmRequest({ tools: [{ function: { name: 'unknown', parameters: { type: 'object', properties: { flag: {} } } } }] }), /unknown.flag/);
  assert.deepEqual(normalizeFmRequest({ model: 'system', messages: [] }), { model: 'system', messages: [] });
});
