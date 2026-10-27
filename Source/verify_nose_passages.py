"""Validate actual exported nose skins and selected capsule centre routes.

SPDX-License-Identifier: MIT. Python 3 + NumPy. Geometry is read from .mu,
not merely trusted from the generator report. Does not run KSP or PhysX.
Distance/topology routines are shared original math from validate_corridors.py.
"""
from pathlib import Path
from collections import defaultdict
import json
import sys
import numpy as np
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'Source'/'source_checks'))
from mu import Mu

def point_triangle(p,tri):
    # Closest point on each triangle, combining plane projection and its edges.
    a,b,c=tri[:,0],tri[:,1],tri[:,2]
    ab=b-a;ac=c-a;n=np.cross(ab,ac);n2=np.sum(n*n,axis=1)
    t=np.sum((p-a)*n,axis=1)/n2
    q=p-t[:,None]*n
    s1=np.sum(np.cross(b-a,q-a)*n,axis=1)
    s2=np.sum(np.cross(c-b,q-b)*n,axis=1)
    s3=np.sum(np.cross(a-c,q-c)*n,axis=1)
    inside=(s1>=-1e-12)&(s2>=-1e-12)&(s3>=-1e-12)
    d=np.where(inside,np.sum((q-p)**2,axis=1),np.inf)
    for u,v in ((a,b),(b,c),(c,a)):
        e=v-u;f=np.clip(np.sum((p-u)*e,axis=1)/np.sum(e*e,axis=1),0,1)
        d=np.minimum(d,np.sum((u+f[:,None]*e-p)**2,axis=1))
    return d

def segment_segment(p,q,a,b):
    # Ericson closest-points with clamping; vectorized for all triangle edges.
    d1=q-p;d2=b-a;r=p-a
    A=np.dot(d1,d1);E=np.sum(d2*d2,axis=1);F=np.sum(d2*r,axis=1)
    C=r@d1;B=d2@d1;den=A*E-B*B
    s=np.divide(B*F-C*E,den,out=np.zeros_like(den),where=np.abs(den)>1e-18)
    s=np.clip(s,0,1);t=(B*s+F)/E
    low=t<0;high=t>1
    s=np.where(low,np.clip(-C/A,0,1),s)
    s=np.where(high,np.clip((B-C)/A,0,1),s)
    t=np.clip(t,0,1)
    return np.sum((p+s[:,None]*d1-(a+t[:,None]*d2))**2,axis=1)

def segment_triangle(p,q,tri):
    d=np.minimum(point_triangle(p,tri),point_triangle(q,tri))
    for i,j in ((0,1),(1,2),(2,0)):
        d=np.minimum(d,segment_segment(p,q,tri[:,i],tri[:,j]))
    a,b,c=tri[:,0],tri[:,1],tri[:,2];n=np.cross(b-a,c-a)
    den=n@(q-p);t=np.divide(np.sum(n*(a-p),axis=1),den,out=np.full_like(den,np.inf),where=np.abs(den)>1e-15)
    safe_t=np.where(np.isfinite(t),t,0)
    hit=p+safe_t[:,None]*(q-p)
    within=np.ones(len(tri),dtype=bool)
    for u,v in ((a,b),(b,c),(c,a)):
        within&=np.sum(np.cross(v-u,hit-u)*n,axis=1)>=-1e-12
    d=np.where(within&(t>=0)&(t<=1),0,d)
    return d

def sample_segments(waypoints,step=.005):
    pts=[]
    for a,b in zip(waypoints[:-1],waypoints[1:]):
        a,b=np.array(a),np.array(b);N=max(1,int(np.ceil(np.linalg.norm(b-a)/step)))
        pts.extend(np.linspace(a,b,N+1).tolist())
    return np.array(pts)

def test_path(tri,waypoints,helmet=False):
    points=sample_segments(waypoints)
    clearance=[]
    for p in points:
        radius=.225 if helmet else .2
        half_segment=.3-radius
        d=segment_triangle(p-[0,half_segment,0],p+[0,half_segment,0],tri)
        clearance.append(float(np.sqrt(d.min())-radius))
    worst=int(np.argmin(clearance));sweep_bound=float(min(clearance)-.005)
    return {'sample_count':len(points),'max_step_metres':.005,'min_sampled_clearance_metres':min(clearance),'conservative_swept_clearance_lower_bound_metres':sweep_bound,'worst_center':points[worst].tolist(),'clear':sweep_bound>0,'shape':'standing capsule radius .225 height .60' if helmet else 'standing capsule radius .20 height .60'}

def topology(verts,faces):
    # Boolean introduces duplicate coplanar vertices; weld geometrically for topology only.
    _,indices=np.unique(np.round(verts,6),axis=0,return_inverse=True);f=indices[faces]
    edges=defaultdict(int)
    for t in f:
        for a,b in zip(t,np.roll(t,-1)):edges[tuple(sorted((int(a),int(b))))]+=1
    boundary=[e for e,n in edges.items() if n==1];g=defaultdict(list)
    for a,b in boundary:g[a].append(b);g[b].append(a)
    pending=set(g);loops=0
    while pending:
        loops+=1;q=[pending.pop()]
        while q:
            a=q.pop()
            for b in g[a]:
                if b in pending:pending.remove(b);q.append(b)
    return {'triangles':len(f),'boundary_loops':loops,'boundary_vertex_degrees_all_two':all(len(x)==2 for x in g.values()),'nonmanifold_edges':sum(n>2 for n in edges.values()),'boundary_edges':len(boundary)}

def walk(o):
    yield o
    for c in o.children:yield from walk(c)


def decoded(mesh):
    return np.asarray(mesh.verts)[:,[0,2,1]],np.asarray(sum(mesh.submeshes,[]))[:,[0,2,1]]


report={'in_game_tested':False,'native_meshcutter_executed':False,
        'method':'Decode actual .mu collision triangles; exact segment/triangle distance at <=5mm centre spacing, subtract 5mm sweep bound. Tests only own skins and stated central trajectories, not source cuts, loader, gravity, attached-part orientation or seating.',
        'models':{}}
authored=json.loads((ROOT/'Tests'/'nose-passage-geometry.json').read_text())['models']
static_triangles={}
dynamic_world_triangles=None
for filename,data in authored.items():
    model=Mu().read(str(ROOT/'Models'/(filename+'.mu')))
    items=list(walk(model.obj))
    node=next(o for o in items if o.transform.name==data['collider'])
    assert node.tag_and_layer.layer==16
    assert not node.collider.convex and not node.collider.isTrigger
    v,f=decoded(node.collider.mesh)
    assert np.allclose(v,data['vertices'],atol=1e-6,rtol=0)
    canonical=lambda face:min(tuple(np.roll(face,k)) for k in range(3))
    assert sorted(map(canonical,f))==sorted(map(canonical,np.array(data['triangles'])))
    tri=v[f]
    static_triangles[filename]=tri
    normals=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0])
    assert np.all(np.linalg.norm(normals,axis=1)>1e-9)
    start,end=np.asarray(data['ports'])
    centers=tri.mean(1)
    t=(centers[:,2]-start[2])/(end[2]-start[2])
    axis=start+(end-start)*t[:,None]
    assert np.all(np.sum(normals*(centers-axis),axis=1)<0),'skin must face inward'
    topo=topology(v,f)
    assert topo['boundary_loops']==2 and topo['nonmanifold_edges']==0
    assert topo['boundary_vertex_degrees_all_two']
    assert not any(np.ptp(face[:,2])<1e-6 for face in tri),'endcaps must not seal route'
    paths={}
    for label,route in [('forward',[start,end]),('reverse',[end,start])]:
        paths[label]={}
        for helmet in [False,True]:
            result=test_path(tri,route,helmet)
            assert result['clear'],(filename,label,result)
            paths[label]['helmet' if helmet else 'body']=result
    lights=[o for o in items if hasattr(o,'light')]
    assert lights
    for light in lights:assert light.light.cullingMask==((1<<16)|(1<<20))
    for o in items:
        if hasattr(o,'renderer'):
            assert len(o.shared_mesh.uvs)==len(o.shared_mesh.verts)
            assert len(o.shared_mesh.normals)==len(o.shared_mesh.verts)
            assert all(0<=m<len(model.materials) for m in o.renderer.materials)
        if 'Fixture' in o.transform.name:assert not hasattr(o,'collider')
    report['models'][filename]={'topology':topo,'export_matches_authored_data':True,
                              'inward_skin':True,'open_terminal_rings':True,
                              'point_lights':len(lights),'capsule_paths':paths}
    if filename=='NoseDockPassage':
        tube=next(o for o in items if o.transform.name=='Mk33NoseDockTube')
        # mu.py stores Blender-order positions and wxyz rotations.
        position=np.array(tube.transform.localPosition)[[0,2,1]]
        assert np.allclose(position,data['dynamic_tube']['origin'],atol=1e-6)
        from scipy.spatial.transform import Rotation
        w,x,y,z=tube.transform.localRotation
        direction=Rotation.from_quat([x,y,z,w]).apply([0,0,-1])
        # Decoder flips Unity Y/Z: Unity down=(0,-1,0) -> Blender(0,0,-1),
        # outward Unity -Z -> Blender(0,-1,0).
        assert np.allclose(direction,[0,-1,0],atol=1e-6),direction
        vv,ff=decoded(tube.collider.mesh)
        assert np.allclose([vv[:,1].min(),vv[:,1].max()],[-1,0],atol=1e-6)
        assert tube.tag_and_layer.layer==16 and not tube.collider.convex and not tube.collider.isTrigger
        vbl=np.asarray(tube.collider.mesh.verts)
        world_bl=Rotation.from_quat([x,y,z,w]).apply(vbl)+np.asarray(tube.transform.localPosition)
        world_unity=world_bl[:,[0,2,1]]
        world_tri=world_unity[ff]
        dynamic_world_triangles=world_tri
        tube_topo=topology(vv,ff)
        assert tube_topo['boundary_loops']==2 and tube_topo['nonmanifold_edges']==0
        assert not any(np.ptp(face[:,1])<1e-6 for face in vv[ff])
        tube_paths={}
        for helmet in [False,True]:
            result=test_path(world_tri,[position,position+[0,0,-1]],helmet)
            assert result['clear'],result
            tube_paths['helmet' if helmet else 'body']=result
        report['models'][filename]['native_dynamic_tube_axis_outward']=True
        report['models'][filename]['native_dynamic_tube_length']=1.
        report['models'][filename]['native_dynamic_tube_topology']=tube_topo
        report['models'][filename]['native_dynamic_tube_capsule_paths']=tube_paths
# The official source craft places ProbeCore and nosecone with the same
# relative orientation; nose origin is ProbeCore.topNode. Joining all decoded
# surfaces tests the actual skin seam, including slight centreline slope.
front=np.asarray(authored['ProbeCorePassage']['ports'][1])
rear=np.asarray(authored['ProbeCorePassage']['ports'][0])
nostart=np.asarray(authored['NoseDockPassage']['ports'][0])
noend=np.asarray(authored['NoseDockPassage']['ports'][1])
joined=np.concatenate([static_triangles['ProbeCorePassage'],
                       static_triangles['NoseDockPassage']+front,
                       dynamic_world_triangles+front])
combined={}
for reverse in [False,True]:
    route=[rear,front,front+noend,front+noend+[0,0,-1]]
    if reverse:route=list(reversed(route))
    label='reverse' if reverse else 'forward'
    combined[label]={}
    for helmet in [False,True]:
        result=test_path(joined,route,helmet)
        assert result['clear'],result
        combined[label]['helmet' if helmet else 'body']=result
report['combined_probe_to_nose_route']={'source_craft_relative_orientation':'identity',
    'nose_origin_in_probe_iva':front.tolist(),'capsule_paths':combined,
    'scope':'combined own skins only; native door opening, part attachment and cockpit source cut remain separate checks'}
(ROOT/'Tests'/'nose-passage-checks.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
