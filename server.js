import http from 'node:http';
import https from 'node:https';
import { readFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { randomBytes, createHash, timingSafeEqual } from 'node:crypto';
import { networkInterfaces } from 'node:os';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { HomeAssistant } from './ha.js';
import { Conversations } from './conversations.js';

const root = dirname(fileURLToPath(import.meta.url));
try { process.loadEnvFile(join(root, '.env')); } catch (error) { if (error.code !== 'ENOENT') throw error; }
const password = process.env.NOVA_PASSWORD || '';
const tls = !process.argv.includes('--http') && existsSync(join(root, '.local/server.key')) && existsSync(join(root, '.local/server.crt'));
const host = process.env.HOST || '127.0.0.1';
if (!['localhost', '127.0.0.1', '::1'].includes(host) && (!password || !tls)) {
  throw new Error('LAN access requires NOVA_PASSWORD and HTTPS. Run npm run setup:https first.');
}
const port = Number(process.env.PORT || 8787);
const ha = new HomeAssistant({ url: process.env.HA_URL || 'http://172.16.152.130', token: process.env.HA_TOKEN,
  pipelineId: process.env.HA_PIPELINE_ID || '01m6bgw84tdtwygj299s623dwh' });
const sessions = new Map();
const attempts = new Map();
const audio = new Map();
const conversations = new Conversations();
let busy = false;
const allowedHosts = new Set(['localhost', '127.0.0.1', '[::1]', 'synapse.local', ...Object.values(networkInterfaces()).flat().filter(Boolean).map(n => n.address)]);
const assets = new Map([
  ['/', ['index.html', 'text/html; charset=utf-8']], ['/app.js', ['app.js', 'text/javascript; charset=utf-8']],
  ['/style.css', ['style.css', 'text/css; charset=utf-8']], ['/recorder.js', ['recorder.js', 'text/javascript; charset=utf-8']],
  ['/pcm-worklet.js', ['pcm-worklet.js', 'text/javascript; charset=utf-8']],
  ['/manifest.webmanifest', ['manifest.webmanifest', 'application/manifest+json']], ['/icon.svg', ['icon.svg', 'image/svg+xml']]
]);
const json = (res, code, value) => { res.writeHead(code, { 'Content-Type': 'application/json' }); res.end(JSON.stringify(value)); };
const hash = value => createHash('sha256').update(value).digest();
const authorized = req => {
  const id = /(?:^|;\s*)nova_session=([^;]+)/.exec(req.headers.cookie || '')?.[1];
  return id && (sessions.get(id) || 0) > Date.now();
};
const session = res => {
  const id = randomBytes(32).toString('hex');
  sessions.set(id, Date.now() + 12 * 60 * 60 * 1000);
  res.setHeader('Set-Cookie', `nova_session=${id}; HttpOnly; SameSite=Strict; Path=/; Max-Age=43200${tls ? '; Secure' : ''}`);
};
async function body(req, limit) {
  const chunks = []; let size = 0;
  for await (const chunk of req) {
    size += chunk.length;
    if (size > limit) throw Object.assign(new Error('Request is too large.'), { status: 413 });
    chunks.push(chunk);
  }
  return Buffer.concat(chunks);
}
async function handle(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('Referrer-Policy', 'no-referrer');
  res.setHeader('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; media-src 'self' blob:; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'");
  res.setHeader('Permissions-Policy', 'microphone=(self), camera=(), geolocation=()');
  const requestHost = req.headers.host || '';
  let url;
  try { url = new URL(req.url, `${tls ? 'https' : 'http'}://${requestHost}`); } catch { return json(res, 400, { error: 'Invalid request.' }); }
  if (!allowedHosts.has(url.hostname)) return json(res, 403, { error: 'Host is not allowed.' });
  if (req.method === 'POST' && req.headers.origin !== url.origin) return json(res, 403, { error: 'Open NOVA directly to use this action.' });
  if (req.method === 'GET' && assets.has(url.pathname)) {
    const [file, type] = assets.get(url.pathname);
    res.writeHead(200, { 'Content-Type': type }); return res.end(await readFile(join(root, 'public', file)));
  }
  if (req.method === 'GET' && url.pathname === '/api/session') {
    if (!password && ['127.0.0.1', '::1', '::ffff:127.0.0.1'].includes(req.socket.remoteAddress)) session(res);
    return json(res, 200, { authenticated: !password || !!authorized(req), secure: tls });
  }
  if (req.method === 'POST' && url.pathname === '/api/login') {
    const address = req.socket.remoteAddress;
    const now = Date.now();
    const attempt = attempts.get(address) || { count: 0, until: now + 5 * 60000 };
    if (attempt.until <= now) { attempt.count = 0; attempt.until = now + 5 * 60000; }
    if (attempt.count >= 10) return json(res, 429, { error: 'Too many attempts. Try again in five minutes.' });
    const data = JSON.parse((await body(req, 2048)).toString());
    if (!password || typeof data.password !== 'string' || !timingSafeEqual(hash(data.password), hash(password))) {
      attempt.count++; attempts.set(address, attempt); return json(res, 401, { error: 'That password did not match.' });
    }
    attempts.delete(address); session(res); return json(res, 200, { ok: true });
  }
  if (!authorized(req)) return json(res, 401, { error: 'Unlock NOVA to continue.' });
  if (req.method === 'GET' && url.pathname === '/api/status') {
    try {
      const pipeline = await ha.pipeline();
      return json(res, 200, { ready: true, voiceReady: !!pipeline.stt_engine && !!pipeline.tts_engine,
        stt: !!pipeline.stt_engine, tts: !!pipeline.tts_engine, voice: pipeline.tts_voice,
        pipeline: pipeline.name, secure: tls });
    } catch (error) { return json(res, 503, { ready: false, error: error.message }); }
  }
  if (req.method === 'GET' && url.pathname.startsWith('/api/audio/')) {
    const item = audio.get(url.pathname.slice('/api/audio/'.length));
    if (!item || item.expires < Date.now()) return json(res, 404, { error: 'Audio expired. Send another request.' });
    res.writeHead(200, { 'Content-Type': item.type, 'Content-Length': item.buffer.length }); return res.end(item.buffer);
  }
  if (req.method === 'POST' && url.pathname === '/api/run') {
    if (busy) return json(res, 409, { error: 'NOVA is handling another request. Try again shortly.' });
    const voice = req.headers['content-type']?.startsWith('application/octet-stream');
    const input = await body(req, voice ? 16000 * 2 * 45 : 12000);
    const text = voice ? undefined : JSON.parse(input.toString()).text?.trim();
    if (voice ? input.length < 3200 || input.length % 2 : typeof text !== 'string' || !text || text.length > 4000) {
      return json(res, 400, { error: voice ? 'Hold the button a little longer, then speak.' : 'Enter a message up to 4,000 characters.' });
    }
    const tab = req.headers['x-nova-conversation'];
    if (tab !== undefined && (typeof tab !== 'string' || !/^[a-f0-9-]{36}$/.test(tab))) {
      return json(res, 400, { error: 'Invalid conversation identifier. Reload NOVA.' });
    }
    const owner = /(?:^|;\s*)nova_session=([^;]+)/.exec(req.headers.cookie || '')?.[1];
    const conversationKey = tab && owner ? `${owner}:${tab}` : undefined;
    busy = true;
    const controller = new AbortController();
    res.on('close', () => { if (!res.writableEnded) controller.abort(); });
    res.writeHead(200, { 'Content-Type': 'text/event-stream', 'X-Accel-Buffering': 'no' });
    const emit = (type, data) => { if (!res.destroyed) res.write(`event: ${type}\ndata: ${JSON.stringify(data)}\n\n`); };
    const heartbeat = setInterval(() => { if (!res.destroyed) res.write(': heartbeat\n\n'); }, 15000);
    let tts;
    try {
      const pipeline = await ha.pipeline();
      emit('stage', { stage: voice ? 'transcribing' : 'thinking' });
      await ha.run({ pipeline, text, conversationId: conversationKey ? conversations.get(conversationKey) : undefined, pcm: voice ? input : undefined, signal: controller.signal,
        onEvent(type, data) {
          if (type === 'conversation') { if (conversationKey) conversations.set(conversationKey, data.id); return; }
          if (type === 'tts') tts = data.url; else emit(type, data); } });
      if (tts) {
        const item = await ha.audio(tts, AbortSignal.any([controller.signal, AbortSignal.timeout(20000)]));
        const id = randomBytes(24).toString('hex');
        audio.set(id, { ...item, expires: Date.now() + 5 * 60000 });
        emit('audio', { url: `/api/audio/${id}` });
      }
      emit('done', {});
    } catch (error) { emit('error', { message: error.message }); }
    finally { busy = false; clearInterval(heartbeat); res.end(); }
    return;
  }
  json(res, 404, { error: 'Not found.' });
}
const listener = (req, res) => handle(req, res).catch(error => {
  if (!res.headersSent) json(res, error.status || 400, { error: error instanceof SyntaxError ? 'Invalid request.' : 'Request could not be completed.' });
  else res.end();
});
const server = tls ? https.createServer({ key: await readFile(join(root, '.local/server.key')), cert: await readFile(join(root, '.local/server.crt')) }, listener) : http.createServer(listener);
server.requestTimeout = 120000;
server.headersTimeout = 15000;
server.listen(port, host, () => console.log(`NOVA listening on ${tls ? 'https' : 'http'}://${host}:${port}`));
let certificateServer;
if (tls) {
  certificateServer = http.createServer(async (req, res) => {
    if (req.url !== '/nova-ca.crt') { res.writeHead(404); return res.end('Use NOVA over HTTPS.'); }
    res.writeHead(200, { 'Content-Type': 'application/x-x509-ca-cert', 'Content-Disposition': 'attachment; filename="nova-ca.crt"' });
    res.end(await readFile(join(root, '.local/ca.crt')));
  }).listen(port + 1, host);
}
const janitor = setInterval(() => {
  const now = Date.now();
  conversations.prune(now);
  for (const [key, value] of audio) if (value.expires < now) audio.delete(key);
  for (const [key, until] of sessions) if (until < now) sessions.delete(key);
  for (const [key, value] of attempts) if (value.until < now) attempts.delete(key);
}, 60000).unref();
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => {
  clearInterval(janitor); server.close(); certificateServer?.close();
});
