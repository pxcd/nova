"""Deterministic strand groom for the isolated FaceBuilder candidate."""
import bpy, math
import numpy as np
from mathutils import Vector

def build_hair(armature, seed=42):
 rng=np.random.default_rng(seed);vertices=[];faces=[];materials=[]
 center=np.array([0,-.035,1.66]);radii=np.array([.104,.112,.107])
 def surface(theta,phi,offset=0):
  p=center+(radii+offset)*np.array([math.sin(theta)*math.cos(phi),math.sin(theta)*math.sin(phi),math.cos(theta)])
  if theta>math.pi/2:p[2]=center[2]-(theta-math.pi/2)*.20
  return p
 # A dark underlayer prevents tiny strand gaps from revealing missing scalp UVs.
 rows,cols=22,96
 for row in range(rows+1):
  for col in range(cols):
   phi=2*math.pi*col/cols;front=max(0,-math.sin(phi));end=2.18-.73*front**2
   vertices.append(surface(.01+(end-.01)*row/rows,phi).tolist())
 for row in range(rows):
  for col in range(cols):
   a=row*cols+col;b=row*cols+(col+1)%cols
   if sum(vertices[i][1] for i in [a,b,a+cols,b+cols])/4<center[1]:continue
   faces.extend([(a,b,b+cols),(a,b+cols,a+cols)]);materials.extend([0,0])
 # Each tapered strand has its own surface normal/highlight, rather than a
 # texture painted across a handful of broad hair polygons.
 count,steps,sides=2600,25,3
 for strand in range(count):
  phi=rng.uniform(0,2*math.pi)
  if math.sin(phi)<-.08:continue
  front=max(0,-math.sin(phi));end=2.20-.74*front**2+rng.normal(0,.045)
  start=rng.uniform(.025,.7);layer=rng.uniform(.0003,.007);width=rng.uniform(.00012,.00024)
  points=[]
  for step in range(steps):
   t=step/(steps-1);theta=start+(end-start)*t;angle=phi+.08*math.sin(math.pi*t)+.018*math.sin(t*7+strand)
   p=surface(theta,angle,layer)
   p[0]-=.024*(1-t)**2
   p[0]*=1-.055*t**8
   p[1]+=.003*math.sin(t*8+strand)*t
   points.append(p)
  start_index=len(vertices)
  for step,p in enumerate(points):
   tangent=points[min(step+1,steps-1)]-points[max(0,step-1)];tangent/=max(np.linalg.norm(tangent),1e-9)
   radial=p-center;radial/=np.linalg.norm(radial);normal=np.cross(tangent,radial)
   if np.linalg.norm(normal)<1e-6:normal=np.cross(tangent,np.array([1,0,0]))
   normal/=np.linalg.norm(normal);binormal=np.cross(tangent,normal)
   taper=min(1,(steps-step)/4)
   for side in range(sides):
    a=2*math.pi*side/sides;vertices.append((p+width*taper*(normal*math.cos(a)+binormal*math.sin(a))).tolist())
  color=1+int(rng.integers(0,8))
  for step in range(steps-1):
   for side in range(sides):
    a=start_index+step*sides+side;b=start_index+step*sides+(side+1)%sides
    faces.extend([(a,b,b+sides),(a,b+sides,a+sides)]);materials.extend([color,color])
 mesh=bpy.data.meshes.new('NOVA strand bob');mesh.from_pydata(vertices,[],faces);mesh.update()
 hair=bpy.data.objects.new('NOVA strand bob',mesh);bpy.context.scene.collection.objects.link(hair)
 for index in range(9):
  mat=bpy.data.materials.new('NOVA brown strand '+str(index));mat.use_nodes=True;shader=mat.node_tree.nodes['Principled BSDF']
  value=.024 if index==0 else .035+.009*index
  shader.inputs['Base Color'].default_value=(value,value*.60,value*.33,1);shader.inputs['Roughness'].default_value=.38 if index else .7
  mesh.materials.append(mat)
 for face,material in zip(mesh.polygons,materials):face.material_index=material;face.use_smooth=True
 group=hair.vertex_groups.new(name='Head');group.add(list(range(len(vertices))),1,'REPLACE');modifier=hair.modifiers.new('NOVA strand attachment','ARMATURE');modifier.object=armature
 hair.parent=armature;hair.matrix_parent_inverse=armature.matrix_world.inverted()
 return hair

def build_photographic_hair(armature, head, fit, rotation, scale, translation):
 """Project the unchanged frontal reference onto a curved, segmented hair shell."""
 import json
 from pathlib import Path
 from mathutils.bvhtree import BVHTree
 fit=Path(fit);frame=json.loads((fit/'frontal-frame.json').read_text());mask=np.load(fit/'hair-mask.npy').squeeze();height,width=mask.shape
 origin=scale*rotation@np.array(frame['camera_origin'])+translation
 axes=rotation@np.array(frame['camera_rotation']);corners=np.array(frame['camera_frame'])
 vertices=[];uvs=[];lookup={};step=2
 surface=BVHTree.FromPolygons([v.co for v in head.data.vertices],[list(face.vertices) for face in head.data.polygons])
 for row in range(0,height,step):
  for col in range(0,width,step):
   if not mask[row,col]:continue
   uv=np.array([col/(width-1),1-row/(height-1)])
   direction=axes@(corners[2]+(corners[1]-corners[2])*uv[0]+(corners[3]-corners[2])*uv[1])
   point=origin+direction*((-.12-origin[1])/direction[1])
   radial=(point[0]/.14)**2+((point[2]-1.63)/.19)**2
   depth=-.005-.135*math.sqrt(max(0,1-radial))
   point=origin+direction*((depth-origin[1])/direction[1])
   hit,normal,face_index,distance=surface.ray_cast(Vector(origin),Vector(direction).normalized())
   if hit is not None:
    weight=np.clip((.080-abs(point[0]))/.020,0,1)*np.clip((point[2]-1.63)/.020,0,1)
    point=point*(1-weight)+np.array(hit+normal*.0015)*weight
   lookup[(row,col)]=len(vertices);vertices.append(point.tolist());uvs.append(uv)
 faces=[]
 for row,col in lookup:
  for triangle in [((row,col),(row+step,col),(row,col+step)),((row,col+step),(row+step,col),(row+step,col+step))]:
   if all(key in lookup for key in triangle):faces.append(tuple(lookup[key] for key in triangle))
 mesh=bpy.data.meshes.new('NOVA calibrated photographic hair');mesh.from_pydata(vertices,[],faces);mesh.update();uv=mesh.uv_layers.new()
 for loop in mesh.loops:uv.data[loop.index].uv=uvs[loop.vertex_index]
 for face in mesh.polygons:face.use_smooth=True
 hair=bpy.data.objects.new('NOVA calibrated photographic hair',mesh);bpy.context.scene.collection.objects.link(hair)
 mat=bpy.data.materials.new('NOVA photographic hair');mat.use_nodes=True;nodes=mat.node_tree.nodes;nodes.clear();tex=nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(fit/'reference.png'),check_existing=True);tex.image.pack();output=nodes.new('ShaderNodeOutputMaterial');mat.node_tree.links.new(tex.outputs['Color'],output.inputs['Surface']);mesh.materials.append(mat)
 group=hair.vertex_groups.new(name='Head');group.add(list(range(len(vertices))),1,'REPLACE');modifier=hair.modifiers.new('NOVA photographic hair attachment','ARMATURE');modifier.object=armature;hair.parent=armature;hair.matrix_parent_inverse=armature.matrix_world.inverted()
 return hair
