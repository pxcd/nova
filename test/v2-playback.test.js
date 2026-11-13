import test from 'node:test';
import assert from 'node:assert/strict';
import { Companion } from '../public/v2/companion.js';
const frame = { duration:.5, sampleRate:10, getChannelData:()=>new Float32Array([0,.1,.2,.1,0]) };
function setup(decode=async()=>frame) {
 const calls=[];const avatar=new Companion({dataset:{}});
 avatar.head={audioCtx:{resume:async()=>{},decodeAudioData:decode},stopSpeaking(){calls.push('stop');},speakAudio(data,options){calls.push({data,options});},speakMarker(callback){this.end=callback;}};
 return {avatar,calls};
}
test('v2 uses the approved viseme names and timestamps with exactly one audio playback',async()=>{
 const {avatar,calls}=setup();let ended=0;
 await avatar.play(new ArrayBuffer(8),[{value:'A',start:0,end:.1},{value:'D',start:.1,end:.3},{value:'F',start:.3,end:.5}],()=>ended++);
 const speech=calls.filter(c=>typeof c==='object');assert.equal(speech.length,1);assert.equal(speech[0].data.audio,frame);assert.deepEqual(speech[0].data.visemes,['PP','aa','U']);assert.deepEqual(speech[0].data.vtimes,[0,100,300]);assert.equal(speech[0].options.isRaw,true);avatar.head.end();assert.equal(ended,1);
});
test('stop during decoding prevents late audio and a stopped marker cannot restart listening',async()=>{
 let finish;const {avatar,calls}=setup(()=>new Promise(resolve=>finish=resolve));let ended=0;
 const pending=avatar.play(new ArrayBuffer(8),[],()=>ended++);while(!finish)await new Promise(resolve=>setImmediate(resolve));avatar.stopPlayback();finish(frame);await pending;assert.equal(calls.filter(c=>typeof c==='object').length,0);
 const normal=setup();await normal.avatar.play(new ArrayBuffer(8),[],()=>ended++);normal.avatar.stopPlayback();normal.avatar.head.end();assert.equal(ended,0);
});
