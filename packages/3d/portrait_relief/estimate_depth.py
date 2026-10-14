"""Infer relative inverse depth from the original photograph, without image generation."""
from pathlib import Path
import argparse
import hashlib
import json
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
import torch
import transformers
from transformers import AutoImageProcessor, AutoModelForDepthEstimation

MODEL = 'depth-anything/Depth-Anything-V2-Small-hf'
REVISION = '5426e4f0f36572d16453bbda7a8389317b1bef99'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[2] / 'outputs/3d/portrait_relief/depth_model')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(8)
    original = Image.open(args.source).convert('RGBA')
    # Replace transparent pixels by neutral gray for inference, retain alpha as foreground mask.
    rgb = Image.new('RGBA', original.size, (128,128,128,255))
    rgb.alpha_composite(original)
    rgb = rgb.convert('RGB')
    processor = AutoImageProcessor.from_pretrained(MODEL, revision=REVISION, use_fast=False)
    model = AutoModelForDepthEstimation.from_pretrained(MODEL, revision=REVISION).eval()
    inputs = processor(images=rgb, return_tensors='pt')
    print('Running Depth Anything V2 on CPU...', flush=True)
    with torch.inference_mode():
        pred = model(**inputs).predicted_depth
        depth = torch.nn.functional.interpolate(pred[:,None], size=original.size[::-1],
                                               mode='bicubic', align_corners=False)[0,0].numpy()
    np.save(args.output/'inverse_depth_raw.npy', depth)
    alpha = np.asarray(original.getchannel('A')) > 127
    # Face-based normalization gives the nose, cheeks and eye sockets room in 0.8mm.
    # These coordinates refer to this supplied photograph, not a general face detector.
    y,x = np.mgrid[:depth.shape[0], :depth.shape[1]]
    face = (((x-724)/185)**2 + ((y-468)/245)**2 < 1) & alpha
    low, high = np.percentile(depth[face], [2,98])
    normalized = np.clip((ndi.median_filter(depth, size=5)-low)/(high-low), 0,1)
    # Non-transparent subject occupies at least the first raised layer.
    field = np.where(alpha, 0.06 + .94*normalized, 0)
    # Centered square includes the full head and naturally crops outer sleeves.
    side = 1240
    offset = (104,-77)
    square = Image.new('L', (side,side), 0)
    square.paste(Image.fromarray(np.rint(field*255).astype('uint8')), (-offset[0],-offset[1]))
    square.save(args.output/'depth_height_source.png')
    raw_lo, raw_hi = np.percentile(depth[alpha], [1,99])
    raw_vis = np.where(alpha, np.clip((depth-raw_lo)/(raw_hi-raw_lo),0,1), 0)
    Image.fromarray(np.rint(raw_vis*255).astype('uint8')).save(args.output/'depth_original_frame.png')
    crop = Image.new('RGBA',(side,side),(0,0,0,0))
    crop.paste(original,(-offset[0],-offset[1]))
    crop.save(args.output/'original_crop.png')
    info = dict(model=MODEL, revision=getattr(model.config,'_commit_hash',None),
                transformers=transformers.__version__, torch=torch.__version__,
                source_sha256=hashlib.sha256(args.source.read_bytes()).hexdigest(),
                inverse_depth=True, larger_values='closer to camera / higher relief',
                normalization='2nd to 98th percentile inside specified face ellipse',
                normalization_bounds=[float(low),float(high)],
                crop_offset_px=list(offset), crop_side_px=side,
                foreground='original alpha > 127', generated_image_used=False)
    (args.output/'depth_metadata.json').write_text(json.dumps(info,indent=2)+'\n')
    print(json.dumps(info,indent=2), flush=True)


if __name__ == '__main__':
    main()
