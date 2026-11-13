import { SRGBColorSpace, TextureLoader } from 'three';

// Photographed open eyes cannot be squeezed onto a closing eyelid. Crossfade
// the registered lid appearance using the same native blink that moves the mesh.
export async function fitLidAppearance(head) {
  const texture = await new TextureLoader().loadAsync('/v2/assets/closed-lids.png');
  texture.flipY = false;
  texture.colorSpace = SRGBColorSpace;
  head.armature.traverse(object => {
    if (!object.isMesh) return;
    const geometry = object.geometry;
    const uv = geometry.attributes._nova_closed_uv || geometry.attributes._NOVA_CLOSED_UV;
    const mask = geometry.attributes._nova_eye_mask || geometry.attributes._NOVA_EYE_MASK;
    if (!uv || !mask) return;
    // Blender exports an unused white COLOR_0 before the authored skin colors
    // on this unlit material. Use the authored layer for underside shading.
    if (geometry.attributes.color_1) geometry.setAttribute('color', geometry.attributes.color_1);
    geometry.setAttribute('novaClosedUV', uv);
    geometry.setAttribute('novaEyeMask', mask);
    const blink = { value: [0, 0] };
    const materials = [].concat(object.material);
    for (const material of materials) {
      material.onBeforeCompile = shader => {
        shader.uniforms.novaClosedLids = { value: texture };
        shader.uniforms.novaBlink = blink;
        shader.vertexShader = `attribute vec2 novaClosedUV;
attribute vec2 novaEyeMask;
varying vec2 novaLidUV;
varying vec2 novaLidMask;
${shader.vertexShader}`;
        shader.vertexShader = shader.vertexShader.replace('#include <uv_vertex>', `#include <uv_vertex>
novaLidUV = vec2(novaClosedUV.x, 1.0 - novaClosedUV.y);
novaLidMask = novaEyeMask;`);
        shader.fragmentShader = `uniform sampler2D novaClosedLids;
uniform vec2 novaBlink;
varying vec2 novaLidUV;
varying vec2 novaLidMask;
${shader.fragmentShader}`;
        shader.fragmentShader = shader.fragmentShader.replace('#include <map_fragment>', `#include <map_fragment>
float novaAmount = max(novaLidMask.x * novaBlink.x, novaLidMask.y * novaBlink.y);
float novaSideBlink = dot(novaLidMask, novaBlink) / max(0.001, novaLidMask.x + novaLidMask.y);
vec2 novaUV = mix(vMapUv, novaLidUV, novaSideBlink);
vec3 novaLidColor = texture2D(novaClosedLids, novaUV).rgb;
diffuseColor.rgb = mix(diffuseColor.rgb, novaLidColor, smoothstep(0.0, 0.65, novaAmount));`);
      };
      material.customProgramCacheKey = () => 'nova-registered-lids-v1';
      material.needsUpdate = true;
    }
    object.onBeforeRender = () => {
      blink.value[0] = Math.max(0, Math.min(1, head.mtAvatar.eyeBlinkLeft?.applied || 0));
      blink.value[1] = Math.max(0, Math.min(1, head.mtAvatar.eyeBlinkRight?.applied || 0));
    };
  });
  return texture;
}
