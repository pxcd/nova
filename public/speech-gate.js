// Local energy-based endpointing. This detects speech-like sound, not a wake word.
export class SpeechGate {
  constructor(rate) {
    this.rate = rate; this.elapsed = 0; this.voiced = 0; this.noise = .002;
    this.pre = []; this.preSamples = 0; this.chunks = []; this.active = false;
  }
  push(chunk) {
    const dt = chunk.length / this.rate;
    this.elapsed += dt;
    const rms = Math.sqrt(chunk.reduce((s, x) => s + x * x, 0) / chunk.length);
    const voice = rms > Math.max(.012, this.noise * 3.5);
    if (!voice && !this.active) this.noise += (rms - this.noise) * Math.min(1, dt * 2);
    if (!this.active) {
      this.pre.push(chunk); this.preSamples += chunk.length;
      while (this.pre.length > 1 && this.preSamples > this.rate * .3) this.preSamples -= this.pre.shift().length;
      this.voiced = voice ? this.voiced + dt : Math.max(0, this.voiced - dt * 2);
      if (this.voiced < .16) return null;
      this.active = true; this.started = this.elapsed;
      this.chunks = this.pre; this.pre = []; this.preSamples = 0;
    } else this.chunks.push(chunk);
    if (voice) this.lastVoice = this.elapsed;
    if (this.elapsed - this.lastVoice >= .95 || this.elapsed - this.started >= 40) {
      const result = this.chunks;
      this.chunks = []; this.active = false;
      return result;
    }
    return null;
  }
}
