import test from 'node:test';
import assert from 'node:assert/strict';
import { HomeAssistant } from '../ha.js';

class FakeSocket extends EventTarget {
  static instances = [];
  static scenario = 'success';
  constructor() { super(); this.sent = []; this.closed = false; FakeSocket.instances.push(this); queueMicrotask(() => this.event({ type: 'auth_required' })); }
  event(data) { this.dispatchEvent(new MessageEvent('message', { data: JSON.stringify(data) })); }
  send(data) {
    this.sent.push(data);
    if (typeof data !== 'string') return;
    const message = JSON.parse(data);
    if (message.type === 'auth') return queueMicrotask(() => this.event({ type: 'auth_ok' }));
    if (message.type === 'assist_pipeline/run') {
      queueMicrotask(() => {
        this.event({ id: 1, type: 'event', event: { type: 'run-start', data: { runner_data: { stt_binary_handler_id: 7 } } } });
        this.event({ id: 1, type: 'event', event: { type: 'intent-end', data: { intent_output: { response: { speech: { plain: { speech: 'Done.' } } } } } } });
        this.event({ id: 1, type: 'event', event: { type: 'run-end', data: {} } });
        if (FakeSocket.scenario === 'timeout') this.event({ id: 1, type: 'event', event: { type: 'error', data: { code: 'timeout', message: 'Timed out' } } });
      });
    }
  }
  close() { this.closed = true; }
}
const pipeline = { id: 'nova', stt_engine: 'stt.whisper', tts_engine: 'tts.piper' };
const client = () => new HomeAssistant({ url: 'http://ha.local', token: 'test-only', WebSocketClass: FakeSocket });
test('audio uses the HA handler byte and an explicit end marker; requests have fresh context', async () => {
  FakeSocket.scenario = 'success'; const events = [];
  const pcm = Buffer.alloc(9000, 42);
  await client().run({ pipeline, pcm, onEvent: (...event) => events.push(event) });
  const ws = FakeSocket.instances.at(-1); const binary = ws.sent.filter(Buffer.isBuffer);
  assert.equal(binary.length, 4);
  assert.ok(binary.every(frame => frame[0] === 7));
  assert.deepEqual(Buffer.concat(binary.slice(0, -1).map(frame => frame.subarray(1))), pcm);
  assert.deepEqual(binary.at(-1), Buffer.from([7]));
  const command = JSON.parse(ws.sent.find(s => typeof s === 'string' && s.includes('assist_pipeline/run')));
  assert.equal(command.start_stage, 'stt'); assert.equal(command.conversation_id, undefined);
  assert.deepEqual(events, [['reply', { text: 'Done.' }]]); assert.equal(ws.closed, true);
});
test('late timeout after run-end is still reported as failure', async () => {
  FakeSocket.scenario = 'timeout';
  await assert.rejects(client().run({ pipeline, text: 'hello', onEvent() {} }), /Timed out/);
  assert.equal(FakeSocket.instances.at(-1).closed, true);
});
test('audio proxy rejects other origins and unrelated HA paths', async () => {
  await assert.rejects(client().audio('https://evil.example/audio.wav'), /unexpected audio/);
  await assert.rejects(client().audio('/api/states'), /unexpected audio/);
});

test('follow-up requests reuse only the supplied HA conversation', async () => {
  FakeSocket.scenario = 'success';
  await client().run({ pipeline, text: 'The 2004 version', conversationId: 'test-conversation', onEvent() {} });
  const ws = FakeSocket.instances.at(-1);
  const command = JSON.parse(ws.sent.find(s => typeof s === 'string' && s.includes('assist_pipeline/run')));
  assert.equal(command.conversation_id, 'test-conversation');
});
