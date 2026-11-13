import { Companion } from './companion.bundle.js';
const avatar=new Companion(document.querySelector('canvas'));
avatar.levelSource=()=>document.querySelector('#hold-mouth').checked ? Number(document.querySelector('#mouth-opening').value)/100/(avatar.voiceGain || 7) : Math.max(0,Math.sin(performance.now()/110)*.05+.035);
const likeness = new URLSearchParams(location.search).get('model') !== 'sample';
if (likeness) document.querySelector('aside p').textContent = 'NOVA likeness study · estimated near-frontal geometry';
try{await avatar.load(likeness ? new URL('./models/nova-likeness-study.vrm', import.meta.url).href : undefined);document.querySelector('#status').textContent='Rig loaded';}catch(e){document.querySelector('#status').textContent=e.message;}
document.querySelector('select').addEventListener('change',e=>avatar.setState(e.target.value));
