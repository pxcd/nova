import http from 'node:http';
import https from 'node:https';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { networkInterfaces } from 'node:os';

const project = dirname(fileURLToPath(import.meta.url));
const files = new Map([
  ['/v2', ['public/v2/index.html', 'text/html; charset=utf-8']],
  ['/v2/', ['public/v2/index.html', 'text/html; charset=utf-8']],
  ['/v2/app.js', ['public/v2/app.js', 'text/javascript; charset=utf-8']],
  ['/v2/style.css', ['public/v2/style.css', 'text/css; charset=utf-8']],
  ['/v2/manifest.webmanifest', ['public/v2/manifest.webmanifest', 'application/manifest+json']],
  ['/v2/companion.bundle.js', ['public/v2/companion.bundle.js', 'text/javascript; charset=utf-8']],
  ['/v2/assets/head.glb', ['.local/facebuilder/v2-current/head.glb', 'model/gltf-binary']],
  ['/v2/assets/closed-lids.png', ['.local/facebuilder/v2-current/closed-lids.png', 'image/png']]
]);
const hopHeaders = ['connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization', 'te', 'trailer', 'transfer-encoding', 'upgrade'];
function clean(headers) {
  const copy = { ...headers };
  for (const key of [...hopHeaders, ...(headers.connection || '').split(',').map(s => s.trim().toLowerCase())]) delete copy[key];
  return copy;
}
function v2Cookie(cookie = '') {
  const pairs = cookie.split(';').map(s => s.trim()).filter(Boolean);
  const own = pairs.find(s => s.startsWith('nova_v2_session='));
  return [...pairs.filter(s => !s.startsWith('nova_session=') && !s.startsWith('nova_v2_session=')), ...(own ? [own.replace(/^nova_v2_session=/, 'nova_session=')] : [])].join('; ');
}
export function handler({ upstream, ca, root = project, hosts = new Set(['127.0.0.1', 'localhost', '[::1]']), secure = true }) {
  const destination = new URL(upstream);
  return async (req, res) => {
    const origin = `${secure ? 'https' : 'http'}://${req.headers.host}`;
    let url;
    try { url = new URL(req.url, origin); } catch { res.writeHead(400); res.end(); return; }
    if (!hosts.has(url.hostname)) { res.writeHead(403); res.end('Host is not allowed.'); return; }
    if (!['GET', 'HEAD', 'OPTIONS'].includes(req.method) && req.headers.origin !== origin) { res.writeHead(403); res.end('Open NOVA directly.'); return; }
    const asset = files.get(url.pathname);
    if (asset && req.method === 'GET') {
      try {
        const bytes = await readFile(join(root, asset[0]));
        res.writeHead(200, { 'Content-Type': asset[1], 'Content-Length': bytes.length, 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
          'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self' blob:; img-src 'self' data: blob:; media-src 'self' blob:; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
          'Permissions-Policy': 'microphone=(self), camera=(), geolocation=()', 'Referrer-Policy': 'no-referrer' });
        res.end(bytes);
      } catch { res.writeHead(503); res.end('V2 asset is not ready.'); }
      return;
    }
    const isolated = url.pathname.startsWith('/v2/api/');
    let path = url.pathname + url.search;
    if (isolated) path = path.slice(3);
    else if (url.pathname === '/v1' || url.pathname === '/v1/') path = '/' + url.search;
    else if (url.pathname.startsWith('/v1/')) path = path.slice(3);
    else if (url.pathname.startsWith('/v2')) { res.writeHead(404); res.end(); return; }
    const headers = clean(req.headers);
    headers.host = destination.host;
    if (headers.origin) headers.origin = destination.origin;
    if (isolated) headers.cookie = v2Cookie(headers.cookie);
    const client = destination.protocol === 'https:' ? https : http;
    const proxied = client.request(destination, { path, method: req.method, headers, ca }, response => {
      const output = clean(response.headers);
      if (isolated && output['set-cookie']) output['set-cookie'] = output['set-cookie'].map(cookie => cookie.replace(/^nova_session=/, 'nova_v2_session=').replace(/Path=\//i, 'Path=/v2'));
      res.writeHead(response.statusCode, output); response.pipe(res);
    });
    proxied.on('error', () => { if (!res.headersSent) { res.writeHead(502); res.end('Current NOVA server is unavailable.'); } else res.destroy(); });
    req.on('aborted', () => proxied.destroy());
    res.on('close', () => { if (!res.writableEnded) proxied.destroy(); });
    req.pipe(proxied);
  };
}
async function main() {
  const plain = process.argv.includes('--http');
  const host = process.env.NOVA_V2_HOST || (plain ? '127.0.0.1' : '0.0.0.0');
  if (plain && !['127.0.0.1', 'localhost', '::1'].includes(host)) throw Error('HTTP preview is loopback-only.');
  const port = Number(process.env.NOVA_V2_PORT || (plain ? 8791 : 8790));
  const ca = await readFile(join(project, '.local/ca.crt'));
  const hosts = new Set(['localhost', '127.0.0.1', '[::1]', 'synapse.local', ...Object.values(networkInterfaces()).flat().filter(Boolean).map(n => n.address)]);
  const listener = handler({ upstream: process.env.NOVA_V1_UPSTREAM || 'https://10.0.0.150:8787', ca, hosts, secure: !plain });
  const server = plain ? http.createServer(listener) : https.createServer({ key: await readFile(join(project, '.local/server.key')), cert: await readFile(join(project, '.local/server.crt')) }, listener);
  server.requestTimeout = 120000; server.headersTimeout = 15000;
  server.listen(port, host, () => console.log(`Versioned NOVA on ${plain ? 'http' : 'https'}://${host}:${port}; existing server untouched`));
  for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => server.close());
}
if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) await main();
