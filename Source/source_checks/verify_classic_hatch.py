"""Check installed FreeIVA classic leaf fit; numerical geometry only, not KSP.
SPDX-License-Identifier: GPL-2.0-or-later. Original art is read, never copied.
"""
from pathlib import Path
import sys,json,hashlib,argparse
import numpy as np
from scipy.spatial.transform import Rotation
from mu import Mu
ROOT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--freeiva',required=True,type=Path,help='Installed GameData/FreeIva directory');args=parser.parse_args()
p=args.freeiva/'Props/FreeIva_Hatch_Round_Size1.mu'
m=Mu().read(str(p));rows=[]
def walk(o,parent=np.eye(4),selected=False):
 t=o.transform;q=t.localRotation;a=np.eye(4);a[:3,:3]=Rotation.from_quat([q[1],q[2],q[3],q[0]]).as_matrix()@np.diag(t.localScale);a[:3,3]=t.localPosition;a=parent@a
 selected=selected or t.name=='Hatch_Size1_Door'
 if selected and hasattr(o,'shared_mesh'):
  v=np.array(o.shared_mesh.verts);v=(np.c_[v,np.ones(len(v))]@a.T)[:,:3]* (.545/.41)
  rows.append((o,v,np.array(sum(o.shared_mesh.submeshes,[]))))
 for c in o.children:walk(c,a,selected)
walk(m.obj)
for o,v,f in rows:print(o.transform.name,len(v),len(f),'Blender bounds',v.min(0),v.max(0))
# Blender model lies in XY at Z=0. Sample ray/triangle projected XY area.
v=rows[0][1];f=rows[0][2];tri=v[f][:,:,:2];a=tri[:,0];u=tri[:,1]-a;w=tri[:,2]-a;den=u[:,0]*w[:,1]-u[:,1]*w[:,0];good=abs(den)>1e-10;a,u,w,den=a[good],u[good],w[good],den[good]
angles=np.linspace(0,2*np.pi,1440,endpoint=False);boundary=np.c_[.525*np.cos(angles),.525*np.sin(angles)]
x=np.linspace(-.525,.525,101);xx,yy=np.meshgrid(x,x);interior=np.c_[xx.ravel(),yy.ravel()];interior=interior[(interior**2).sum(1)<=.525**2+1e-10]
points=np.vstack([boundary,interior]);side_reports=[]
for side in [-1,1]:
 miss=[]
 for offset in range(0,len(points),100):
  pnt=points[offset:offset+100];d=pnt[:,None]-a[None];s=(d[:,:,0]*w[None,:,1]-d[:,:,1]*w[None,:,0])/den;t=(u[None,:,0]*d[:,:,1]-u[None,:,1]*d[:,:,0])/den
  hit=((s>=-1e-8)&(t>=-1e-8)&((s+t)<=1+1e-8)&(den*side>0)).any(1) | ((pnt**2).sum(1) <= (.145*np.cos(np.pi/32))**2)
  miss.extend(pnt[~hit].tolist())
 print('side',side,'coverage',len(points),'misses',len(miss));assert not miss
 side_reports.append({'view_direction':side,'samples':len(points),'misses':len(miss)})
report={'in_game_tested':False,'source_model':'FreeIva/Props/FreeIva_Hatch_Round_Size1','source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'source_nominal_leaf_radius_m':.41,'target_leaf_radius_m':.545,'existing_aperture_radius_m':.525,'renderers':[{'name':o.transform.name,'vertices':len(v),'triangles':len(f),'bounds_unity_min':v[:,[0,2,1]].min(0).tolist(),'bounds_unity_max':v[:,[0,2,1]].max(0).tolist()} for o,v,f in rows],'opaque_porthole_insert_radius_m':.145,'projected_aperture_samples':len(points),'projection_misses':len(miss),'both_sided_backface_culled_projection_checks':side_reports,'physical_colliders_copied':0,'frame_cutout_tube_animation_copied':False,'source_art_redistributed':False,'scope':'Original model numerical audit; no Unity/PhysX render or gameplay execution.'}
(ROOT/'Tests/classic-hatch-asset-checks.json').write_text(json.dumps(report,indent=2)+'\n')
