import test from 'node:test';
import assert from 'node:assert/strict';
import { toPCM16 } from '../public/recorder.js';
test('recorded audio becomes 16 kHz mono little-endian PCM with clipping', () => {
  const chunks = [new Float32Array([1, 1, 1, -1, -1, -1]), new Float32Array([2, 2, 2, 0, 0, 0])];
  const pcm = new DataView(toPCM16(chunks, 48000));
  assert.equal(pcm.byteLength, 8);
  assert.deepEqual([0, 2, 4, 6].map(offset => pcm.getInt16(offset, true)), [32767, -32768, 32767, 0]);
});
test('empty recording remains empty', () => assert.equal(toPCM16([], 48000).byteLength, 0));
