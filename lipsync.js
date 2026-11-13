import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { mkdtemp, writeFile, rm, access } from 'node:fs/promises';
import { join, dirname } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';
import { validateCues } from './public/visemes.js';

const root = dirname(fileURLToPath(import.meta.url));
export const defaultBinary = join(root, '.local/rhubarb/Rhubarb-Lip-Sync-1.14.0-macOS/rhubarb');
const execute = promisify(execFile);
export async function lipSyncReady(binary = process.env.NOVA_LIPSYNC_BIN || defaultBinary) {
  try { await access(binary); return true; } catch { return false; }
}
export async function speechCues(buffer, text, signal, { binary = process.env.NOVA_LIPSYNC_BIN || defaultBinary, run = execute, timeout = 3000 } = {}) {
  const wav = Buffer.isBuffer(buffer) && buffer.toString('ascii', 0, 4) === 'RIFF' && buffer.toString('ascii', 8, 12) === 'WAVE';
  const mp3 = Buffer.isBuffer(buffer) && (buffer.toString('ascii', 0, 3) === 'ID3' || (buffer[0] === 0xff && (buffer[1] & 0xe0) === 0xe0));
  if (!Buffer.isBuffer(buffer) || buffer.length > 20_000_000 || (!wav && !mp3)) throw new Error('Speech timing requires WAV or MP3 audio');
  signal?.throwIfAborted();
  const directory = await mkdtemp(join(tmpdir(), 'nova-lipsync-'));
  const started = performance.now();
  try {
    const audio = join(directory, 'reply.wav');
    if (wav) await writeFile(audio, buffer, { mode: 0o600 });
    else {
      const source = join(directory, 'reply.mp3');
      await writeFile(source, buffer, { mode: 0o600 });
      await run(process.env.NOVA_FFMPEG_BIN || '/opt/homebrew/bin/ffmpeg', ['-nostdin', '-v', 'error', '-i', source, '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', audio], { signal, timeout, maxBuffer: 1_000_000 });
      signal?.throwIfAborted();
    }
    const args = ['-q', '-f', 'json', '-r', 'phonetic', '--extendedShapes', 'GX', '--threads', '4'];
    if (typeof text === 'string' && text.length && text.length <= 20000) {
      const dialog = join(directory, 'reply.txt');
      await writeFile(dialog, text, { mode: 0o600 }); args.push('-d', dialog);
    }
    args.push(audio);
    const { stdout } = await run(binary, args, { signal, timeout, maxBuffer: 1_000_000, cwd: dirname(binary) });
    signal?.throwIfAborted();
    const result = JSON.parse(stdout);
    const duration = result.metadata?.duration;
    return { cues: validateCues(result.mouthCues, duration), duration, analysisMs: Math.round(performance.now() - started) };
  } finally {
    // Only this invocation's private scratch directory is removed.
    await rm(directory, { recursive: true, force: true });
  }
}
