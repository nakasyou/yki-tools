"""Modify the already-generated normal STL; embed relief without extra thickness.

Run: uv run --with numpy --with trimesh --with manifold3d --with matplotlib --with scipy
     python 3d/portrait_relief/embed_in_normal.py
"""
from pathlib import Path
import hashlib
import json
import numpy as np
import trimesh

HERE = Path(__file__).resolve().parents[2] / 'outputs/3d/portrait_relief'
BASE = HERE.parent / 'B661_E83A_normal.stl'
RELIEF = HERE / 'portrait_37p8mm_5layers.stl'
OUTPUT = HERE.parent / 'B661_E83A_normal_portrait.stl'


def main():
    base = trimesh.load_mesh(BASE)
    relief = trimesh.load_mesh(RELIEF)
    if not base.is_volume or not relief.is_volume:
        raise ValueError('Input STL must be a closed, consistently oriented solid')
    thickness = float(relief.extents[2])
    if not np.allclose(relief.bounds[0, 2], 0) or not np.isclose(thickness, 1):
        raise ValueError('Expected relief at Z=0..1 mm')
    # The normal medal's display face points toward -Z. Rotate, do not reflect.
    # Turn the portrait 180 degrees in its plane relative to the first build:
    # the user inserts the medal from the side carrying the reading pegs.
    transform = np.diag([-1., 1., -1., 1.])
    transform[2, 3] = thickness
    relief.apply_transform(transform)
    # Cut the front pocket into the imported STL, leaving 0.01 mm overlap
    # between the pocket floor and relief backing for a robust solid union.
    pocket = trimesh.creation.cylinder(radius=18.92, height=1.99, sections=512)
    pocket.apply_translation([0, 0, -0.005])  # Z=-1..0.99
    carved = trimesh.boolean.difference([base, pocket], engine='manifold')
    # Extend only the flat backing by 0.02 mm radially to match the pocket.
    # This avoids intersecting almost-identical tessellated circle boundaries.
    backing = trimesh.creation.cylinder(radius=18.92, height=0.21, sections=512)
    backing.apply_translation([0, 0, 0.905])  # Z=0.8..1.01
    result = trimesh.boolean.union([carved, relief, backing], engine='manifold')
    result.export(OUTPUT)
    result = trimesh.load_mesh(OUTPUT)
    if not result.is_volume or len(result.split()) != 1:
        raise ValueError('Output must be one closed solid')
    if not np.allclose(result.bounds, base.bounds, atol=1e-5):
        raise ValueError('Original medal bounds changed')
    # All modifications must remain in the front pocket below Z=1 mm.
    upper = trimesh.creation.box(extents=[60, 60, 10])
    upper.apply_translation([0, 0, 6.001])
    before = trimesh.boolean.intersection([base, upper], engine='manifold')
    after = trimesh.boolean.intersection([result, upper], engine='manifold')
    deltas = [
        trimesh.boolean.difference([before, after], engine='manifold'),
        trimesh.boolean.difference([after, before], engine='manifold'),
    ]
    changed_upper_volume = sum(float(abs(delta.volume)) for delta in deltas if len(delta.faces))
    if changed_upper_volume > 1e-5:
        raise ValueError('Reading-side geometry changed')
    report = dict(
        base=str(BASE), relief=str(RELIEF), output=str(OUTPUT),
        sha256=hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
        canonical_bits=['1110', '1000', '0011', '1010'],
        mode='normal', bounds_mm=result.bounds.tolist(), extents_mm=result.extents.tolist(),
        watertight=result.is_watertight, winding_consistent=result.is_winding_consistent,
        components=len(result.split()), triangles=len(result.faces),
        volume_mm3=float(result.volume), pocket_diameter_mm=37.84,
        pocket_floor_z_mm=0.99, relief_z_range_mm=[0, 1],
        reading_side_difference_volume_mm3=changed_upper_volume,
        hardware_tested=False,
        portrait_in_plane_correction_degrees=180,
        insertion_direction='reading-peg side first (user specified)',
    )
    OUTPUT.with_suffix('.validation.json').write_text(json.dumps(report, indent=2)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    fig = plt.figure(figsize=(10, 5))
    for i, elev in enumerate([-70, 65], 1):
        ax = fig.add_subplot(1, 2, i, projection='3d')
        normals=result.face_normals
        light=np.array([-.3, -.5, -1 if elev<0 else 1]); light/=np.linalg.norm(light)
        shade=.35+.55*np.maximum(0, normals@light)
        colors=np.column_stack([shade, shade, shade, np.ones(len(shade))])
        ax.add_collection3d(Poly3DCollection(result.triangles,facecolors=colors,edgecolors='none'))
        ax.set_xlim(-22,22);ax.set_ylim(-22,22);ax.set_zlim(0,3.8)
        ax.set_box_aspect((43,43,3.8));ax.view_init(elev=elev,azim=-90)
        ax.set_title('Portrait face' if i==1 else 'Reading side');ax.set_axis_off()
    fig.savefig(OUTPUT.with_suffix('.png'),dpi=160,bbox_inches='tight')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
