"""Fit only the generated mouth-interior reference; no image leaves the machine."""
from pathlib import Path
import os
root=Path(__file__).resolve().parents[2]
os.environ.setdefault('MPLCONFIGDIR',str(root/'.local/avatar-tools/matplotlib'))
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions,vision
import numpy as np
with vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=str(root/'.local/avatar-models/face_landmarker.task')),num_faces=1)) as detector:
 r=detector.detect(mp.Image.create_from_file(str(root/'public/avatar/assets/nova-mouth-reference-v2.png')))
 if len(r.face_landmarks)!=1:raise RuntimeError('Expected one mouth reference face')
 np.save(root/'.local/avatar-models/mouth-reference-fit.npy',[[p.x,p.y] for p in r.face_landmarks[0]])
 print('Mouth reference fit saved locally.')
