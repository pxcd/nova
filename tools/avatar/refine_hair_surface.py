"""Fit a strand-preserving alpha cutout to the calibrated head surface."""
import json,math
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

def refine_hair(head,armature,root):
 fit=Path(root)/'.local/facebuilder/frontal-texture-v1';frame=json.loads((fit/'frontal-frame.json').read_text())
 rotation=np.array(frame['rotation']);scale=json.loads((Path(root)/'.local/facebuilder/rig-v30/report.json').read_text())['alignment_scale']
 # Infer the exact fit translation from unchanged forehead/nose vertices.
 with bpy.data.libraries.load(str(fit/'head.blend'),link=False) as (_,data):data.objects=['NOVA FaceBuilder head']
 raw=data.objects[0];source=np.array([v.co[:] for v in raw.data.shape_keys.key_blocks['Basis'].data]);base=np.array([v.co[:] for v in head.data.shape_keys.key_blocks['Basis'].data]);translation=np.median(base-source@rotation.T*scale,axis=0);bpy.data.objects.remove(raw,do_unlink=True)
 origin=scale*rotation@np.array(frame['camera_origin'])+translation;axes=rotation@np.array(frame['camera_rotation']);corners=np.array(frame['camera_frame'])
 surface=BVHTree.FromPolygons([v.co for v in head.data.vertices],[list(f.vertices) for f in head.data.polygons])
 image=bpy.data.images.load(str(Path(root)/'.local/facebuilder/reference-v3/hair.png'),check_existing=True);image.pack()
 width,height=image.size;alpha=np.array(image.pixels[:],dtype=np.float32).reshape(height,width,4)[:,:,3]
 vertices=[];uvs=[];faces=[];step=6;lookup={}
 # Keep an extra cell around every strand; alpha, not polygon edges, defines
 # the silhouette. This avoids the old binary-mask staircase at the ears.
 for row in range(0,height,step):
  for col in range(0,width,step):
   if np.max(alpha[max(0,row-step):min(height,row+step+1),max(0,col-step):min(width,col+step+1)])<.015:continue
   uv=np.array([col/(width-1),row/(height-1)])
   direction=axes@(corners[2]+(corners[1]-corners[2])*uv[0]+(corners[3]-corners[2])*uv[1]);direction/=np.linalg.norm(direction)
   point=origin+direction*((-.12-origin[1])/direction[1]);radial=(point[0]/.14)**2+((point[2]-1.63)/.19)**2
   depth=-.005-.135*math.sqrt(max(0,1-radial));point=origin+direction*((depth-origin[1])/direction[1])
   hit,_,_,distance=surface.ray_cast(Vector(origin),Vector(direction))
   if hit is not None and np.linalg.norm(point-origin)>distance-.003:point=np.array(hit)-direction*.003
   lookup[(row,col)]=len(vertices);vertices.append(point);uvs.append(uv)
 for row,col in lookup:
  for triangle in [((row,col),(row+step,col),(row,col+step)),((row,col+step),(row+step,col),(row+step,col+step))]:
   if all(key in lookup for key in triangle):faces.append(tuple(lookup[key] for key in triangle))
 mesh=bpy.data.meshes.new('NOVA strand-edge surface');mesh.from_pydata(vertices,[],faces);mesh.update();uv=mesh.uv_layers.new()
 for loop in mesh.loops:uv.data[loop.index].uv=uvs[loop.vertex_index]
 for poly in mesh.polygons:poly.use_smooth=True
 hair=bpy.data.objects.new('NOVA strand-edge surface',mesh);bpy.context.scene.collection.objects.link(hair)
 mat=bpy.data.materials.new('NOVA strand-edge hair');mat.use_nodes=True;shader=mat.node_tree.nodes.get('Principled BSDF');tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=image;shader.inputs['Base Color'].default_value=(0,0,0,1);shader.inputs['Emission Strength'].default_value=1;shader.inputs['Roughness'].default_value=1;shader.inputs['Specular IOR Level'].default_value=0;mat.node_tree.links.new(tex.outputs['Color'],shader.inputs['Emission Color']);mat.node_tree.links.new(tex.outputs['Alpha'],shader.inputs['Alpha']);mat.surface_render_method='DITHERED';mesh.materials.append(mat)
 group=hair.vertex_groups.new(name='Head');group.add(list(range(len(vertices))),1,'REPLACE');modifier=hair.modifiers.new('NOVA hair attachment','ARMATURE');modifier.object=armature;hair.parent=armature;hair.matrix_parent_inverse=armature.matrix_world.inverted()
 old=bpy.data.objects.get('NOVA calibrated photographic hair')
 if old:bpy.data.objects.remove(old,do_unlink=True)
 # Remove protruding ends of the old back groom below the photographed bob.
 back=bpy.data.objects.get('NOVA strand bob')
 if back:
  import bmesh
  bm=bmesh.new();bm.from_mesh(back.data);bm.verts.ensure_lookup_table();bmesh.ops.delete(bm,geom=[v for v in bm.verts if v.index>=23*96 or v.co.z<1.515],context='VERTS');bm.to_mesh(back.data);bm.free()
 return hair
