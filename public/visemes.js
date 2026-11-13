// Rhubarb groups similar speech sounds into visual mouth poses, not exact phonemes.
const poses = {
  X: [0, 0, 0, 0], A: [0, 0, 0, 0], // rest / M, B, P
  B: [0, .28, 0, 0], C: [.6, .1, 0, 0], D: [.95, 0, 0, 0],
  E: [.12, 0, .6, 0], F: [0, 0, .9, 0], G: [0, .08, 0, .8],
};
export function validateCues(cues, duration) {
  if (!Number.isFinite(duration) || duration <= 0 || duration > 180 || !Array.isArray(cues) || !cues.length || cues.length > 5000) throw new Error('Invalid speech timings');
  let end = 0;
  return cues.map(c => {
    if (!c || !Object.hasOwn(poses, c.value) || !Number.isFinite(c.start) || !Number.isFinite(c.end) || c.start < end - .001 || c.start < 0 || c.end <= c.start || c.end > duration + .05) throw new Error('Invalid speech cue');
    end = c.end;
    return { start: c.start, end: c.end, value: c.value };
  });
}
export function poseAt(cues, time) {
  if (!Number.isFinite(time) || time < 0 || !cues?.length) return poses.X;
  let lo = 0, hi = cues.length - 1, index = -1;
  while (lo <= hi) { const mid = (lo + hi) >> 1; if (cues[mid].start <= time) { index = mid; lo = mid + 1; } else hi = mid - 1; }
  if (index < 0 || time >= cues[index].end) return poses.X;
  const cue = cues[index], target = poses[cue.value] || poses.X;
  const previous = index > 0 && cue.start - cues[index - 1].end < .05 ? poses[cues[index - 1].value] || poses.X : poses.X;
  const blend = Math.min(1, (time - cue.start) / Math.min(.035, (cue.end - cue.start) / 2));
  return target.map((value, i) => previous[i] + (value - previous[i]) * blend);
}
