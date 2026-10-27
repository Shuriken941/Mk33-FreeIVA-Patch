# SPDX-License-Identifier: GPL-2.0-or-later
import argparse, json
from pathlib import Path
import numpy as np
from cut_math import nodes, cylinder_planes, cut, distances
p=argparse.ArgumentParser();p.add_argument('--assets',type=Path,required=True);args=p.parse_args()
base=args.assets
def cyl_y(center,ylo,yhi,r):
 return [(n[[0,2,1]],d) for n,d in cylinder_planes(center[0],center[1],ylo,yhi,r)]
def box_planes(center,size):
 ans=[]
 for i in range(3):
  n=np.zeros(3);n[i]=1;ans.extend([(n,center[i]+size[i]/2),(-n,-center[i]+size[i]/2)])
 return ans
specs={
 'airlock':(base/'mk33AirlockSpace.mu',{'airlockIVAMesh':[cylinder_planes(0,0,-1.26,-1.08),cylinder_planes(0,0,1.02,1.20),cyl_y((0,0),1.14,1.32,.525)]},{'front_and_rear':[(0,0,z) for z in np.linspace(-1.4,1.4,281)],'roof':[(0,y,0) for y in np.linspace(.6,1.6,101)]},[]),
 'krew_roof':(base/'crewModuleIVA.mu',{name:[box_planes((1.11893,1.80,.76054),(.62,.24,.70))] for name in ['crewTube','cabinMesh']},{'roof':[(1.11893,y,.76054) for y in np.linspace(-.1,2.15,226)]},['crewDoor','straps']),
 'control_cab_roof':(base/'controlCabIVA.mu',{'cabIVAMesh':[cyl_y((0,.17),1.56,1.74,.5)]},{'roof':[(0,y,.17) for y in np.linspace(.6,1.95,136)]},[])
}
report={'in_game_tested':False,'native_meshcutter_executed':False,'method':'independent convex triangle subtraction, radius .20/height .60 upright capsule sampled every <=.01m; .01m allowance for segment and pose sampling; fixed source meshes including seats. This is not Unity collision cooking or locomotion.' ,'cases':{}}
for label,(file,tools,routes,exclude) in specs.items():
 tris=[];names=[]
 for node in nodes(file):
  if 'mesh' not in node or node['name'] in exclude:continue
  t=node['verts'][np.array(sum(node['mesh'].submeshes,[]))]
  for planes in tools.get(node['name'],[]):t=cut(t,planes)
  tris.extend(t);names.extend([node['name']]*len(t))
 T=np.array(tris);names=np.array(names);low=T.min(1);high=T.max(1);results={}
 for route,poses in routes.items():
  best=100;worst=None;near=None
  for center in poses:
   for dy in np.linspace(-.1,.1,21):
    p=np.array(center)+[0,dy,0];delta=np.maximum(low-p,0)+np.maximum(p-high,0);ids=np.nonzero((delta*delta).sum(1)<.65**2)[0]
    if not len(ids):continue
    ds=distances(p,T[ids]);j=int(np.argmin(ds));d=float(ds[j])-.20-.01
    if d<best:best=d;worst=list(center);near=str(names[ids[j]])
  results[route]={'samples':len(poses),'clearance_lower_bound_m':best,'nearest_mesh':near,'worst_center':worst,'clear':best>0}
 report['cases'][label]=results
 print(label,results,flush=True)
(Path(__file__).resolve().parents[2]/'Tests'/'remaining-aperture-checks.json').write_text(json.dumps(report,indent=2)+'\n')
