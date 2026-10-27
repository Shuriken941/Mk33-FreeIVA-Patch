"""Static authored-collider checks. No KSP/Unity runtime claim. SPDX-License-Identifier: MIT.
Run with Python 3 + numpy. Uses only our parametric geometry JSON, no game art.
Capsule distance is exact segment/triangle Euclidean distance at sampled poses;
swept clearance is conservatively bounded by the maximum step between poses.
"""
from pathlib import Path
import json
import numpy as np
from collections import defaultdict, deque
ROOT=Path(__file__).resolve().parent.parent

def point_triangle(p,tri):
    # Closest point on each triangle, combining plane projection and its edges.
    a,b,c=tri[:,0],tri[:,1],tri[:,2]
    ab=b-a;ac=c-a;n=np.cross(ab,ac);n2=np.sum(n*n,axis=1)
    valid=n2>1e-30
    t=np.divide(np.sum((p-a)*n,axis=1),n2,out=np.zeros_like(n2),where=valid)
    q=p-t[:,None]*n
    s1=np.sum(np.cross(b-a,q-a)*n,axis=1)
    s2=np.sum(np.cross(c-b,q-b)*n,axis=1)
    s3=np.sum(np.cross(a-c,q-c)*n,axis=1)
    # Scale barycentric tolerance by squared triangle area. An absolute
    # tolerance made tiny source-cut slivers falsely contain distant points.
    tolerance=1e-12*n2
    inside=valid&(s1>=-tolerance)&(s2>=-tolerance)&(s3>=-tolerance)
    d=np.where(inside,np.sum((q-p)**2,axis=1),np.inf)
    for u,v in ((a,b),(b,c),(c,a)):
        e=v-u;ee=np.sum(e*e,axis=1)
        f=np.clip(np.divide(np.sum((p-u)*e,axis=1),ee,out=np.zeros_like(ee),where=ee>1e-30),0,1)
        d=np.minimum(d,np.sum((u+f[:,None]*e-p)**2,axis=1))
    return d

def segment_segment(p,q,a,b):
    # Ericson closest-points with clamping; vectorized for all triangle edges.
    d1=q-p;d2=b-a;r=p-a
    A=np.dot(d1,d1);E=np.sum(d2*d2,axis=1);F=np.sum(d2*r,axis=1)
    C=r@d1;B=d2@d1;den=A*E-B*B
    s=np.divide(B*F-C*E,den,out=np.zeros_like(den),where=np.abs(den)>1e-14*A*E)
    s=np.clip(s,0,1);t=np.divide(B*s+F,E,out=np.zeros_like(E),where=E>1e-30)
    low=t<0;high=t>1
    s=np.where(low,np.clip(-C/A,0,1),s)
    s=np.where(high,np.clip((B-C)/A,0,1),s)
    t=np.clip(t,0,1)
    s=np.where(E>1e-30,s,np.clip(-C/A,0,1))
    return np.sum((p+s[:,None]*d1-(a+t[:,None]*d2))**2,axis=1)

def segment_triangle(p,q,tri):
    d=np.minimum(point_triangle(p,tri),point_triangle(q,tri))
    for i,j in ((0,1),(1,2),(2,0)):
        d=np.minimum(d,segment_segment(p,q,tri[:,i],tri[:,j]))
    a,b,c=tri[:,0],tri[:,1],tri[:,2];n=np.cross(b-a,c-a)
    n2=np.sum(n*n,axis=1)
    den=n@(q-p);limit=1e-14*np.sqrt(n2)*np.linalg.norm(q-p)
    t=np.divide(np.sum(n*(a-p),axis=1),den,out=np.full_like(den,np.inf),where=np.abs(den)>limit)
    safe_t=np.where(np.isfinite(t),t,0)
    hit=p+safe_t[:,None]*(q-p)
    within=n2>1e-30
    for u,v in ((a,b),(b,c),(c,a)):
        within&=np.sum(np.cross(v-u,hit-u)*n,axis=1)>=-1e-12*n2
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

data=json.loads((ROOT/'Tests/corridor-geometry.json').read_text())
report={'in_game_tested':False,'method':'Euclidean segment/triangle tests at <=5mm sample spacing; subtract 5mm Lipschitz bound for swept clearance. Capsule vertical in local IVA; gravity, stepping, Unity cooking, visual source cuts and seat-to-route access are not modeled here.','models':{}}
for name,m in data['models'].items():
    v=np.array(m['vertices']);f=np.array(m['triangles']);tri=v[f]
    ar=np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=1)
    if name=='CockpitCorridor':
        C=np.array(m['ports'][0]);T=np.array(m['ports'][1]);junction=C+(T-C)*((.525-C[2])/(T[2]-C[2]))
        paths={'main_forward': [C,T], 'main_reverse':[T,C], 'upper_to_main':[(0,1.49,-.04404),(0,1.49,.525),junction.tolist()], 'main_to_upper':[junction.tolist(),(0,1.49,.525),(0,1.49,-.04404)]}
        expected=3
    else:
        route=m.get('route',m['ports'])
        paths={'forward':route,'reverse':list(reversed(route))};expected=2
    top=topology(v,f);top['expected_boundary_loops']=expected
    checks={'topology':top,'degenerate_triangles':int(sum(ar<1e-10)),'paths':{}}
    assert top['boundary_loops']==expected and top['boundary_vertex_degrees_all_two'] and top['nonmanifold_edges']==0,checks
    assert checks['degenerate_triangles']==0,checks
    for label,points in paths.items():
        checks['paths'][label]={'body':test_path(tri,points),'helmet_capsule':test_path(tri,points,True)}
        assert checks['paths'][label]['body']['clear'],(name,label,checks['paths'][label])
        assert checks['paths'][label]['helmet_capsule']['clear'],(name,label,checks['paths'][label])
    report['models'][name]=checks
    if 'central_seal' in m:
        # Include the actual, solid central seal triangles in the motion check.
        seal=m['central_seal'];st=np.array(seal['vertices'])[np.array(seal['triangles'])]
        combined=np.concatenate([tri,st])
        checks['with_central_roof_sealed']={label:{'body':test_path(combined,points),'helmet_capsule':test_path(combined,points,True)} for label,points in paths.items()}
        assert all(x[k]['clear'] for x in checks['with_central_roof_sealed'].values() for k in ['body','helmet_capsule'])
(ROOT/'Tests/corridor-clearance-checks.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
