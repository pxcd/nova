import { SpeechGate } from './speech-gate.js';
import { toPCM16 } from './recorder.js';

export class ConversationCall {
  constructor(recorder, { onState, onTurn, onError, onStop }) {
    this.recorder = recorder;
    Object.assign(this, { onState, onTurn, onError, onStop });
    this.active = false; this.muted = false; this.pending = false;
    this.processing = false; this.version = 0;
  }
  async start() {
    if (this.active || this.pending) return;
    this.active = true; this.muted = false; this.version++;
    await this.listen();
  }
  stop() {
    this.active = false; this.version++; this.recorder.cleanup();
    this.onStop(); this.onState('idle');
  }
  async setMuted(muted) {
    this.muted = muted; this.version++; this.recorder.cleanup();
    if (muted && !this.processing) this.onState('muted');
    else if (!this.processing) await this.listen();
  }
  async listen() {
    if (!this.active || this.muted || this.pending || this.processing) return;
    const version = this.version;
    this.pending = true; this.onState('connecting');
    let gate;
    try {
      await this.recorder.start({ onChunk: (chunk, rate) => {
        if (!this.active || this.muted || this.processing || version !== this.version) return;
        gate ||= new SpeechGate(rate);
        const chunks = gate.push(chunk);
        if (chunks) this.turn(chunks, rate);
        else if (gate.active) this.onState('recording');
      } });
      if (version !== this.version || !this.active || this.muted) this.recorder.cleanup();
      else this.onState('listening');
    } catch (error) {
      if (version === this.version) { this.stop(); this.onError(error); }
    } finally {
      this.pending = false;
      if (!this.active) this.onState('idle');
      else if (this.muted && !this.processing) this.onState('muted');
      else if (version !== this.version && !this.muted) await this.listen();
    }
  }
  async turn(chunks, rate) {
    this.processing = true; this.recorder.cleanup();
    try { await this.onTurn(toPCM16(chunks, rate)); }
    catch (error) { this.onError(error); }
    finally {
      this.processing = false;
      if (this.active && !this.muted) await this.listen();
      else this.onState(this.active ? 'muted' : 'idle');
    }
  }
}
