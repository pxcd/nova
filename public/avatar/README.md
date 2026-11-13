# NOVA avatar study

Run locally from the repository:

```sh
python3 -m http.server 8811 --bind 127.0.0.1 --directory public/avatar
```

Open http://127.0.0.1:8811 for the standalone study. The main NOVA HTTPS interface now embeds the same puppet above its existing push-to-talk button. Its asset allowlist serves the renderer and three expression images.

In the live interface, `levelSource` reads the recorder's output analyser, sharing its already-unlocked AudioContext. No second microphone stream or audio output path is created. Listening adds a small attentive lean; transcription/thinking/voicing adds a slight tilt. Speaking opens the mouth only when response audio has energy. Stop, natural playback end and failed playback return it to rest. Replay uses the same analyser. Microphone input does not animate NOVA's speaking mouth.

The dependency-free Canvas renderer uses the approved portrait plus feathered eye/mouth patches from generated expression frames. It supports idle sway/breathing, automatic and manual blinking, head tilt and a two-state speaking mouth. Local audio playback drives the mouth through Web Audio RMS with a short silence hold. The talking-preview button is explicitly simulated. No recording or file is uploaded; no HA actions are called.

This is a frontal sprite prototype, not a mesh/deformer rig or phoneme-level lip sync. Rich facial expressions, hair physics, independent gaze and head turns are not implemented. Artwork registration, audio thresholds and iPad Safari performance still need device testing. Browsers require user interaction to start audio analysis.

## Artwork provenance

All three images were produced with the built-in image-generation tool. The neutral image was approved in chat. Expression frames were generated from it; only their eye/mouth regions are composited, preserving the neutral portrait elsewhere. The original uploaded photograph is not included in this repository.

Prompt set, summarized:

- Neutral: front-facing head-only semi-realistic 2D portrait preserving the supplied reference's facial proportions, blonde bob/bangs, dark eyes and white flower crown; gently closed lips, no hands/body/text; transparent background.
- Blink: change only both eyes to gently fully closed; preserve the approved portrait's scale, position, face, mouth, hair, crown and transparency.
- Speaking: change only the mouth to a modest open “ah” with natural upper teeth; preserve all other portrait details and registration; transparent background.

Generated images remain flattened source frames. No layered PSD or Cubism asset is implied.
