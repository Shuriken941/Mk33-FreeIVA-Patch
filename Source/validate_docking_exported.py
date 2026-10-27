"""Actual authored .mu collider seam checks; SPDX-License-Identifier: MIT.

Python 3 + numpy. This checks exported triangles, not only generator arrays.
It does not execute Unity physics, FreeIVA interaction or KSP docking.
"""
from pathlib import Path
import contextlib
import io
import json
import sys
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
sys.path.insert(0,str(HERE/'source_checks'))
from mu import Mu
with contextlib.redirect_stdout(io.StringIO()):
    from validate_corridors import test_path, topology, segment_triangle

def matrix(t):
    w,x,y,z=t.localRotation
    r=np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
                [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
                [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
    m=np.eye(4);m[:3,:3]=r@np.diag(t.localScale);m[:3,3]=t.localPosition
    return m

def colliders(name,tube_scale=None):
    result={}
    def visit(o,parent):
        local=matrix(o.transform)
        if o.transform.name=='Mk33KrewDockTube' and tube_scale is not None:
            local[:3,:3]=local[:3,:3]@np.diag([1,1,tube_scale])
        world=parent@local
        c=getattr(o,'collider',None)
        if c is not None and hasattr(c,'mesh'):
            # .mu reader converts Unity into Blender coordinates and winding.
            # Transform in those coordinates first, then convert back to Unity.
            v=(np.array(c.mesh.verts)@world[:3,:3].T+world[:3,3])[:,[0,2,1]]
            f=np.array(sum(c.mesh.submeshes,[]))[:,[0,2,1]]
            result[o.transform.name]={'v':v,'f':f,'triangles':v[f],'layer':o.tag_and_layer.layer,'trigger':bool(c.isTrigger),'convex':bool(c.convex)}
        for child in o.children:visit(child,world)
    mu=Mu().read(str(ROOT/'Models'/(name+'.mu')));visit(mu.obj,np.eye(4))
    return result

def fixture_triangles(name):
    result=[]
    def visit(o,parent):
        world=parent@matrix(o.transform)
        if 'Fixture' in o.transform.name and hasattr(o,'shared_mesh'):
            v=(np.array(o.shared_mesh.verts)@world[:3,:3].T+world[:3,3])[:,[0,2,1]]
            f=np.array(sum(o.shared_mesh.submeshes,[]))[:,[0,2,1]]
            result.extend(v[f])
        for child in o.children:visit(child,world)
    mu=Mu().read(str(ROOT/'Models'/(name+'.mu')));visit(mu.obj,np.eye(4))
    return np.array(result)

body=colliders('KrewDockPassage')
shell=body['Mk33KrewDockPassageShell']
assert 'Mk33KrewCentralSeal' not in body, 'The true central docking route must stay open.'
meta=json.loads((ROOT/'Tests/corridor-geometry.json').read_text())['models']['KrewDockPassage']
def canonical(face):return min(tuple(np.roll(face,k)) for k in range(3))
assert np.allclose(shell['v'],meta['vertices'],atol=1e-6)
assert sorted(map(canonical,shell['f']))==sorted(map(canonical,meta['triangles']))
assert all(c['layer']==16 and not c['trigger'] and not c['convex'] for c in body.values())
outlet=float(meta['outlet_y'])
assert np.isclose(outlet,1.80) and np.isclose(meta['radius'],.39)
# The fixed lining stays below the original central shaft roof. Its front neck
# projects only 16 mm into the cabin at the real AIRLOCK door, never above the
# outside EVA hatch. The telescoping portion alone crosses the roof.
assert shell['v'][:,1].min()>=.649999 and shell['v'][:,1].max()<=1.800001
assert np.abs(shell['v'][:,0]).max()<=.390001
assert shell['v'][:,2].min()>=.079999 and shell['v'][:,2].max()<=1.005513
scales={'native_unit_length':1.0,'deployed_docking_plane':2.8598599433898926-outlet}
report={'in_game_tested':False,'actual_exported_colliders_checked':True,'static_central_shaft':topology(shell['v'],shell['f']),'outside_offset_dogleg_absent':True,'central_docking_route_not_sealed':True,'fixed_lining_below_original_roof':True,'models':{}}
for label,scale in scales.items():
    sleeve=colliders('KrewDockTube',scale)['Mk33KrewDockTube']
    assert sleeve['layer']==16 and not sleeve['trigger'] and not sleeve['convex']
    assert not np.any(np.ptp(sleeve['triangles'][:,:,1],axis=1)<1e-7)
    radial=np.linalg.norm(sleeve['v'][:,[0,2]]-np.array([0,.61551148]),axis=1)
    assert radial.max()<.390001 and radial.max()<.3989
    tube_start=sleeve['v'][np.isclose(sleeve['v'][:,1],outlet,atol=1e-6)]
    shell_exit=shell['v'][np.isclose(shell['v'][:,1],outlet,atol=1e-6)]
    assert len(tube_start)==32 and len(shell_exit)==32
    seam_distance=np.linalg.norm(tube_start[:,None,:]-shell_exit[None,:,:],axis=2)
    assert seam_distance.min(1).max()<1e-6
    tris=np.concatenate([shell['triangles'],sleeve['triangles']])
    route=meta['route'][:-1]+[(0,outlet+scale,.61551148)]
    checks={}
    for direction,path in [('forward',route),('reverse',list(reversed(route)))]:
        checks[direction]={'body':test_path(tris,path),'helmet_capsule':test_path(tris,path,True)}
        assert all(c['clear'] for c in checks[direction].values())
    report['models'][label]={'tube_scale_y':scale,'outlet_seam_maximum_vertex_gap_m':float(seam_distance.min(1).max()),'maximum_tube_radius_m':float(radial.max()),'within_original_port_lip_radius_m':.3989,'no_tube_caps':True,'paths':checks}
    fixture_checks={k:test_path(np.concatenate([tris,fixture_triangles('KrewDockPassage')]),route,k=='helmet_capsule') for k in ['body','helmet_capsule']}
    assert all(c['clear'] for c in fixture_checks.values())
    report['models'][label]['including_decorative_fixtures']=fixture_checks
(ROOT/'Tests/docking-exported-clearance-checks.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
