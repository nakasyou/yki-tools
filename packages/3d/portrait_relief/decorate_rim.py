"""Decorate the existing portrait medal STL; all edits remain below Z=1 mm.

uv run --with numpy --with trimesh --with manifold3d --with shapely --with scipy python 3d/portrait_relief/decorate_rim.py
"""
from pathlib import Path
import json
import hashlib
import numpy as np
import trimesh
import manifold3d
from shapely.geometry import Point, Polygon, box

ROOT = Path(__file__).resolve().parents[2] / 'outputs/3d'
SOURCE = ROOT / 'B661_E83A_normal_portrait.stl'
OUTPUT = ROOT / 'B661_E83A_normal_portrait_rim.stl'


def solid(poly, low, high):
    contours = [np.asarray(poly.exterior.coords)[:-1]]
    contours += [np.asarray(r.coords)[:-1] for r in poly.interiors]
    m = manifold3d.CrossSection(contours, manifold3d.FillRule.EvenOdd).extrude(high-low).to_mesh()
    result = trimesh.Trimesh(vertices=np.asarray(m.vert_properties)[:, :3], faces=np.asarray(m.tri_verts))
    result.apply_translation([0, 0, low])
    return result


def bezier(start, control1, control2, end):
    t = np.linspace(0, 1, 16)[:, None]
    return ((1-t)**3*np.array(start) + 3*(1-t)**2*t*np.array(control1)
            + 3*(1-t)*t*t*np.array(control2) + t**3*np.array(end)).tolist()


def note_outline():
    # Hand-traced silhouette of the supplied note: oval head, tilted stem,
    # and short angular flag with a notch; no generic font glyph substitution.
    points = [[111, 20], [137, 18], [148, 27], [169, 28], [173, 39],
              [164, 48], [151, 43], [141, 44], [143, 70]]
    points += bezier([143,70],[153,95],[138,129],[110,135])[1:]
    points += bezier([110,135],[84,141],[67,132],[65,111])[1:]
    points += bezier([65,111],[59,89],[81,75],[105,77])[1:]
    points += [[123, 78], [111, 20]]
    xy=np.asarray(points,dtype=float)
    xy[:,0]=(xy[:,0]-117)*3.55/114
    xy[:,1]=(77-xy[:,1])*3.55/124 - 19.22
    # Facing -Z: screen right is world -X. Keep the note readable on the front.
    xy[:,0]*=-1
    return Polygon(xy)


def main():
    source=trimesh.load_mesh(SOURCE)
    disk=Point(0,0).buffer(21.35,quad_segs=128)
    top=box(-2.7,17.45,2.7,21.2).buffer(.15,quad_segs=8).intersection(disk)
    bottom=box(-2.65,-21.2,2.65,-17.2).buffer(.15,quad_segs=8).intersection(disk)
    cuts=[]
    for panel in [top,bottom]: cuts.append(solid(panel,-.1,.20))
    cutter=trimesh.boolean.union(cuts,engine='manifold')
    carved=trimesh.boolean.difference([source,cutter],engine='manifold')
    # Panels span the portrait's outer edge; a flat floor prevents the image
    # terraces from showing through behind the symbols.
    additions=[solid(panel,0,.95) for panel in [top,bottom]]
    arrow=Polygon([(0,20.9),(-1.25,19.3),(1.25,19.3)])
    arrow=arrow.union(box(-.28,18.7,.28,19.6))
    note=note_outline()
    symbol_cuts=[]
    for shape in [arrow.intersection(top),note.intersection(bottom)]:
        for poly in getattr(shape,'geoms',[shape]): symbol_cuts.append(solid(poly,-.1,.20))
    result=trimesh.boolean.union([carved,*additions],engine='manifold')
    # Sink the entire symbol silhouette, rather than drawing its outline.
    result=trimesh.boolean.difference([result,trimesh.boolean.union(symbol_cuts,engine='manifold')],engine='manifold')
    result.export(OUTPUT)
    result=trimesh.load_mesh(OUTPUT)
    assert result.is_volume and len(result.split())==1
    assert np.allclose(result.bounds,source.bounds,atol=1e-5)
    upper=trimesh.creation.box(extents=[60,60,10]);upper.apply_translation([0,0,6.001])
    a=trimesh.boolean.intersection([source,upper],engine='manifold')
    b=trimesh.boolean.intersection([result,upper],engine='manifold')
    deltas=[trimesh.boolean.difference([a,b],engine='manifold'),trimesh.boolean.difference([b,a],engine='manifold')]
    difference=sum(abs(float(m.volume)) for m in deltas if len(m.faces))
    assert difference<1e-5
    report=dict(source=str(SOURCE),output=str(OUTPUT),sha256=hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
        extents_mm=result.extents.tolist(),watertight=result.is_watertight,components=len(result.split()),
        triangles=len(result.faces),reading_side_difference_volume_mm3=difference,
        ring_grooves=False,radial_cuts=False,symbol_recess_depth_mm=.20,
        portrait_orientation='unchanged',arrow_position='positive Y, reading pegs insertion side',
        note='filled silhouette recessed; hand-traced angular flag and oval head',hardware_tested=False)
    OUTPUT.with_suffix('.validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
