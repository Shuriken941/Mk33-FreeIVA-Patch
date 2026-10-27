"""Analytic regressions for distance checks on small source-cut triangles. MIT."""
from pathlib import Path
import ast,json,numpy as np
ROOT=Path(__file__).resolve().parents[2]
tree=ast.parse((ROOT/'Source/validate_corridors.py').read_text());tree.body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'point_triangle','segment_segment','segment_triangle'}]
scope={'np':np};exec(compile(tree,'distance-functions','exec'),scope)
results=[]
for edge in [1e-7,1e-5,.1,1.]:
    tri=np.array([[[2.,0.,0.],[2.+edge,0.,0.],[2.,edge,0.]]])
    d=scope['segment_triangle'](np.array([0.,0.,-1.]),np.array([0.,0.,1.]),tri)[0]
    assert np.isclose(d,4.,rtol=1e-9,atol=1e-12),('far tiny triangle falsely intersected',edge,d)
    x=2.+edge/3;y=edge/3
    hit=scope['segment_triangle'](np.array([x,y,-1.]),np.array([x,y,1.]),tri)[0]
    assert hit<1e-20,('real intersection missed',edge,hit)
    results.append({'edge_metres':edge,'known_separation_metres':2.,'calculated_separation_metres':float(np.sqrt(d)),'actual_ray_intersection_detected':True})
zero=np.array([[[2.,0.,0.],[2.,0.,0.],[2.,0.,0.]]])
assert np.isclose(scope['segment_triangle'](np.array([0.,0.,-1.]),np.array([0.,0.,1.]),zero)[0],4.)
report={'in_game_tested':False,'distance_check_only':True,'method':'Analytic 2m separation and genuine through-triangle intersections for triangles down to .1 micrometre edges; also degenerate point triangle.','cases':results,'degenerate_point_triangle_handles_without_false_plane_hit':True}
(ROOT/'Tests/distance-math-checks.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
