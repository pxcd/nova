import test from 'node:test';
import assert from 'node:assert/strict';
import { validateCues, poseAt } from '../public/visemes.js';
const cues=[{start:0,end:.2,value:'A'},{start:.2,end:.5,value:'D'},{start:.5,end:.8,value:'F'},{start:.8,end:1,value:'X'}];
test('pronunciation shapes close for M/B/P, open for AH, round for OO, and rest after speech',()=>{
 const data=validateCues(cues,1);
 assert.deepEqual(poseAt(data,.1),[0,0,0,0]);
 assert.ok(poseAt(data,.3)[0]>.8);
 assert.ok(poseAt(data,.6)[2]>.8);
 assert.deepEqual(poseAt(data,.9),[0,0,0,0]);
 assert.deepEqual(poseAt(data,1.1),[0,0,0,0]);
 assert.deepEqual(poseAt(data,null),[0,0,0,0]);
});
test('transitions blend rather than snapping and gaps do not hold an old shape',()=>{
 const middle=poseAt(cues,.51);assert.ok(middle[0]>0 && middle[2]>0);
 assert.deepEqual(poseAt([{start:.2,end:.4,value:'D'}],.1),[0,0,0,0]);
});
test('malformed, overlapping and unbounded cues fail validation',()=>{
 for(const bad of [[{start:0,end:Infinity,value:'D'}],[{start:0,end:.1,value:'__proto__'}],[{start:.3,end:.2,value:'A'}],[...cues,{start:.1,end:1,value:'A'}],Array(5001).fill(cues[0])])assert.throws(()=>validateCues(bad,1));
});
