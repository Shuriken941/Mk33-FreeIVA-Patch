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
import zlib
from pathlib import Path
from mathutils import Vector

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
        self.ints(76543, 5)
        self.string(name)
        self.transform(name, 20)
    def ints(self,*values): self.b.extend(struct.pack('<'+'i'*len(values),*values))
    def floats(self,*values): self.b.extend(struct.pack('<'+'f'*len(values),*values))
    def bytes(self,*values): self.b.extend(values)
    def string(self,value):
        payload=value.encode('utf-8'); n=len(payload)
        while n > 127:
            self.bytes((n&127)|128); n >>= 7
        self.bytes(n); self.b.extend(payload)
    def transform(self,name,layer,tag='Untagged'):
        self.string(name); self.floats(0,0,0,0,0,0,1,1,1,1)
        self.ints(24); self.string(tag); self.ints(layer)
    def mesh(self,verts,faces,render=False):
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
            for x,y,z in verts:self.floats(x,z)
        self.ints(19,3*len(faces))
        for f in faces:self.ints(*f)
        self.ints(22)
    def collider(self,name,verts,faces):
        self.ints(0);self.transform(name,16)
        self.ints(25);self.bytes(0,0);self.mesh(verts,faces)
        self.ints(1)
    def surface(self,name,verts,faces):
        self.ints(0);self.transform(name,20)
        self.ints(7);self.mesh(verts,faces,True)
        self.ints(8);self.bytes(1,1);self.ints(1,0)
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
        self.ints(8);self.bytes(1,1);self.ints(1,0)
        self.ints(1)
        bpy.data.objects.remove(o,do_unlink=True)
    def trigger(self,name,center,size):
        self.ints(0);self.transform(name,16,'Ladder')
        self.ints(28);self.bytes(1);self.floats(*size);self.floats(*center)
        self.ints(1)
    def finish(self,path):
        self.ints(10,1);self.string('Mk33FreeIVA_coolGrey');self.string('KSP/Unlit');self.ints(2)
        self.string('_Color');self.ints(0);self.floats(1,1,1,1)
        self.string('_MainTex');self.ints(4,0);self.floats(1,1,0,0)
        self.ints(12,1);self.string('corridorGrey');self.ints(0)
        path.write_bytes(self.b)

def png(path):
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    # Authored 2x2 grey texture; no borrowed pixels.
    raw = b'\x00'+bytes([132,142,151,255])*2+b'\x00'+bytes([136,146,155,255])*2
    path.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>2I5B',2,2,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b''))

report = {'in_game_tested':False,'geometry_source':'original parametric primitives; no imported mesh','units':'Unity INTERNAL local metres','models':{}}
clear()
C=(0,-.6503,-1.5674);T=(0,-.02293,2.80137)
main=tube_volume('corridorVolume',C,T,.54)
union(main,box('accessShaft',(-.32,-.45,.15),(.32,1.85,.9)))
union(main,box('upperNeck',(-.32,1.13,-.04404),(.32,1.85,.9)))
v,f,removed=extract_inward(main,[(2,C[2]),(2,T[2]),(2,-.04404)])
w=MuWriter('Mk33CockpitCorridor')
w.collider('Mk33CorridorShell',v,f);w.surface('Mk33CorridorSurface',v,f)
w.trigger('Mk33AccessRail',(0,.70,.51),(.60,2.10,.68))
# Persistent interaction colliders are configured on InteractionPoints.mu.
# The shaft has a small functional ladder on its rear wall.
for i,y in enumerate([-.2,0,.2,.4,.6,.8,1,1.2,1.4,1.6]):
    rung=box('rung',(-.25,y-.012,.845),(.25,y+.012,.87))
    bpy.context.view_layer.objects.active=rung
    mod=rung.modifiers.new('Tri','TRIANGULATE');bpy.ops.object.modifier_apply(modifier=mod.name)
    rv=[tuple(x.co) for x in rung.data.vertices];rf=[tuple(x.vertices) for x in rung.data.polygons]
    w.surface('Mk33AccessRung'+str(i),rv,rf)
w.finish(OUT/'CockpitCorridor.mu')
report['models']['CockpitCorridor']={'collider':'Mk33CorridorShell','vertices':v,'triangles':f,'removed_terminal_triangles':removed,'ports':[C,T,(0,1.49,-.04404)],'radius':.54,'shaft':{'x':[-.32,.32],'y':[-.45,1.85],'z':[.15,.9]},'neck':{'x':[-.32,.32],'y':[1.13,1.85],'z':[-.04404,.9]}}
clear()
start=(0,-.025,1.1502);end=(0,0,1.31982)
bridge=tube_volume('bridgeVolume',start,end,.54)
v,f,removed=extract_inward(bridge,[(2,start[2]),(2,end[2])])
w=MuWriter('Mk33KrewAirlockBridge')
w.collider('Mk33KrewAirlockBridgeShell',v,f);w.surface('Mk33KrewAirlockBridgeSurface',v,f)
w.finish(OUT/'KrewAirlockBridge.mu')
report['models']['KrewAirlockBridge']={'collider':'Mk33KrewAirlockBridgeShell','vertices':v,'triangles':f,'removed_terminal_triangles':removed,'ports':[start,end],'radius':.54}
png(OUT/'corridorGrey.png')
(OUT.parent/'Tests'/'corridor-geometry.json').parent.mkdir(exist_ok=True)
(OUT.parent/'Tests'/'corridor-geometry.json').write_text(json.dumps(report,indent=2))
print('Built original corridor and bridge assets:',OUT)
