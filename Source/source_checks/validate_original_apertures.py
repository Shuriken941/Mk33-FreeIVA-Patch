# SPDX-License-Identifier: GPL-2.0-or-later
import sys,json,math
from pathlib import Path
import numpy as np
import argparse
p=argparse.ArgumentParser();p.add_argument('--assets',type=Path,required=True);args=p.parse_args()
ASSETS=args.assets
REPORT=Path(__file__).resolve().parents[2]/'Tests'/'original-apertures-rerun.json'
from inspect_mu import nodes

def distances(p,tri):
 a,b,c=tri[:,0],tri[:,1],tri[:,2];u=b-a;v=c-a;w=p-a
 uu=(u*u).sum(1);vv=(v*v).sum(1);uv=(u*v).sum(1);wu=(w*u).sum(1);wv=(w*v).sum(1)
 den=uu*vv-uv*uv;valid=abs(den)>1e-20
 s=np.zeros_like(den);t=s.copy();s[valid]=(wu[valid]*vv[valid]-wv[valid]*uv[valid])/den[valid];t[valid]=(wv[valid]*uu[valid]-wu[valid]*uv[valid])/den[valid]
 d=np.full(len(tri),np.inf);inside=valid&(s>=0)&(t>=0)&(s+t<=1);q=a+s[:,None]*u+t[:,None]*v;d[inside]=((p-q[inside])**2).sum(1)
 for aa,bb in [(a,b),(b,c),(c,a)]:
  e=bb-aa;ed=(e*e).sum(1);f=np.clip(((p-aa)*e).sum(1)/np.maximum(ed,1e-20),0,1);ds=((p-aa-e*f[:,None])**2).sum(1);d=np.minimum(d,ds)
 return np.sqrt(d)

def split(poly,n,d):
 inside=[];outside=[]
 for a,b in zip(poly,poly[1:]+poly[:1]):
  da=np.dot(a,n)-d;db=np.dot(b,n)-d
  if da<=1e-9:inside.append(a)
  if da>=-1e-9:outside.append(a)
  if (da<-1e-9 and db>1e-9) or (da>1e-9 and db<-1e-9):
   p=a+(b-a)*(da/(da-db));inside.append(p);outside.append(p)
 return inside,outside

def cylinder_planes(x,y,zlo,zhi,r=.525,N=32):
 planes=[(np.array([0,0,-1]),-zlo),(np.array([0,0,1]),zhi)]
 for i in range(N):
  a=(i+.5)*2*np.pi/N;n=np.array([np.cos(a),np.sin(a),0]);planes.append((n,np.dot(n,[x,y,0])+r*np.cos(np.pi/N)))
 return planes

def cut(ts,planes):
 output=[]
 for tri in ts:
  remainder=list(tri)
  for n,d in planes:
   if len(remainder)<3:break
   remainder,outside=split(remainder,n,d)
   output.extend([outside[0],outside[i],outside[i+1]] for i in range(1,len(outside)-1))
 return np.array(output)

specs={
 'cockpit':{'file':'cockpitIVA','cuts':{'crewTube':[(0,-.6503,-1.64,-1.50)],'Dashboard':[(0,-.6503,-1.64,-1.50)]},'route':[(0,-.6503,z) for z in np.linspace(-1.8,-1.3,101)],'exclude':['crewDoor','seatbelts']},
 'krew':{'file':'crewModuleIVA','cuts':{'crewTube':[(0,-.025,-1.23,-1.08),(0,-.025,1.08,1.23)],'cabinMesh':[(0,-.025,-1.23,-1.08),(0,-.025,1.08,1.23)]},'route':[(0,-.025,z) for z in np.linspace(-1.4,1.4,281)],'exclude':['crewDoor','straps']}}
report={'in_game_tested':False,'algorithm':'32-sided convex cylinder triangle subtraction and sampled capsule segment distance, independent of Unity/FreeIVA implementation','models':{}}
for name,spec in specs.items():
 ns=nodes(ASSETS/(spec['file']+'.mu'));all_t=[];names=[];counts={}
 for n in ns:
  if 'mesh' not in n or n['name'] in spec['exclude']:continue
  ts=n['verts'][np.array(sum(n['mesh'].submeshes,[]))]
  before=len(ts)
  for c in spec['cuts'].get(n['name'],[]):ts=cut(ts,cylinder_planes(*c))
  counts[n['name']]={'before':before,'after':len(ts)}
  all_t.extend(ts);names.extend([n['name']]*len(ts))
 T=np.array(all_t);names=np.array(names);Tlo=T.min(1);Thi=T.max(1)
 out=[]
 for center in spec['route']:
  min_dist=100.;obstacle='none';off=0
  # Radius .2, height .6 => centre segment +/- .1. Dense sampling
  # conservatively reduce observed distance by half the sample spacing (.005).
  for dy in np.linspace(-.1,.1,21):
   p=np.array(center)+[0,dy,0]
   aa=np.maximum(Tlo-p,0)+np.maximum(p-Thi,0);ids=np.nonzero((aa*aa).sum(1)<.6**2)[0]
   if not len(ids):continue
   ds=distances(p,T[ids]);j=int(np.argmin(ds))
   if ds[j]<min_dist:min_dist=float(ds[j]);obstacle=str(names[ids[j]]);off=float(dy)
  out.append({'center':list(center),'capsule_radial_clearance_lower_bound':min_dist-.005-.2,'nearest_mesh':obstacle,'segment_offset_y':off})
 report['models'][name]={'cuts':spec['cuts'],'mesh_triangle_counts':counts,'minimum_capsule_clearance_lower_bound':min(x['capsule_radial_clearance_lower_bound'] for x in out),'route':out}
 print(name, min(out,key=lambda x:x['capsule_radial_clearance_lower_bound']))
# upper passage fixed geometry excludes movable crewDoor, uses all remaining solid meshes.
ns=nodes(ASSETS/'cockpitIVA.mu');T=[];names=[]
for n in ns:
 if 'mesh' not in n or n['name'] in ['crewDoor','seatbelts']:continue
 ts=n['verts'][np.array(sum(n['mesh'].submeshes,[]))];T.extend(ts);names.extend([n['name']]*len(ts))
T=np.array(T);names=np.array(names);Tlo=T.min(1);Thi=T.max(1);upper=[]
for z in np.linspace(-.4,.2,61):
 best=100;near='none'
 for dy in np.linspace(-.1,.1,21):
  p=np.array([0,1.49+dy,z]);aa=np.maximum(Tlo-p,0)+np.maximum(p-Thi,0);ids=np.nonzero((aa*aa).sum(1)<.6**2)[0];ds=distances(p,T[ids]);j=int(np.argmin(ds))
  if ds[j]<best:best=float(ds[j]);near=str(names[ids[j]])
 upper.append({'center':[0,1.49,float(z)],'capsule_radial_clearance_lower_bound':best-.205,'nearest_mesh':near})
report['upper_door_open_route']={'minimum_capsule_clearance_lower_bound':min(x['capsule_radial_clearance_lower_bound'] for x in upper),'route':upper}
print('upper',min(upper,key=lambda x:x['capsule_radial_clearance_lower_bound']))
REPORT.write_text(json.dumps(report,indent=2))
