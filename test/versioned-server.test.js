import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { once } from 'node:events';
import { handler } from '../versioned-server.js';
async function start(listener) { const server=http.createServer(listener);server.listen(0,'127.0.0.1');await once(server,'listening');return {server,url:`http://127.0.0.1:${server.address().port}`}; }
async function close(server) { server.closeAllConnections();await new Promise(resolve=>server.close(resolve)); }
test('v2 home-screen installation stays inside v2',async()=>{
 const proxy=await start(handler({upstream:'http://127.0.0.1:1',secure:false}));
 try {
  const response=await fetch(proxy.url+'/v2/manifest.webmanifest');
  assert.equal(response.status,200);assert.match(response.headers.get('content-type'),/application\/manifest\+json/);
  const manifest=await response.json();assert.equal(manifest.start_url,'/v2/');assert.equal(manifest.scope,'/v2/');
 } finally {await close(proxy.server);}
});
test('version proxy preserves v1 and isolates v2 session cookies and origins',async()=>{
 const seen=[];const upstream=await start((req,res)=>{seen.push({path:req.url,cookie:req.headers.cookie,origin:req.headers.origin});res.setHeader('Set-Cookie','nova_session=generated; HttpOnly; SameSite=Strict; Path=/; Max-Age=60; Secure');res.end(req.url);});
 const proxy=await start(handler({upstream:upstream.url,secure:false}));
 try {
  let r=await fetch(proxy.url+'/v1',{headers:{Cookie:'nova_session=old'}});assert.equal(await r.text(),'/');assert.equal(seen.at(-1).cookie,'nova_session=old');assert.match(r.headers.get('set-cookie'),/^nova_session=/);
  r=await fetch(proxy.url+'/v2/api/login',{method:'POST',headers:{Origin:proxy.url,Cookie:'nova_session=old; nova_v2_session=new','Content-Type':'application/json'},body:'{}'});
  assert.equal(await r.text(),'/api/login');assert.equal(seen.at(-1).cookie,'nova_session=new');assert.equal(seen.at(-1).origin,upstream.url);assert.match(r.headers.get('set-cookie'),/^nova_v2_session=/);assert.match(r.headers.get('set-cookie'),/Path=\/v2;/);assert.match(r.headers.get('set-cookie'),/Secure/);
  await fetch(proxy.url+'/v2/api/session',{headers:{Cookie:'nova_session=old'}});assert.equal(seen.at(-1).cookie,'');
  await fetch(proxy.url+'/api/session',{headers:{Cookie:'nova_session=old; nova_v2_session=new'}});assert.match(seen.at(-1).cookie,/nova_session=old/);
 } finally {await close(proxy.server);await close(upstream.server);}
});
test('unknown v2 paths do not reach the backend; protocol-relative paths stay pinned to the configured upstream',async()=>{
 const seen=[];const upstream=await start((req,res)=>{seen.push(req.url);res.end('ok');});const proxy=await start(handler({upstream:upstream.url,secure:false}));
 try {
  assert.equal((await fetch(proxy.url+'/v2/not-a-route')).status,404);assert.equal(seen.length,0);
  await fetch(proxy.url+'/v1//example.invalid/nope');assert.equal(seen.at(-1),'//example.invalid/nope');
  assert.equal((await fetch(proxy.url+'/v2/api/login',{method:'POST',body:'{}'})).status,403);
  assert.equal((await fetch(proxy.url+'/v2/api/login',{method:'POST',headers:{Origin:'https://elsewhere.invalid'},body:'{}'})).status,403);
 } finally {await close(proxy.server);await close(upstream.server);}
});
test('API responses stream through without waiting for the full reply',async()=>{
 let release;const tail=new Promise(resolve=>release=resolve);const upstream=await start(async(req,res)=>{res.writeHead(200,{'Content-Type':'text/event-stream'});res.write('event: stage\ndata: {}\n\n');await tail;res.end('event: done\ndata: {}\n\n');});const proxy=await start(handler({upstream:upstream.url,secure:false}));
 try {
  const r=await fetch(proxy.url+'/v2/api/run');const reader=r.body.getReader();const first=await reader.read();assert.match(new TextDecoder().decode(first.value),/event: stage/);release();let rest='';for(;;){const c=await reader.read();if(c.done)break;rest+=new TextDecoder().decode(c.value);}assert.match(rest,/event: done/);
 } finally {release();await close(proxy.server);await close(upstream.server);}
});
