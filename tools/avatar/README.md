# Local likeness reconstruction study

This is a local modelling experiment, not a general photo-to-avatar service or a replacement for an artist-built head. It fits the generated front portrait `public/avatar/assets/nova-call-neutral-v2.png`, itself derived from the user's newer reference. The original photo is not processed by an external service here.

`probe.py` runs Google's Face Landmarker and Selfie Multiclass Segmenter locally, saving estimated landmarks and segmentation in ignored `.local/avatar-models/reference-fit.npz`. `build_likeness.py` produces a VRM with a 468-vertex estimated face, morph targets, recessed eye/mouth geometry, a depth shell for hair/ears, and a skinned neck/shoulder surface. The source PNG is embedded unchanged as a UV texture. The morph targets are heuristic; this is not motion capture or a complete sculpt. The model is suitable for restrained near-frontal movements only.

## Rebuild

Create a Python 3.12 environment under `.local/avatar-tools` with `uv venv --python python3.12 .local/avatar-tools`, then `uv pip install --python .local/avatar-tools/bin/python -r tools/avatar/requirements.txt`.

Download the three public inputs in `inputs.json` to `.local/avatar-models/` using their filenames. Verify their SHA-256 values before running the probe; upstream `latest` URLs may eventually change, so a different hash needs deliberate review. Inputs are not bundled in Git. Then run:

```sh
.local/avatar-tools/bin/python tools/avatar/probe.py
.local/avatar-tools/bin/python tools/avatar/probe_mouth.py
.local/avatar-tools/bin/python tools/avatar/build_likeness.py
npm run build:avatar
```

The current model and provenance are in `public/avatar/models/nova-likeness-study.{vrm,json}`. Raw landmark/cache data stays ignored. Model use in NOVA does not grant rights to the original reference photograph or its likeness. The embedded restrictive study metadata is not an assertion of ownership of the reference.

## Checks

The local Khronos glTF Validator 2.0.0-dev.3.10 reports zero core errors and warnings for this export; it does not validate the `VRMC_vrm` extension. The actual three-vrm browser loader was also checked. Remaining informational messages describe the unsupported extension, non-power-of-two texture, and empty humanoid bone endpoints. Visual checks remain necessary; file validation cannot establish likeness or natural movement.

The MediaPipe topology is Apache-2.0; its license is retained in `MEDIAPIPE-LICENSE.txt`. MediaPipe models and task documentation: https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker and https://developers.google.com/edge/mediapipe/solutions/vision/image_segmenter . No Blender installation or global Python changes were made.

## Speech revision

`morphs.py` now uses mouth-local curved lip rims. Speech does not move the chin, mandible contour or other non-mouth face vertices. The lip corners stay fixed; opening, width and rounding differ between the three targets. The recessed mouth interior uses an unchanged generated expression-reference texture instead of procedural teeth. Blink, gaze, head, shoulder and call behaviour are unchanged. The two geometry tests assert locality, fixed corners, limited displacement and distinct curved mouth shapes. These checks do not establish perceptual realism; voice playback and user review remain necessary.

`probe_mouth.py` fits `public/avatar/assets/nova-mouth-reference-v2.png`, a previously generated open-mouth/closed-eye frame from the same portrait. Only the mouth interior is mapped into recessed geometry; it does not replace the eyes or face texture. The source PNG is embedded unchanged. Its source prompt requested only a natural closed-eye blink and a modest open “ah” on the otherwise unchanged portrait, using the built-in image tool.
