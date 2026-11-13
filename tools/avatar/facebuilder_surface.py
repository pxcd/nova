"""Fit the lower head surface to the calibrated reference neck silhouette."""
from pathlib import Path
import json
import numpy as np
import bpy

def fit_neck(head, fit, rotation, scale, translation):
 fit=Path(fit);frame=json.loads((fit/'frontal-frame.json').read_text());valid=np.load(fit/'neck-mask.npy').squeeze();height,width=valid.shape
 camera_rotation=np.array(frame['camera_rotation']);origin=np.array(frame['camera_origin']);corners=np.array(frame['camera_frame'])
 def project(points):
  raw=(points-translation)@rotation/scale;camera=(raw-origin)@camera_rotation
  plane=camera[:,:2]*(corners[0,2]/camera[:,2,None])
  return np.column_stack(((plane[:,0]-corners[2,0])/(corners[1,0]-corners[2,0]),(plane[:,1]-corners[2,1])/(corners[3,1]-corners[2,1]))),camera
 base=np.array([v.co[:] for v in head.data.shape_keys.key_blocks['Basis'].data]);uv,camera=project(base);delta=np.zeros_like(base)
 for i,p in enumerate(base):
  if p[2]>=1.53:continue
  row=int(np.clip((1-uv[i,1])*(height-1),0,height-1));col=int(np.clip(uv[i,0]*(width-1),0,width-1))
  choices=np.flatnonzero(valid[row])
  if not len(choices):continue
  if choices[0]<=col<=choices[-1]:continue
  target=np.clip(col,choices[0],choices[-1])/(width-1);plane_x=corners[2,0]+target*(corners[1,0]-corners[2,0]);camera_x=plane_x*camera[i,2]/corners[0,2]
  delta[i]=scale*(rotation@camera_rotation[:,0])*(camera_x-camera[i,0])
 for key in head.data.shape_keys.key_blocks:
  points=np.array([v.co[:] for v in key.data]);key.data.foreach_set('co',(points+delta).ravel())
 base+=delta;head.data.vertices.foreach_set('co',base.ravel());uv,_=project(base)
 layer=head.data.uv_layers.new(name='NOVA reference neck')
 for loop in head.data.loops:layer.data[loop.index].uv=uv[loop.vertex_index]
 head.data.uv_layers[0].active_render=True;head.data.uv_layers.active_index=0
 mat=bpy.data.materials.new('NOVA cleaned photo albedo');mat.use_nodes=True;nodes=mat.node_tree.nodes;nodes.clear();tex=nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(fit/'reference.png'),check_existing=True);tex.image.pack();coords=nodes.new('ShaderNodeUVMap');coords.uv_map=layer.name;mat.node_tree.links.new(coords.outputs['UV'],tex.inputs['Vector']);output=nodes.new('ShaderNodeOutputMaterial');mat.node_tree.links.new(tex.outputs['Color'],output.inputs['Surface'])
 head.data.materials.clear();head.data.materials.append(mat)
 for face in head.data.polygons:face.material_index=0
 for old in list(head.data.uv_layers):
  if old.name!=layer.name:head.data.uv_layers.remove(old)
 head.data.uv_layers.active_index=0;head.data.uv_layers[0].active_render=True;head.data.update()
