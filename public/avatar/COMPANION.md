# Fullscreen companion prototype

The main NOVA HTTPS app now uses `Companion` (Three.js + three-vrm), replacing the frontal sprite puppet. The original `index.html`/`studio.js` study remains available for comparison. `call-preview.html` is a standalone motion study with simulated speech energy; actual NOVA uses response audio from its existing recorder context.

## Build

```sh
npm ci
npm run build:avatar
npm start
```

`companion.bundle.js` is built from `companion.js`. Libraries and the model are served locally; no CDN or photo upload is required. Third-party notices are in `THIRD_PARTY_NOTICES.txt`; sample model source/embedded permissions are in `models/ATTRIBUTION.json`.

## Model and animation

The default model is now `nova-likeness-study.vrm`, reconstructed locally from the approved front portrait derived from the user's newer reference. It has an estimated face surface, six facial morphs, recessed eye/mouth geometry, a depth shell for hair/ears, and a skinned neck/shoulder surface. The likeness was approved in chat and then refined around the face edge and blink. This is not a complete artist-built sculpt or a calibrated scan: larger turns, hidden head geometry, hair volume and facial deformation quality remain limited. Build inputs, provenance, exact versions and verification boundaries are documented in `tools/avatar/README.md`; the model hash and source artwork hash are in `models/nova-likeness-study.json`.

The original pixiv sample remains in the standalone motion study for comparison. Its source/permissions are in `models/ATTRIBUTION.json`. The file picker loads a VRM locally for the current browser session without uploading it; files over 50 MB are rejected.

Animation includes eased head/neck rotation, shoulder breathing, gaze targets, blink, restrained expression blending and audio-derived vowel approximation. It is procedural, not motion capture, and does not infer emotions from the LLM. Speech uses locally recognized timed mouth-shape cues when available, with spectral animation as a fallback. Reduced-motion preference removes idle head/body movement. Rendering is capped at 30 fps, pixel ratio 1.5, and skips hidden documents.

## Conversation

Tap Start conversation once, grant microphone access, and speak. The local energy gate buffers 300 ms of preroll, requires sustained sound, and ends an utterance after roughly 950 ms below its adaptive threshold. Continuous sound is capped near 40 seconds. Idle audio is bounded in memory and not sent to HA. This is sound-energy detection, not a semantic speech classifier or wake word; TV/music/background conversation can trigger it.

The microphone stream closes during inference and playback; listening resumes after the reply ends. No barge-in yet. Mute affects the microphone; End aborts the request, stops playback and releases the mic. Leaving the page ends the call. The app remains the existing STT → LLM/tools → TTS pipeline, not native realtime speech-to-speech. Chat opens as an overlay; sending typed text ends an active microphone call. The existing credentials, tool routing and camera policy are retained.

## Verification (2026-11-04)

- 20 Node tests passed: existing HA/audio/conversation checks plus speech segmentation, bounded idle storage, continuous-sound limit, mic closure during replies, permission/stop races and playback cancellation.
- Browser verified the 3D model, framing, controls, actual HA/Piper spoken reply and animated mouth.
- HTTPS asset requests, CA validation and authenticated HA pipeline readiness passed.
- User confirmed iPad hands-free turn-taking works and the motion looks more natural than the earlier puppet. No measured iPad frame-rate/battery figures are claimed.

## Artwork reference

`assets/nova-call-neutral-v2.png` was generated with the built-in image tool from the newer user-supplied portrait. Prompt: create a front-facing, head-and-shoulders, semi-realistic illustrated video-call portrait preserving the reference face, short side-parted light brown hair, necklace and black-trimmed white top, with closed neutral lips, relaxed shoulders, even lighting and a softly blurred charcoal background; remove other people, hands, devices and event setting. It is a design/fallback image, not a 3D model or texture map. The original photograph was not copied into the repository or uploaded to a third-party modelling service.

Native iPad packaging was discussed as a later step; no native app has been created in this change.

## Likeness update verification

The custom export passed Khronos glTF core validation with zero errors and zero warnings. The validator does not validate VRMC_vrm; the actual three-vrm loader was checked separately in the browser. The model and face loaded in the full authenticated call UI; HTTPS delivery and voice-pipeline readiness passed. The 20 Node tests passed again. iPad naturalness/performance of this custom model still requires user review; the earlier successful iPad turn-taking test used the sample model.

The custom likeness speech range is calibrated separately from the sample VRM. Speech now uses curved mouth-local lip targets, keeping the chin/jaw contour stationary; the recessed mouth interior is textured from the generated expression reference. Two additional Python geometry tests cover this change. Photographic textures and estimated geometry still limit expression quality.

## Pronunciation timing

The server runs [Rhubarb Lip Sync 1.14.0](https://github.com/DanielSWolf/rhubarb-lip-sync) locally on the completed TTS audio, using its phonetic recognizer. Cues group sounds into visual poses: closed M/B/P, open vowels, rounded vowels and F/V. The renderer blends them against the Web Audio playback clock, including Replay; head, eyes and shoulders retain their existing motion. These are approximate visemes, not a phoneme transcript or a fully sculpted facial rig.

Install the official macOS release into `.local/rhubarb/Rhubarb-Lip-Sync-1.14.0-macOS/` with its adjacent resources, or set `NOVA_LIPSYNC_BIN` to the binary. The downloaded `Rhubarb-Lip-Sync-1.14.0-macOS.zip` SHA-256 is `f991deacac6c973a14a4431a16a58b842f436531e120cfaea142c87c0d3ab4c5`. The installed binary is local and ignored by Git. MP3 TTS is converted to mono PCM for analysis with the existing `/opt/homebrew/bin/ffmpeg` (`NOVA_FFMPEG_BIN` overrides it); playback retains the original audio. Private temporary audio/dialog files are removed after analysis or failure. Nothing is uploaded for lip sync.

Each analysis subprocess has a three-second limit. Missing dependencies, invalid audio or timeout preserve voice playback with audio-reactive mouth motion. The UI identifies the active mode as “speech-synced” or “audio reactive.” The plain `call-preview.html` now defaults to the likeness model; `?model=sample` selects the sample. Its controls remain a simulated animation preview, not a voice-connected call.

Pronunciation update verification: 28 Node tests pass; the rebuilt model passes core glTF validation with zero errors/warnings. An authenticated HTTPS run returned timed cues with the original playable MP3, and the browser displayed speech-synced mode and replayed the reply. Local MP3 conversion plus timing took 727 ms for a 3.26-second Piper recording. Perceived lip-sync quality on the iPad remains for user review.
