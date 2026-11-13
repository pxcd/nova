"""Build a local near-frontal VRM likeness study from the generated portrait.

This produces an estimated face surface and segmented depth shells, not a complete
sculpt. Original portrait pixels are embedded unchanged as the UV texture.
"""
from pathlib import Path
from morphs import speech_targets
import io,json,struct,hashlib
import numpy as np
from PIL import Image,ImageDraw
from scipy.spatial import cKDTree
from scipy.ndimage import binary_erosion,binary_dilation
from scipy.interpolate import LinearNDInterpolator

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'.local/avatar-models'
fit=np.load(DATA/'reference-fit.npz');lm=fit['landmarks'][:468];seg=fit['segments'].squeeze()
W,H=int(fit['width']),int(fit['height']);S=.34;aspect=H/W
anchor=np.array([lm[152,0],lm[152,1],lm[168,2]])
face=np.column_stack(((lm[:,0]-anchor[0])*S,(anchor[1]-lm[:,1])*S*aspect,-(lm[:,2]-anchor[2])*S+.065)).astype('f4')
tri=[]
for line in (DATA/'canonical_face_model.obj').read_text().splitlines():
 if line.startswith('f '):tri.append([int(x.split('/')[0])-1 for x in line.split()[1:]])
tri=np.array(tri,dtype='u4')
left=[33,7,163,144,145,153,154,155,133,173,157,158,159,160,161,246]
right=[263,249,390,373,374,380,381,382,362,398,384,385,386,387,388,466]
inside=[78,95,88,178,87,14,317,402,318,324,308,415,310,311,312,13,82,81,80,191]
tri=np.array([t for t in tri if not any(set(t)<=set(loop) for loop in [left,right,inside])],dtype='u4')

blob=bytearray();g={'asset':{'version':'2.0','generator':'NOVA local likeness study'},'scene':0,'scenes':[{'nodes':[0]}],'nodes':[{'name':'AvatarRoot','children':[]}],'meshes':[],'materials':[],'accessors':[],'bufferViews':[],'buffers':[{'byteLength':0}],'extensionsUsed':['VRMC_vrm','KHR_materials_unlit'],'extensions':{},'extras':{'novaPortrait':{'centerOffsetY':.1,'cameraDistance':.86,'voiceGain':7,'voiceRange':.6},'studyLimitations':'Estimated near-frontal surface; hair and shoulders are segmented depth shells, not a complete sculpt.'}}

def binary(data,target=None):
 while len(blob)%4:blob.append(0)
 off=len(blob);blob.extend(data);v={'buffer':0,'byteOffset':off,'byteLength':len(data)}
 if target:v['target']=target
 g['bufferViews'].append(v);return len(g['bufferViews'])-1

def accessor(a,kind,component=5126,target=34962):
 a=np.asarray(a,dtype='f4' if component==5126 else 'u4');a=np.ascontiguousarray(a)
 d={'bufferView':binary(a.tobytes(),target),'componentType':component,'count':len(a),'type':kind}
 if component==5126 and kind!='MAT4':d.update(min=a.reshape(len(a),-1).min(0).tolist(),max=a.reshape(len(a),-1).max(0).tolist())
 g['accessors'].append(d);return len(g['accessors'])-1

def node(name,parent=0,translation=(0,0,0),**kw):
 n=len(g['nodes']);g['nodes'].append(dict(name=name,translation=np.asarray(translation).tolist(),**kw));g['nodes'][parent].setdefault('children',[]).append(n);return n

bones={};world={0:np.zeros(3)}
def bone(name,parent,xyz):
 i=node(name,parent,xyz);bones[name]={'node':i};world[i]=world[parent]+xyz;return i
hips=bone('hips',0,np.array([0,1,0]));spine=bone('spine',hips,np.array([0,.13,0]));chest=bone('chest',spine,np.array([0,.17,0]));neck=bone('neck',chest,np.array([0,.14,0]));head=bone('head',neck,np.array([0,.06,0]))
for side,sign in [('left',1),('right',-1)]:
 arm=bone(side+'UpperArm',chest,np.array([.14*sign,.04,0]));fore=bone(side+'LowerArm',arm,np.array([.22*sign,0,0]));bone(side+'Hand',fore,np.array([.2*sign,0,0]));leg=bone(side+'UpperLeg',hips,np.array([.07*sign,-.08,0]));calf=bone(side+'LowerLeg',leg,np.array([0,-.4,0]));bone(side+'Foot',calf,np.array([0,-.4,.03]))

png=(ROOT/'public/avatar/assets/nova-call-neutral-v2.png').read_bytes()
g['images']=[{'bufferView':binary(png),'mimeType':'image/png'}];g['samplers']=[{'magFilter':9729,'minFilter':9729,'wrapS':33071,'wrapT':33071}];g['textures']=[{'sampler':0,'source':0}]
def material(name,color=(1,1,1,1),texture=False,texture_index=0):
 pbr={'baseColorFactor':list(color),'metallicFactor':0,'roughnessFactor':1}
 if texture:pbr['baseColorTexture']={'index':texture_index}
 g['materials'].append({'name':name,'doubleSided':True,'pbrMetallicRoughness':pbr,'extensions':{'KHR_materials_unlit':{}}});return len(g['materials'])-1
photo=material('Portrait UV texture',texture=True)

def mesh(name,positions,indices,uv,mat,parent,targets=None,skin=None,colors=None):
 attrs={'POSITION':accessor(positions,'VEC3')}
 if uv is not None:attrs['TEXCOORD_0']=accessor(uv,'VEC2')
 if colors is not None:attrs['COLOR_0']=accessor(colors,'VEC4')
 primitive={'attributes':attrs,'indices':accessor(np.array(indices).reshape(-1),'SCALAR',5125,34963),'material':mat}
 if targets:primitive['targets']=[{'POSITION':accessor(t,'VEC3')} for t in targets]
 if skin:
  a=np.where(np.asarray(skin[1])>0,np.asarray(skin[0]),0).astype('u2')
  g['accessors'].append({'bufferView':binary(a.tobytes(),34962),'componentType':5123,'count':len(a),'type':'VEC4'})
  attrs['JOINTS_0']=len(g['accessors'])-1
  attrs['WEIGHTS_0']=accessor(skin[1],'VEC4')
 g['meshes'].append({'name':name,'primitives':[primitive],**({'weights':[0]*len(targets),'extras':{'targetNames':['aa','ih','ou','blink','happy','fv']}} if targets else {})})
 n=node(name,parent,mesh=len(g['meshes'])-1)
 if skin:
  g['nodes'][n]['skin']=0;g['nodes'][0]['children'].remove(n);g['scenes'][0]['nodes'].append(n)
 return n

# Speech shapes affect the lip rims only; chin and jaw remain stationary.
aa,ih,ou,happy=speech_targets(face)
blink=np.zeros_like(face)
fv=np.zeros_like(face)
for i in [14,87,178,88,95,317,402,318,324,17,84,181,91,146,314,405,321,375]:
 fv[i,1]=.0015;fv[i,2]=-.0006
fv[[61,78,291,308]]=0
mouth_center=(face[13]+face[14])/2
for loop in [left,right]:
 a,b=face[loop[0]],face[loop[8]]
 for i in loop:
  fraction=np.clip((face[i,0]-a[0])/(b[0]-a[0]),0,1)
  low,high=face[loop,1].min(),face[loop,1].max()
  closure=low+.2*(high-low)
  line=a[1]*(1-fraction)+b[1]*fraction+(closure-(a[1]+b[1])/2)*np.sin(np.pi*fraction)
  blink[i,1]=line-face[i,1]
# Feather the edge into the overlapping head surface to avoid a cut-out contour.
boundary=set([10,338,297,332,284,251,389,356,454,323,361,288,397,365,379,378,400,377,152,148,176,149,150,136,172,58,132,93,234,127,162,21,54,103,67,109])
alpha=np.ones(468);alpha[list(boundary)]=0
neighbors=set(int(i) for t in tri if set(t)&boundary for i in t)-boundary
alpha[list(neighbors)]=.6
colors=np.column_stack([np.ones((468,3)),alpha])
g['materials'].append(dict(g['materials'][photo],name='Feathered face surface',alphaMode='BLEND'))
face_mat=len(g['materials'])-1
face_node=mesh('NOVA face surface',face,tri,lm[:,:2],face_mat,head,[aa,ih,ou,blink,happy,fv],colors=colors)

# Textured eye surfaces sit behind the eyelids; lids occlude them when blinking.
for label,loop in [('rightEye',left),('leftEye',right)]:
 points=face[loop];uv=lm[loop,:2];lo=points.min(0);hi=points.max(0);mid=(lo+hi)/2;mid[2]=lo[2]-.0015
 eye=bone(label,head,mid)
 positions=np.array([[lo[0],lo[1],mid[2]],[hi[0],lo[1],mid[2]],[hi[0],hi[1],mid[2]],[lo[0],hi[1],mid[2]]])-mid
 coords=np.array([[uv[:,0].min(),uv[:,1].max()],[uv[:,0].max(),uv[:,1].max()],[uv[:,0].max(),uv[:,1].min()],[uv[:,0].min(),uv[:,1].min()]])
 mesh(label+' surface',positions,[[0,1,2],[0,2,3]],coords,photo,eye)

# A recessed, UV-textured mouth interior replaces the flat strip/procedural teeth.
oral_png=(ROOT/'public/avatar/assets/nova-mouth-reference-v2.png').read_bytes()
g['images'].append({'bufferView':binary(oral_png),'mimeType':'image/png'})
g['textures'].append({'sampler':0,'source':len(g['images'])-1})
oral_mat=material('Reference mouth interior',(.82,.82,.82,1),True,len(g['textures'])-1)
oral_uv=np.load(DATA/'mouth-reference-fit.npy')[inside]
uv_center=(oral_uv.min(0)+oral_uv.max(0))/2
span=oral_uv.max(0)-oral_uv.min(0)
c=mouth_center.copy();c[2]=face[inside,2].min()-.008;c[1]-=.003
positions=np.column_stack([c[0]+(oral_uv[:,0]-uv_center[0])/span[0]*.044,
 c[1]-(oral_uv[:,1]-uv_center[1])/span[1]*.016,np.full(len(oral_uv),c[2])])
positions=np.vstack([c,positions]);oral_coords=np.vstack([uv_center,oral_uv])
fan=[[0,i+1,(i+1)%len(oral_uv)+1] for i in range(len(oral_uv))]
mesh('Mouth interior',positions,fan,oral_coords,oral_mat,head)

# Remove the reconstructed face from the depth shell, retaining hair/ears.
mask=Image.new('L',(W,H));draw=ImageDraw.Draw(mask)
oval=[10,338,297,332,284,251,389,356,454,323,361,288,397,365,379,378,400,377,152,148,176,149,150,136,172,58,132,93,234,127,162,21,54,103,67,109]
draw.polygon([(lm[i,0]*W,lm[i,1]*H) for i in oval],fill=255);face_area=binary_erosion(np.array(mask)>0,iterations=7)
rows=np.arange(H)[:,None]/H
cutouts=Image.new('L',(W,H));cutdraw=ImageDraw.Draw(cutouts)
for loop in [left,right,inside]:cutdraw.polygon([(lm[i,0]*W,lm[i,1]*H) for i in loop],fill=255)
holes=binary_dilation(np.array(cutouts)>0,iterations=3)
head_mask=(seg!=0)&(rows<lm[152,1]+.012)&(~holes)
body_mask=(seg!=0)&(rows>=lm[152,1]-.006)&(seg!=1)

def shell(name,mask,parent,is_body=False):
 step=3;xs=np.arange(0,W,step);ys=np.arange(0,H,step);cols=len(xs)
 uu,vv=np.meshgrid(xs/W,ys/H);uu=uu.ravel();vv=vv.ravel();pos=np.column_stack(((uu-anchor[0])*S,(anchor[1]-vv)*S*aspect,np.zeros_like(uu)))
 if is_body:
  pos[:,2]=.025+.035*np.sqrt(np.clip(1-((uu-.5)/.55)**2,0,1));pos[:,1]+=1.5
  blend=np.clip((vv-anchor[1])/.065,0,1);pos[:,2]=face[152,2]*(1-blend)+pos[:,2]*blend
 else:
  radial=((uu-.5)/.36)**2+((vv-.3)/.33)**2;pos[:,2]=.045+.05*np.sqrt(np.clip(1-radial,0,1))
  distance,nearest=cKDTree(lm[:,:2]*[1,aspect]).query(np.column_stack((uu,vv))*[1,aspect])
  blend=np.clip(distance/.09,0,1);pos[:,2]=face[nearest,2]*(1-blend)+pos[:,2]*blend
  fitted=LinearNDInterpolator(lm[:,:2],face[:,2])(np.column_stack((uu,vv)))
  in_face=np.isfinite(fitted);pos[in_face,2]=fitted[in_face]-.0006
 valid=mask[np.minimum((vv*H).astype(int),H-1),np.minimum((uu*W).astype(int),W-1)]
 ids=[]
 for j in range(len(ys)-1):
  for i in range(cols-1):
   a=j*cols+i
   for t in [[a,a+cols,a+1],[a+1,a+cols,a+cols+1]]:
    if valid[t].all():ids.append(t)
 used=np.unique(ids);remap=np.full(len(pos),-1);remap[used]=np.arange(len(used));inds=remap[np.array(ids)]
 positions=pos[used];uv=np.column_stack((uu,vv))[used]
 skin=None
 if is_body:
  v=(1.5-positions[:,1]);h=np.clip(1-v/.065,0,1)*.8;n=(1-h)*np.clip(1-v/.14,0,1);c=1-h-n
  skin=(np.tile([0,1,2,0],(len(used),1)),np.column_stack((c,n,h,np.zeros(len(used)))))
 targets=None
 if not is_body:
  _,nearest=cKDTree(lm[:,:2]*[1,aspect]).query(uv*[1,aspect])
  targets=[target[nearest] for target in [aa,ih,ou,blink,happy,fv]]
 return mesh(name,positions,inds,uv,photo,parent,skin=skin,targets=targets)
# Bind neck/shoulder surface to chest, neck and head for continuous small motion.
g['skins']=[{'joints':[chest,neck,head]}]
# glTF matrices are column-major.
mats=[]
for j in [chest,neck,head]:
 m=np.eye(4,dtype='f4');m[:3,3]=-world[j];mats.append(m.T.reshape(16))
g['skins'][0]['inverseBindMatrices']=accessor(mats,'MAT4',target=None)
head_shell=shell('NOVA head depth shell',head_mask,head)
shell('NOVA neck and shoulders',body_mask,0,True)
g['extensions']['VRMC_vrm']={'specVersion':'1.0','meta':{'name':'NOVA likeness study','version':'0.1','authors':['NOVA local reconstruction study'],'licenseUrl':'https://vrm.dev/licenses/1.0/','avatarPermission':'onlyAuthor','commercialUsage':'personalNonProfit','allowRedistribution':False,'modification':'prohibited'},'humanoid':{'humanBones':bones},'expressions':{'preset':{name:{'morphTargetBinds':[{'node':face_node,'index':i,'weight':1},{'node':head_shell,'index':i,'weight':1}],'isBinary':False} for i,name in enumerate(['aa','ih','ou','blink','happy'])}},'lookAt':{'offsetFromHeadBone':[0,.1,.06],'type':'bone','rangeMapHorizontalInner':{'inputMaxValue':90,'outputScale':8},'rangeMapHorizontalOuter':{'inputMaxValue':90,'outputScale':8},'rangeMapVerticalDown':{'inputMaxValue':90,'outputScale':6},'rangeMapVerticalUp':{'inputMaxValue':90,'outputScale':6}}}
g['extensions']['VRMC_vrm']['expressions']['custom']={'fv':{'morphTargetBinds':[{'node':face_node,'index':5,'weight':1},{'node':head_shell,'index':5,'weight':1}],'isBinary':False}}
while len(blob)%4:blob.append(0)
g['buffers'][0]['byteLength']=len(blob);j=json.dumps(g,separators=(',',':')).encode();j+=b' '*((-len(j))%4)
out=struct.pack('<III',0x46546c67,2,12+8+len(j)+8+len(blob))+struct.pack('<II',len(j),0x4e4f534a)+j+struct.pack('<II',len(blob),0x004e4942)+blob
path=ROOT/'public/avatar/models/nova-likeness-study.vrm';temporary=path.with_suffix('.vrm.tmp');temporary.write_bytes(out);temporary.replace(path)
print(json.dumps({'output':str(path),'bytes':len(out),'meshes':len(g['meshes']),'faceVertices':len(face),'sha256':hashlib.sha256(out).hexdigest()}))
