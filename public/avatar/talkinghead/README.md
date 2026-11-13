# TalkingHead comparison study

Open `https://10.0.0.150:8787/talkinghead`, then tap **Play voice sample**. This isolated page uses a prerecorded local Piper reply and Rhubarb cues mapped to Oculus visemes. There is no microphone or inference connection. NOVA's production avatar and conversation client do not import TalkingHead.

The official reference GLB has a Mixamo-compatible skeleton and 72 facial targets on its face/eyes/teeth, including the 15 Oculus speech shapes. Only the eight Rhubarb cue groups are used in this comparison. This isolates rig and renderer quality from voice/timing changes; it does not evaluate TalkingHead's text-to-viseme engine. No cloud TTS key or third-party runtime requests are needed.

TalkingHead is pinned to 1.7.0. Rebuild with `npm run build:talkinghead`. Its MIT license and the reference avatar's CC BY-NC 4.0 license are retained beside the assets; `ATTRIBUTION.json` records immutable model origin and hashes. The reference avatar is for noncommercial evaluation, not NOVA's custom likeness.

Movement is restrained using a low movement factor, low gaze-linked head movement, and small neutral head/body rotation ranges. Broad random pose changes are removed. The movement toggle controls sway/head movement; breathing and blinking remain. Reduced-motion preference disables sway initially. Hidden pages stop speech and animation.

Verification: browser model loading, speech animation, Stop, replay and movement toggle checked; trusted HTTPS delivery of all preview assets checked; existing 29 Node tests passed. The unchanged upstream GLB passes core validation with zero errors and 15 warnings (generated tangent space and non-root skinned mesh nodes). The iPad's rendering performance and perceived mouth quality remain for user review.

## Fitted NOVA movement prototype

`/talkinghead?model=nova` selects the separate experimental likeness. The default page still selects the unmodified cartoon reference. The live NOVA app continues to use its existing VRM.

`tools/avatar/build_talkinghead_likeness.py` fits the reference mesh to the approved portrait landmarks with a smooth local deformation, transfers all 72 authored facial targets through the local deformation Jacobian, and preserves separate teeth, original skinning and topology. The portrait PNG is unchanged. Custom UV/mask attributes and a preview-only material shader project it onto the fitted surface; this is not a finished baked, portable photoreal avatar. A curved portrait hair surface and a shortened backing cap are attached to the head. The sample body/clothes remain. Temples, hair, eye/eyelid mapping and oblique views still have visible artifacts.

The fitting input is a local 1280×720 screenshot of `fit.html`, an orthographic view 0.4 m high centred at y=1.60, with source hair/glasses hidden. Run `tools/avatar/fit_rig.py` with the project-local avatar Python environment, then the builder. Local fit caches remain ignored. `nova-rig-study.json` records hashes and limitations; the derivative retains the reference CC BY-NC 4.0 terms.

Checks: two independent structural tests preserve authored targets, moving mouth/teeth targets, finite geometry and immutable reference/provenance hashes; core glTF validation has zero errors and 13 warnings; browser playback and framing inspected. The warnings concern generated tangent space and inherited non-root skinned mesh nodes. Perceived realism/movement quality remains a user review gate.

## Anatomical-head variant

`/talkinghead?model=realistic` selects the new anatomical MakeHuman base, while `?model=nova` preserves the prior approved movement prototype. The same `speakAudio` call, Rhubarb-to-Oculus mapping, audio sample, viseme times, and subdued movement settings are used. The vertex motions belong to the new mesh's authored facial shapes; identical vertex-level motion across different topologies is not claimed. The live NOVA app is unchanged.

The CC0 reference is TalkingHead's `mpfb.glb` at commit `1563de184c19b310de4b636664d5835e2c74dbba`, stored as `realistic-base.glb`. It has a continuous anatomical head/body mesh, separate detailed teeth and tongue, facial targets and a Mixamo-compatible skeleton. `build_realistic_head.py` fits the face and auxiliary oral/eye meshes locally, preserving their topology and target names, including sparse glTF targets. The detailed portrait is unchanged. Projected facial shading, including likeness/eye matching, remains approximate. Source eyebrow/lash overlays were removed to avoid doubling features already in the portrait; the projected material omits the source normal and AO maps.

Hair uses the official CC0 MakeHuman `bob01` OBJ/texture as a complete 3D backing, with detailed portrait groom cards at the front. This closes the unsupported cutout gaps of the previous prototype but remains limited to near-frontal, subtle motion. It is an experimental likeness, not a finished photoreal sculpt. The source clothing/body remain. `MAKEHUMAN-CC0-LICENSE.txt`, `ATTRIBUTION.json` and `nova-realistic-study.json` retain licensing, immutable model origin, hashes and limitations. The general noncommercial restriction on the older RPM variant does not apply to this CC0 base.

Rebuild inputs: approved portrait fit cache, a 1280×720 local screenshot of `fit.html?model=human` saved as `.local/avatar-models/mpfb/front.png`, and official `bob01` assets extracted under `.local/avatar-models/mpfb/bob01/`. Run `fit_rig.py --anatomical`, `build_realistic_head.py`, then `npm run build:talkinghead` using the existing project-local avatar Python environment. Original reference photos are not uploaded. Performance work is deferred.

Visual review gate: the anatomical-head experiment was rejected for promotion. Hair coverage, projected facial shading and eye alignment remain visibly unnatural despite valid geometry. The approved mouth prototype (`?model=nova`) and production NOVA avatar were preserved. Structural tests establish rig integrity, not aesthetic success.
