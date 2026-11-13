"""Keep the multiview geometry, selecting the closest reference for texture detail."""
import bpy,importlib,json,sys,argparse
import numpy as np
import shutil
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
if (out/'head.blend').exists():raise RuntimeError('Output already exists')
name='bl_ext.user_default.keentools'
if name not in bpy.context.preferences.addons:bpy.ops.preferences.addon_enable(module=name)
module=lambda suffix:importlib.import_module(name+'.'+suffix)
settings=module('addon_config').fb_settings();head=settings.get_head(0);loader=settings.loader();loader.load_model(0)
for i,camera in enumerate(head.cameras):camera.use_in_tex_baking=i==0
settings.tex_fill_gaps=True;settings.tex_uv_expand_percents=.5
material=module('utils.materials');status=material.bake_tex(0,head.preview_texture_name())
if not status.success:raise RuntimeError(status.error_message)
texture=bpy.data.images[head.preview_texture_name()];texture.filepath_raw=str(out/'head-texture.png');texture.file_format='PNG';texture.save();texture.pack()
# Use the unlit inspection material for pixel-faithful initial rig evaluation.
mat=bpy.data.materials.new('NOVA fitted skin texture');mat.use_nodes=True;nodes=mat.node_tree.nodes;nodes.clear();t=nodes.new('ShaderNodeTexImage');t.image=texture;e=nodes.new('ShaderNodeEmission');o=nodes.new('ShaderNodeOutputMaterial');mat.node_tree.links.new(t.outputs['Color'],e.inputs['Color']);mat.node_tree.links.new(e.outputs[0],o.inputs['Surface']);head.headobj.data.materials.clear();head.headobj.data.materials.append(mat)
bpy.context.view_layer.update()
reference=head.get_camera(0);camera=reference.camobj
camera_rotation=np.array(camera.matrix_world.to_quaternion().to_matrix())
front=np.array([[1,0,0],[0,0,-1],[0,1,0]])@camera_rotation.T
(out/'frontal-frame.json').write_text(json.dumps({'rotation':front.tolist(),'camera_origin':list(camera.matrix_world.translation),'camera_rotation':camera_rotation.tolist(),'camera_frame':[list(v) for v in camera.data.view_frame(scene=bpy.context.scene)]}))
shutil.copyfile(bpy.path.abspath(reference.cam_image.filepath),out/'reference.png')
builder=loader.get_builder()
def mesh_faces():
 mesh=builder.applied_args_model().mesh(0)
 return [tuple(mesh.face_point(i,j) for j in range(mesh.face_size(i))) for i in range(mesh.faces_count())]
faces=mesh_faces();mouth_index=list(builder.mask_names()).index('Mouth');enabled=builder.masks()[mouth_index]
try:
 builder.set_mask(mouth_index,False);remaining=set(mesh_faces())
finally:
 builder.set_mask(mouth_index,enabled)
(out/'mouth-mask.json').write_text(json.dumps({'faces_count':len(faces),'removed_faces':[i for i,face in enumerate(faces) if face not in remaining]}))
loader.save_fb_serial_and_image_pathes(0);bpy.ops.wm.save_as_mainfile(filepath=str(out/'head.blend'))
print('NOVA_RETEXTURE multiview geometry retained; closest reference texture selected',flush=True)
