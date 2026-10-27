"""Original functional hatch/rail assets. SPDX-License-Identifier: MIT.
Run with Python 3; all geometry below is original parametric geometry.
Unity local +Y points into the room; hatch lies in XZ. No cutout or auto tube.
"""
import math, struct, json
from pathlib import Path
from mu_material_table import compact_material_table
OUT=Path(__file__).resolve().parent.parent/'Models'
OUT.mkdir(parents=True,exist_ok=True)
class W:
    def __init__(self,name):
        self.data=bytearray();self.i(76543,5);self.s(name);self.transform(name,20)
        self.material_sites=[]
        self.materials=[('Mk33Hatch','KSP/Diffuse','hatchGrey'),('Mk33Wall','KSP/Diffuse','corridorWall'),('Mk33Floor','KSP/Diffuse','corridorFloor'),('Mk33Ceiling','KSP/Diffuse','corridorCeiling'),('Mk33Metal','KSP/Diffuse','corridorGrey'),('Mk33StripLight','KSP/Unlit','corridorCeiling')]
        if name=='Mk33KrewDockTubeModel':self.materials[5]=('Mk33StripLight','KSP/Unlit','corridorLight')
    def i(self,*v):self.data.extend(struct.pack('<'+'i'*len(v),*v))
    def f(self,*v):self.data.extend(struct.pack('<'+'f'*len(v),*v))
    def b(self,*v):self.data.extend(v)
    def s(self,s):
        raw=s.encode();n=len(raw)
        while n>=128:self.b((n&127)|128);n>>=7
        self.b(n);self.data.extend(raw)
    def transform(self,name,layer,pos=(0,0,0),rotation=(0,0,0,1),tag='Untagged'):
        self.s(name);self.f(*pos,*rotation,1,1,1);self.i(24);self.s(tag);self.i(layer)
    def mesh(self,vertices,faces,render=False,projection='disc'):
        self.i(13,len(vertices),1,14)
        for p in vertices:self.f(*p)
        if render:
            normals=[[0,0,0] for _ in vertices]
            for a,b,c in faces:
                A=vertices[a];B=vertices[b];C=vertices[c]
                u=[B[i]-A[i] for i in range(3)];v=[C[i]-A[i] for i in range(3)]
                n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
                for q in [a,b,c]:
                    for i in range(3):normals[q][i]+=n[i]
            self.i(17)
            for n in normals:
                length=math.sqrt(sum(x*x for x in n)) or 1
                self.f(*(x/length for x in n))
            self.i(15)
            for x,y,z in vertices:
                if projection=='disc':self.f(.5+x/1.16,.5+z/1.16)
                elif projection in ('floor','ceiling'):self.f(.5+x,-y)
                else:self.f(-y,z)
        self.i(19,len(faces)*3)
        for face in faces:self.i(*face)
        self.i(22)
    def geometry(self,name,v,f,layer=20,collider=False,convex=False,material=0,projection='disc',close=True):
        self.i(0);self.transform(name,layer)
        if collider:self.i(25);self.b(0,int(convex));self.mesh(v,f)
        self.i(7);self.mesh(v,f,True,projection);self.i(8);self.b(1,1);self.i(1)
        self.material_sites.append((len(self.data),material));self.i(material)
        if close:self.i(1)
    def handle(self,name,y):
        self.i(0);self.transform(name,20,(0,y,0))
        self.i(28);self.b(0);self.f(.32,.025,.10,0,0,0);self.i(1)
    def finish(self,name):
        materials,textures=compact_material_table(self.data,self.materials,self.material_sites)
        self.i(10,len(materials))
        for n,shader,tex in materials:
            self.s(n);self.s(shader);self.i(2)
            self.s('_Color');self.i(0);self.f(1,1,1,1)
            self.s('_MainTex');self.i(4,textures.index(tex));self.f(1,1,0,0)
        self.i(12,len(textures))
        for tex in textures:self.s(tex);self.i(0)
        (OUT/name).write_bytes(self.data)
    def light(self,name,position):
        self.i(0);self.transform(name,20,position)
        self.i(23,2);self.f(.65,1.5,.78,.91,1,1);self.i((1<<16)|(1<<20));self.f(30);self.i(1)
def disc(r=.545,thickness=.035,n=32):
    v=[(r*math.cos(2*math.pi*i/n),y,r*math.sin(2*math.pi*i/n)) for y in [-thickness/2,thickness/2] for i in range(n)]
    v.extend([(0,-thickness/2,0),(0,thickness/2,0)])
    f=[]
    for i in range(n):
        j=(i+1)%n
        f.extend([(i,j,n+i),(j,n+j,n+i),(2*n,j,i),(2*n+1,n+i,n+j)])
    # The cylinder is solid; its faces must point outward (unlike the tunnel).
    return v,[(a,c,b) for a,b,c in f]
def box(lo,hi):
    v=[(x,y,z) for x in [lo[0],hi[0]] for y in [lo[1],hi[1]] for z in [lo[2],hi[2]]]
    quads=[(0,1,3,2),(4,6,7,5),(0,4,5,1),(2,3,7,6),(0,2,6,4),(1,5,7,3)]
    f=[t for a,b,c,d in quads for t in [(a,b,c),(a,c,d)]]
    return v,f

def mounted_tube_fixture(writer,name,y,radius=.39,n=32):
    """Backing conforms to the actual polygon skin, including native Y scale."""
    ring=[(radius*math.cos(2*math.pi*i/n),radius*math.sin(2*math.pi*i/n)) for i in range(n)]
    def roof(x):
        hits=[]
        for (ax,az),(bx,bz) in zip(ring,ring[1:]+ring[:1]):
            if min(ax,bx)-1e-9<=x<=max(ax,bx)+1e-9 and abs(bx-ax)>1e-9:
                hits.append(az+(bz-az)*(x-ax)/(bx-ax))
        return max(hits)
    def prism(width,length,back,front):
        points=[(u*width/2,y+v*length/2,roof(u*width/2)) for v in [-1,0,1] for u in [-1,0,1]]
        vertices=[(x,cy,z+d) for d in [back,front] for x,cy,z in points]
        quads=[]
        for row in range(2):
            for col in range(2):
                a=row*3+col;q=(a,a+1,a+4,a+3)
                quads.extend([q,tuple(i+9 for i in reversed(q))])
        boundary=[0,1,2,5,8,7,6,3]
        for a,b in zip(boundary,boundary[1:]+boundary[:1]):quads.append((b,a,a+9,b+9))
        faces=[tri for a,b,c,d in quads for tri in [(a,b,c),(a,c,d)]]
        return vertices,faces,points
    hv,hf,points=prism(.15,.14,.001,-.023)
    writer.geometry(name+'Housing',hv,hf,material=4,projection='ceiling')
    lv,lf,_=prism(.108,.1092,-.021,-.027)
    writer.geometry(name+'Lens',lv,lf,material=5,projection='ceiling')
    return {'housing':name+'Housing','lens':name+'Lens','supporting_shell_points_local':points,'backing_overlap_m':.001,'maximum_inward_projection_m':.027,'parent_native_scale_transform':'Mk33KrewDockTube'}

w=W('Mk33CircularHatch');v,f=disc();w.geometry('door',v,f,16,True,True,close=False)
# Visible handles belong to the moving door. Persistent layer-20 interaction
# boxes remain on the PROP so the same click locations can close an open hatch.
for sign,label in [(1,'Inside'),(-1,'Outside')]:
    a,b=sorted([sign*.034,sign*.065])
    v,f=box((-.17,a,-.045),(.17,b,.045));w.geometry('Mk33Handle'+label,v,f,material=4)
    for x in [-.145,.145]:
        a,b=sorted([sign*.018,sign*.04])
        v,f=box((x-.017,a,-.035),(x+.017,b,.035));w.geometry('Mk33HandleMount'+label+str(x),v,f,material=4)
w.i(1)
w.handle('handleInside',.04);w.handle('handleOutside',-.04);w.finish('CircularHatch.mu')
# Coaxial size-1 docking tube, in INTERNAL coordinates. Its root starts at the
# existing central shaft's roof outlet. The cabin AIRLOCK door enters the shaft
# from the side. Native FreeIVA scales local -Y along +IVA Y inside the real port.
w=W('Mk33KrewDockTubeModel')
w.i(0);w.transform('Mk33KrewDockTubeRoot',20,(0,1.80,.61551148),(1,0,0,0))
N=32;radius=.39
v=[(radius*math.cos(2*math.pi*i/N),y,radius*math.sin(2*math.pi*i/N)) for y in [0,-1] for i in range(N)]
f=[]
for i in range(N):
    j=(i+1)%N;f.extend([(i,N+i,j),(j,N+i,N+j)])
w.i(0);w.transform('Mk33KrewDockTube',16)
w.i(25);w.b(0,0);w.mesh(v,f)
# Separate wall/floor/ceiling renderers share the exact existing collision tube.
groups={k:[] for k in ['Floor','RightWall','Ceiling','LeftWall']}
for i in range(N):
    angle=2*math.pi*(i+.5)/N
    key='Ceiling' if math.sin(angle)>.65 else 'Floor' if math.sin(angle)<-.65 else 'RightWall' if math.cos(angle)>0 else 'LeftWall'
    groups[key].extend(f[i*2:i*2+2])
for label,fs in groups.items():
    w.geometry('Mk33Dock'+label,v,fs,material=2 if label=='Floor' else 3 if label=='Ceiling' else 1,projection=label.lower())
tube_mounts=[]
for i,y in enumerate([-.20,-.75]):
    tube_mounts.append(mounted_tube_fixture(w,'Mk33DockFixture'+str(i),y))
    w.light('Mk33DockLight'+str(i),(0,y,radius-.065))
# Native climbing volume follows the same telescopic scale as the solid skin.
w.i(0);w.transform('Mk33DockLadder',16,tag='Ladder')
w.i(28);w.b(1);w.f(.64,1,.64,0,-.5,0);w.i(1)
w.i(1);w.i(1);w.finish('KrewDockTube.mu')
(OUT.parent/'Tests'/'dock-tube-fixture-mounts.json').write_text(json.dumps({'in_game_tested':False,'radius':radius,'sides':N,'fixtures':tube_mounts},indent=2)+'\n')
w=W('Mk33InteractionPoints')
for name in ['Mk33DoorHandle','Mk33RailOne','Mk33RailTwo']:
    w.i(0);w.transform(name,20);w.i(1)
w.finish('InteractionPoints.mu')
# build_materials.py owns all generated texture files.
print('Built CircularHatch.mu and KrewDockTube.mu')
