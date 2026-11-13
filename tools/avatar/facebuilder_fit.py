"""Fit an isolated FaceBuilder head project from a supplied reference photograph.

Run with Blender --background --python this_file -- --reference ... --output ...
Requires the user's installed/licensed KeenTools extension. No cloud photo upload.
"""
import argparse, hashlib, importlib, json, sys
from pathlib import Path
import bpy
import numpy as np
args=argparse.ArgumentParser();args.add_argument('--reference',required=True,action='append');args.add_argument('--output',required=True)
a=args.parse_args(sys.argv[sys.argv.index('--')+1:]);sources=[Path(p).resolve() for p in a.reference];source=sources[0];out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
if (out/'head.blend').exists():raise RuntimeError('Use a new output directory; existing head.blend will not be overwritten')
name='bl_ext.user_default.keentools'
if name not in bpy.context.preferences.addons:bpy.ops.preferences.addon_enable(module=name)
module=lambda suffix:importlib.import_module(name+'.'+suffix)
settings=module('addon_config').fb_settings();loader=settings.loader()
# This is a separate process and output file, never the user's active GUI scene.
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
if bpy.ops.keentools_fb.add_head()!={'FINISHED'}:raise RuntimeError('Could not create FaceBuilder head')
head=settings.get_head(0);settings.current_headnum=0
fb=loader.get_builder();head.use_emotions=len(sources)>1;fb.set_use_emotions(head.use_emotions)
references=[]
for index,source in enumerate(sources):
 cam=loader.add_new_camera_with_image(0,str(source));loader.center_geo_camera_projection(0,index);kid=cam.get_keyframe()
 module('utils.focal_length').configure_focal_mode_and_fixes(fb,head)
 module('facebuilder.pick_operator')._init_fb_detected_faces(fb,0,index)
 faces=module('utils.detect_faces').get_detected_faces()
 if not len(faces):raise RuntimeError(f'No face detected in reference {index+1}')
 face=max(faces,key=lambda f:float(np.prod(np.asarray(f.xy_max)-np.asarray(f.xy_min))))
 print(f'NOVA_FB_STAGE fitting_view_{index+1}',flush=True)
 if not fb.detect_face_pose(kid,face):raise RuntimeError(f'Pose fitting failed for view {index+1}')
 fb.remove_pins(kid);fb.add_preset_pins_and_solve(kid)
 loader.update_camera_pins_count(0,index)
 references.append({'filename':source.name,'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'dimensions':list(cam.cam_image.size),'keyframe':kid})
head.set_neutral_expression_view()
module('utils.coords').update_head_mesh_neutral(fb,head)
loader.update_all_camera_positions(0);loader.update_all_camera_focals(0);loader.save_fb_serial_and_image_pathes(0)
cam=head.get_camera(0);kid=cam.get_keyframe()
obj=head.headobj;obj.name='NOVA FaceBuilder head'
print('NOVA_FB_STAGE baking_texture',flush=True)
settings.tex_width=2048;settings.tex_height=2048
materials=module('utils.materials');texture_name=head.preview_texture_name();status=materials.bake_tex(0,texture_name)
if not status.success:raise RuntimeError(status.error_message)
material=materials.show_texture_in_mat(texture_name,head.preview_material_name());materials.assign_material_to_object(obj,material)
texture=bpy.data.images[texture_name];texture.filepath_raw=str(out/'head-texture.png');texture.file_format='PNG';texture.save();texture.pack()
print('NOVA_FB_STAGE facial_shapes',flush=True)
count=module('utils.blendshapes').create_facs_blendshapes(obj,fb.current_scale())
if count<1:raise RuntimeError('FaceBuilder facial shapes unavailable')
# A fitted-camera render makes alignment and texture defects reviewable before
# any retargeting or live-avatar replacement.
scene=bpy.context.scene;scene.camera=cam.camobj;scene.render.engine='CYCLES';scene.cycles.samples=16
scene.render.resolution_x=720;scene.render.resolution_y=954;scene.render.resolution_percentage=100
world=bpy.data.worlds.new('NOVA inspection world');scene.world=world;world.use_nodes=True;world.node_tree.nodes['Background'].inputs['Color'].default_value=(.5,.5,.5,1);world.node_tree.nodes['Background'].inputs['Strength'].default_value=.8
# Emission inspection shows the baked pixels independently of added lighting.
inspection=bpy.data.materials.new('NOVA unlit texture inspection');inspection.use_nodes=True;nodes=inspection.node_tree.nodes;nodes.clear();tex=nodes.new('ShaderNodeTexImage');tex.image=texture;emission=nodes.new('ShaderNodeEmission');output=nodes.new('ShaderNodeOutputMaterial');inspection.node_tree.links.new(tex.outputs['Color'],emission.inputs['Color']);inspection.node_tree.links.new(emission.outputs[0],output.inputs['Surface']);obj.data.materials[0]=inspection
scene.render.film_transparent=True;scene.render.image_settings.file_format='PNG';scene.render.filepath=str(out/'fitted-camera.png')
for image in bpy.data.images:
 if image.source=='FILE' and image.pixels:image.pack()
bpy.context.view_layer.objects.active=obj;obj.select_set(True)
bpy.ops.wm.save_as_mainfile(filepath=str(out/'head.blend'))
report={'references':references,'blender':bpy.app.version_string,'vertices':len(obj.data.vertices),'faces':len(obj.data.polygons),'pins':sum(fb.pins_count(c.get_keyframe()) for c in head.cameras),'facs_shapes':count,'shape_names':[s.name for s in obj.data.shape_keys.key_blocks],'current_scale':fb.current_scale(),'mask_names':list(fb.mask_names()),'source_upload':False,'status':'fitted_head_pending_visual_review','limitations':['Reference views do not fully cover the hidden side or back of the head','Reference lighting is baked into the texture','Hair, oral rig integration and photoreal review are not complete','The approved TalkingHead prototype and live NOVA are unchanged']}
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print('NOVA_FB_REPORT '+json.dumps({k:report[k] for k in ['vertices','faces','pins','facs_shapes','current_scale','mask_names','status']}),flush=True)
bpy.ops.render.render(write_still=True)
print('NOVA_FB_STAGE render_complete',flush=True)
