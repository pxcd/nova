import unittest
import numpy as np
from morphs import speech_targets, UPPER_INNER, LOWER_INNER, UPPER_OUTER, LOWER_OUTER

class MouthTests(unittest.TestCase):
    def face(self):
        face=np.tile([0., .08, .04],(468,1))
        for ids,y in [(UPPER_INNER,.04),(LOWER_INNER,.039),(UPPER_OUTER,.044),(LOWER_OUTER,.036)]:
            face[ids,0]=np.linspace(-.025,.025,len(ids));face[ids,1]=y
        return face
    def test_speech_does_not_move_chin_jaw_or_non_mouth_vertices(self):
        face=self.face();allowed=set(UPPER_INNER+LOWER_INNER+UPPER_OUTER+LOWER_OUTER)
        outside=[i for i in range(468) if i not in allowed]
        for target in speech_targets(face)[:3]:
            np.testing.assert_array_equal(target[outside],0)
            np.testing.assert_array_equal(target[[61,78,291,308]],0)
            self.assertTrue(np.isfinite(target).all())
            self.assertLess(np.linalg.norm(target,axis=1).max(),.011)
    def test_lip_shapes_have_curved_opening_and_distinct_rounding(self):
        aa,ih,ou,_=speech_targets(self.face())
        self.assertGreater(aa[13,1],0);self.assertLess(aa[14,1],0)
        self.assertGreater(abs(aa[14,1]),abs(ih[14,1]))
        self.assertGreater(ou[14,2],0)
        self.assertGreater(abs(aa[14,1]),abs(aa[95,1]))
if __name__=='__main__':unittest.main()
