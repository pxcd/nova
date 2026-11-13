"""Build a fitted FaceBuilder conversation rig with the existing speech driver.

Operates in a separate Blender process; never modifies the reference GLB or
FaceBuilder fit. Native FACS shapes produce the phoneme targets; original speech timing is retained.
"""
import bpy,sys,argparse,json,hashlib
from pathlib import Path
import numpy as np
from mathutils import Matrix
p=argparse.ArgumentParser();p.add_argument('--fit',required=True);p.add_argument('--output',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
ROOT=Path(__file__).resolve().parents[2];out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
if (out/'head.glb').exists() or (out/'rigged-head.blend').exists():raise RuntimeError('Use a new output directory; existing model will not be overwritten')
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=str(ROOT/'public/avatar/talkinghead/reference.glb'))
reference=bpy.data.objects['Wolf3D_Head'];armature=next(o for o in bpy.data.objects if o.type=='ARMATURE');bpy.context.view_layer.update()
def xyz(obj,shape='Basis'):
 key=obj.data.shape_keys.key_blocks[shape];data=np.empty((len(key.data),3),dtype=np.float64);key.data.foreach_get('co',data.ravel());m=np.array(obj.matrix_world);return data@m[:3,:3].T+m[:3,3]
def anchor(obj,shape):
 base=xyz(obj);delta=xyz(obj,shape)-base;w=np.linalg.norm(delta,axis=1);return (base*w[:,None]).sum(0)/w.sum()
ref=xyz(reference)
with bpy.data.libraries.load(str(Path(a.fit)/'head.blend'),link=False) as (available,data):data.objects=['NOVA FaceBuilder head']
head=data.objects[0];bpy.context.scene.collection.objects.link(head);bpy.context.view_layer.update()
features=['eyeBlinkLeft','eyeBlinkRight','mouthClose']
x=np.array([anchor(head,n) for n in features]);y=np.array([anchor(reference,n) for n in features]);cx=x.mean(0);cy=y.mean(0);u,s,vt=np.linalg.svd((x-cx).T@(y-cy));rotation=vt.T@u.T
if np.linalg.det(rotation)<0:vt[-1]*=-1;rotation=vt.T@u.T
scale=s.sum()/np.sum((x-cx)**2)
# Use the fitted frontal camera, not cartoon anchor depths, to define facing.
rotation=np.array(json.loads((Path(a.fit)/'frontal-frame.json').read_text())['rotation'])
translation=y[2]-scale*rotation@x[2]
for key in head.data.shape_keys.key_blocks:
 v=xyz(head,key.name);v=v@rotation.T*scale+translation
 key.data.foreach_set('co',v.ravel());key.value=0
head.matrix_world=Matrix.Identity(4);base=xyz(head);head.data.vertices.foreach_set('co',base.ravel())
# Keep the approved cue scheduler, using the new head's authored anatomy.
sys.path.insert(0,str(Path(__file__).parent))
from facebuilder_visemes import add_visemes
transferred=add_visemes(head)
teeth=bpy.data.objects['Wolf3D_Teeth'];add_visemes(teeth,allow_subset=True)
# The sample's large dental rows need anatomical sizing on this fitted face.
tb=xyz(teeth);jd=xyz(teeth,'jawOpen')-tb;lower=jd[:,2]<-.0001;resized=tb.copy()
for selected,factor,offset in [(lower,.45,-.010),(~lower,1.0,0)]:
 if not np.any(selected):continue
 center=(tb[selected,2].min()+tb[selected,2].max())/2;resized[selected,2]=center+(tb[selected,2]-center)*factor+offset
inverse=np.array(teeth.matrix_world.inverted())
for key in teeth.data.shape_keys.key_blocks:
 points=resized+(xyz(teeth,key.name)-tb);local=points@inverse[:3,:3].T+inverse[:3,3];key.data.foreach_set('co',local.ravel())
for original in list(teeth.data.materials):
 mat=original.copy();shader=mat.node_tree.nodes.get('Principled BSDF')
 if shader:
  socket=shader.inputs['Base Color']
  if socket.is_linked:
   source=socket.links[0].from_socket;tint=mat.node_tree.nodes.new('ShaderNodeMixRGB');tint.blend_type='MULTIPLY';tint.inputs[0].default_value=1;tint.inputs[2].default_value=(.72,.68,.62,1);mat.node_tree.links.new(source,tint.inputs[1]);mat.node_tree.links.new(tint.outputs[0],socket)
  shader.inputs['Roughness'].default_value=.8;shader.inputs['Specular IOR Level'].default_value=.15
 teeth.data.materials[teeth.data.materials.find(original.name)]=mat
head.name='NOVA fitted head';head.data.name='NOVA FaceBuilder fitted surface'
# Bind the neck gradually to existing chest/neck/head bones.
groups={name:head.vertex_groups.new(name=name) for name in ['Head','Neck','Spine2']}
for i,v in enumerate(base):
 h=float(np.clip((v[2]-1.47)/.035,0,1));h=h*h*(3-2*h);chest=float(np.clip((1.48-v[2])/.05,0,1))*(1-h);neck=1-h-chest
 for name,w in [('Head',h),('Neck',neck),('Spine2',chest)]:
  if w>0:groups[name].add([i],w,'REPLACE')
modifier=head.modifiers.new('NOVA inherited head rig','ARMATURE');modifier.object=armature
head.parent=armature;head.matrix_parent_inverse=armature.matrix_world.inverted()
# Keep the approved teeth mesh and rig. The fitted head supplies its own eyes.
for name in ['Wolf3D_Head','Wolf3D_Hair','Wolf3D_Glasses','EyeLeft','EyeRight']:
 if name in bpy.data.objects:bpy.data.objects.remove(bpy.data.objects[name],do_unlink=True)
for obj in bpy.data.objects:
 if obj.type=='MESH' and obj.name.startswith('Wolf3D_Outfit'):
  mat=bpy.data.materials.new('NOVA charcoal clothing');mat.diffuse_color=(.025,.035,.035,1);mat.use_nodes=True;mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.025,.035,.035,1);mat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.95;obj.data.materials.clear();obj.data.materials.append(mat)
from facebuilder_surface import fit_neck
fit_neck(head,a.fit,rotation,scale,translation)
# Build an actual strand surface instead of distorting a stock hair shell.
sys.path.insert(0,str(Path(__file__).parent))
from facebuilder_hair import build_hair,build_photographic_hair
hair=build_hair(armature)
build_photographic_hair(armature,head,a.fit,rotation,scale,translation)
# Keep FaceBuilder's own gaze/blink geometry. TalkingHead animates ARKit
# eyeLook shapes, not eye-bone rotations; the native surfaces already match it.
# Build a recessed oral tunnel from the native mouth boundary. Its facial
# targets follow the lips exactly while leaving the reference teeth in front.
mask=json.loads((Path(a.fit)/'mouth-mask.json').read_text());cap=set(mask['removed_faces'])
if mask['faces_count']!=len(head.data.polygons):raise RuntimeError('Mouth mask topology mismatch')
cap_faces=[tuple(head.data.polygons[i].vertices) for i in sorted(cap)];ids=sorted({v for face in cap_faces for v in face});index={v:i for i,v in enumerate(ids)};count=len(ids)
edges={}
for face in cap_faces:
 for i,a0 in enumerate(face):
  edge=tuple(sorted((a0,face[(i+1)%len(face)])));edges[edge]=edges.get(edge,0)+1
boundary=[edge for edge,n in edges.items() if n==1]
def oral_points(key):
 front=np.array([key.data[i].co[:] for i in ids]);back=front.copy();center=front.mean(0);back[:,[0,2]]=center[[0,2]]+(back[:,[0,2]]-center[[0,2]])*1.08;back[:,1]+=.050
 return np.concatenate([front,back])
points=oral_points(head.data.shape_keys.key_blocks['Basis']);faces=[tuple(index[v]+count for v in face) for face in cap_faces]
faces.extend((index[a0],index[b0],index[b0]+count,index[a0]+count) for a0,b0 in boundary)
mesh=bpy.data.meshes.new('NOVA authored oral tunnel');mesh.from_pydata(points,[],faces);mesh.update();cavity=bpy.data.objects.new('NOVA authored oral tunnel',mesh);bpy.context.scene.collection.objects.link(cavity);cavity.shape_key_add(name='Basis')
for key in head.data.shape_keys.key_blocks:
 if key.name=='Basis':continue
 target=cavity.shape_key_add(name=key.name);target.data.foreach_set('co',oral_points(key).ravel());target.value=0
oral=bpy.data.materials.new('NOVA oral interior');oral.use_nodes=True;shader=oral.node_tree.nodes['Principled BSDF'];shader.inputs['Base Color'].default_value=(.006,.0015,.0015,1);shader.inputs['Roughness'].default_value=1;shader.inputs['Specular IOR Level'].default_value=0;mesh.materials.append(oral)
group=cavity.vertex_groups.new(name='Head');group.add(list(range(len(points))),1,'REPLACE');modifier=cavity.modifiers.new('NOVA oral attachment','ARMATURE');modifier.object=armature;cavity.parent=armature;cavity.matrix_parent_inverse=armature.matrix_world.inverted()
import bmesh
bm=bmesh.new();bm.from_mesh(head.data);bm.faces.ensure_lookup_table();bmesh.ops.delete(bm,geom=[bm.faces[i] for i in cap],context='FACES_ONLY');bm.to_mesh(head.data);bm.free()
bpy.context.view_layer.objects.active=head;head.select_set(True)
bpy.ops.wm.save_as_mainfile(filepath=str(out/'rigged-head.blend'))
bpy.ops.object.select_all(action='DESELECT')
armature.select_set(True)
for obj in bpy.data.objects:
 if obj.type=='MESH' and obj.parent==armature:obj.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(out/'head.glb'),use_selection=True,export_format='GLB',export_morph=True,export_morph_normal=True,export_skins=True,export_animations=False,export_cameras=False,export_lights=False)
report={'source_fit':Path(a.fit).name,'alignment_scale':float(scale),'cartoon_reference_anchor_offsets_m':np.linalg.norm((x@rotation.T*scale+translation)-y,axis=1).tolist(),'vertices':len(base),'native_facs':51,'viseme_names':transferred,'viseme_method':'native_ARKit_composition','orientation':'fitted_frontal_camera','model_sha256':hashlib.sha256((out/'head.glb').read_bytes()).hexdigest(),'limitations':['Eye/mouth and hair visual review pending','Reference lighting remains baked into skin texture','Photographic hair shell and back groom are intended for near-frontal views','Live root application is unchanged']}
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('NOVA_RIG_REPORT '+json.dumps(report),flush=True)
