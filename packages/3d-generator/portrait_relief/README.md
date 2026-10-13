# Thin Portrait Relief for Medals

`portrait_37p8mm_5layers.stl` is an applique with a diameter of 37.8 mm and a maximum thickness of 1.0 mm. It does not include the medal body. Its diameter provides 0.2 mm clearance within the existing model's 38 mm front recess.

Place the bottom at Z = 0 on the build plate and print both the first and subsequent layers at 0.2 mm. The five height levels are 0.2, 0.4, 0.6, 0.8, and 1.0 mm. A full circular base, 0.2 mm thick, supports all features. Detail reproduction depends on the nozzle diameter and slicer; physical printing with a 0.4 mm nozzle has not been verified. Brighter regions are taller. On a single-color print, shadows from the steps affect its appearance.

## Processing Method

1. Use the built-in imagegen tool to create a grayscale relief image from the original photograph while preserving the person's face and pose. The generated image is not a precise depth estimate of the photograph and includes approximate facial details.
2. Sample the image as a height field at 0.1 mm intervals and suppress small-scale noise with a 3 × 3 median filter.
3. Quantize heights at grayscale thresholds of 90, 135, 175, and 215. Remove isolated raised regions smaller than 0.12 mm². Ensure each upper layer's mask is contained within the layer below.
4. Convert masks to polygons, resolve point contacts with a 0.002 mm expansion, and take their solid union with the circular base.
5. Check mesh closure, orientation, connectedness, and overall dimensions. Record results in `validation.json`.

`height_5levels.png` shows quantized heights: white is 1 mm and the darkest region is 0.2 mm. `layer_1.png` through `layer_5.png` are cross-section masks at each height. `mesh_preview.png` is a shaded preview of the actual STL geometry, not a photograph of a print.

## Regeneration

Install the dependencies in a Python environment. Run these commands from this script directory:

```bash
pip install numpy pillow scipy shapely trimesh mapbox-earcut manifold3d matplotlib
python build_relief.py
# Change the outer diameter; facial details scale by the same ratio.
python build_relief.py --diameter 36 --output ../../outputs/3d/portrait_relief/diameter36
```

The default source and output directory are under `outputs/3d/portrait_relief/` at the repository root. The output STL filename is fixed, so use a separate output directory for a different diameter.

## Instructions Supplied to imagegen

Edit the original photograph while preserving the same person's facial proportions, expression, hairline, eyes, eyebrows, nose, mouth, and pose with both hands behind the head. Use a circular, front-facing composition and a purely grayscale height field. Make the hair and clothing dark, the face bright, and the eyes, eyebrows, nostrils, and mouth dark recesses.

Omit skin pores, fine hair, fabric texture, and speckles. Prioritize broad shapes recognizable on a medal roughly 40 mm across. Do not add directional shadows, metallic textures, text, or decoration.

The generated image retains shading, so this process produces a grayscale relief rather than an anatomical 3D reconstruction.
