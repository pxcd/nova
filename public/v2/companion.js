import { fitLidAppearance } from './appearance.js';
import { TalkingHead } from '@met4citizen/talkinghead';

const shapes = { A: 'PP', B: 'SS', C: 'E', D: 'aa', E: 'O', F: 'U', G: 'FF', X: 'sil' };
export class Companion {
  constructor(node) { this.node = node; this.version = 0; this.state = 'idle'; }
  async load() {
    const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
    this.head = new TalkingHead(this.node, {
      lipsyncModules: [], cameraView: 'head', cameraDistance: .28, cameraY: .1,
      cameraRotateEnable: false, cameraPanEnable: false, cameraZoomEnable: false,
      modelFPS: 30, modelPixelRatio: Math.min(devicePixelRatio, 1.5),
      modelMovementFactor: reduced ? 0 : .18,
      avatarIdleHeadMove: reduced ? 0 : .12, avatarSpeakingHeadMove: reduced ? 0 : .16,
      avatarIdleEyeContact: .8, avatarSpeakingEyeContact: .9,
      lightAmbientIntensity: .55, lightDirectColor: 0xfff5eb, lightDirectIntensity: .75, mixerGainSpeech: 1
    });
    await this.head.showAvatar({ url: '/v2/assets/head.glb', body: 'F', avatarMood: 'neutral' });
    this.lidTexture = await fitLidAppearance(this.head);
    this.head.armature.traverse(object => {
      for (const material of [].concat(object.material || [])) {
        if (material.name === 'NOVA strand-edge hair') {
          material.alphaTest = .06; material.alphaToCoverage = true; material.depthWrite = true; material.toneMapped = false;
        }

        if (['NOVA cleaned photo albedo', 'NOVA photographic hair', 'NOVA photographic neck'].includes(material.name)) material.toneMapped = false;
      }
    });
    // The sample's idle cheek/mouth gestures exaggerate this anatomical rig.
    // Keep speech untouched; idle motion comes from gaze, blink and small sway.
    const pose = structuredClone(this.head.poseTemplates.straight);
    for (const bone of ['Hips', 'Spine', 'Spine1', 'Spine2', 'Neck', 'Head']) pose.props[`${bone}.rotation`] = { x: 0, y: 0, z: 0 };
    pose.props['Head.rotation'].x = .15;
    this.head.setPoseFromTemplate(pose, 0);
    this.head.mtRandomized = ['browOuterUpLeft', 'browOuterUpRight'];
    for (const [name, target] of Object.entries(this.head.mtAvatar)) {
      if (/^(eyeLook|eyesLook)/.test(name)) target.max = .12;
      if (/^headRotate/.test(name)) { target.min = -.035; target.max = .035; }
      if (/^browOuterUp/.test(name)) target.max = .08;
    }
    this.head.animQueue = this.head.animQueue.filter(a => ['breathing', 'blink'].includes(a.template.name));
    this.head.animMoods.neutral.baseline = {};
    this.head.animMoods.neutral.anims = this.head.animMoods.neutral.anims.filter(a => ['breathing', 'blink'].includes(a.name));
    this.head.animMoods.neutral.anims.push({ name: 'eyes', delay: [1800, 4200], dt: [350, 1200, 350], vs: { eyesRotateX: [0, [-.025, .025], 0], eyesRotateY: [0, [-.035, .035], 0] } });
    this.head.animMoods.neutral.anims.push({ name: 'head', dt: [[2600, 5200]], vs: {
      bodyRotateX: reduced ? [0] : [[-.012, .018]],
      bodyRotateY: reduced ? [0] : [[-.025, .025]],
      bodyRotateZ: reduced ? [0] : [[-.012, .012]]
    } });
    this.head.setMood('neutral'); this.node.dataset.ready = 'true';
  }
  get audioContext() { return this.head.audioCtx; }
  async unlock() { await this.head.audioCtx.resume(); }
  setState(state) { this.state = state; this.node.dataset.state = state; }
  stopPlayback() { this.version++; this.head?.stopSpeaking(); }
  async play(bytes, cues, onEnded) {
    this.stopPlayback(); const version = this.version;
    await this.unlock();
    const audio = await this.head.audioCtx.decodeAudioData(bytes.slice(0));
    if (version !== this.version) return;
    // Use exactly the approved TalkingHead speech scheduler and cue mapping.
    let visemes = cues;
    if (!visemes?.length) {
      const samples = audio.getChannelData(0); visemes = [];
      for (let start = 0; start < audio.duration; start += .1) {
        const from = Math.floor(start * audio.sampleRate), end = Math.min(samples.length, from + Math.floor(audio.sampleRate * .1));
        let energy = 0; for (let i = from; i < end; i++) energy += samples[i] ** 2;
        visemes.push({ start, end: Math.min(audio.duration, start + .1), value: Math.sqrt(energy / Math.max(1, end - from)) > .025 ? 'D' : 'X' });
      }
    }
    this.head.speakAudio({ audio, words: [], visemes: visemes.map(c => shapes[c.value]),
      vtimes: visemes.map(c => c.start * 1000), vdurations: visemes.map(c => (c.end - c.start) * 1000) }, { isRaw: true });
    this.head.speakMarker(() => { if (version === this.version) onEnded(); });
  }
  destroy() { this.stopPlayback(); this.lidTexture?.dispose(); this.head?.dispose(); }
}
