"""Add source-photo monochrome features to inferred depth, without generative editing."""
from pathlib import Path
import json
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[2] / 'outputs/3d/portrait_relief'
OUT = ROOT/'depth_features'


def main():
    OUT.mkdir(exist_ok=True)
    original = Image.open(ROOT/'depth_model/original_photo.png').convert('RGBA')
    rgb = np.asarray(original)[:,:,:3].astype(float)/255
    alpha = np.asarray(original)[:,:,3] > 127
    gray = rgb @ np.array([.299,.587,.114])
    gray = ndi.median_filter(gray, size=5)
    y,x = np.mgrid[:gray.shape[0],:gray.shape[1]]
    face = (((x-724)/190)**2+((y-473)/245)**2 < 1) & alpha
    local = ndi.gaussian_filter(gray, sigma=13)
    # Restrict adaptive darkness to facial-feature windows; cheeks remain depth-only.
    brows = (x>550)&(x<895)&(y>310)&(y<375)
    eyes = (x>570)&(x<875)&(y>374)&(y<428)
    nostrils = (x>665)&(x<778)&(y>487)&(y<536)
    mouth = (x>625)&(x<818)&(y>555)&(y<628)
    dark = (((brows|eyes|nostrils)&((gray<.30)|((local-gray>.065)&(gray<.52)))) |
            (mouth&(local-gray>.035)&(gray<.60))) & face
    # Close small gaps and give features a printable width of approximately 0.35mm.
    dark = ndi.binary_closing(dark, iterations=2)
    dark = ndi.binary_dilation(dark, iterations=3) & face
    hair_candidates = (gray<.25)&(y<490)&(x>460)&(x<980)&alpha
    labels, count = ndi.label(hair_candidates)
    sizes = np.bincount(labels.ravel()); sizes[0] = 0
    hair = labels == int(np.argmax(sizes))
    jacket = (rgb[:,:,2]-rgb[:,:,0]>.13)&(rgb[:,:,2]>rgb[:,:,1]*1.1)&alpha
    depth = np.load(ROOT/'depth_model/inverse_depth_raw.npy')
    metadata = json.loads((ROOT/'depth_model/depth_metadata.json').read_text())
    low,high = metadata['normalization_bounds']
    field = .06+.94*np.clip((ndi.median_filter(depth,5)-low)/(high-low),0,1)
    # Raise the facial substrate so dark source features can occupy a lower terrace.
    field[face] = np.maximum(field[face], .66)
    field[dark] = .25
    field[hair] = .35
    # Dark blue jacket follows depth within a narrower range; white piping stays high.
    field[jacket] = .30+.26*field[jacket]
    field[~alpha] = 0
    field = ndi.median_filter(field, size=3)
    feature = np.where(dark|hair|jacket,0,255).astype('uint8')
    feature[~alpha] = 128
    Image.fromarray(feature).save(OUT/'monochrome_features_original.png')
    square = Image.new('L',(1240,1240),0)
    square.paste(Image.fromarray(np.rint(field*255).astype('uint8')),(-104,77))
    square.save(OUT/'combined_height_source.png')
    metadata['method'] = 'inverse depth plus source luminance features in face windows; blue jacket segmentation'
    metadata['feature_window_coordinates_px'] = dict(brows=[550,310,895,375],eyes=[570,374,875,428],
                                                    nostrils=[665,487,778,536],mouth=[625,555,818,628])
    metadata['facial_floor_normalized'] = .66
    metadata['dark_feature_normalized'] = .25
    metadata['generative_editing'] = False
    (OUT/'method.json').write_text(json.dumps(metadata,indent=2)+'\n')


if __name__ == '__main__':
    main()
