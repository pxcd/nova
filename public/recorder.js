export function toPCM16(chunks, sourceRate, targetRate = 16000) {
  const length = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
  const input = new Float32Array(length);
  let offset = 0;
  for (const chunk of chunks) { input.set(chunk, offset); offset += chunk.length; }
  const count = Math.floor(length * targetRate / sourceRate);
  const output = new ArrayBuffer(count * 2);
  const view = new DataView(output);
  const ratio = sourceRate / targetRate;
  for (let i = 0; i < count; i++) {
    const start = Math.floor(i * ratio);
    const end = Math.min(input.length, Math.max(start + 1, Math.floor((i + 1) * ratio)));
    let value = 0;
    for (let j = start; j < end; j++) value += input[j];
    value = Math.max(-1, Math.min(1, value / (end - start)));
    view.setInt16(i * 2, Math.round(value * (value < 0 ? 32768 : 32767)), true);
  }
  return output;
}

export class Recorder {
  setAudioSession(type) {
    // Safari can retain recording volume/routing after the microphone stops.
    try { if (globalThis.navigator?.audioSession) navigator.audioSession.type = type; } catch { /* Optional browser API. */ }
  }
  async prepare() {
    if (!globalThis.isSecureContext || !navigator.mediaDevices?.getUserMedia) throw new Error('Microphone access needs HTTPS. Open the secure NOVA address and trust its local certificate.');
    const stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
    stream.getTracks().forEach(track => track.stop());
    await this.unlock();
  }
  async unlock() {
    this.context ||= new AudioContext();
    await this.context.resume();
  }
  async start({ onChunk } = {}) {
    this.setAudioSession('play-and-record');
    await this.unlock();
    this.stopPlayback();
    this.chunks = [];
    this.stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
    try {
      if (!this.workletLoaded) { await this.context.audioWorklet.addModule('/pcm-worklet.js'); this.workletLoaded = true; }
      this.source = this.context.createMediaStreamSource(this.stream);
      this.worklet = new AudioWorkletNode(this.context, 'nova-capture');
      this.worklet.port.onmessage = e => onChunk ? onChunk(e.data, this.context.sampleRate) : this.chunks.push(e.data);
      this.mute = this.context.createGain(); this.mute.gain.value = 0;
      this.source.connect(this.worklet).connect(this.mute).connect(this.context.destination);
    } catch (error) { this.cleanup(); throw error; }
  }
  cleanup() {
    this.source?.disconnect(); this.worklet?.disconnect(); this.mute?.disconnect();
    if (this.worklet) this.worklet.port.onmessage = null;
    this.stream?.getTracks().forEach(track => track.stop());
    this.source = this.worklet = this.mute = this.stream = null;
  }
  stop() {
    this.cleanup();
    return toPCM16(this.chunks || [], this.context.sampleRate);
  }
  stopPlayback() {
    this.playVersion = (this.playVersion || 0) + 1;
    if (this.playing) { this.playing.onended = null; this.playing.stop(); this.playing.disconnect(); this.playing = null; }
  }
  playbackLevel() {
    if (!this.playing || !this.analyser || this.context.state !== 'running') return 0;
    this.analyser.getFloatTimeDomainData(this.samples);
    return Math.sqrt(this.samples.reduce((sum, n) => sum + n * n, 0) / this.samples.length);
  }
  playbackSpectrum() {
    if (!this.playing || !this.analyser) return { low: .5, high: .5 };
    this.frequencies ||= new Uint8Array(this.analyser.frequencyBinCount);
    this.analyser.getByteFrequencyData(this.frequencies);
    let low = 0, high = 0;
    for (let i = 1; i < this.frequencies.length; i++) {
      const hz = i * this.context.sampleRate / this.analyser.fftSize;
      if (hz < 800) low += this.frequencies[i];
      else if (hz < 3500) high += this.frequencies[i];
    }
    const total = low + high || 1;
    return { low: low / total, high: high / total };
  }
  playbackTime() { return this.playing ? Math.max(0, this.context.currentTime - this.playStarted) : null; }
  async play(bytes, onEnded) {
    this.stopPlayback();
    this.setAudioSession('playback');
    const version = this.playVersion;
    await this.unlock();
    const buffer = await this.context.decodeAudioData(bytes.slice(0));
    if (version !== this.playVersion) return;
    if (!this.analyser) {
      this.analyser = this.context.createAnalyser(); this.analyser.fftSize = 1024;
      this.samples = new Float32Array(this.analyser.fftSize);
      this.analyser.connect(this.context.destination);
    }
    this.playing = this.context.createBufferSource(); this.playing.buffer = buffer;
    this.playing.connect(this.analyser);
    this.playing.onended = () => { this.playing.disconnect(); this.playing = null; onEnded(); };
    this.playStarted = this.context.currentTime;
    this.playing.start(this.playStarted);
  }
}
