export class HomeAssistant {
  constructor({ url, token, pipelineId, WebSocketClass = WebSocket }) {
    this.url = new URL(url);
    this.token = token;
    this.pipelineId = pipelineId;
    this.WebSocketClass = WebSocketClass;
  }

  async connect(signal) {
    if (!this.token) throw new Error('Set HA_TOKEN in the server .env file.');
    const url = new URL('/api/websocket', this.url);
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new this.WebSocketClass(url);
    try {
      await new Promise((resolve, reject) => {
        const timer = setTimeout(() => finish(new Error('Home Assistant connection timed out.')), 10000);
        const aborted = () => finish(new Error('Request cancelled.'));
        const error = () => finish(new Error('Cannot connect to Home Assistant.'));
        const message = event => {
          let data;
          try { data = JSON.parse(event.data); } catch { return; }
          if (data.type === 'auth_required') ws.send(JSON.stringify({ type: 'auth', access_token: this.token }));
          if (data.type === 'auth_ok') finish();
          if (data.type === 'auth_invalid') finish(new Error('Home Assistant rejected HA_TOKEN.'));
        };
        const finish = error => {
          clearTimeout(timer);
          ws.removeEventListener('message', message);
          ws.removeEventListener('error', errorHandler);
          ws.removeEventListener('close', errorHandler);
          signal?.removeEventListener('abort', aborted);
          error ? reject(error) : resolve();
        };
        const errorHandler = error;
        ws.addEventListener('message', message);
        ws.addEventListener('error', errorHandler);
        ws.addEventListener('close', errorHandler);
        signal?.addEventListener('abort', aborted, { once: true });
        if (signal?.aborted) aborted();
      });
      return ws;
    } catch (error) { ws.close(); throw error; }
  }

  async request(type, fields = {}, signal) {
    const ws = await this.connect(signal);
    try {
      return await new Promise((resolve, reject) => {
        const timer = setTimeout(() => finish(new Error('Home Assistant request timed out.')), 15000);
        const aborted = () => finish(new Error('Request cancelled.'));
        const closed = () => finish(new Error('Home Assistant disconnected.'));
        const finish = (error, result) => {
          clearTimeout(timer);
          ws.removeEventListener('message', message);
          ws.removeEventListener('close', closed);
          ws.removeEventListener('error', closed);
          signal?.removeEventListener('abort', aborted);
          error ? reject(error) : resolve(result);
        };
        const message = event => {
          let data;
          try { data = JSON.parse(event.data); } catch { return; }
          if (data.id !== 1 || data.type !== 'result') return;
          data.success ? finish(null, data.result) : finish(new Error(data.error?.message || 'Home Assistant request failed.'));
        };
        ws.addEventListener('message', message);
        ws.addEventListener('close', closed);
        ws.addEventListener('error', closed);
        signal?.addEventListener('abort', aborted, { once: true });
        ws.send(JSON.stringify({ id: 1, type, ...fields }));
      });
    } finally { ws.close(); }
  }

  async pipeline() {
    const result = await this.request('assist_pipeline/pipeline/list');
    const pipeline = result.pipelines.find(p => p.id === this.pipelineId)
      || (!this.pipelineId && result.pipelines.find(p => p.id === result.preferred_pipeline));
    if (!pipeline) throw new Error('Configured Home Assistant voice pipeline was not found.');
    return pipeline;
  }

  async run({ pipeline, text, pcm, conversationId, onEvent, signal }) {
    const ws = await this.connect(signal);
    const voice = pcm !== undefined;
    if (voice && !pipeline.stt_engine) { ws.close(); throw new Error('Choose a speech-to-text engine in Home Assistant.'); }
    try {
      await new Promise((resolve, reject) => {
        let sent = false;
        let finishTimer;
        const timeout = setTimeout(() => finish(new Error('NOVA timed out waiting for Home Assistant.')), 95000);
        const aborted = () => finish(new Error('Request cancelled.'));
        const disconnected = () => finish(new Error('Home Assistant disconnected during the request.'));
        const finish = error => {
          clearTimeout(timeout); clearTimeout(finishTimer);
          ws.removeEventListener('message', message);
          ws.removeEventListener('close', disconnected);
          ws.removeEventListener('error', disconnected);
          signal?.removeEventListener('abort', aborted);
          error ? reject(error) : resolve();
        };
        const message = event => {
          let data;
          try { data = JSON.parse(event.data); } catch { return; }
          if (data.id !== 1) return;
          if (data.type === 'result' && !data.success) return finish(new Error(data.error?.message || 'Pipeline failed.'));
          if (data.type !== 'event') return;
          const e = data.event;
          if (e.type === 'error') return finish(new Error(e.data?.message || e.data?.code || 'Voice pipeline failed.'));
          if (e.type === 'run-start' && voice && !sent) {
            sent = true;
            const handler = e.data.runner_data.stt_binary_handler_id;
            if (!Number.isInteger(handler) || handler < 0 || handler > 255) return finish(new Error('Invalid audio handler from Home Assistant.'));
            for (let offset = 0; offset < pcm.length; offset += 4096) {
              ws.send(Buffer.concat([Buffer.from([handler]), pcm.subarray(offset, offset + 4096)]));
            }
            ws.send(Buffer.from([handler]));
          }
          // Never forward HA access tokens or signed audio URLs to the browser.
          if (e.type === 'stt-end') onEvent('transcript', { text: e.data.stt_output.text });
          if (e.type === 'intent-start') onEvent('stage', { stage: 'thinking' });
          if (e.type === 'intent-end') {
            const id = e.data.intent_output?.conversation_id;
            if (id) onEvent('conversation', { id });
            const speech = e.data.intent_output?.response?.speech?.plain?.speech;
            if (speech) onEvent('reply', { text: speech });
          }
          if (e.type === 'tts-start') onEvent('stage', { stage: 'voicing' });
          if (e.type === 'tts-end' && e.data.tts_output?.url) onEvent('tts', { url: e.data.tts_output.url });
          // HA can emit a timeout error immediately after run-end.
          if (e.type === 'run-end') finishTimer = setTimeout(() => finish(), 75);
        };
        ws.addEventListener('message', message);
        ws.addEventListener('close', disconnected);
        ws.addEventListener('error', disconnected);
        signal?.addEventListener('abort', aborted, { once: true });
        ws.send(JSON.stringify({ id: 1, type: 'assist_pipeline/run', pipeline: pipeline.id,
          ...(conversationId ? { conversation_id: conversationId } : {}),
          start_stage: voice ? 'stt' : 'intent', end_stage: pipeline.tts_engine ? 'tts' : 'intent',
          input: voice ? { sample_rate: 16000 } : { text }, timeout: 90 }));
      });
    } finally { ws.close(); }
  }

  async audio(path, signal) {
    const url = new URL(path, this.url);
    if (url.origin !== this.url.origin || !/^\/api\/tts_proxy\//.test(url.pathname)) {
      throw new Error('Home Assistant returned an unexpected audio location.');
    }
    const response = await fetch(url, { headers: { Authorization: `Bearer ${this.token}` }, signal, redirect: 'error' });
    if (!response.ok) throw new Error('Could not fetch the spoken response.');
    const buffer = Buffer.from(await response.arrayBuffer());
    if (buffer.length > 10 * 1024 * 1024) throw new Error('Spoken response is too large.');
    return { buffer, type: response.headers.get('content-type') || 'audio/wav' };
  }
}
