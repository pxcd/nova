import test from 'node:test';import assert from 'node:assert/strict';
import { readFile, access } from 'node:fs/promises';import { dirname } from 'node:path';
import { speechCues } from '../lipsync.js';
const wav=Buffer.from('RIFF0000WAVE');const output=JSON.stringify({metadata:{duration:1,soundFile:'/private/path'},mouthCues:[{start:0,end:.4,value:'D'},{start:.4,end:1,value:'X'}]});
test('alignment uses argument arrays, keeps dialogue literal, strips paths, and cleans private scratch files',async()=>{
 let folder;
 const r=await speechCues(wav,'literal $(echo nope)',undefined,{binary:'/tmp/rhubarb',run:async(bin,args,options)=>{
  assert.equal(bin,'/tmp/rhubarb');assert.equal(args[args.indexOf('-r')+1],'phonetic');assert.equal(options.timeout,3000);
  const path=args.at(-1);folder=dirname(path);assert.deepEqual(await readFile(path),wav);
  assert.equal(await readFile(args[args.indexOf('-d')+1],'utf8'),'literal $(echo nope)');
  return {stdout:output};
 }});
 assert.equal(r.cues[0].value,'D');assert.equal(r.duration,1);assert.equal(r.soundFile,undefined);
 await assert.rejects(access(folder));
});
test('analysis failures and cancellation clean up and propagate instead of fabricating cues',async()=>{
 let folder;
 await assert.rejects(speechCues(wav,'',undefined,{run:async(_,args)=>{folder=dirname(args.at(-1));throw Error('timeout');}}));
 await assert.rejects(access(folder));
 const controller=new AbortController();controller.abort();
 await assert.rejects(speechCues(wav,'',controller.signal));
 await assert.rejects(speechCues(Buffer.from('not audio'),'x'));
});
test('invalid recognizer output is rejected',async()=>{
 await assert.rejects(speechCues(wav,'',undefined,{run:async()=>({stdout:'{"metadata":{"duration":1},"mouthCues":[{"start":0,"end":2,"value":"D"}]}'})}));
});
test('MP3 speech is converted locally for timing without replacing the playback audio',async()=>{
 let calls=0;
 const result=await speechCues(Buffer.from('ID3synthetic'),'hello',undefined,{binary:'/tmp/rhubarb',run:async(bin,args)=>{
  calls++;
  if(calls===1){assert.equal(bin,process.env.NOVA_FFMPEG_BIN||'/opt/homebrew/bin/ffmpeg');assert.ok(args.includes('-nostdin'));assert.equal((await readFile(args[args.indexOf('-i')+1])).toString(),'ID3synthetic');return {stdout:''};}
  assert.equal(bin,'/tmp/rhubarb');return {stdout:output};
 }});
 assert.equal(calls,2);assert.equal(result.cues.length,2);
});
