"""Verify the installed central AIRLOCK leaf covers its rectangular aperture.

Uses original source triangles without copying them into the report. Python 3,
NumPy and SciPy required. Geometry proof only, not Unity/PhysX/gameplay.
SPDX-License-Identifier: GPL-2.0-or-later.
"""
from pathlib import Path
import argparse, json, sys
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import ConvexHull
from inspect_mu import nodes
parser=argparse.ArgumentParser()
parser.add_argument('--assets',type=Path,required=True,help='Installed Mk-33 Parts/SharedAssets directory')
parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[2]/'Tests/leaf-aperture-checks.json')
args=parser.parse_args()
package=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(package/'Source'))
from verify_package import parse,value
def vector(text):return np.array([float(x) for x in text.split(',')])
interior=next(n for n in parse((package/'Patches/Mk33_FreeIVA.cfg').read_text()) if n['type'].startswith('@INTERNAL[wbiMk33CrewModuleSpace]'))
hatch=next(n for n in interior['nodes'] if value(n,'doorTransformName')=='Mk33KrewCentralDoor')
geometry=next(n for n in interior['nodes'] if value(n,'name')=='Mk33FreeIvaGeometry')
cut=next(n for n in geometry['nodes'] if value(n,'type')=='Cube' and value(n,'target')=='cabinMesh')
configured_size=vector(value(cut,'scale'));configured_center=vector(value(cut,'position'))
assert np.allclose(configured_size,[.60,.70,.34],atol=1e-10)
assert np.allclose(configured_center,[0,1.055827,.17],atol=1e-10)
assert np.allclose(vector(value(hatch,'extractBoundsMin')),[-.34,.67,.02],atol=1e-10)
assert np.allclose(vector(value(hatch,'extractBoundsMax')),[.34,1.44,.125],atol=1e-10)
assert value(hatch,'extractExpectedTriangles')=='352'
seal=next(n for n in hatch['nodes'] if n['type']=='DoorCollider')
seal_size=vector(value(seal,'dimensions'));seal_center=vector(value(seal,'center'))+vector(value(hatch,'position'))
assert abs(seal_center[0]-configured_center[0])<1e-8 and abs(seal_center[1]-configured_center[1])<1e-8
entry=next(n for n in nodes(args.assets/'crewModuleIVA.mu') if n['name']=='cabinMesh')
v=entry['verts'];f=np.array(sum(entry['mesh'].submeshes,[]))
inside=np.all((v>=[-.34,.67,.02])&(v<=[.34,1.44,.125]),axis=1)
selected=f[inside[f].all(1)]
assert len(selected)==352
_,w=np.unique(np.round(v,5),axis=0,return_inverse=True)
edges=np.vstack([w[selected[:,[0,1]]],w[selected[:,[1,2]]],w[selected[:,[2,0]]]])
_,labels=connected_components(coo_matrix((np.ones(len(edges)),(edges[:,0],edges[:,1])),shape=(w.max()+1,w.max()+1)),directed=False)
components=[selected[labels[w[selected[:,0]]]==k] for k in np.unique(labels[w[selected[:,0]]])]
leaf=max(components,key=len);assert len(leaf)==224
tri=v[leaf][:,:,:2]
ab,ac=tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]
area_signed=(ab[:,0]*ac[:,1]-ab[:,1]*ac[:,0])*.5
front=tri[area_signed>1e-12]
xy=v[np.unique(leaf),:2];hull=ConvexHull(xy)
hull_area=hull.volume
front_area=float(area_signed[area_signed>1e-12].sum())
# Convex triangle clipping verifies projected front triangles do not overlap.
def cross(a,b):return float(a[0]*b[1]-a[1]*b[0])
def area(poly):
 if len(poly)<3:return 0.
 return abs(sum(cross(a,b) for a,b in zip(poly,poly[1:]+poly[:1])))*.5
def clip(poly,a,b):
 out=[]
 for p,q in zip(poly,poly[1:]+poly[:1]):
  dp,dq=cross(b-a,p-a),cross(b-a,q-a)
  ip,iq=dp>=-1e-13,dq>=-1e-13
  if ip:out.append(p)
  if ip != iq:out.append(p+(q-p)*(dp/(dp-dq)))
 return out
max_overlap=0.
for i,a in enumerate(front):
 for b in front[i+1:]:
  poly=list(a)
  for p,q in zip(b,np.roll(b,-1,axis=0)):
   if not poly:break
   poly=clip(poly,p,q)
  max_overlap=max(max_overlap,area(poly))
assert abs(front_area-hull_area)<1e-9,(front_area,hull_area)
assert max_overlap<1e-9,max_overlap
checks={}
for width,height in [(0.70,0.80),(0.66,0.74),(0.60,0.70)]:
 corners=np.array([[sx*width/2,1.055827+sy*height/2] for sx in [-1,1] for sy in [-1,1]])
 signed=corners@hull.equations[:,:2].T+hull.equations[:,2]
 margin=-float(signed.max())
 checks[f'{width:.2f}x{height:.2f}']={'full_rectangle_inside_opaque_leaf_projection':bool(margin>=0),'minimum_projected_leaf_overlap_m':margin}
assert checks['0.60x0.70']['full_rectangle_inside_opaque_leaf_projection']
report={'in_game_tested':False,'scope':'Source triangle projection geometry only; independent of Unity rendering/PhysX. Does not measure a gas simulation.', 'selected_original_door_and_handle_triangles':len(selected),'door_leaf_triangles':len(leaf),'projected_hull_area_m2':float(hull_area),'front_triangle_projection_area_m2':front_area,'maximum_pairwise_front_triangle_overlap_area_m2':max_overlap,'projected_front_exactly_tiles_convex_leaf_hull':True,'aperture_checks':checks,'current_cfg_matches_proved_aperture':True,'primitive_seal_aperture_overlap_m':{'left_right':float((seal_size[0]-configured_size[0])/2),'top_bottom':float((seal_size[1]-configured_size[1])/2)}}
args.output.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
