"""Convert a portrait height field into a connected, five-layer medal applique.

Dependencies: numpy pillow scipy shapely trimesh mapbox-earcut manifold3d matplotlib
"""
from pathlib import Path
import argparse
import json
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from shapely.geometry import box, Point
from shapely.ops import unary_union
from shapely.geometry.polygon import orient
import trimesh
import manifold3d


def extrude(poly, height):
    contours = [np.asarray(poly.exterior.coords)[:-1]]
    contours.extend(np.asarray(r.coords)[:-1] for r in poly.interiors)
    solid = manifold3d.CrossSection(contours, manifold3d.FillRule.EvenOdd).extrude(height)
    raw = solid.to_mesh()
    return trimesh.Trimesh(vertices=np.asarray(raw.vert_properties)[:,:3], faces=np.asarray(raw.tri_verts))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--diameter', type=float, default=37.8)
    p.add_argument('--pitch', type=float, default=0.1)
    p.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[2] / 'outputs/3d/portrait_relief/portrait_height_source.png')
    p.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[2] / 'outputs/3d/portrait_relief')
    p.add_argument('--no-crop', action='store_true', help='Source already covers the output disk square')
    p.add_argument('--thresholds', type=float, nargs=4, default=[90, 135, 175, 215])
    p.add_argument('--name', default='portrait_37p8mm_5layers')
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    n = int(round(args.diameter / args.pitch))
    pitch = args.diameter / n
    # The generated disk occupies this normalized square, excluding black margins.
    im = Image.open(args.source).convert('L')
    w, h = im.size
    if not args.no_crop:
        im = im.crop((int(w*.023), int(h*.023), int(w*.971), int(h*.971)))
    field = np.asarray(im.resize((n, n), Image.Resampling.LANCZOS), dtype=float)
    # Median filtering rejects texture while retaining the large facial edges.
    field = ndi.median_filter(field, size=3)
    thresholds = args.thresholds
    yy, xx = np.mgrid[:n, :n]
    inside = ((xx+.5-n/2)**2 + (yy+.5-n/2)**2) < (n/2)**2
    levels = np.ones((n,n), dtype=np.uint8)
    previous = inside.copy()
    masks = []
    for threshold in thresholds:
        mask = (field >= threshold) & previous
        labels, count = ndi.label(mask)
        sizes = np.bincount(labels.ravel())
        # Remove isolated raised specks smaller than 0.12 mm².
        keep = sizes >= max(3, int(.12 / pitch**2))
        keep[0] = False
        mask = keep[labels] & previous
        masks.append(mask)
        levels += mask
        previous = mask
    circle = Point(0,0).buffer(args.diameter/2, quad_segs=192)
    solids = [extrude(circle, .2)]
    layer_areas = [circle.area]
    for k, mask in enumerate(masks):
        runs = []
        for row in range(n):
            edges = np.diff(np.r_[False, mask[row], False].astype(int))
            for start, stop in zip(np.where(edges==1)[0], np.where(edges==-1)[0]):
                runs.append(box((start-n/2)*pitch, (n/2-row-1)*pitch,
                                (stop-n/2)*pitch, (n/2-row)*pitch))
        # A 0.002 mm planar expansion resolves diagonal pixel contacts before triangulation.
        poly = unary_union(runs).buffer(.002, join_style=2).intersection(circle).simplify(.025, preserve_topology=True)
        layer_areas.append(poly.area)
        polys = list(poly.geoms) if poly.geom_type == 'MultiPolygon' else [poly]
        for component in polys:
            if component.is_empty or component.area < .01:
                continue
            # Extend to the underside: every raised region is supported by the base.
            solid = extrude(orient(component), .2*(k+2))
            solid.fix_normals()
            if not solid.is_volume:
                raise ValueError(f'Invalid polygon at layer {k+2}: area={component.area}, watertight={solid.is_watertight}')
            solids.append(solid)
    mesh = trimesh.boolean.union(solids, engine='manifold')
    # Remove edges below STL's practical resolution before float32 export.
    cleaned = manifold3d.Manifold(manifold3d.Mesh(
        np.asarray(mesh.vertices, dtype=np.float32), np.asarray(mesh.faces, dtype=np.uint32))).simplify(.002)
    raw = cleaned.to_mesh()
    mesh = trimesh.Trimesh(vertices=np.asarray(raw.vert_properties)[:,:3], faces=np.asarray(raw.tri_verts))
    mesh.remove_unreferenced_vertices()
    assert mesh.is_watertight and mesh.is_winding_consistent
    assert len(mesh.split()) == 1
    assert np.allclose(mesh.extents, [args.diameter, args.diameter, 1.0], atol=.001)
    mesh.export(args.output / f'{args.name}.stl')
    exported = trimesh.load_mesh(args.output / f'{args.name}.stl')
    assert exported.is_watertight and exported.is_winding_consistent and len(exported.split()) == 1
    # This PNG is an exact discrete height-field diagnostic, not a beauty render.
    diagnostic = np.where(inside, levels*51, 0).astype(np.uint8)
    Image.fromarray(diagnostic).resize((1134,1134), Image.Resampling.NEAREST).save(args.output/'height_5levels.png')
    for k in range(5):
        mask = inside if k == 0 else masks[k-1]
        Image.fromarray((mask*255).astype(np.uint8)).save(args.output/f'layer_{k+1}.png')
    stats = dict(diameter_mm=args.diameter, thickness_mm=1.0, layer_height_mm=.2,
                 base_mm=.2, pitch_mm=pitch, thresholds=thresholds,
                 watertight=bool(mesh.is_watertight), components=len(mesh.split()),
                 extents_mm=mesh.extents.tolist(), triangles=len(mesh.faces),
                 volume_mm3=float(mesh.volume), layer_areas_mm2=layer_areas)
    (args.output/'validation.json').write_text(json.dumps(stats, indent=2)+'\n')
    print(json.dumps(stats, indent=2))
    # Render actual exported geometry under oblique light to show the terraces.
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    fig = plt.figure(figsize=(10,8), facecolor='#eeeeee')
    ax = fig.add_subplot(111, projection='3d')
    ax.set_facecolor('#eeeeee')
    light = np.array([-.45,-.35,.82]); light /= np.linalg.norm(light)
    intensity = .40 + .60*np.maximum(0, mesh.face_normals @ light)
    colors = np.c_[intensity*.93, intensity*.78, intensity*.48, np.ones(len(intensity))]
    ax.add_collection3d(Poly3DCollection(mesh.triangles, facecolors=colors, edgecolors='none', linewidths=0, antialiased=False))
    r=args.diameter/2
    ax.set(xlim=(-r,r), ylim=(-r,r), zlim=(0,2))
    ax.set_box_aspect((args.diameter,args.diameter,2))
    ax.view_init(elev=62, azim=-90)
    ax.set_axis_off()
    fig.savefig(args.output/'mesh_preview.png', dpi=150, bbox_inches='tight')


if __name__ == '__main__':
    main()
