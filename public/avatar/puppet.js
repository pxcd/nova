// A small sprite puppet. Patch coordinates refer to the approved 1280px artwork.
// This is deliberately a frontal rig: rotation never invents hidden face geometry.
export class NovaPuppet {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.tilt = 0;
    this.preview = false;
    this.nextBlink = 0;
    this.blinkUntil = 0;
    this.running = false;
    this.state = 'idle';
    this.levelSource = null;
    this.reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
  }

  async load() {
    const load = async name => {
      const image = new Image();
      image.src = new URL(`./assets/nova-${name}-v1.png`, import.meta.url).href;
      await image.decode();
      return image;
    };
    const [base, blink, speaking] = await Promise.all(['neutral', 'blink', 'speaking'].map(load));
    this.base = base;
    this.eyes = this.patch(blink, 625, 706, 292, 84);
    this.mouth = this.patch(speaking, 640, 1035, 124, 92);
    this.running = true;
    this.nextBlink = performance.now() + 2300;
    this.frame = requestAnimationFrame(t => this.draw(t));
  }

  patch(image, x, y, rx, ry) {
    const layer = document.createElement('canvas');
    layer.width = layer.height = 1280;
    const ctx = layer.getContext('2d');
    ctx.drawImage(image, 0, 0, 1280, 1280);
    ctx.globalCompositeOperation = 'destination-in';
    ctx.save(); ctx.translate(x, y); ctx.scale(rx, ry);
    const fade = ctx.createRadialGradient(0, 0, .72, 0, 0, 1);
    fade.addColorStop(0, '#fff'); fade.addColorStop(1, '#fff0');
    ctx.fillStyle = fade; ctx.fillRect(-1, -1, 2, 2); ctx.restore();
    // destination-in only affects the painted area; clear everything outside it.
    ctx.clearRect(0, 0, 1280, y - ry);
    ctx.clearRect(0, y + ry, 1280, 1280);
    ctx.clearRect(0, y - ry, x - rx, ry * 2);
    ctx.clearRect(x + rx, y - ry, 1280, ry * 2);
    return layer;
  }

  blink() { this.blinkUntil = performance.now() + 145; }

  setState(state) { this.state = state; if (state !== 'speaking') this.lastSound = -1000; }

  async connectAudio(audio) {
    if (!this.audioContext) {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      this.audioContext = new AudioContext();
      this.source = this.audioContext.createMediaElementSource(audio);
      this.analyser = this.audioContext.createAnalyser();
      this.analyser.fftSize = 1024;
      this.source.connect(this.analyser);
      this.analyser.connect(this.audioContext.destination);
      this.samples = new Float32Array(this.analyser.fftSize);
      this.audio = audio;
    }
    await this.audioContext.resume();
  }

  draw(t) {
    if (!this.running) return;
    const c = this.ctx;
    c.clearRect(0, 0, 1280, 1280);
    if (t > this.nextBlink) {
      this.blink(); this.nextBlink = t + 2800 + Math.random() * 3200;
    }
    let talking = false;
    if (this.levelSource) {
      if (this.state === 'speaking' && this.levelSource() > .018) this.lastSound = t;
      talking = this.state === 'speaking' && t - (this.lastSound ?? -1000) < 85;
    } else if (this.analyser && !this.audio.paused && !this.audio.ended) {
      this.analyser.getFloatTimeDomainData(this.samples);
      const rms = Math.sqrt(this.samples.reduce((sum, n) => sum + n * n, 0) / this.samples.length);
      if (rms > .018) this.lastSound = t;
      talking = t - (this.lastSound ?? -1000) < 85;
    } else if (this.preview) {
      talking = Math.sin(t / 115) + Math.sin(t / 49) > .15;
    }
    const thinking = ['thinking', 'transcribing', 'voicing'].includes(this.state);
    const sway = this.reducedMotion ? 0 : Math.sin(t / 2400) * .55 + (thinking ? -2 : 0);
    c.save(); c.translate(640, 700);
    c.rotate((Number(this.tilt) + sway) * Math.PI / 180);
    const breath = this.reducedMotion ? 1 : 1 + Math.sin(t / 1500) * .003;
    const attentive = !this.reducedMotion && this.state === 'recording' ? 1.015 : 1;
    c.scale(breath * attentive, breath * attentive); c.translate(-640, -700);
    c.drawImage(this.base, 0, 0, 1280, 1280);
    if (t < this.blinkUntil) c.drawImage(this.eyes, 0, 0);
    if (talking) c.drawImage(this.mouth, 0, 0);
    c.restore();
    this.frame = requestAnimationFrame(next => this.draw(next));
  }

  destroy() {
    this.running = false; cancelAnimationFrame(this.frame);
    this.source?.disconnect(); this.analyser?.disconnect();
    return this.audioContext?.close();
  }
}
