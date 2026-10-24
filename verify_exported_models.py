"""Verify actual exported .mu geometry against authored data. GPL-2.0-or-later.
Requires NumPy and the supplied GPL mu.py parser; does not run KSP.
"""
from pathlib import Path
import json
import numpy as np
from mu import Mu
ROOT=Path(__file__).resolve().parents[2]
def walk(o):
    yield o
    for c in o.children:yield from walk(c)
def mesh_data(mesh):
    return np.array(mesh.verts)[:,[0,2,1]],np.array(sum(mesh.submeshes,[]))[:,[0,2,1]]
def canonical(f):return min(tuple(np.roll(f,k)) for k in range(3))
report={'in_game_tested':False}
for name,data in json.loads((ROOT/'Tests/corridor-geometry.json').read_text())['models'].items():
    m=Mu().read(str(ROOT/'Models'/(name+'.mu')))
    collider=next(o for o in walk(m.obj) if o.transform.name==data['collider'])
    verts,faces=mesh_data(collider.collider.mesh)
    assert np.allclose(verts,data['vertices'],rtol=0,atol=1e-6)
    assert sorted(map(canonical,faces))==sorted(map(canonical,data['triangles']))
    assert collider.tag_and_layer.layer==16 and not collider.collider.isTrigger and not collider.collider.convex
    assert not any(o.transform.name.startswith('Mk33UpperHandle') for o in walk(m.obj))
    report[name]={'actual_mu_matches_generated_geometry_json':True,'layer':16,'convex':False,'isTrigger':False,'vertex_count':len(verts),'triangle_count':len(faces)}
m=Mu().read(str(ROOT/'Models/CircularHatch.mu'))
door=next(o for o in walk(m.obj) if o.transform.name=='door')
assert door.collider.convex and not door.collider.isTrigger and door.tag_and_layer.layer==16
v,f=mesh_data(door.shared_mesh);t=v[f]
signed=np.sum(np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0])*t.mean(1),axis=1)
assert np.all(signed>0),'door triangles must face outward'
layers=[o.tag_and_layer.layer for o in walk(m.obj) if o.transform.name.startswith('handle')]
assert layers==[20,20]
report['CircularHatch']={'closed_door_convex_collider':True,'door_layer':16,'handle_layers':layers,'all_128_faces_outward':True}
m=Mu().read(str(ROOT/'Models/KrewDockTube.mu'))
matches=[o for o in walk(m.obj) if o.transform.name=='Mk33KrewDockTube']
assert len(matches)==1,'native depth-first tube lookup must be unambiguous'
o=matches[0];v,f=mesh_data(o.collider.mesh);t=v[f];center=np.array([0,-.5,0])
signed=np.sum(np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0])*(t.mean(1)-center),axis=1)
assert np.all(signed<0),'dock tube must face inward'
assert o.tag_and_layer.layer==16 and not o.collider.convex and not o.collider.isTrigger
report['KrewDockTube']={'unique_named_tube':True,'inward_faces':True,'layer':16}
m=Mu().read(str(ROOT/'Models/InteractionPoints.mu'))
assert not any(hasattr(o,'collider') for o in walk(m.obj))
report['InteractionPoints']={'no_embedded_physical_colliders':True}
(ROOT/'Tests/exported-model-checks.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
