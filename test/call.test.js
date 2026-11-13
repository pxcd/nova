import test from 'node:test';
import assert from 'node:assert/strict';
import { SpeechGate } from '../public/speech-gate.js';
import { ConversationCall } from '../public/conversation-call.js';
const tick = () => new Promise(resolve => setImmediate(resolve));
const frame = level => new Float32Array(960).fill(level);

test('idle speech detection stays bounded; short clicks do not trigger turns', () => {
 const gate = new SpeechGate(48000);
 for (let i=0;i<90000;i++) assert.equal(gate.push(frame(i%500===0?.08:0)),null);
 assert.ok(gate.preSamples<=48000*.32); assert.equal(gate.chunks.length,0);
});
test('speech ends after a pause, with preroll; no silence-only turn', () => {
 const gate=new SpeechGate(48000);
 for(let i=0;i<100;i++)assert.equal(gate.push(frame(0)),null);
 for(let i=0;i<40;i++)assert.equal(gate.push(frame(.08)),null);
 let result;for(let i=0;i<55&&!result;i++)result=gate.push(frame(0));
 assert.ok(result);assert.ok(result.reduce((s,c)=>s+c.length,0)<48000*3);
});
test('continuous sound is capped below the 45-second server limit', () => {
 const gate=new SpeechGate(48000);let result;
 for(let i=0;i<2200&&!result;i++)result=gate.push(frame(.08));
 assert.ok(result);assert.ok(result.reduce((s,c)=>s+c.length,0)<48000*42);
});
function setup(onTurn=async()=>{}) {
 const states=[];const errors=[];
 const recorder={starts:0,stops:0,async start({onChunk}){this.chunk=onChunk;this.starts++;},cleanup(){this.chunk=null;this.stops++;}};
 const call=new ConversationCall(recorder,{onState:s=>states.push(s),onTurn,onError:e=>errors.push(e),onStop(){}});
 return {call,recorder,states,errors};
}
function speech(recorder){for(let i=0;i<40;i++)recorder.chunk?.(frame(.08),48000);for(let i=0;i<55;i++)recorder.chunk?.(frame(0),48000);}
test('microphone closes during processing/TTS, then listening resumes',async()=>{
 let finish;const pending=new Promise(r=>finish=r);const {call,recorder,errors}=setup(async pcm=>{assert.ok(pcm.byteLength>3200);await pending;});
 await call.start();speech(recorder);assert.equal(call.processing,true);assert.equal(recorder.chunk,null);
 finish();await tick();assert.equal(recorder.starts,2);assert.equal(call.processing,false);assert.deepEqual(errors,[]);call.stop();
});
test('ending during a reply prevents automatic microphone restart',async()=>{
 let finish;const {call,recorder}=setup(()=>new Promise(r=>finish=r));await call.start();speech(recorder);call.stop();finish();await tick();assert.equal(recorder.starts,1);assert.equal(recorder.chunk,null);
});
test('end/mute while mic permission is pending releases the eventual stream',async()=>{
 const {call,recorder,states}=setup();let permit;recorder.start=({onChunk})=>new Promise(r=>{permit=()=>{recorder.chunk=onChunk;r();};});
 const started=call.start();call.stop();permit();await started;assert.equal(recorder.chunk,null);assert.equal(call.active,false);assert.equal(call.pending,false);assert.equal(states.at(-1),'idle');
});
test('microphone failure ends the call and reports the error',async()=>{
 const {call,recorder,errors}=setup();recorder.start=async()=>{throw Error('denied');};await call.start();assert.equal(call.active,false);assert.equal(errors.length,1);
});
