"""Read-only, local landmark/segmentation probe for the generated reference portrait."""
from pathlib import Path
import json,os
os.environ.setdefault('MPLCONFIGDIR',str(Path(__file__).resolve().parents[2]/'.local/avatar-tools/matplotlib'))
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions, vision
import numpy as np

root=Path(__file__).resolve().parents[2]
source=root/'public/avatar/assets/nova-call-neutral-v2.png'
image=mp.Image.create_from_file(str(source))
with vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
 base_options=BaseOptions(model_asset_path=str(root/'.local/avatar-models/face_landmarker.task')),
 running_mode=vision.RunningMode.IMAGE,num_faces=1,output_facial_transformation_matrixes=True)) as detector:
 result=detector.detect(image)
 if len(result.face_landmarks)!=1:raise RuntimeError('One face required')
 points=np.array([[p.x,p.y,p.z] for p in result.face_landmarks[0]])
with vision.ImageSegmenter.create_from_options(vision.ImageSegmenterOptions(
 base_options=BaseOptions(model_asset_path=str(root/'.local/avatar-models/selfie_multiclass.tflite')),
 running_mode=vision.RunningMode.IMAGE,output_category_mask=True,output_confidence_masks=False)) as segmenter:
 segments=segmenter.segment(image).category_mask.numpy_view().copy()
np.savez(root/'.local/avatar-models/reference-fit.npz',landmarks=points,segments=segments,width=image.width,height=image.height)
print(json.dumps({'landmarks':len(points),'image':[image.width,image.height],'segments':{str(k):int((segments==k).sum()) for k in np.unique(segments)}}))
