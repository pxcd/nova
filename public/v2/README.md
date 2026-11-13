# NOVA v2

Run `npm run build:v2`, then `npm run start:v2` alongside the existing NOVA server on HTTPS port 8787. The separate HTTPS listener uses port 8790: `/v1` proxies the existing app and `/v2` serves the fitted-head client. It does not restart the original server or replace its files. V2 authenticates with a separate `nova_v2_session` cookie scoped to `/v2`; Home Assistant credentials remain in the original backend.

The private model is served from `.local/facebuilder/v2-current/head.glb`. That relative symlink selects an immutable candidate directory. Reference photographs, generated frontal reference, fit projects, segmentation masks and rendered review evidence stay under ignored `.local/facebuilder/`; they are not bundled into the repository. The generated frontal reference and its exact image-generation prompt/provenance are in `reference-v2/` there.

The head uses FaceBuilder's native gaze/blink shapes and 15 Oculus phoneme targets composed from its authored ARKit facial shapes. Existing Piper audio, Rhubarb cue timing and the TalkingHead speech scheduler are unchanged. The thin inner-mouth fill is replaced by a recessed oral tunnel with matching facial targets behind the retained teeth. Neutral idle animation is limited to breathing, blink, restrained gaze and small sway. Photographic skin and front hair contain baked lighting; the reconstructed head is intended for near-frontal conversation, not unrestricted viewing or dynamic relighting. The front hair surface uses a strand-preserving alpha cutout calibrated to the reference camera over a back cap. Registered open/closed eye appearances follow the native blink target, avoiding a photographed iris being compressed onto closing lid skin. The neck fitting tapers continuously at the jaw and includes underside attenuation. These are near-frontal appearance corrections, not a scanned or fully relightable digital human. The retained sample body/teeth remain subject to `public/avatar/talkinghead/ATTRIBUTION.json` and its noncommercial license.

To rebuild a candidate using the existing project-local avatar tools and installed Blender/FaceBuilder:

1. Run `tools/avatar/facebuilder_fit.py` in a separate background Blender process with `--reference` inputs and a new `--output` directory.
2. Open that `head.blend` in background Blender and run `tools/avatar/facebuilder_retexture.py -- --output <new-fit-directory>`. This saves the first reference camera's texture, frame and unchanged reference image.
3. Run `.local/avatar-tools/bin/python tools/avatar/segment_reference.py --fit <new-fit-directory>`.
4. Run `tools/avatar/facebuilder_rig.py` in background Blender with `--fit <new-fit-directory> --output <new-rig-directory>`. Existing model outputs are never overwritten.
5. For the matched appearance pass, run `tools/avatar/facebuilder_appearance.py` with `--source` pointing to the immutable fitted rig and `--output` to a new candidate. It expects the registered reference edits and prompts under ignored `.local/facebuilder/reference-v3/`, and writes the paired `head.glb` and `closed-lids.png`.
6. Validate the GLB and review actual speech, blink, silhouette and seams before changing the `v2-current` symlink. The client must load both assets from the same candidate.

`npm test` covers the client voice pipeline, cue mapping, cancellation, proxy streaming, session isolation and v2 home-screen routing. GLB structural validation and visual/model review are separate checks and require the private candidate assets.
