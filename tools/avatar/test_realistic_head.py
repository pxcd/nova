"""Independent structural checks for the anatomical head and retained speech rig."""
from pathlib import Path
import hashlib,json,struct,unittest
import numpy as np
ROOT=Path(__file__).resolve().parents[2]/'public/avatar/talkinghead'
def load(file):
 b=(ROOT/file).read_bytes();n=struct.unpack_from('<I',b,12)[0];return json.loads(b[20:20+n]),b[28+n:]
def values(g,b,i):
 a=g['accessors'][i];width={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}[a['type']];dtype=np.dtype({5126:'<f4',5125:'<u4',5123:'<u2',5121:'u1'}[a['componentType']]);r=np.zeros((a['count'],width),dtype=dtype)
 if 'bufferView'in a:
  v=g['bufferViews'][a['bufferView']];r[:]=np.ndarray(r.shape,dtype=dtype,buffer=b,offset=v.get('byteOffset',0)+a.get('byteOffset',0),strides=(v.get('byteStride',width*dtype.itemsize),dtype.itemsize))
 if 'sparse'in a:
  s=a['sparse'];i=s['indices'];v=g['bufferViews'][i['bufferView']];ids=np.frombuffer(b,dtype={5121:'u1',5123:'<u2',5125:'<u4'}[i['componentType']],count=s['count'],offset=v.get('byteOffset',0)+i.get('byteOffset',0));v=g['bufferViews'][s['values']['bufferView']];r[ids]=np.frombuffer(b,dtype=dtype,count=s['count']*width,offset=v.get('byteOffset',0)+s['values'].get('byteOffset',0)).reshape(-1,width)
 return r
class AnatomicalRigTests(unittest.TestCase):
 def test_existing_topology_and_authored_speech_targets_survive(self):
  original,ob=load('realistic-base.glb');new,nb=load('nova-realistic-study.glb')
  for name in ['base','teeth_base','tongue01','high-poly','mind_eyebrows_02','mind_eyelashes_02']:
   old=next(m for m in original['meshes'] if m['name']==name);mesh=next(m for m in new['meshes'] if m['name']==name)
   self.assertEqual(old['extras']['targetNames'],mesh['extras']['targetNames'])
   p=mesh['primitives'][0];self.assertTrue(np.array_equal(values(original,ob,old['primitives'][0]['indices']),values(new,nb,p['indices'])))
   self.assertTrue(np.isfinite(values(new,nb,p['attributes']['POSITION'])).all())
   for target in p['targets']:
    delta=values(new,nb,target['POSITION']);self.assertTrue(np.isfinite(delta).all());self.assertLess(float(np.abs(delta).max()),.15)
   if name in ['base','teeth_base','tongue01']:
    i=mesh['extras']['targetNames'].index('viseme_aa');self.assertGreater(float(np.linalg.norm(values(new,nb,p['targets'][i]['POSITION']))),0)
 def test_closed_head_topology_and_three_dimensional_hair_replace_cutouts(self):
  g,b=load('nova-realistic-study.glb');mesh=next(m for m in g['meshes'] if m['name']=='NOVA full 3D bob');p=values(g,b,mesh['primitives'][0]['attributes']['POSITION'])
  self.assertTrue(np.isfinite(p).all());self.assertGreater(float(np.ptp(p[:,2])),.15);self.assertGreater(float(np.ptp(p[:,1])),.2)
  report=json.loads((ROOT/'nova-realistic-study.json').read_text());self.assertEqual(hashlib.sha256((ROOT/'nova-realistic-study.glb').read_bytes()).hexdigest(),report['model_sha256'])
  self.assertEqual(hashlib.sha256((ROOT/'realistic-base.glb').read_bytes()).hexdigest(),'63c645a2a863b9972e9a9c2ed576a1de4c390b8475508e1473e69c87a3ee299c')
 def test_speech_sample_and_timing_are_the_approved_inputs(self):
  self.assertEqual(hashlib.sha256((ROOT/'sample.mp3').read_bytes()).hexdigest(),'8cd9433fff5b95df3a57d9410aea2d45eae1802b860a55d5ee83e46821a5c141')
  clip=json.loads((ROOT/'sample.json').read_text());self.assertEqual(len(clip['visemes']),len(clip['vtimes']));self.assertEqual(len(clip['visemes']),len(clip['vdurations']))
if __name__=='__main__':unittest.main()
