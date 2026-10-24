import sys, json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from mu import Mu

def nodes(path):
    mu=Mu().read(str(path))
    found=[]
    def walk(o, parent):
        t=o.transform
        w,x,y,z=t.localRotation
        transform=np.eye(4)
        transform[:3,:3]=Rotation.from_quat([x,y,z,w]).as_matrix()@np.diag(t.localScale)
        transform[:3,3]=t.localPosition
        world=parent@transform
        item=dict(name=t.name,object=o,matrix=world)
        mesh=getattr(o,'shared_mesh',None)
        if mesh is not None:
            vb=np.array(mesh.verts)@world[:3,:3].T+world[:3,3]
            item['verts']=vb[:,[0,2,1]] # root Unity coords
            item['mesh']=mesh
        found.append(item)
        for child in o.children:walk(child,world)
    walk(mu.obj,np.eye(4))
    return found

if __name__=='__main__':
    path=Path(sys.argv[1])
    ns=nodes(path)
    out=[]
    for item in ns:
        o=item['object'];m=item['matrix'];p=m[:3,3]
        d={'name':item['name'],'position_unity':p[[0,2,1]].tolist()}
        if 'verts' in item:
            v=item['verts'];d['bounds_unity']=[v.min(axis=0).tolist(),v.max(axis=0).tolist()];d['triangles']=len(sum(item['mesh'].submeshes,[]));d['vertices']=len(v)
        if hasattr(o,'collider'):d['collider']=type(o.collider).__name__
        out.append(d)
    print(json.dumps(out,indent=2))
