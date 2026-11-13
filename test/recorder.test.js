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

test('playback meter follows output and resets on stop/end; a new reply has one output path', async () => {
  const { Recorder } = await import('../public/recorder.js');
  const recorder = new Recorder(); const sources = []; let destinations = 0;
  recorder.context = {
    state: 'running', resume: async () => {}, decodeAudioData: async () => ({}), destination: {},
    createAnalyser: () => ({ fftSize: 1024, connect() { destinations++; }, getFloatTimeDomainData(a) { a.fill(.1); } }),
    createBufferSource: () => { const s = { connect() {}, disconnect() {}, start() {}, stop() {} }; sources.push(s); return s; }
  };
  let ended = 0;
  await recorder.play(new ArrayBuffer(8), () => ended++);
  assert.ok(Math.abs(recorder.playbackLevel() - .1) < .001);
  recorder.stopPlayback(); assert.equal(recorder.playbackLevel(), 0); assert.equal(ended, 0);
  await recorder.play(new ArrayBuffer(8), () => ended++);
  sources[1].onended(); assert.equal(ended, 1); assert.equal(recorder.playbackLevel(), 0);
  assert.equal(destinations, 1);
});

test('stopping while reply audio decodes prevents late playback', async () => {
  const { Recorder } = await import('../public/recorder.js');
  const recorder = new Recorder(); let decoded; let started = false;
  recorder.context = { resume: async () => {}, decodeAudioData: () => new Promise(resolve => { decoded = resolve; }),
    createBufferSource() { started = true; throw new Error('Cancelled audio must not start'); } };
  const playing = recorder.play(new ArrayBuffer(8), () => {});
  while (!decoded) await new Promise(resolve => setImmediate(resolve));
  recorder.stopPlayback(); decoded({}); await playing;
  assert.equal(started, false); assert.equal(recorder.playbackLevel(), 0);
});

test('viseme time uses the audio context clock and resets after stop',async()=>{
 const {Recorder}=await import('../public/recorder.js');const r=new Recorder();
 r.context={currentTime:12};r.playing={onended:null,stop(){},disconnect(){}};r.playStarted=10;
 assert.equal(r.playbackTime(),2);r.context.currentTime=12.5;assert.equal(r.playbackTime(),2.5);
 r.stopPlayback();assert.equal(r.playbackTime(),null);
});

test('reply playback requests media audio before resuming the context; unsupported session APIs remain optional', async () => {
  const { Recorder } = await import('../public/recorder.js');
  const descriptor = Object.getOwnPropertyDescriptor(navigator, 'audioSession');
  const events = [];
  try {
    Object.defineProperty(navigator, 'audioSession', { configurable: true, value: { set type(value) { events.push(value); } } });
    const r = new Recorder();
    r.context = { resume: async () => events.push('resume'), decodeAudioData: async () => { throw Error('stop after resume'); } };
    await assert.rejects(r.play(new ArrayBuffer(8), () => {}));
    assert.deepEqual(events, ['playback', 'resume']);
    Object.defineProperty(navigator, 'audioSession', { configurable: true, value: { set type(_) { throw Error('unsupported'); } } });
    assert.doesNotThrow(() => r.setAudioSession('playback'));
    delete navigator.audioSession;
    assert.doesNotThrow(() => r.setAudioSession('playback'));
  } finally {
    if (descriptor) Object.defineProperty(navigator, 'audioSession', descriptor); else delete navigator.audioSession;
  }
});
