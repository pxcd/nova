import { Recorder } from './recorder.js';
const $ = id => document.getElementById(id);
const recorder = new Recorder();
let conversationKey = crypto.randomUUID();
let readiness, busy = false, recording = false, starting = false, held = false, timer, controller, lastAudio;
let micReady = false, recordingCancelled = false;
const stages = {
  idle: ['Hold to talk', 'Press, speak, release. NOVA will take it from there.'],
  recording: ['I’m listening.', 'Release when you’re done.'],
  transcribing: ['Getting your words.', 'Turning a little sound into a little sense.'],
  thinking: ['On it.', 'Checking in with your home.'],
  voicing: ['Finding my voice.', 'Your reply is on its way.'],
  speaking: ['NOVA has the floor.', 'You can stop the voice below.']
};
function state(name, customHint) {
  $('voice-console').dataset.state = name;
  const [title, hint] = stages[name] || stages.idle;
  $('status').textContent = title; $('hint').textContent = customHint || hint;
  $('talk').disabled = busy || !micReady || !readiness?.voiceReady;
  $('send').disabled = busy || recording || starting || !readiness?.ready;
  $('cancel').hidden = !busy;
  $('stop-audio').hidden = name !== 'speaking';
}
function notice(text) { $('notice').textContent = text || ''; $('notice').hidden = !text; }
function message(speaker, text, error = false) {
  $('empty')?.remove();
  const row = document.createElement('div'); row.className = `message ${speaker}${error ? ' error' : ''}`;
  const label = document.createElement('span'); label.className = 'speaker'; label.textContent = speaker === 'user' ? 'YOU' : 'NOVA';
  const content = document.createElement('p'); content.textContent = text;
  row.append(label, content); $('messages').append(row);
  while ($('messages').children.length > 30) $('messages').firstElementChild.remove();
  $('messages').scrollTop = $('messages').scrollHeight;
}
async function jsonFetch(url, options) {
  const r = await fetch(url, options); const data = await r.json();
  if (r.status === 401) { $('assistant').hidden = true; $('login-panel').hidden = false; }
  if (!r.ok) throw new Error(data.error || 'Could not connect.');
  return data;
}
async function refresh() {
  try {
    readiness = await jsonFetch('/api/status');
    $('connection').textContent = 'Connected to home'; $('connection-dot').className = 'dot online';
    $('pipeline-label').textContent = `SYNAPSE / ${readiness.pipeline.toUpperCase()}`;
    $('enable-mic').hidden = micReady || !readiness.voiceReady;
    notice(!readiness.voiceReady ? 'The assistant needs speech-to-text and text-to-speech in Home Assistant. You can type while those are being configured.' : !isSecureContext ? 'Use HTTPS for the microphone on your iPhone.' : '');
    state('idle', !micReady ? 'Enable your microphone below, or type a message.' : undefined);
  } catch (error) {
    readiness = { ready: false }; $('connection').textContent = 'Home unavailable'; $('connection-dot').className = 'dot offline';
    notice(error.message); state('idle', 'Check the connection, then reload NOVA.');
  }
}
async function initialize() {
  try {
    const session = await jsonFetch('/api/session');
    $('login-panel').hidden = session.authenticated; $('assistant').hidden = !session.authenticated;
    if (session.authenticated) await refresh();
    else { $('connection').textContent = 'Private connection'; $('connection-dot').className = 'dot'; }
  } catch (error) { $('login-panel').hidden = false; $('login-error').textContent = error.message; }
}
$('login-form').addEventListener('submit', async e => {
  e.preventDefault(); $('login-error').textContent = '';
  try {
    await jsonFetch('/api/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ password: $('password').value }) });
    $('password').value = ''; await initialize();
  } catch (error) { $('login-error').textContent = error.message; }
});
$('enable-mic').addEventListener('click', async () => {
  try { await recorder.prepare(); micReady = true; $('enable-mic').hidden = true; notice(''); state('idle'); }
  catch (error) { notice(error.name === 'NotAllowedError' ? 'Microphone access was denied. Allow it in Safari’s website settings, then try again.' : error.message); }
});
async function run(payload, voice = false) {
  busy = true; controller = new AbortController(); state(voice ? 'transcribing' : 'thinking'); notice('');
  lastAudio = null; $('replay').hidden = true; recorder.stopPlayback();
  try {
    const r = await fetch('/api/run', { method: 'POST', headers: { 'Content-Type': voice ? 'application/octet-stream' : 'application/json', 'X-NOVA-Conversation': conversationKey },
      body: voice ? payload : JSON.stringify({ text: payload }), signal: controller.signal });
    if (!r.ok) { const d = await r.json(); throw new Error(d.error || 'Request failed.'); }
    let pending = ''; const decoder = new TextDecoder(); const reader = r.body.getReader(); let audioUrl;
    while (true) {
      const { done, value } = await reader.read();
      pending += decoder.decode(value, { stream: !done });
      let index;
      while ((index = pending.indexOf('\n\n')) !== -1) {
        const frame = pending.slice(0, index); pending = pending.slice(index + 2);
        const type = /^event: (.+)$/m.exec(frame)?.[1]; const raw = /^data: (.+)$/m.exec(frame)?.[1];
        if (!type || !raw) continue;
        const data = JSON.parse(raw);
        if (type === 'stage') state(data.stage);
        if (type === 'transcript') message('user', data.text);
        if (type === 'reply') message('assistant', data.text);
        if (type === 'error') throw new Error(data.message);
        if (type === 'audio') audioUrl = data.url;
      }
      if (done) break;
    }
    if (audioUrl) {
      const response = await fetch(audioUrl, { signal: controller.signal });
      if (!response.ok) throw new Error('The spoken reply could not be loaded.');
      lastAudio = await response.arrayBuffer(); $('replay').hidden = false;
    }
    busy = false; state('idle');
    if (lastAudio) { try { await play(); } catch { notice('Tap Replay response to hear NOVA.'); } }
  } catch (error) {
    if (error.name !== 'AbortError') { message('assistant', error.message, true); notice(error.message); }
    busy = false; state('idle');
  }
}
async function play() {
  state('speaking');
  await recorder.play(lastAudio, () => state('idle'));
}
async function begin() {
  if (busy || starting || recording || !micReady) return;
  starting = true; held = true; recordingCancelled = false;
  try {
    await recorder.start(); starting = false;
    if (recordingCancelled) { recorder.stop(); state('idle'); return; }
    recording = true; state('recording'); notice('');
    if (!held) return finish();
    timer = setTimeout(finish, 45000);
  } catch (error) { starting = false; held = false; notice(error.message); state('idle'); }
}
function finish() {
  held = false;
  if (!recording) return;
  clearTimeout(timer); recording = false;
  const pcm = recorder.stop();
  if (pcm.byteLength < 3200) { state('idle'); notice('Hold the button while you speak, then release.'); return; }
  run(pcm, true);
}
$('talk').addEventListener('pointerdown', e => {
  if (e.button !== 0) return;
  e.preventDefault(); $('talk').setPointerCapture(e.pointerId); begin();
});
$('talk').addEventListener('pointerup', finish);
$('talk').addEventListener('pointercancel', () => { held = false; recordingCancelled = true; if (recording) { clearTimeout(timer); recording = false; recorder.stop(); state('idle'); notice('Recording cancelled.'); } });
$('talk').addEventListener('contextmenu', e => e.preventDefault());
$('talk').addEventListener('keydown', e => { if ([' ', 'Enter'].includes(e.key)) { e.preventDefault(); if (!e.repeat) begin(); } });
$('talk').addEventListener('keyup', e => { if ([' ', 'Enter'].includes(e.key)) { e.preventDefault(); finish(); } });
$('text-form').addEventListener('submit', async e => {
  e.preventDefault(); const text = $('message').value.trim(); if (!text || busy || recording || starting) return;
  recorder.unlock().catch(() => {}); message('user', text); $('message').value = ''; await run(text);
});
$('cancel').addEventListener('click', () => controller?.abort());
$('stop-audio').addEventListener('click', () => { recorder.stopPlayback(); state('idle'); });
$('replay').addEventListener('click', () => play().catch(error => { notice(error.message); state('idle'); }));
$('clear').addEventListener('click', () => { conversationKey = crypto.randomUUID(); $('messages').replaceChildren(); lastAudio = null; $('replay').hidden = true; });
document.addEventListener('visibilitychange', () => {
  if (document.hidden) {
    held = false; recordingCancelled = true;
    if (recording) { clearTimeout(timer); recording = false; recorder.stop(); state('idle'); notice('Recording cancelled when NOVA left the screen.'); }
  }
});
initialize();
