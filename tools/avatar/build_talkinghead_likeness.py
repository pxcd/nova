"""Adapt the approved reference rig to NOVA's locally fitted portrait.

Keeps the authored topology, skinning, oral geometry and all expression targets.
This is an experimental landmark fit, not a calibrated scan or finished sculpt.
The portrait itself is unchanged; the preview projects it onto the fitted surface.
"""
from pathlib import Path
import hashlib, json, struct
import numpy as np
from scipy.interpolate import RBFInterpolator
from scipy.spatial import cKDTree, ConvexHull

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'.local/avatar-models'
OUT=ROOT/'public/avatar/talkinghead'
source=OUT/'reference.glb'
b=source.read_bytes();size=struct.unpack_from('<I',b,12)[0]
g=json.loads(b[20:20+size]);blob=bytearray(b[28+size:])
fit=np.load(DATA/'reference-fit.npz');src=fit['landmarks'][:468]
base=np.load(DATA/'rig-front-fit.npy')[:468]
# The fitting view is orthographic, 0.4 m high, centred at y=1.60.
xy=np.column_stack(((base[:,0]-.5)*.4*1280/720,1.6+(.5-base[:,1])*.4))
center=src[[33,263],:2].mean(0);anchor=xy[[33,263]].mean(0)
scale=(xy[263,0]-xy[33,0])/(src[263,0]-src[33,0])
target=np.column_stack(((src[:,0]-center[0])*scale+anchor[0],(center[1]-src[:,1])*scale*float(fit['height']/fit['width'])+anchor[1]))
warp=RBFInterpolator(xy,target-xy,kernel='thin_plate_spline',smoothing=1e-6,neighbors=48)
project=RBFInterpolator(xy,src[:,:2],kernel='thin_plate_spline',smoothing=1e-7,neighbors=48)

def read(i):
 a=g['accessors'][i];v=g['bufferViews'][a['bufferView']]
 widths={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}
 dtypes={5126:'<f4',5125:'<u4',5123:'<u2',5121:'u1'}
 dtype=np.dtype(dtypes[a['componentType']]);w=widths[a['type']]
 return np.ndarray((a['count'],w),dtype=dtype,buffer=blob,offset=v.get('byteOffset',0)+a.get('byteOffset',0),strides=(v.get('byteStride',dtype.itemsize*w),dtype.itemsize)).copy()

def append(array,kind,component=5126):
 array=np.ascontiguousarray(array,dtype='<f4' if component==5126 else '<u4')
 while len(blob)%4:blob.append(0)
 off=len(blob);blob.extend(array.tobytes());g['bufferViews'].append({'buffer':0,'byteOffset':off,'byteLength':array.nbytes,'target':34962})
 a={'bufferView':len(g['bufferViews'])-1,'componentType':component,'count':len(array),'type':kind}
 if kind=='VEC3':a.update(min=array.min(0).tolist(),max=array.max(0).tolist())
 g['accessors'].append(a);return len(g['accessors'])-1

def deform(p):
 # Blend into the untouched neck and back of the head.
 weight=np.clip((p[:,2]-.025)/.07,0,1)*np.clip((p[:,1]-1.46)/.07,0,1)
 delta=np.clip(warp(p[:,:2]),-.025,.025)*weight[:,None]
 result=p.copy();result[:,:2]+=delta
 return result

def normals(p,tri):
 n=np.zeros_like(p);cross=np.cross(p[tri[:,1]]-p[tri[:,0]],p[tri[:,2]]-p[tri[:,0]])
 for j in range(3):np.add.at(n,tri[:,j],cross)
 return n/np.maximum(np.linalg.norm(n,axis=1,keepdims=True),1e-9)

hull=ConvexHull(src[:,:2]*[1,1.5])
records=[]
for mesh in g['meshes']:
 name=mesh['name']
 if name not in ['Wolf3D_Head','Wolf3D_Teeth','EyeLeft','EyeRight']:continue
 for prim in mesh['primitives']:
  old=read(prim['attributes']['POSITION']);oldn=read(prim['attributes']['NORMAL']);p=deform(old)
  tri=read(prim['indices']).reshape(-1,3).astype(int);n=normals(p,tri)
  # A local Jacobian transfers authored speech displacements through the fit.
  jac=np.zeros((len(old),3,3));eps=1e-4
  for axis in range(3):
   shifted=old.copy();shifted[:,axis]+=eps;jac[:,:,axis]=(deform(shifted)-p)/eps
  prim['attributes']['POSITION']=append(p,'VEC3');prim['attributes']['NORMAL']=append(n,'VEC3')
  prim['attributes'].pop('TANGENT',None)
  for morph in prim.get('targets',[]):
   delta=read(morph['POSITION']);newdelta=np.einsum('nij,nj->ni',jac,delta)
   morph['POSITION']=append(newdelta,'VEC3')
   if 'NORMAL'in morph:morph['NORMAL']=append(normals(p+newdelta,tri)-n,'VEC3')
   morph.pop('TANGENT',None)
  if name!='Wolf3D_Teeth':
   uv=project(old[:,:2]);dist=-(uv*[1,1.5])@hull.equations[:,:2].T-hull.equations[:,2]
   inside=np.clip(dist.min(1)/.022,0,1)
   mask=inside*np.clip((old[:,2]-.08)/.025,0,1)*np.clip((oldn[:,2]-.05)/.45,0,1)
   sx=np.clip((uv[:,0]*fit['width']).astype(int),0,int(fit['width'])-1)
   sy=np.clip((uv[:,1]*fit['height']).astype(int),0,int(fit['height'])-1)
   mask *= np.isin(fit['segments'].squeeze()[sy,sx],[1,3])
   if name.startswith('Eye'):mask[:]=1
   prim['attributes']['_NOVA_FACE_UV']=append(uv,'VEC2')
   prim['attributes']['_NOVA_FACE_MASK']=append(mask[:,None],'SCALAR')
  records.append({'mesh':name,'vertices':len(p),'morphs':len(prim.get('targets',[])),'max_fit_displacement_m':float(np.linalg.norm(p-old,axis=1).max())})
# Reuse the approved portrait's hair as a curved, segmented surface, attached to
# the existing head joint. It remains a near-frontal study, not a hair sculpt.
segments=fit['segments'].squeeze();H,W=segments.shape;step=2
xs=np.arange(0,W,step);ys=np.arange(0,H,step);uu,vv=np.meshgrid(xs/W,ys/H);uv=np.column_stack((uu.ravel(),vv.ravel()))
valid=segments[np.minimum((uv[:,1]*H).astype(int),H-1),np.minimum((uv[:,0]*W).astype(int),W-1)]==1
hair=np.column_stack(((uv[:,0]-center[0])*scale+anchor[0],(center[1]-uv[:,1])*scale*H/W+anchor[1],np.zeros(len(uv))))
radial=(hair[:,0]/.14)**2+((hair[:,1]-1.64)/.21)**2
hair[:,2]=.075+.09*np.sqrt(np.clip(1-radial,0,1))
tri=[];cols=len(xs)
for row in range(len(ys)-1):
 for col in range(cols-1):
  i=row*cols+col
  for t in [[i,i+cols,i+1],[i+1,i+cols,i+cols+1]]:
   if valid[t].all():tri.append(t)
tri=np.array(tri);used=np.unique(tri);remap=np.full(len(uv),-1);remap[used]=np.arange(len(used));tri=remap[tri]
hair=hair[used];uv=uv[used]
portrait=(ROOT/'public/avatar/assets/nova-call-neutral-v2.png').read_bytes()
while len(blob)%4:blob.append(0)
off=len(blob);blob.extend(portrait);g['bufferViews'].append({'buffer':0,'byteOffset':off,'byteLength':len(portrait)})
g['images'].append({'bufferView':len(g['bufferViews'])-1,'mimeType':'image/png'})
g['textures'].append({'source':len(g['images'])-1,'sampler':0})
g['materials'].append({'name':'NOVA portrait hair','doubleSided':True,'pbrMetallicRoughness':{'baseColorTexture':{'index':len(g['textures'])-1},'metallicFactor':0,'roughnessFactor':1}})
headnode=next(i for i,x in enumerate(g['nodes']) if x.get('name')=='Head')
headmeshnode=next(x for x in g['nodes'] if x.get('name')=='Wolf3D_Head')
skin=headmeshnode['skin'];headjoint=g['skins'][skin]['joints'].index(headnode)
joints=np.zeros((len(hair),4));joints[:,0]=headjoint;weights=np.zeros_like(joints);weights[:,0]=1
indices=append(tri.reshape(-1,1),'SCALAR',5125);g['bufferViews'][g['accessors'][indices]['bufferView']]['target']=34963
attrs={'POSITION':append(hair,'VEC3'),'NORMAL':append(normals(hair,tri),'VEC3'),'TEXCOORD_0':append(uv,'VEC2'),'JOINTS_0':append(joints,'VEC4',5125),'WEIGHTS_0':append(weights,'VEC4')}
# Joint indices must be unsigned short rather than unsigned int in glTF.
a=g['accessors'][attrs['JOINTS_0']];arr=joints.astype('<u2')
while len(blob)%4:blob.append(0)
off=len(blob);blob.extend(arr.tobytes());g['bufferViews'].append({'buffer':0,'byteOffset':off,'byteLength':arr.nbytes,'target':34962});a['bufferView']=len(g['bufferViews'])-1;a['componentType']=5123
g['meshes'].append({'name':'NOVA hair study','primitives':[{'attributes':attrs,'indices':indices,'material':len(g['materials'])-1}]})
g['nodes'].append({'name':'NOVA hair study','mesh':len(g['meshes'])-1,'skin':skin});g['scenes'][g.get('scene',0)]['nodes'].append(len(g['nodes'])-1)
# The sample glasses are not part of NOVA's likeness. Keep the original rig file intact.
for node in g['nodes']:
 if node.get('name')=='Wolf3D_Glasses':node.pop('mesh',None);node.pop('skin',None)
# A shortened opaque hair cap closes the side/back gaps behind the portrait hair.
hairmesh=next(m for m in g['meshes'] if m['name']=='Wolf3D_Hair')
g['materials'].append({'name':'Brown hair backing','doubleSided':True,'pbrMetallicRoughness':{'baseColorFactor':[.11,.075,.04,1],'metallicFactor':0,'roughnessFactor':1}})
for prim in hairmesh['primitives']:
 points=read(prim['attributes']['POSITION']);triangles=read(prim['indices']).reshape(-1,3).astype(int)
 triangles=triangles[((points[triangles,1]>1.52)&(points[triangles,2]<.065)).all(1)]
 idx=append(triangles.reshape(-1,1),'SCALAR',5125);g['bufferViews'][g['accessors'][idx]['bufferView']]['target']=34963
 prim['indices']=idx;prim['material']=len(g['materials'])-1
g['asset']['generator']='NOVA TalkingHead landmark fit prototype'
g['extras']={'novaLikeness':{'sourcePortrait':'../assets/nova-call-neutral-v2.png','originalRig':'reference.glb','limitations':'Experimental fitted head; projected portrait; reference body remains; portrait hair is a curved surface. Not a finished realistic sculpt.'}}
g['buffers'][0]['byteLength']=len(blob)
j=json.dumps(g,separators=(',',':')).encode();j+=b' '*((-len(j))%4);blob+=b'\0'*((-len(blob))%4)
result=b'glTF'+struct.pack('<II',2,28+len(j)+len(blob))+struct.pack('<I4s',len(j),b'JSON')+j+struct.pack('<I4s',len(blob),b'BIN\0')+blob
path=OUT/'nova-rig-study.glb';path.write_bytes(result)
metadata={'kind':'Experimental NOVA likeness on the reference facial rig','model_sha256':hashlib.sha256(result).hexdigest(),'reference_sha256':hashlib.sha256(b).hexdigest(),'portrait_sha256':hashlib.sha256((ROOT/'public/avatar/assets/nova-call-neutral-v2.png').read_bytes()).hexdigest(),'meshes':records,'license':'Derivative of CC BY-NC 4.0 reference avatar; noncommercial evaluation only','limitations':g['extras']['novaLikeness']['limitations']}
(OUT/'nova-rig-study.json').write_text(json.dumps(metadata,indent=2)+'\n')
print(json.dumps(metadata,indent=2))
