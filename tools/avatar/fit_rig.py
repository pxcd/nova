"""Fit local landmarks from the developer-only orthographic rig screenshot."""
from pathlib import Path
import os,argparse
ROOT=Path(__file__).resolve().parents[2]
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.local/avatar-tools/matplotlib'))
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions,vision
import numpy as np
parser=argparse.ArgumentParser();parser.add_argument('--anatomical',action='store_true');args=parser.parse_args()
source=ROOT/'.local/avatar-models/mpfb/front.png' if args.anatomical else ROOT/'.local/avatar-models/rig-front.png'
output=ROOT/'.local/avatar-models/mpfb/front-fit.npy' if args.anatomical else ROOT/'.local/avatar-models/rig-front-fit.npy'
image=mp.Image.create_from_file(str(source))
if (image.width,image.height)!=(1280,720):raise RuntimeError('Expected the 1280x720 orthographic fitting view')
with vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=str(ROOT/'.local/avatar-models/face_landmarker.task')),num_faces=1)) as detector:
 result=detector.detect(image)
 if len(result.face_landmarks)!=1:raise RuntimeError('Expected one rig face')
 np.save(output,[[p.x,p.y,p.z] for p in result.face_landmarks[0]])
 print('Neutral rig landmarks saved locally')
