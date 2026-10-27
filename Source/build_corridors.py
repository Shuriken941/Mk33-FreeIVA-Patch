"""Original Mk33FreeIVA connecting geometry. SPDX-License-Identifier: MIT.

Build with Blender 3.4+: blender -b --python build_corridors.py -- <Models-dir>
No original Mk-33 or FreeIVA art is read or embedded. All dimensions are metres
in Unity INTERNAL coordinates. Blender is used only for exact volume unions.
"""
import bpy
import bmesh
import math
import struct
import sys
import json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from mu_material_table import compact_material_table
from mathutils import Vector
from mathutils.geometry import intersect_ray_tri

OUT = Path(sys.argv[sys.argv.index('--') + 1]) if '--' in sys.argv else Path(__file__).resolve().parent.parent / 'Models'
OUT.mkdir(parents=True, exist_ok=True)
SIDES = 32

def clear():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

def tube_volume(name, start, end, radius):
    # Deliberately use XY end rings: ports are axial, while their heights differ.
    verts = [(p[0] + radius*math.cos(2*math.pi*i/SIDES), p[1] + radius*math.sin(2*math.pi*i/SIDES), p[2]) for p in (start, end) for i in range(SIDES)]
    faces = []
    for i in range(SIDES):
        j = (i+1) % SIDES
        faces.append((i,j,j+SIDES,i+SIDES))
    faces.append(tuple(reversed(range(SIDES))))
    faces.append(tuple(range(SIDES,2*SIDES)))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name,mesh)
    bpy.context.collection.objects.link(obj)
    return obj

def axial_volume(name,start,end,radius,end_radius=None):
    """Closed circular primitive along an arbitrary centreline, Unity metres."""
    a,b=Vector(start),Vector(end);axis=(b-a).normalized()
    seed=Vector((0,1,0)) if abs(axis.y)<.9 else Vector((1,0,0))
    u=axis.cross(seed).normalized();v=axis.cross(u).normalized()
    radii=[radius,radius if end_radius is None else end_radius]
    verts=[tuple(p+r*(u*math.cos(2*math.pi*i/SIDES)+v*math.sin(2*math.pi*i/SIDES))) for p,r in zip((a,b),radii) for i in range(SIDES)]
    faces=[(i,(i+1)%SIDES,(i+1)%SIDES+SIDES,i+SIDES) for i in range(SIDES)]
    faces += [tuple(reversed(range(SIDES))),tuple(range(SIDES,2*SIDES))]
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);mesh.update()
    obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj)
    return obj

def box(name, lo, hi):
    bpy.ops.mesh.primitive_cube_add(size=1, location=tuple((a+b)/2 for a,b in zip(lo,hi)))
    o = bpy.context.object
    o.name = name
    o.scale = tuple(b-a for a,b in zip(lo,hi))
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return o

def union(target, addition):
    bpy.context.view_layer.objects.active = target
    modifier = target.modifiers.new('VolumeUnion','BOOLEAN')
    modifier.operation = 'UNION'
    modifier.solver = 'EXACT'
    modifier.object = addition
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    bpy.data.objects.remove(addition, do_unlink=True)

def extract_inward(obj, ports):
    # Exact booleans can leave coincident vertices at shared box faces. Weld
    # before triangulation so PhysX never receives microscopic sliver faces.
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-5)
    bmesh.ops.dissolve_degenerate(bm, edges=list(bm.edges), dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(obj.data)
    bm.free()
    bpy.context.view_layer.objects.active = obj
    mod = obj.modifiers.new('Triangulate','TRIANGULATE')
    bpy.ops.object.modifier_apply(modifier=mod.name)
    verts = [tuple(v.co) for v in obj.data.vertices]
    faces = []
    removed = [0]*len(ports)
    for poly in obj.data.polygons:
        f = tuple(poly.vertices)
        for i, (axis, coordinate) in enumerate(ports):
            if all(abs(verts[v][axis]-coordinate) < 2e-5 for v in f):
                removed[i] += 1
                break
        else:
            faces.append(tuple(reversed(f)))
    assert all(removed), ('missing terminal cap',removed)
    return verts, faces, removed

class MuWriter:
    def __init__(self, name):
        self.b = bytearray()
        self.material_sites=[]
        self.ints(76543, 5)
        self.string(name)
        self.transform(name, 20)
        self.materials=[('Mk33Wall','KSP/Diffuse','corridorWall'),('Mk33WallWarm','KSP/Diffuse','corridorWallWarm'),('Mk33Floor','KSP/Diffuse','corridorFloor'),('Mk33Ceiling','KSP/Diffuse','corridorCeiling'),('Mk33Metal','KSP/Diffuse','corridorGrey'),('Mk33StripLight','KSP/Unlit','corridorLight')]
    def ints(self,*values): self.b.extend(struct.pack('<'+'i'*len(values),*values))
    def floats(self,*values): self.b.extend(struct.pack('<'+'f'*len(values),*values))
    def bytes(self,*values): self.b.extend(values)
    def string(self,value):
        payload=value.encode('utf-8'); n=len(payload)
        while n > 127:
            self.bytes((n&127)|128); n >>= 7
        self.bytes(n); self.b.extend(payload)
    def transform(self,name,layer,tag='Untagged',position=(0,0,0)):
        self.string(name); self.floats(*position,0,0,0,1,1,1,1)
        self.ints(24); self.string(tag); self.ints(layer)
    def mesh(self,verts,faces,render=False,projection='wall'):
        self.ints(13,len(verts),1,14)
        for v in verts:self.floats(*v)
        if render:
            ns=[Vector((0,0,0)) for _ in verts]
            for f in faces:
                n=(Vector(verts[f[1]])-Vector(verts[f[0]])).cross(Vector(verts[f[2]])-Vector(verts[f[0]]))
                for i in f:ns[i]+=n
            self.ints(17)
            for n in ns:
                n.normalize();self.floats(*n)
            self.ints(15)
            # Metre-scaled UVs preserve texture density along all three axes.
            for x,y,z in verts:
                if projection in ('floor','ceiling'):self.floats(x+.5,z)
                elif projection in ('floorX','ceilingX'):self.floats(z+.5,-x)
                elif projection=='metal':self.floats(x*2,z*2)
                elif projection=='right':self.floats(-z,y)
                elif projection=='wallX':self.floats(x,y)
                elif projection=='wallXMirror':self.floats(-x,y)
                else:self.floats(z,y)
        self.ints(19,3*len(faces))
        for f in faces:self.ints(*f)
        self.ints(22)
    def collider(self,name,verts,faces):
        self.ints(0);self.transform(name,16)
        self.ints(25);self.bytes(0,0);self.mesh(verts,faces)
        self.ints(1)
    def surface(self,name,verts,faces,material=4,projection='metal'):
        # Split faces before export: no vertex may average floor/wall UVs or
        # round the normal across a panel seam. Collider topology stays welded.
        rv=[];rf=[]
        for face in faces:
            rf.append(tuple(range(len(rv),len(rv)+len(face))))
            rv.extend(verts[i] for i in face)
        self.ints(0);self.transform(name,20)
        self.ints(7);self.mesh(rv,rf,True,projection)
        self.ints(8);self.bytes(1,1);self.ints(1)
        self.material_sites.append((len(self.b),material));self.ints(material)
        self.ints(1)
    def interior(self,name,verts,faces,along='z'):
        groups={}
        for face in faces:
            a,b,c=(Vector(verts[i]) for i in face)
            n=(b-a).cross(c-a).normalized()
            key='floor' if n.y>.65 else 'ceiling' if n.y<-.65 else 'left' if n.x>0 else 'right'
            projection=key
            if key in ('floor','ceiling') and along=='x':projection=key+'X'
            elif key not in ('floor','ceiling') and abs(n.z)>abs(n.x):projection='wallX' if n.z>0 else 'wallXMirror'
            groups.setdefault((key,projection),[]).append(face)
        for (key,projection),fs in groups.items():
            if fs:self.surface(name+'_'+key+'_'+projection,verts,fs,{'floor':2,'ceiling':3,'left':0,'right':1}[key],projection)
    def light(self,name,position,intensity=.65,distance=1.6):
        self.ints(0);self.transform(name,20,position=position)
        # Unity LightType.Point = 2; illuminate IVA layers and kerbals only.
        self.ints(23,2);self.floats(intensity,distance,.78,.91,1,1)
        self.ints((1<<16)|(1<<20));self.floats(30)
        self.ints(1)
    def handle(self,name,center,size):
        self.ints(0);self.transform(name,20)
        self.ints(28);self.bytes(0);self.floats(*size);self.floats(*center)
        lo=tuple(c-s/2 for c,s in zip(center,size));hi=tuple(c+s/2 for c,s in zip(center,size))
        o=box(name+'Volume',lo,hi)
        bpy.context.view_layer.objects.active=o
        mod=o.modifiers.new('Tri','TRIANGULATE');bpy.ops.object.modifier_apply(modifier=mod.name)
        verts=[tuple(v.co) for v in o.data.vertices];faces=[tuple(p.vertices) for p in o.data.polygons]
        self.ints(7);self.mesh(verts,faces,True)
        self.ints(8);self.bytes(1,1);self.ints(1)
        self.material_sites.append((len(self.b),0));self.ints(0)
        self.ints(1)
        bpy.data.objects.remove(o,do_unlink=True)
    def trigger(self,name,center,size):
        self.ints(0);self.transform(name,16,'Ladder')
        self.ints(28);self.bytes(1);self.floats(*size);self.floats(*center)
        self.ints(1)
    def finish(self,path):
        materials,textures=compact_material_table(self.b,self.materials,self.material_sites)
        self.ints(10,len(materials))
        for name,shader,texture in materials:
            self.string(name);self.string(shader);self.ints(2)
            self.string('_Color');self.ints(0);self.floats(1,1,1,1)
            self.string('_MainTex');self.ints(4,textures.index(texture));self.floats(1,1,0,0)
        self.ints(12,len(textures))
        for name in textures:self.string(name);self.ints(0)
        path.write_bytes(self.b)

def box_surface(writer,name,lo,hi,material=4,projection='metal'):
    obj=box(name,lo,hi)
    bpy.context.view_layer.objects.active=obj
    mod=obj.modifiers.new('Tri','TRIANGULATE');bpy.ops.object.modifier_apply(modifier=mod.name)
    vertices=[tuple(p.co) for p in obj.data.vertices];faces=[tuple(p.vertices) for p in obj.data.polygons]
    writer.surface(name,vertices,faces,material,projection)
    bpy.data.objects.remove(obj,do_unlink=True)

def wall_hit(vertices,faces,origin,direction):
    origin,direction=Vector(origin),Vector(direction).normalized()
    candidates=[]
    for face in faces:
        hit=intersect_ray_tri(*(Vector(vertices[i]) for i in face),direction,origin,True)
        if hit is not None:
            distance=(hit-origin).dot(direction)
            if distance>1e-5:candidates.append((distance,hit))
    if not candidates:raise ValueError('Fixture has no supporting shell at '+str(tuple(origin)))
    distance,hit=min(candidates,key=lambda p:p[0])
    if distance>.25:raise ValueError('Fixture ray reached distant wall at '+str(tuple(origin)))
    return hit

def mounted_fixture(writer,name,vertices,faces,center,uaxis,vaxis,normal,width,length):
    """Metal housing conforms to actual cut shell; inset lens touches housing.

    Three-by-three backing points follow the exported skin, including polygon
    curvature and the sloped main tube. An outward 1 mm overlap prevents a
    visible separation. Nothing bridges a Boolean opening: every backing point
    must independently hit a nearby surface or the generator fails.
    """
    center,uaxis,vaxis,normal=map(Vector,(center,uaxis,vaxis,normal))
    def prism(w,h,back_depth,front_depth):
        hits=[wall_hit(vertices,faces,center+uaxis*(u*w/2)+vaxis*(v*h/2),normal) for v in [-1,0,1] for u in [-1,0,1]]
        verts=[tuple(hit+normal*d) for d in [back_depth,front_depth] for hit in hits]
        quads=[]
        for row in range(2):
            for col in range(2):
                a=row*3+col;q=(a,a+1,a+4,a+3)
                if uaxis.cross(vaxis).dot(normal)<0:q=tuple(reversed(q))
                quads.extend([q,tuple(i+9 for i in reversed(q))])
        boundary=[0,1,2,5,8,7,6,3]
        if uaxis.cross(vaxis).dot(normal)<0:boundary.reverse()
        for a,b in zip(boundary,boundary[1:]+boundary[:1]):quads.append((b,a,a+9,b+9))
        fs=[tri for a,b,c,d in quads for tri in [(a,b,c),(a,c,d)]]
        return verts,fs,[tuple(p) for p in hits]
    hv,hf,hits=prism(width,length,.001,-.023)
    writer.surface(name+'Housing',hv,hf,4,'metal')
    lv,lf,_=prism(width*.72,length*.78,-.021,-.027)
    writer.surface(name+'Lens',lv,lf,5,'ceiling')
    return {'housing':name+'Housing','lens':name+'Lens','supporting_shell_points':hits,'normal_to_wall':tuple(normal),'backing_overlap_m':.001,'maximum_inward_projection_m':.027}

report = {'in_game_tested':False,'geometry_source':'original parametric primitives; no imported mesh','units':'Unity INTERNAL local metres','models':{}}
mounts={'in_game_tested':False,'method':'Backing grid raycast into the actual final Boolean-cut shell; render-only metal housings overlap skin 1 mm and inset lenses intersect housings.','models':{}}
clear()
C=(0,-.6503,-1.5674);T=(0,-.02293,2.80137)
main=tube_volume('corridorVolume',C,T,.54)
union(main,box('accessShaft',(-.32,-.45,.15),(.32,1.85,.9)))
union(main,box('upperNeck',(-.32,1.13,-.04404),(.32,1.85,.9)))
v,f,removed=extract_inward(main,[(2,C[2]),(2,T[2]),(2,-.04404)])
w=MuWriter('Mk33CockpitCorridor')
w.collider('Mk33CorridorShell',v,f);w.interior('Mk33CorridorSurface',v,f)
# The former Z=.85 light was below the access-shaft opening. Relocate it to
# intact ceiling; all housings follow the slope and actual polygon profile.
mounts['models']['CockpitCorridor']={'fixtures':[],'ladder':{}}
for i,z in enumerate([-1.20,-.30,1.10,1.85,2.55]):
    cy=C[1]+(T[1]-C[1])*(z-C[2])/(T[2]-C[2])
    mounts['models']['CockpitCorridor']['fixtures'].append(mounted_fixture(w,'Mk33CeilingFixture'+str(i),v,f,(0,cy+.46,z),(1,0,0),(0,0,1),(0,1,0),.18,.28))
    w.light('Mk33CeilingLight'+str(i),(0,cy+.45,z))
# The raised shaft has its own real roof. Illuminate its mounted ladder from
# a compact flush fitting there instead of suspending a lamp over the opening.
mounts['models']['CockpitCorridor']['fixtures'].append(mounted_fixture(w,'Mk33CeilingFixture5',v,f,(0,1.78,.52),(1,0,0),(0,0,1),(0,1,0),.14,.20))
w.light('Mk33CeilingLight5',(0,1.69,.52),.40,1.25)
w.trigger('Mk33AccessRail',(0,.70,.51),(.60,2.10,.68))
# Persistent interaction colliders are configured on InteractionPoints.mu.
# The rear wall begins above the main-bore crown (~Y.244 at Z.9). The old
# low rungs crossed that opening. Keep the visible ladder wholly on real wall,
# with two continuous rails and six spacers that actually enter Z=.9 skin.
for side,x in [('Left',-.25),('Right',.25)]:
    box_surface(w,'Mk33AccessRail'+side,(x-.016,.30,.834),(x+.016,1.80,.867))
    for i,y in enumerate([.35,.95,1.70]):
        # Validate each mounting face against final shell topology.
        hit=wall_hit(v,f,(x,y,.86),(0,0,1))
        assert abs(hit.z-.9)<1e-5
        box_surface(w,'Mk33AccessMount'+side+str(i),(x-.025,y-.025,.858),(x+.025,y+.025,.902))
for i,y in enumerate([.35,.55,.75,.95,1.15,1.35,1.55,1.75]):
    box_surface(w,'Mk33AccessRung'+str(i),(-.25,y-.012,.845),(.25,y+.012,.870))
mounts['models']['CockpitCorridor']['ladder']={'rung_centres_y':[.35,.55,.75,.95,1.15,1.35,1.55,1.75],'rail_y_bounds':[.30,1.80],'wall_z':.9,'mount_centres_y':[.35,.95,1.70],'lower_main_opening_kept_clear':True,'native_trigger_unchanged':True}
w.finish(OUT/'CockpitCorridor.mu')
report['models']['CockpitCorridor']={'collider':'Mk33CorridorShell','vertices':v,'triangles':f,'removed_terminal_triangles':removed,'ports':[C,T,(0,1.49,-.04404)],'radius':.54,'shaft':{'x':[-.32,.32],'y':[-.45,1.85],'z':[.15,.9]},'neck':{'x':[-.32,.32],'y':[1.13,1.85],'z':[-.04404,.9]}}
clear()
start=(0,-.025,1.1502);end=(0,0,1.31982)
bridge=tube_volume('bridgeVolume',start,end,.54)
v,f,removed=extract_inward(bridge,[(2,start[2]),(2,end[2])])
w=MuWriter('Mk33KrewAirlockBridge')
w.collider('Mk33KrewAirlockBridgeShell',v,f);w.interior('Mk33KrewAirlockBridgeSurface',v,f)
w.light('Mk33BridgeLight',(0,.39,1.23),.45,1.0)
w.finish(OUT/'KrewAirlockBridge.mu')
report['models']['KrewAirlockBridge']={'collider':'Mk33KrewAirlockBridgeShell','vertices':v,'triangles':f,'removed_terminal_triangles':removed,'ports':[start,end],'radius':.54}

# The white AIRLOCK door is embedded in cabinMesh on the front of the
# central shaft. The separate offset crewDoor is an exterior EVA hatch.
# Keep the whole fixed lining within that existing central shaft; only the
# native FreeIVA telescoping tube continues above the vessel roof.
clear()
door=(0,1.055827,.096354)
axis_z=.61551148
outlet=(0,1.80,axis_z)
passage=axial_volume('KrewCentralShaft',(0,.65,axis_z),outlet,.39)
union(passage,box('KrewCentralDoorNeck',(-.30,.705827,.08),(.30,1.405827,.70)))
v,f,removed=extract_inward(passage,[(2,.08),(1,outlet[1])])
w=MuWriter('Mk33KrewDockPassage')
w.collider('Mk33KrewDockPassageShell',v,f);w.interior('Mk33KrewDockPassageSurface',v,f)
w.trigger('Mk33KrewDockAccessLadder',(0,1.18,axis_z),(.62,1.24,.62))
mounts['models']['KrewDockPassage']={'fixtures':[]}
# Compact fittings touch the real back wall and leave the entry and shaft axis
# unobstructed. The fixed passage ends below the original roof at Y~1.82.
for i,y in enumerate([.94,1.53]):
    mounts['models']['KrewDockPassage']['fixtures'].append(mounted_fixture(w,'Mk33KrewPassageFixture'+str(i),v,f,(0,y,.95),(1,0,0),(0,1,0),(0,0,1),.14,.18))
    w.light('Mk33KrewPassageLight'+str(i),(0,y,.94),.45,1.1)
w.finish(OUT/'KrewDockPassage.mu')
route=[(0,1.055827,-.08),(0,1.055827,axis_z),(0,2.30,axis_z)]
report['models']['KrewDockPassage']={'collider':'Mk33KrewDockPassageShell','vertices':v,'triangles':f,'removed_terminal_triangles':removed,'ports':[(0,1.055827,.08),outlet],'route':route,'radius':.39,'original_airlock_door':door,'docking_axis':(0,axis_z),'outlet_y':outlet[1],'fixed_lining_within_original_central_shaft':True,'offset_eva_door_excluded':True,'entry_bounds':{'x':[-.30,.30],'y':[.705827,1.405827],'z':[.08,.70]},'source_shaft_bounds':{'x':[-.525,.525],'y':[.625,1.8203555],'z':[.0905192,1.1405194]}}
# Canonical source textures are verified by build_materials.py; see material_sources.json.
(OUT.parent/'Tests'/'corridor-geometry.json').parent.mkdir(exist_ok=True)
(OUT.parent/'Tests'/'corridor-geometry.json').write_text(json.dumps(report,indent=2))
(OUT.parent/'Tests'/'corridor-fixture-mounts.json').write_text(json.dumps(mounts,indent=2))
print('Built original corridor and bridge assets:',OUT)
