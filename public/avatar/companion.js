import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';
import { poseAt } from '../visemes.js';

export class Companion {
  constructor(canvas) {
    this.canvas = canvas; this.state = 'idle'; this.levelSource = () => 0;
    this.spectrumSource = () => ({ low: .5, high: .5 });
    this.reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
    this.look = new THREE.Vector3(); this.lookGoal = new THREE.Vector3();
    this.mouth = 0; this.elapsed = 0; this.loadVersion = 0; this.nextBlink = 2.8;
  }
  async load(modelUrl = new URL('./models/motion-sample.vrm', import.meta.url).href) {
    this.renderer = new THREE.WebGLRenderer({ canvas: this.canvas, antialias: true, alpha: true });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.scene = new THREE.Scene();
    this.scene.add(new THREE.HemisphereLight(0xf2f0ff, 0x67778a, 2));
    const key = new THREE.DirectionalLight(0xffeee0, 2.4); key.position.set(-1, 2, 3); this.scene.add(key);
    this.camera = new THREE.PerspectiveCamera(28, 1, .05, 20);
    this.target = new THREE.Object3D(); this.scene.add(this.target);
    this.observer = new ResizeObserver(() => this.resize()); this.observer.observe(this.canvas);
    await this.loadModel(modelUrl);
    this.running = true; this.lastFrame = performance.now();
    this.frame = requestAnimationFrame(t => this.draw(t));
  }
  async loadModel(url) {
    const version = ++this.loadVersion;
    const loader = new GLTFLoader(); loader.register(parser => new VRMLoaderPlugin(parser));
    const gltf = await loader.loadAsync(url);
    const vrm = gltf.userData.vrm;
    if (!vrm?.humanoid?.getNormalizedBoneNode('head') || !vrm.expressionManager) {
      VRMUtils.deepDispose(gltf.scene); throw new Error('Choose a rigged VRM avatar with a head and facial expressions.');
    }
    if (version !== this.loadVersion) { VRMUtils.deepDispose(vrm.scene); return; }
    if (this.vrm) { this.scene.remove(this.vrm.scene); VRMUtils.deepDispose(this.vrm.scene); }
    this.vrm = vrm; VRMUtils.rotateVRM0(vrm); this.scene.add(vrm.scene);
    const bone = name => vrm.humanoid.getNormalizedBoneNode(name);
    this.bones = Object.fromEntries(['head', 'neck', 'chest', 'spine', 'leftUpperArm', 'rightUpperArm'].map(name => [name, bone(name)]));
    if (this.bones.leftUpperArm) this.bones.leftUpperArm.rotation.z = -1.2;
    if (this.bones.rightUpperArm) this.bones.rightUpperArm.rotation.z = 1.2;
    vrm.update(0); vrm.scene.updateMatrixWorld(true);
    const head = bone('head').getWorldPosition(new THREE.Vector3());
    const chest = (bone('chest') || bone('spine')).getWorldPosition(new THREE.Vector3());
    const height = Math.max(.4, (head.y - chest.y) * 2);
    const framing = gltf.parser.json.extras?.novaPortrait;
    this.voiceGain = Number.isFinite(framing?.voiceGain) ? THREE.MathUtils.clamp(framing.voiceGain, 2, 16) : 12;
    this.voiceRange = Number.isFinite(framing?.voiceRange) ? THREE.MathUtils.clamp(framing.voiceRange, .2, 1) : 1;
    this.center = head.clone(); this.center.y += Number.isFinite(framing?.centerOffsetY) ? THREE.MathUtils.clamp(framing.centerOffsetY, 0, .2) : .05;
    this.distance = Number.isFinite(framing?.cameraDistance) ? THREE.MathUtils.clamp(framing.cameraDistance, .6, 1.2) : height * 2.0;
    this.gazeOrigin = head.clone(); this.look.set(0, 0, 0); this.lookGoal.set(0, 0, 0);
    if (vrm.lookAt) vrm.lookAt.target = this.target;
    this.resize();
  }
  resize() {
    if (!this.renderer || !this.center) return;
    const { width, height } = this.canvas.getBoundingClientRect();
    if (!width || !height) return;
    this.renderer.setSize(width, height, false);
    this.camera.aspect = width / height;
    // Preserve the whole head in narrow portrait screens and show shoulders in landscape.
    const distance = this.distance * Math.max(1, .72 / this.camera.aspect);
    this.camera.position.set(0, this.center.y, distance);
    this.camera.lookAt(this.center); this.camera.updateProjectionMatrix();
  }
  setState(state) { this.state = state; }
  draw(t) {
    if (!this.running) return;
    this.frame = requestAnimationFrame(next => this.draw(next));
    if (document.hidden || t - this.lastFrame < 1000 / 30) return;
    const dt = Math.min(.05, (t - this.lastFrame) / 1000); this.lastFrame = t; this.elapsed += dt;
    const time = this.elapsed;
    const speaking = this.state === 'speaking';
    const listening = ['listening', 'recording'].includes(this.state);
    const thinking = ['thinking', 'transcribing', 'voicing'].includes(this.state);
    const energy = speaking ? Math.min(this.voiceRange, this.levelSource() * this.voiceGain) : 0;
    this.mouth = THREE.MathUtils.damp(this.mouth, energy < .08 ? 0 : energy, energy > this.mouth ? 28 : 14, dt);
    if (time > (this.nextLook || 0)) {
      this.lookGoal.set((Math.random() - .5) * (listening ? .05 : .2), (Math.random() - .5) * .07, 0);
      this.nextLook = time + 3 + Math.random() * 5;
    }
    this.look.lerp(this.lookGoal, 1 - Math.exp(-dt * 2));
    this.target.position.copy(this.gazeOrigin).add(new THREE.Vector3(this.look.x, this.look.y, 1.5));
    const move = this.reducedMotion ? 0 : 1;
    const yaw = (Math.sin(time * .41) * .035 + this.look.x * .2) * move;
    const nod = (Math.sin(time * .73) * .012 + (speaking ? Math.sin(time * 2.2) * this.mouth * .016 : 0) + (listening ? -.025 : 0)) * move;
    const tilt = (Math.sin(time * .29) * .025 + (thinking ? .045 : 0)) * move;
    for (const [name, factor] of [['head', .75], ['neck', .25]]) {
      const b = this.bones[name]; if (b) {
        b.rotation.x = THREE.MathUtils.damp(b.rotation.x, nod * factor, 3, dt);
        b.rotation.y = THREE.MathUtils.damp(b.rotation.y, yaw * factor, 3, dt);
        b.rotation.z = THREE.MathUtils.damp(b.rotation.z, tilt * factor, 3, dt);
      }
    }
    const chest = this.bones.chest || this.bones.spine;
    if (chest) { chest.rotation.x = Math.sin(time * 1.15) * .007 * move; chest.rotation.z = -tilt * .16; }
    if (time > (this.nextBlink || 0)) { this.blinkStart = time; this.nextBlink = time + 2.8 + Math.random() * 4; }
    const phase = (time - (this.blinkStart ?? -1)) / .21;
    const blink = phase >= 0 && phase <= 1 ? Math.sin(phase * Math.PI) : 0;
    const expression = this.vrm.expressionManager;
    expression.setValue('blink', blink);
    const { low, high } = this.spectrumSource();
    // Timed speech shapes take precedence; spectral shapes are the bounded fallback.
    const round = Math.min(.65, low * .65);
    const wide = Math.min(.65, high * .65);
    const timed = this.visemeSource?.();
    const pose = timed ? poseAt(timed.cues, timed.time) : null;
    expression.setValue('aa', pose ? pose[0] * this.voiceRange : this.mouth * (1 - round) * (1 - wide));
    expression.setValue('ih', pose ? pose[1] * this.voiceRange : this.mouth * wide);
    expression.setValue('ou', pose ? pose[2] * this.voiceRange : this.mouth * round);
    if (expression.getExpression('fv')) expression.setValue('fv', pose ? pose[3] * this.voiceRange : 0);
    this.canvas.dataset.lipSync = timed ? 'phonetic' : 'audio-reactive';
    expression.setValue('happy', speaking ? .1 : .04);
    this.vrm.update(dt);
    this.renderer.render(this.scene, this.camera);
    this.canvas.dataset.mouth = this.mouth.toFixed(2);
    this.canvas.dataset.state = this.state;
  }
  destroy() {
    this.running = false; this.loadVersion++; cancelAnimationFrame(this.frame);
    this.observer?.disconnect(); if (this.vrm) VRMUtils.deepDispose(this.vrm.scene);
    this.renderer?.dispose();
  }
}
