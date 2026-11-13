import { NovaPuppet } from './puppet.js';
const puppet = new NovaPuppet(document.querySelector('canvas'));
const status = document.querySelector('#status');
const error = document.querySelector('#error');
const audio = document.querySelector('audio');
const preview = document.querySelector('#preview');
let audioUrl;
try {
  await puppet.load();
  for (const control of document.querySelectorAll('button, input[type=file]')) control.disabled = false;
  status.textContent = 'Idle · breathing & blinking';
} catch {
  error.textContent = 'The avatar artwork could not be loaded. Reload to try again.';
}
document.querySelector('#blink').addEventListener('click', () => puppet.blink());
document.querySelector('#tilt').addEventListener('input', e => { puppet.tilt = e.target.value; });
preview.addEventListener('click', () => {
  audio.pause(); puppet.preview = !puppet.preview;
  preview.setAttribute('aria-pressed', String(puppet.preview));
  status.textContent = puppet.preview ? 'Simulated talking preview' : 'Idle · breathing & blinking';
});
document.querySelector('#audio-file').addEventListener('change', e => {
  const file = e.target.files[0];
  if (!file) return;
  audio.pause(); if (audioUrl) URL.revokeObjectURL(audioUrl);
  audioUrl = URL.createObjectURL(file); audio.src = audioUrl;
  puppet.preview = false; preview.setAttribute('aria-pressed', 'false');
  error.textContent = ''; status.textContent = 'Recording ready · press Play';
});
audio.addEventListener('play', async () => {
  puppet.preview = false; preview.setAttribute('aria-pressed', 'false');
  try { await puppet.connectAudio(audio); status.textContent = 'Mouth follows recording audio'; }
  catch { audio.pause(); error.textContent = 'Audio analysis could not start. Try Play again.'; }
});
audio.addEventListener('pause', () => { status.textContent = 'Idle · breathing & blinking'; });
audio.addEventListener('error', () => { error.textContent = 'This recording cannot be played. Try an MP3, M4A or WAV file.'; });
document.addEventListener('visibilitychange', () => {
  if (document.hidden) { audio.pause(); puppet.preview = false; preview.setAttribute('aria-pressed', 'false'); }
});
window.addEventListener('pagehide', () => {
  if (audioUrl) URL.revokeObjectURL(audioUrl);
  puppet.destroy();
}, { once: true });
