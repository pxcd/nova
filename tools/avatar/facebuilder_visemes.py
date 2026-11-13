"""Oculus phoneme targets composed from the fitted head's authored ARKit shapes.

The TalkingHead/Rhubarb timing remains unchanged. Native anatomy replaces a
nearest-vertex transfer that cannot preserve closed-lip topology across rigs.
"""
WEIGHTS={
 'sil':{},
 'PP':{'mouthPressLeft':.3,'mouthPressRight':.3,'mouthRollLower':.12,'mouthRollUpper':.12},
 'FF':{'jawOpen':.16,'mouthRollLower':.3,'mouthUpperUpLeft':.12,'mouthUpperUpRight':.12},
 'TH':{'jawOpen':.25,'mouthLowerDownLeft':.15,'mouthLowerDownRight':.15},
 'DD':{'jawOpen':.27,'mouthStretchLeft':.12,'mouthStretchRight':.12},
 'kk':{'jawOpen':.38},
 'CH':{'jawOpen':.23,'mouthPucker':.35,'mouthFunnel':.2},
 'SS':{'jawOpen':.14,'mouthStretchLeft':.25,'mouthStretchRight':.25},
 'nn':{'jawOpen':.2,'mouthStretchLeft':.12,'mouthStretchRight':.12},
 'RR':{'jawOpen':.25,'mouthFunnel':.35,'mouthPucker':.15},
 'aa':{'jawOpen':.52,'mouthLowerDownLeft':.08,'mouthLowerDownRight':.08},
 'E':{'jawOpen':.30,'mouthStretchLeft':.25,'mouthStretchRight':.25},
 'I':{'jawOpen':.18,'mouthStretchLeft':.35,'mouthStretchRight':.35},
 'O':{'jawOpen':.38,'mouthFunnel':.45,'mouthPucker':.2},
 'U':{'jawOpen':.17,'mouthPucker':.6,'mouthFunnel':.2}
}

def add_visemes(obj, allow_subset=False):
 import numpy as np
 base=np.array([v.co[:] for v in obj.data.shape_keys.key_blocks['Basis'].data]);native={}
 for key in obj.data.shape_keys.key_blocks:
  if not key.name.startswith('viseme_'):native[key.name]=np.array([v.co[:] for v in key.data])-base
 missing={name for weights in WEIGHTS.values() for name in weights}-native.keys()
 if missing and not allow_subset:raise RuntimeError("Missing facial shapes: "+", ".join(sorted(missing)))
 names=[]
 for name,weights in WEIGHTS.items():
  coordinates=base.copy()
  for shape,weight in weights.items():
   if shape not in native:continue # The retained teeth have only a subset of facial FACS.
   coordinates+=native[shape]*weight
  key=obj.data.shape_keys.key_blocks.get('viseme_'+name) or obj.shape_key_add(name='viseme_'+name)
  key.data.foreach_set('co',coordinates.ravel());key.value=0;names.append(key.name)
 return names
