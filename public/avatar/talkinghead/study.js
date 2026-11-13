import { TextureLoader, SRGBColorSpace } from 'three';
import { TalkingHead } from '@met4citizen/talkinghead';
const selectedModel = new URLSearchParams(location.search).get('model');
const realistic = selectedModel === 'realistic';
const likeness = selectedModel === 'nova' || realistic;
const $ = id => document.getElementById(id);
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
$('motion').checked = !reducedMotion;
let head, clip, active = false, version = 0;
const status = text => { $('status').textContent = text; };
function stop() {
  version++; active = false; head?.stopSpeaking();
  $('speak').disabled = !clip; $('stop').disabled = true;
  if (clip) status('Ready · local voice, timed mouth shapes');
}
function motion() {
  const enabled = $('motion').checked;
  head.opt.modelMovementFactor = enabled ? .18 : 0;
  head.opt.avatarIdleHeadMove = enabled ? .12 : 0;
  head.opt.avatarSpeakingHeadMove = enabled ? .16 : 0;
  // Keep breathing, eye contact and blinks; replace broad pose changes with small sway.
  head.animQueue = head.animQueue.filter(a => a.template.name !== 'pose');
  head.animMoods.neutral.anims = head.animMoods.neutral.anims.filter(a => !['pose', 'head'].includes(a.name));
  head.animMoods.neutral.anims.push({ name: 'head', dt: [[2600, 5200]], vs: {
    bodyRotateX: enabled ? [[-.012, .018]] : [0],
    bodyRotateY: enabled ? [[-.025, .025]] : [0],
    bodyRotateZ: enabled ? [[-.012, .012]] : [0]
  } });
  head.setMood('neutral');
}
try {
  head = new TalkingHead($('stage'), {
    lipsyncModules: [], cameraView: likeness ? 'head' : 'upper', cameraDistance: likeness ? .15 : -.15,
    cameraRotateEnable: false, cameraPanEnable: false, cameraZoomEnable: false,
    modelFPS: 30, modelPixelRatio: Math.min(devicePixelRatio, 1.5),
    modelMovementFactor: .18, avatarIdleHeadMove: .12, avatarSpeakingHeadMove: .16,
    avatarIdleEyeContact: .8, avatarSpeakingEyeContact: .9,
    lightAmbientIntensity: likeness ? 1 : 2, lightDirectIntensity: realistic ? 2 : likeness ? 4 : 12,
    mixerGainSpeech: 1
  });
  await head.showAvatar({ url: realistic ? '/avatar/talkinghead/nova-realistic-study.glb' : likeness ? '/avatar/talkinghead/nova-rig-study.glb' : '/avatar/talkinghead/reference.glb', body: 'F', avatarMood: 'neutral' });
  if (likeness) {
    document.querySelector('.eyebrow').textContent = realistic ? 'NOVA · ANATOMICAL HEAD STUDY' : 'NOVA LIKENESS · FITTED RIG STUDY';
    document.querySelector('h1').textContent = realistic ? 'A human base. The same voice.' : 'NOVA, on the speech rig.';
    document.title = 'NOVA · fitted facial rig';
    $('stage').setAttribute('aria-label', 'NOVA fitted facial rig prototype');
    if (realistic) document.querySelectorAll('details p')[2].firstChild.textContent = 'Experimental NOVA fit on the CC0 MakeHuman reference and bob01 hair. TalkingHead mouth scheduling is unchanged. ';
    else document.querySelectorAll('details p')[2].firstChild.textContent = 'Experimental NOVA likeness on the reference rig. Reference body and noncommercial license retained. Avatar: Ready Player Me / TalkingHead, CC BY-NC 4.0. '; 
    const portrait = await new TextureLoader().loadAsync('/avatar/assets/nova-call-neutral-v2.png');
    portrait.flipY = false; portrait.colorSpace = SRGBColorSpace;
    head.armature.traverse(object => {
      if (!object.isMesh || !object.geometry.attributes._nova_face_uv) return;
      object.material = object.material.clone();
      if (realistic) { object.material.normalMap = null; object.material.aoMap = null; }
      object.material.onBeforeCompile = shader => {
        shader.uniforms.novaPortrait = { value: portrait };
        shader.vertexShader = 'attribute vec2 _nova_face_uv; attribute float _nova_face_mask; varying vec2 novaUV; varying float novaMask;\n' + shader.vertexShader;
        shader.vertexShader = shader.vertexShader.replace('#include <uv_vertex>', '#include <uv_vertex>\nnovaUV = _nova_face_uv; novaMask = _nova_face_mask;');
        shader.fragmentShader = 'uniform sampler2D novaPortrait; varying vec2 novaUV; varying float novaMask;\n' + shader.fragmentShader;
        shader.fragmentShader = shader.fragmentShader.replace('#include <map_fragment>', '#include <map_fragment>\ndiffuseColor.rgb = mix(diffuseColor.rgb, texture2D(novaPortrait, novaUV).rgb, clamp(novaMask, 0.0, 1.0));');
      };
      if (realistic) {
        const faceShader = object.material.onBeforeCompile;
        object.material.onBeforeCompile = shader => {
          faceShader(shader);
          shader.fragmentShader = shader.fragmentShader.replace('texture2D(novaPortrait, novaUV).rgb', 'texture2D(novaPortrait, novaUV).rgb * 0.72');
          shader.vertexShader = 'attribute float _nova_scalp_mask; varying float novaScalp;\n' + shader.vertexShader;
          shader.vertexShader = shader.vertexShader.replace('novaUV = _nova_face_uv;', 'novaScalp = _nova_scalp_mask; novaUV = _nova_face_uv;');
          shader.fragmentShader = 'varying float novaScalp;\n' + shader.fragmentShader;
          shader.fragmentShader = shader.fragmentShader.replace('#include <color_fragment>', '#include <color_fragment>\ndiffuseColor.rgb = mix(diffuseColor.rgb, vec3(0.035, 0.018, 0.009), novaScalp);');
        };
      }
      object.material.customProgramCacheKey = () => realistic ? 'nova-anatomical-projection-v1' : 'nova-portrait-projection-v1';
      object.material.needsUpdate = true;
    });
    const note = document.querySelector('details p');
    note.textContent = realistic ? 'Anatomical MakeHuman head with separate teeth/tongue meshes and a full 3D bob. The same TalkingHead driver, speech timing, and subtle movement; NOVA portrait fit. Reference clothing retained. No live NOVA changes.' : 'Experimental NOVA landmark fit on the working facial rig. Real teeth and authored speech shapes; portrait-projected skin and curved hair. Reference body retained. No live NOVA changes.';
  }
  motion();
  const response = await fetch('/avatar/talkinghead/sample.json');
  if (!response.ok) throw Error('Voice sample could not load.');
  clip = await response.json();
  $('transcript').textContent = clip.text;
  $('speak').disabled = false; status('Ready · local voice, timed mouth shapes');
  $('stage').dataset.ready = 'true';
} catch (error) { status('Preview unavailable: ' + error.message); console.error(error); }
$('motion').addEventListener('change', () => { if (head) motion(); });
$('stop').addEventListener('click', stop);
$('speak').addEventListener('click', async () => {
  stop(); const current = version; active = true;
  $('speak').disabled = true; $('stop').disabled = false;
  status('Preparing voice…');
  try {
    try { if (navigator.audioSession) navigator.audioSession.type = 'playback'; } catch { /* Optional Safari API. */ }
    await head.audioCtx.resume();
    const response = await fetch('/avatar/talkinghead/sample.mp3');
    if (!response.ok) throw Error('Voice sample could not load.');
    const audio = await head.audioCtx.decodeAudioData(await response.arrayBuffer());
    if (current !== version || !active) return;
    head.speakAudio({ audio, words: [], visemes: clip.visemes, vtimes: clip.vtimes, vdurations: clip.vdurations }, { isRaw: true });
    status('Speaking · watch the lips, teeth and jaw');
    head.speakMarker(() => { if (current === version) stop(); });
  } catch (error) { if (current === version) { stop(); status(error.message); } }
});
document.addEventListener('visibilitychange', () => {
  if (document.hidden) { stop(); head?.stop(); } else head?.start();
});
window.addEventListener('pagehide', () => { stop(); head?.dispose(); });
