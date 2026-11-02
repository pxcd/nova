import http from 'node:http';
import { Readable } from 'node:stream';
import { normalizeFmRequest } from '../fm-schema.js';

const host = process.env.FM_BRIDGE_HOST || '127.0.0.1';
const port = Number(process.env.FM_BRIDGE_PORT || 1977);
const upstream = new URL(process.env.FM_UPSTREAM || 'http://127.0.0.1:1976');
if (!['http:', 'https:'].includes(upstream.protocol)) throw new Error('FM_UPSTREAM must be an HTTP(S) URL.');
const routes = new Set(['GET /health', 'GET /v1/models', 'POST /v1/chat/completions']);
const server = http.createServer(async (req, res) => {
  res.setHeader('Cache-Control', 'no-store');
  if (!routes.has(`${req.method} ${req.url}`)) { res.writeHead(404); res.end(); return; }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 90000);
  res.on('close', () => { if (!res.writableEnded) controller.abort(); });
  try {
    let body;
    if (req.method === 'POST') {
      const chunks = []; let bytes = 0;
      for await (const chunk of req) {
        bytes += chunk.length;
        if (bytes > 1024 * 1024) throw new RangeError('Request exceeds 1 MiB.');
        chunks.push(chunk);
      }
      body = JSON.stringify(normalizeFmRequest(JSON.parse(Buffer.concat(chunks).toString())));
    }
    const response = await fetch(new URL(req.url, upstream), {
      method: req.method, headers: { 'Content-Type': 'application/json' }, body,
      signal: controller.signal, redirect: 'error'
    });
    res.writeHead(response.status, { 'Content-Type': response.headers.get('content-type') || 'application/json' });
    if (response.body) {
      await new Promise((resolve, reject) => {
        const stream = Readable.fromWeb(response.body);
        stream.on('error', reject); res.on('finish', resolve);
        res.on('close', resolve); stream.pipe(res);
      });
    } else res.end();
  } catch (error) {
    if (!res.headersSent) {
      res.writeHead(error instanceof RangeError ? 413 : error instanceof TypeError || error instanceof SyntaxError ? 400 : 502,
        { 'Content-Type': 'application/json' });
      const message = error instanceof TypeError || error instanceof SyntaxError || error instanceof RangeError
        ? error.message : 'Apple FM upstream request failed.';
      res.end(JSON.stringify({ error: { type: 'fm_compatibility_error', message } }));
    } else res.destroy();
  } finally { clearTimeout(timer); }
});
server.requestTimeout = 120000;
server.headersTimeout = 15000;
server.listen(port, host, () => console.log(`Apple FM compatibility bridge listening on http://${host}:${port}`));
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => server.close(() => process.exit(0)));
