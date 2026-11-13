"""Build the next NOVA study on the anatomical CC0 MakeHuman reference.

Existing TalkingHead audio/viseme scheduling is unchanged. This preserves the
reference's authored facial targets, real oral meshes and volumetric hair asset.
"""
from pathlib import Path
import json,struct,hashlib
import numpy as np
from scipy.interpolate import RBFInterpolator
from scipy.spatial import ConvexHull
ROOT=Path(__file__).resolve().parents[2];DATA=ROOT/'.local/avatar-models';OUT=ROOT/'public/avatar/talkinghead'
raw=(OUT/'realistic-base.glb').read_bytes();size=struct.unpack_from('<I',raw,12)[0];g=json.loads(raw[20:20+size]);blob=bytearray(raw[28+size:])
fit=np.load(DATA/'reference-fit.npz');portrait=fit['landmarks'][:468];landmarks=np.load(DATA/'mpfb/front-fit.npy')[:468]
xy=np.column_stack(((landmarks[:,0]-.5)*.4*1280/720,1.6+(.5-landmarks[:,1])*.4))
center=portrait[[33,263],:2].mean(0);anchor=xy[[33,263]].mean(0);scale=(xy[263,0]-xy[33,0])/(portrait[263,0]-portrait[33,0]);aspect=float(fit['height']/fit['width'])
target=np.column_stack(((portrait[:,0]-center[0])*scale+anchor[0],(center[1]-portrait[:,1])*scale*aspect+anchor[1]))
warp=RBFInterpolator(xy,target-xy,neighbors=48,smoothing=1e-6);projection=RBFInterpolator(xy,portrait[:,:2],neighbors=48,smoothing=1e-7)

def read(i):
 a=g['accessors'][i];width={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}[a['type']];dtype=np.dtype({5126:'<f4',5125:'<u4',5123:'<u2',5121:'u1'}[a['componentType']])
 if 'bufferView'in a:
  v=g['bufferViews'][a['bufferView']];result=np.ndarray((a['count'],width),dtype=dtype,buffer=blob,offset=v.get('byteOffset',0)+a.get('byteOffset',0),strides=(v.get('byteStride',dtype.itemsize*width),dtype.itemsize)).copy()
 else:result=np.zeros((a['count'],width),dtype=dtype)
 if 'sparse'in a:
  sparse=a['sparse'];indices=sparse['indices'];v=g['bufferViews'][indices['bufferView']];it={5121:'u1',5123:'<u2',5125:'<u4'}[indices['componentType']]
  ids=np.frombuffer(blob,dtype=it,count=sparse['count'],offset=v.get('byteOffset',0)+indices.get('byteOffset',0))
  values=sparse['values'];v=g['bufferViews'][values['bufferView']];result[ids]=np.frombuffer(blob,dtype=dtype,count=sparse['count']*width,offset=v.get('byteOffset',0)+values.get('byteOffset',0)).reshape(-1,width)
 return result
def add(a,kind,component=5126,target=34962):
 a=np.ascontiguousarray(a,dtype={5126:'<f4',5125:'<u4',5123:'<u2'}[component])
 if component==5126 and kind=='VEC3':
  ids=np.flatnonzero(np.any(np.abs(a)>1e-10,axis=1))
  if len(ids)<len(a)*.5:
   acc={'componentType':5126,'count':len(a),'type':kind,'min':a.min(0).tolist(),'max':a.max(0).tolist()}
   if len(ids):
    views=[]
    for data in [ids.astype('<u4').tobytes(),a[ids].tobytes()]:
     blob.extend(b'\0'*((-len(blob))%4));off=len(blob);blob.extend(data);g['bufferViews'].append({'buffer':0,'byteOffset':off,'byteLength':len(data)});views.append(len(g['bufferViews'])-1)
    acc['sparse']={'count':len(ids),'indices':{'bufferView':views[0],'componentType':5125},'values':{'bufferView':views[1]}}
   g['accessors'].append(acc);return len(g['accessors'])-1
 blob.extend(b'\0'*((-len(blob))%4));off=len(blob);blob.extend(a.tobytes());g['bufferViews'].append({'buffer':0,'byteOffset':off,'byteLength':a.nbytes,'target':target});acc={'bufferView':len(g['bufferViews'])-1,'componentType':component,'count':len(a),'type':kind}
 if kind=='VEC3':acc.update(min=a.min(0).tolist(),max=a.max(0).tolist())
 g['accessors'].append(acc);return len(g['accessors'])-1
def deform(p):
 q=p.copy();selected=np.flatnonzero((p[:,1]>1.49)&(p[:,2]>.015))
 v=p[selected];weight=np.clip((v[:,1]-1.49)/.06,0,1)*np.clip((v[:,2]-.015)/.08,0,1)
 q[selected,:2]+=np.clip(warp(v[:,:2]),-.018,.018)*weight[:,None]
 return q
hull=ConvexHull(portrait[:,:2]*[1,aspect]);records=[]
for mesh in g['meshes']:
 if mesh['name'] not in ['base','high-poly','mind_eyebrows_02','mind_eyelashes_02','teeth_base','tongue01']:continue
 for p in mesh['primitives']:
  old=read(p['attributes']['POSITION']);points=deform(old);jac=np.zeros((len(old),3,3));eps=1e-4
  for axis in range(3):
   moved=old.copy();moved[:,axis]+=eps;jac[:,:,axis]=(deform(moved)-points)/eps
  p['attributes']['POSITION']=add(points,'VEC3');p['attributes'].pop('TANGENT',None)
  # Transform normal vectors with the inverse transpose of the local fit.
  normal=read(p['attributes']['NORMAL']);inverse=np.linalg.pinv(jac).transpose(0,2,1);newnormal=np.einsum('nij,nj->ni',inverse,normal);newnormal/=np.maximum(np.linalg.norm(newnormal,axis=1,keepdims=True),1e-9);p['attributes']['NORMAL']=add(newnormal,'VEC3')
  for shape in p.get('targets',[]):
   if 'POSITION'in shape:shape['POSITION']=add(np.einsum('nij,nj->ni',jac,read(shape['POSITION'])),'VEC3')
   if 'NORMAL'in shape:
    end=normal+read(shape['NORMAL']);end=np.einsum('nij,nj->ni',inverse,end);end/=np.maximum(np.linalg.norm(end,axis=1,keepdims=True),1e-9);shape['NORMAL']=add(end-newnormal,'VEC3')
   shape.pop('TANGENT',None)
  if mesh['name']=='base':
   uv=projection(old[:,:2]);signed=-(uv*[1,aspect])@hull.equations[:,:2].T-hull.equations[:,2]
   mask=np.clip(signed.min(1)/.035,0,1)*np.clip((normal[:,2]-.1)/.5,0,1)*np.clip((old[:,2]-.08)/.04,0,1)
   sx=np.clip((uv[:,0]*fit['width']).astype(int),0,int(fit['width'])-1);sy=np.clip((uv[:,1]*fit['height']).astype(int),0,int(fit['height'])-1)
   mask*=np.clip((uv[:,1]-.27)/.025,0,1)
   mask*=np.clip((old[:,1]-1.50)/.04,0,1)
   p['attributes']['_NOVA_FACE_UV']=add(uv,'VEC2');p['attributes']['_NOVA_FACE_MASK']=add(mask[:,None],'SCALAR')
   p['attributes']['_NOVA_SCALP_MASK']=add(np.clip((old[:,1]-1.715)/.025,0,1)[:,None],'SCALAR')
  records.append({'name':mesh['name'],'vertices':len(old),'targets':len(p.get('targets',[])),'max_displacement_m':float(np.linalg.norm(points-old,axis=1).max())})
# The true 3D bob is appended below after its local source assets are available.
hairdir=DATA/'mpfb/bob01';obj=hairdir/'bob01.obj'
if not obj.exists():raise RuntimeError('Official bob01 asset is required')
verts=[];uvs=[];faces=[]
for line in obj.read_text().splitlines():
 parts=line.split()
 if not parts:continue
 if parts[0]=='v':verts.append([float(v) for v in parts[1:4]])
 elif parts[0]=='vt':uvs.append([float(v) for v in parts[1:3]])
 elif parts[0]=='f':faces.append([tuple(int(v)-1 for v in corner.split('/')[:2]) for corner in parts[1:]])
verts=np.array(verts);uvs=np.array(uvs);lo,hi=verts.min(0),verts.max(0)
# Align the canonical hairstyle to this anatomical head's rest space. The
# source mesh topology and UVs remain intact; this is a fitted game hair asset.
verts[:,0]=(verts[:,0]-(lo[0]+hi[0])/2)/(hi[0]-lo[0])*.23
verts[:,1]=1.49+(verts[:,1]-lo[1])/(hi[1]-lo[1])*.33
verts[:,2]=-.075+(verts[:,2]-lo[2])/(hi[2]-lo[2])*.255
# Lift the central fringe out of the eye/mouth area while keeping side lengths.
fringe=np.clip((verts[:,2]-.10)/.035,0,1)*np.clip((.09-np.abs(verts[:,0]))/.025,0,1)
floor=1.715-.025*np.minimum(1,np.abs(verts[:,0])/.09)
verts[:,1]+=np.maximum(0,floor-verts[:,1])*fringe
keys={};points=[];coords=[];tri=[]
for face in faces:
 indices=[]
 for key in face:
  if key not in keys:keys[key]=len(points);points.append(verts[key[0]]);coords.append(uvs[key[1]])
  indices.append(keys[key])
 for i in range(1,len(indices)-1):tri.append([indices[0],indices[i],indices[i+1]])
points=np.array(points);coords=np.array(coords);tri=np.array(tri);coords[:,1]=1-coords[:,1]
n=np.zeros_like(points);cross=np.cross(points[tri[:,1]]-points[tri[:,0]],points[tri[:,2]]-points[tri[:,0]])
for i in range(3):np.add.at(n,tri[:,i],cross)
n/=np.maximum(np.linalg.norm(n,axis=1,keepdims=True),1e-9)
material=(hairdir/'bob01.mhmat').read_text();texture=None
for line in material.splitlines():
 if line.startswith('diffuseTexture '):texture=hairdir/line.split(maxsplit=1)[1].strip()
if texture is None or not texture.exists():raise RuntimeError('Hair diffuse texture is missing')
image=texture.read_bytes();blob.extend(b'\0'*((-len(blob))%4));off=len(blob);blob.extend(image);g['bufferViews'].append({'buffer':0,'byteOffset':off,'byteLength':len(image)});g['images'].append({'bufferView':len(g['bufferViews'])-1,'mimeType':'image/png'});g['textures'].append({'source':len(g['images'])-1,'sampler':0})
g['materials'].append({'name':'CC0 anatomical bob hair','doubleSided':True,'alphaMode':'MASK','alphaCutoff':.35,'pbrMetallicRoughness':{'baseColorTexture':{'index':len(g['textures'])-1},'baseColorFactor':[.9,.8,.65,1],'metallicFactor':0,'roughnessFactor':.85}})
skin=0;head=next(i for i,n in enumerate(g['nodes']) if n.get('name')=='Head');joint=g['skins'][skin]['joints'].index(head);joints=np.zeros((len(points),4));joints[:,0]=joint;weights=np.zeros_like(joints);weights[:,0]=1
attrs={'POSITION':add(points,'VEC3'),'NORMAL':add(n,'VEC3'),'TEXCOORD_0':add(coords,'VEC2'),'JOINTS_0':add(joints,'VEC4',5123),'WEIGHTS_0':add(weights,'VEC4')}
g['meshes'].append({'name':'NOVA full 3D bob','primitives':[{'attributes':attrs,'indices':add(tri.reshape(-1,1),'SCALAR',5125,34963),'material':len(g['materials'])-1}]});g['nodes'].append({'name':'NOVA full 3D bob','mesh':len(g['meshes'])-1,'skin':skin});g['scenes'][g.get('scene',0)]['nodes'].append(len(g['nodes'])-1)
for node in g['nodes']:
 if node.get('name') in ['Human.ponytail01','Human.mindfront_eyebrows_02','Human.mindfront_eyelashes_02']:node.pop('mesh',None);node.pop('skin',None)
# Detailed portrait hair cards sit in front of a complete 3D hairstyle, rather
# than leaving the isolated cutout surfaces and open gaps of the previous study.
seg=fit['segments'].squeeze();H,W=seg.shape;step=2
xx,yy=np.meshgrid(np.arange(0,W,step)/W,np.arange(0,H,step)/H);hairuv=np.column_stack((xx.ravel(),yy.ravel()));valid=seg[np.minimum((hairuv[:,1]*H).astype(int),H-1),np.minimum((hairuv[:,0]*W).astype(int),W-1)]==1
hp=np.column_stack(((hairuv[:,0]-center[0])*scale+anchor[0],(center[1]-hairuv[:,1])*scale*aspect+anchor[1],np.zeros(len(hairuv))))
radial=(hp[:,0]/.15)**2+((hp[:,1]-1.67)/.22)**2;hp[:,2]=.15+.075*np.sqrt(np.clip(1-radial,0,1))
ht=[];cols=xx.shape[1]
for row in range(xx.shape[0]-1):
 for col in range(cols-1):
  i=row*cols+col
  for face in [[i,i+cols,i+1],[i+1,i+cols,i+cols+1]]:
   if valid[face].all():ht.append(face)
ht=np.array(ht);used=np.unique(ht);remap=np.full(len(hairuv),-1);remap[used]=np.arange(len(used));ht=remap[ht];hp=hp[used];hairuv=hairuv[used]
hn=np.zeros_like(hp);cross=np.cross(hp[ht[:,1]]-hp[ht[:,0]],hp[ht[:,2]]-hp[ht[:,0]])
for i in range(3):np.add.at(hn,ht[:,i],cross)
hn/=np.maximum(np.linalg.norm(hn,axis=1,keepdims=True),1e-9)
image=(ROOT/'public/avatar/assets/nova-call-neutral-v2.png').read_bytes();blob.extend(b'\0'*((-len(blob))%4));off=len(blob);blob.extend(image);g['bufferViews'].append({'buffer':0,'byteOffset':off,'byteLength':len(image)});g['images'].append({'bufferView':len(g['bufferViews'])-1,'mimeType':'image/png'});g['textures'].append({'source':len(g['images'])-1,'sampler':0})
g['materials'].append({'name':'NOVA portrait groom cards','doubleSided':True,'pbrMetallicRoughness':{'baseColorTexture':{'index':len(g['textures'])-1},'metallicFactor':0,'roughnessFactor':1}})
hj=np.zeros((len(hp),4));hj[:,0]=joint;hw=np.zeros_like(hj);hw[:,0]=1
ha={'POSITION':add(hp,'VEC3'),'NORMAL':add(hn,'VEC3'),'TEXCOORD_0':add(hairuv,'VEC2'),'JOINTS_0':add(hj,'VEC4',5123),'WEIGHTS_0':add(hw,'VEC4')}
g['meshes'].append({'name':'NOVA detailed groom cards','primitives':[{'attributes':ha,'indices':add(ht.reshape(-1,1),'SCALAR',5125,34963),'material':len(g['materials'])-1}]});g['nodes'].append({'name':'NOVA detailed groom cards','mesh':len(g['meshes'])-1,'skin':skin});g['scenes'][g.get('scene',0)]['nodes'].append(len(g['nodes'])-1)
g['asset']['generator']='NOVA anatomical head study';g['extras']={'novaStudy':'Anatomical CC0 head, unchanged TalkingHead speech scheduling, local portrait fit, full 3D bob; experimental likeness.'};g['buffers'][0]['byteLength']=len(blob)
j=json.dumps(g,separators=(',',':')).encode();j+=b' '*((-len(j))%4);blob+=b'\0'*((-len(blob))%4);result=b'glTF'+struct.pack('<II',2,28+len(j)+len(blob))+struct.pack('<I4s',len(j),b'JSON')+j+struct.pack('<I4s',len(blob),b'BIN\0')+blob
(OUT/'nova-realistic-study.glb').write_bytes(result)
report={'model_sha256':hashlib.sha256(result).hexdigest(),'base_sha256':hashlib.sha256(raw).hexdigest(),'base_source':'https://github.com/met4citizen/TalkingHead/blob/1563de184c19b310de4b636664d5835e2c74dbba/avatars/mpfb.glb','base_license':'CC0, as stated by upstream TalkingHead README','hair_source':'Official MakeHuman system assets bob01','hair_license':'CC0','meshes':records,'limitations':['Experimental landmark-based likeness fit, not a calibrated sculpt','Portrait shading is projected; skin/eye matching remains approximate','Layered portrait hair cards over a full 3D bob; near-frontal views only','Reference body and clothing retained','No production NOVA avatar change']}
report['hair_asset_hashes']={n:hashlib.sha256((hairdir/n).read_bytes()).hexdigest() for n in ['bob01.obj','bob01.mhmat','bob01_diffuse.png']}
report['hair_pack_url']='https://files.makehumancommunity.org/asset_packs/makehuman_system_assets/makehuman_system_assets_cc0.zip'
report['source_portrait_sha256']=hashlib.sha256((ROOT/'public/avatar/assets/nova-call-neutral-v2.png').read_bytes()).hexdigest()
(OUT/'nova-realistic-study.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
