"""Structural regression checks for the fitted rig, independent of the builder."""
from pathlib import Path
import json,struct,unittest,hashlib
import numpy as np
ROOT=Path(__file__).resolve().parents[2]/'public/avatar/talkinghead'
def load(name):
 data=(ROOT/name).read_bytes();n=struct.unpack_from('<I',data,12)[0]
 return json.loads(data[20:20+n]),data[28+n:]
def positions(g,blob,i):
 a=g['accessors'][i];v=g['bufferViews'][a['bufferView']]
 return np.ndarray((a['count'],3),dtype='<f4',buffer=blob,offset=v.get('byteOffset',0)+a.get('byteOffset',0),strides=(v.get('byteStride',12),4))
class RigTests(unittest.TestCase):
 def test_authored_face_and_teeth_shapes_survive_the_fit(self):
  original,_=load('reference.glb');fitted,blob=load('nova-rig-study.glb')
  for name in ['Wolf3D_Head','Wolf3D_Teeth','EyeLeft','EyeRight']:
   before=next(m for m in original['meshes'] if m['name']==name)
   after=next(m for m in fitted['meshes'] if m['name']==name)
   self.assertEqual(before['extras']['targetNames'],after['extras']['targetNames'])
   p=after['primitives'][0];self.assertEqual(len(p['targets']),72)
   self.assertTrue(np.isfinite(positions(fitted,blob,p['attributes']['POSITION'])).all())
   for morph in p['targets']:
    delta=positions(fitted,blob,morph['POSITION']);self.assertTrue(np.isfinite(delta).all());self.assertLess(float(np.abs(delta).max()),.15)
   aa=after['extras']['targetNames'].index('viseme_aa')
   if name in ['Wolf3D_Head','Wolf3D_Teeth']:
    self.assertGreater(float(np.linalg.norm(positions(fitted,blob,p['targets'][aa]['POSITION']))),0)
 def test_reference_unchanged_and_derivative_provenance_matches(self):
  meta=json.loads((ROOT/'nova-rig-study.json').read_text())
  self.assertEqual(hashlib.sha256((ROOT/'reference.glb').read_bytes()).hexdigest(),'8864c504b5c11daa2f0037afffdc0815bb0fa2e6062e37a584746116a3c2f538')
  self.assertEqual(hashlib.sha256((ROOT/'nova-rig-study.glb').read_bytes()).hexdigest(),meta['model_sha256'])
if __name__=='__main__':unittest.main()
