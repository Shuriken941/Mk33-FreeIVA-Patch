"""Check the real rounded AIRLOCK leaf against the configured rectangular cut.

Reads installed original art only. No KSP/Unity/PhysX claim. GPL-2.0-or-later.
"""
import argparse,ast,json
from pathlib import Path
import numpy as np
from inspect_mu import nodes

ROOT=Path(__file__).resolve().parents[2]
def check(assets,width=.60,height=.70):
    entry=next(e for e in nodes(Path(assets)/'crewModuleIVA.mu') if e['name']=='cabinMesh')
    verts=entry['verts'];faces=np.array(sum(entry['mesh'].submeshes,[]));tri=verts[faces]
    lo=np.array([-.34,.67,.02]);hi=np.array([.34,1.44,.125])
    selected=((tri>=lo-1e-6)&(tri<=hi+1e-6)).all((1,2));door=tri[selected]
    assert len(door)==352, 'Original central AIRLOCK geometry changed.'
    tree=ast.parse((ROOT/'Source/validate_corridors.py').read_text())
    tree.body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'point_triangle','segment_segment','segment_triangle'}]
    scope={'np':np};exec(compile(tree,'capsule-distance-functions','exec'),scope)
    def ray(x,y):
        return float(np.sqrt(scope['segment_triangle'](np.array([x,y,0]),np.array([x,y,.14]),door).min()))
    cy=1.055827
    corners=[ray(x,cy+y) for x in [-width/2,width/2] for y in [-height/2,height/2]]
    assert max(corners)<1e-7, ('Aperture corners extend beyond rounded original leaf.',corners)
    maximum=0.
    for x in np.linspace(-width/2,width/2,31):
        for y in np.linspace(cy-height/2,cy+height/2,31):maximum=max(maximum,ray(x,y))
    assert maximum<1e-7, ('Visible original leaf has a hole over the aperture.',maximum)
    old=[ray(x,cy+y) for x in [-.35,.35] for y in [-.40,.40]]
    assert min(old)>.01, 'Negative oversized-rectangle fixture must expose the corner gap.'
    return {'in_game_tested':False,'method':'Line/triangle intersections through original selected AIRLOCK door at all four cut corners and a 31x31 interior grid; regression rejects the earlier oversized rectangle. This checks original visible leaf coverage, not PhysX.','extracted_source_triangles':len(door),'aperture_width_metres':width,'aperture_height_metres':height,'actual_leaf_covers_all_four_aperture_corners':True,'corner_ray_distance_metres':corners,'interior_grid_probes':31*31,'maximum_grid_ray_distance_metres':maximum,'oversized_0_70_by_0_80_corner_ray_distance_metres':old,'oversized_aperture_regression_rejected':True}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--assets',type=Path,required=True);a=p.parse_args();report=check(a.assets)
    (ROOT/'Tests/central-door-coverage-checks.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
