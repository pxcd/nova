"""Build a near-frontal appearance candidate, preserving all speech targets.

Matched lid appearances prevent photographing an iris onto closing lid skin.
This remains a photo-based reconstruction, not a relightable digital scan.
"""
import argparse,json,sys,shutil
from pathlib import Path
import bpy,numpy as np
p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);root=Path(__file__).resolve().parents[2];source=Path(a.source).resolve();out=Path(a.output).resolve()
if (out/'head.glb').exists() or (out/'rigged-head.blend').exists():raise RuntimeError('Use a new candidate directory')
out.mkdir(parents=True,exist_ok=True);bpy.ops.wm.open_mainfile(filepath=str(source/'rigged-head.blend'))
head=bpy.data.objects['NOVA fitted head'];armature=head.parent;fit=root/'.local/facebuilder/frontal-texture-v1';frame=json.loads((fit/'frontal-frame.json').read_text());rotation=np.array(frame['rotation']);scale=json.loads((source/'report.json').read_text())['alignment_scale']
with bpy.data.libraries.load(str(fit/'head.blend'),link=False) as (_,data):data.objects=['NOVA FaceBuilder head']
raw=data.objects[0];raw_base=np.array([v.co[:] for v in raw.data.shape_keys.key_blocks['Basis'].data]);base=np.array([v.co[:] for v in head.data.shape_keys.key_blocks['Basis'].data]);translation=np.median(base-raw_base@rotation.T*scale,axis=0);bpy.data.objects.remove(raw,do_unlink=True)
# The first fit clamped every vertex below a hard jaw-height cutoff. That
# creates a ledge under the chin. Restore the fit and taper the correction.
restored=raw_base@rotation.T*scale+translation
camera_rotation=np.array(frame['camera_rotation']);origin=np.array(frame['camera_origin']);corners=np.array(frame['camera_frame']);valid=np.load(fit/'neck-mask.npy').squeeze();height,width=valid.shape
camera=(raw_base-origin)@camera_rotation;plane=camera[:,:2]*(corners[0,2]/camera[:,2,None]);reference_uv=np.column_stack(((plane[:,0]-corners[2,0])/(corners[1,0]-corners[2,0]),(plane[:,1]-corners[2,1])/(corners[3,1]-corners[2,1])))
for i,point in enumerate(restored):
 if point[2]>=1.53:continue
 row=int(np.clip((1-reference_uv[i,1])*(height-1),0,height-1));choices=np.flatnonzero(valid[row])
 if not len(choices):continue
 target=np.clip(reference_uv[i,0],choices[0]/(width-1),choices[-1]/(width-1));plane_x=corners[2,0]+target*(corners[1,0]-corners[2,0]);camera_x=plane_x*camera[i,2]/corners[0,2]
 weight=float(np.clip((1.53-point[2])/.04,0,1));weight=weight*weight*(3-2*weight)
 restored[i]+=weight*scale*(rotation@camera_rotation[:,0])*(camera_x-camera[i,0])
correction=restored-base
for key in head.data.shape_keys.key_blocks:
 points=np.array([v.co[:] for v in key.data]);key.data.foreach_set('co',(points+correction).ravel())
base=restored;head.data.vertices.foreach_set('co',base.ravel())
closed=base.copy()
for name in ['eyeBlinkLeft','eyeBlinkRight']:closed+=np.array([v.co[:] for v in head.data.shape_keys.key_blocks[name].data])-base
camera_rotation=np.array(frame['camera_rotation']);origin=np.array(frame['camera_origin']);corners=np.array(frame['camera_frame'])
def project(points):
 raw=(points-translation)@rotation/scale;camera=(raw-origin)@camera_rotation;plane=camera[:,:2]*(corners[0,2]/camera[:,2,None])
 return np.column_stack(((plane[:,0]-corners[2,0])/(corners[1,0]-corners[2,0]),(plane[:,1]-corners[2,1])/(corners[3,1]-corners[2,1])))
uv=project(base);closed_uv=project(closed);
for loop in head.data.loops:head.data.uv_layers.active.data[loop.index].uv=uv[loop.vertex_index]
landmarks=json.loads((root/'.local/facebuilder/reference-v2/landmarks.json').read_text());masks=[]
for index in [473,468]:
 center=np.array([landmarks[index][0],1-landmarks[index][1]]);radius=np.sqrt(np.sum(((uv-center)/np.array([.085,.040]))**2,axis=1));weight=np.clip((1-radius)/.35,0,1);masks.append(weight*weight*(3-2*weight))
for name,values in [('_NOVA_CLOSED_UV',closed_uv),('_NOVA_EYE_MASK',np.column_stack(masks))]:
 attribute=head.data.attributes.new(name=name,type='FLOAT2',domain='POINT');attribute.data.foreach_set('vector',values.astype(np.float32).ravel())
# The underside of the chin needs attenuation; the frontal photograph cannot
# describe its occluded lighting. Keep the correction off the lips/cheeks.
head.data.update()
for previous in list(head.data.color_attributes):head.data.color_attributes.remove(previous)
colors=head.data.color_attributes.new(name='NOVA underside shading',type='FLOAT_COLOR',domain='CORNER')
for poly in head.data.polygons:
 for loop_index in poly.loop_indices:
  vertex=head.data.vertices[head.data.loops[loop_index].vertex_index];z=vertex.co.z
  window=np.clip((z-1.505)/.009,0,1)*np.clip((1.549-z)/.012,0,1)
  darkness=.85*max(0,-vertex.normal.z)**.5*window;value=1-darkness
  colors.data[loop_index].color=(value,value,value,1)
head.data.color_attributes.active_color=colors
sys.path.insert(0,str(Path(__file__).parent));from refine_hair_surface import refine_hair
refine_hair(head,armature,root)
for obj in bpy.data.objects:
 if obj.type=='MESH' and obj.name.startswith('Wolf3D_Outfit'):
  for material in obj.data.materials:
   shader=material.node_tree.nodes.get('Principled BSDF')
   if shader:shader.inputs['Base Color'].default_value=(.003,.004,.005,1);shader.inputs['Specular IOR Level'].default_value=.08
shutil.copyfile(root/'.local/facebuilder/reference-v3/bare-lids.png',out/'closed-lids.png')
bpy.ops.wm.save_as_mainfile(filepath=str(out/'rigged-head.blend'));bpy.ops.object.select_all(action='DESELECT');armature.select_set(True)
for obj in bpy.data.objects:
 if obj.type=='MESH' and obj.parent==armature:obj.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(out/'head.glb'),use_selection=True,export_format='GLB',export_morph=True,export_morph_normal=True,export_attributes=True,export_skins=True,export_animations=False,export_cameras=False,export_lights=False)
(out/'report.json').write_text(json.dumps({'source':str(source),'changes':['Registered closed-lid appearance attributes','Strand-preserving photographic hair alpha','Under-chin attenuation'],'limitations':['Near-frontal photo-based reconstruction','Reference lighting remains baked in','Not a fully relightable digital human']},indent=2))
