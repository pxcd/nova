import { Recorder } from './recorder.js';
import { Companion } from './avatar/companion.bundle.js';
import { ConversationCall } from './conversation-call.js';
import { validateCues } from './visemes.js';
const $ = id => document.getElementById(id);
const recorder = new Recorder();
const avatar = new Companion($('nova-avatar'));
let playbackDone;
avatar.levelSource = () => recorder.playbackLevel();
avatar.spectrumSource = () => recorder.playbackSpectrum();
avatar.visemeSource = () => lastVisemes ? { cues: lastVisemes, time: recorder.playbackTime() } : null;
avatar.load(new URL('/avatar/models/nova-likeness-study.vrm', location.href).href).then(() => { $('avatar-fallback').hidden = true; $('model-file').disabled = false; }).catch(() => { $('nova-avatar').hidden = true; notice('3D could not load. Voice is still available.'); });
let conversationKey = crypto.randomUUID();
let readiness, busy = false, controller, lastAudio;
let lastVisemes = null;

const stages = {
  idle: ['NOVA is here.', 'Start a conversation, then speak naturally.'],
  connecting: ['Connecting your microphone…', 'One moment.'],
  listening: ['I’m listening.', 'Speak naturally. A short pause sends your message.'],
  muted: ['Microphone muted.', 'Unmute when you’re ready.'],
  recording: ['I’m listening.', 'Pause briefly when you’ve finished.'],
  transcribing: ['Getting your words.', 'Turning a little sound into a little sense.'],
  thinking: ['On it.', 'Checking in with your home.'],
  voicing: ['Finding my voice.', 'Your reply is on its way.'],
  speaking: ['NOVA has the floor.', 'You can stop the voice below.']
};
function state(name, customHint) {
  avatar.setState(name);
  $('voice-console').dataset.state = name;
  const [title, hint] = stages[name] || stages.idle;
  $('status').textContent = title; $('hint').textContent = customHint || hint;
  $('talk').disabled = !call.active && (busy || name === 'speaking' || call.pending || !readiness?.voiceReady);
  $('replay').disabled = busy || name === 'speaking';
  $('talk').textContent = call.active ? 'End conversation' : 'Start conversation';
  $('talk').classList.toggle('end-call', call.active);
  $('mute').hidden = !call.active;
  $('mute').textContent = call.muted ? 'Unmute' : 'Mute';
  $('mute').setAttribute('aria-pressed', String(call.muted));
  $('send').disabled = busy || call.pending || !readiness?.ready;
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
    $('enable-mic').hidden = true;
    notice(!readiness.voiceReady ? 'The assistant needs speech-to-text and text-to-speech in Home Assistant. You can type while those are being configured.' : !isSecureContext ? 'Use HTTPS for the microphone on your iPhone.' : '');
    state('idle');
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
async function run(payload, voice = false) {
  busy = true; controller = new AbortController(); state(voice ? 'transcribing' : 'thinking'); notice('');
  lastAudio = null; lastVisemes = null; $('replay').hidden = true; recorder.stopPlayback();
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
        if (type === 'audio') {
          audioUrl = data.url;
          try { lastVisemes = data.visemes ? validateCues(data.visemes, data.duration) : null; } catch { lastVisemes = null; }
          $('model-label').textContent = lastVisemes ? 'NOVA · speech-synced' : 'NOVA · audio reactive';
        }
      }
      if (done) break;
    }
    if (audioUrl) {
      const response = await fetch(audioUrl, { signal: controller.signal });
      if (!response.ok) throw new Error('The spoken reply could not be loaded.');
      lastAudio = await response.arrayBuffer(); $('replay').hidden = false;
    }
    busy = false; state('idle');
    if (lastAudio) { try { await play(); } catch { state('idle'); notice('Tap Replay response to hear NOVA.'); } }
  } catch (error) {
    if (error.name !== 'AbortError') { message('assistant', error.message, true); notice(error.message); }
    busy = false; state('idle');
  }
}
async function play() {
  state('speaking');
  await new Promise((resolve, reject) => {
    playbackDone = resolve;
    recorder.play(lastAudio, () => { playbackDone = null; state('idle'); resolve(); })
      .catch(error => { playbackDone = null; state('idle'); reject(error); });
  });
}
const call = new ConversationCall(recorder, {
  onState: state,
  onTurn: pcm => run(pcm, true),
  onError: error => notice(error.name === 'NotAllowedError' ? 'Allow microphone access, then start the conversation again.' : error.message),
  onStop: () => { controller?.abort(); recorder.stopPlayback(); playbackDone?.(); playbackDone = null; }
});
$('talk').addEventListener('click', () => {
  notice('');
  if (call.active) call.stop(); else call.start();
});
$('mute').addEventListener('click', async () => { await call.setMuted(!call.muted); state($('voice-console').dataset.state); });
$('chat-toggle').addEventListener('click', () => {
  const open = $('conversation').hidden;
  $('conversation').hidden = !open;
  $('chat-toggle').setAttribute('aria-expanded', String(open));
});
$('model-file').addEventListener('change', async e => {
  const file = e.target.files[0]; if (!file) return;
  if (file.size > 50 * 1024 * 1024) { notice('Choose a VRM file smaller than 50 MB.'); return; }
  const url = URL.createObjectURL(file);
  try { await avatar.loadModel(url); $('model-label').textContent = 'Your avatar'; notice(''); }
  catch (error) { notice(error.message || 'This avatar could not be loaded.'); }
  finally { URL.revokeObjectURL(url); }
});
$('text-form').addEventListener('submit', async e => {
  e.preventDefault(); const text = $('message').value.trim(); if (!text || busy || call.pending) return;
  if (call.active) call.stop();
  recorder.unlock().catch(() => {}); message('user', text); $('message').value = ''; await run(text);
});
$('cancel').addEventListener('click', () => controller?.abort());
$('stop-audio').addEventListener('click', () => { recorder.stopPlayback(); playbackDone?.(); playbackDone = null; state('idle'); });
$('replay').addEventListener('click', async () => {
  const resume = call.active && !call.muted;
  if (resume) await call.setMuted(true);
  try { await play(); } catch (error) { notice(error.message); state('idle'); }
  finally { if (resume && call.active) await call.setMuted(false); }
});
$('clear').addEventListener('click', () => { conversationKey = crypto.randomUUID(); $('messages').replaceChildren(); lastAudio = null; $('replay').hidden = true; });
document.addEventListener('visibilitychange', () => {
  if (document.hidden && call.active) { call.stop(); notice('Conversation ended when NOVA left the screen.'); }
});
window.addEventListener('pagehide', e => { call.stop(); if (!e.persisted) avatar.destroy(); });
initialize();
