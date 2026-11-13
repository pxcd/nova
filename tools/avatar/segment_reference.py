"""Save a local hair classification mask for the calibrated 3D hair surface."""
from pathlib import Path
import argparse, os

ROOT=Path(__file__).resolve().parents[2]
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.local/avatar-tools/matplotlib'))
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions, vision
import numpy as np

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--fit',required=True);args=parser.parse_args()
 fit=Path(args.fit);image=mp.Image.create_from_file(str(fit/'reference.png'))
 options=vision.ImageSegmenterOptions(base_options=BaseOptions(model_asset_path=str(ROOT/'.local/avatar-models/selfie_multiclass.tflite')),running_mode=vision.RunningMode.IMAGE,output_category_mask=True,output_confidence_masks=False)
 with vision.ImageSegmenter.create_from_options(options) as segmenter:
  result=segmenter.segment(image)
  mask=result.category_mask.numpy_view().copy().squeeze()
 if mask.ndim!=2 or not np.any(mask==1):raise RuntimeError('Reference hair segmentation failed')
 np.save(fit/'hair-mask.npy',mask==1)
 np.save(fit/'neck-mask.npy',np.isin(mask,[2,3,4]))
 print(f'Local hair mask: {mask.shape[1]} x {mask.shape[0]}')

if __name__=='__main__':main()
