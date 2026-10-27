"""Original pressure passages for Mk33ProbeCore and Mk33DockingNoseCone.

SPDX-License-Identifier: MIT. Run with Python 3 (standard library only).
No upstream meshes/art are read, embedded or modified by this generator.
All coordinates are Unity INTERNAL local metres. The rings stay in XY to
match the existing axial Mk-33 attach interfaces and sloped tunnel envelope.
"""
from pathlib import Path
import math
import struct
import json
from mu_material_table import compact_material_table

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'Models'
OUT.mkdir(exist_ok=True)
N = 32
RADIUS = .515
PROBE_REAR = (0., -.625, 1.5852)
PROBE_FRONT = (-.0059150452726, -.76936990023, -1.37194791559)
NOSE_REAR = (0., 0., 0.)
NOSE_OUTLET = (0., 0., -.245)


def sub(a, b): return tuple(x-y for x, y in zip(a, b))
def cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def dot(a, b): return sum(x*y for x, y in zip(a, b))


def tube(start, end, radius=RADIUS):
    v = [(p[0]+radius*math.cos(2*math.pi*i/N),
          p[1]+radius*math.sin(2*math.pi*i/N), p[2])
         for p in (start, end) for i in range(N)]
    faces = []
    for i in range(N):
        j = (i+1) % N
        for face in ((i, j, N+j), (i, N+j, N+i)):
            p = tuple(sum(v[k][a] for k in face)/3 for a in range(3))
            t = (p[2]-start[2])/(end[2]-start[2])
            axis = tuple(start[a]+t*(end[a]-start[a]) for a in range(3))
            normal = cross(sub(v[face[1]], v[face[0]]), sub(v[face[2]], v[face[0]]))
            faces.append(tuple(reversed(face)) if dot(normal, sub(p, axis)) > 0 else face)
    return v, faces


class Writer:
    def __init__(self, name):
        self.b=bytearray(); self.i(76543,5); self.s(name); self.transform(name,20)
        self.material_sites=[]
        self.materials=[('Mk33NoseWall','KSP/Diffuse','corridorWall'),
                        ('Mk33NoseWallWarm','KSP/Diffuse','corridorWallWarm'),
                        ('Mk33NoseFloor','KSP/Diffuse','corridorFloor'),
                        ('Mk33NoseCeiling','KSP/Diffuse','corridorCeiling'),
                        ('Mk33NoseLight','KSP/Unlit','corridorLight'),
                        ('Mk33NoseMetal','KSP/Diffuse','corridorGrey')]
    def i(self,*a): self.b.extend(struct.pack('<'+'i'*len(a),*a))
    def f(self,*a): self.b.extend(struct.pack('<'+'f'*len(a),*a))
    def bytes(self,*a): self.b.extend(a)
    def s(self,value):
        data=value.encode(); length=len(data)
        while length>=128: self.bytes((length&127)|128); length >>= 7
        self.bytes(length); self.b.extend(data)
    def transform(self,name,layer,position=(0,0,0),rotation=(0,0,0,1),tag='Untagged'):
        self.s(name); self.f(*position,*rotation,1,1,1); self.i(24); self.s(tag); self.i(layer)
    def mesh(self,v,faces,render=False,projection='wall'):
        self.i(13,len(v),1,14)
        for p in v:self.f(*p)
        if render:
            normals=[[0.,0.,0.] for p in v]
            for face in faces:
                n=cross(sub(v[face[1]],v[face[0]]),sub(v[face[2]],v[face[0]]))
                for idx in face:
                    for a in range(3):normals[idx][a]+=n[a]
            self.i(17)
            for n in normals:
                length=math.sqrt(dot(n,n)) or 1
                self.f(*(a/length for a in n))
            self.i(15)
            for x,y,z in v:
                if projection in ('floor','ceiling'):self.f(x+.5,-z)
                elif projection=='tube-floor':self.f(x+.5,-y)
                elif projection=='tube-wall':self.f(-y,-z)
                elif projection=='tube-left':self.f(y,-z)
                elif projection=='left':self.f(z,y)
                elif projection=='lamp':self.f((x+.12)/.24,(-z)*4)
                else:self.f(-z,y)
        self.i(19,len(faces)*3)
        for face in faces:self.i(*face)
        self.i(22)
    def collider(self,name,v,faces):
        self.i(0); self.transform(name,16); self.i(25); self.bytes(0,0)
        self.mesh(v,faces); self.i(1)
    def surface(self,name,v,faces,material=0,projection='wall'):
        vv=[];ff=[]
        for face in faces:
            ff.append(tuple(range(len(vv),len(vv)+3))); vv.extend(v[i] for i in face)
        self.i(0);self.transform(name,20);self.i(7);self.mesh(vv,ff,True,projection)
        self.i(8);self.bytes(1,1);self.i(1)
        self.material_sites.append((len(self.b),material));self.i(material);self.i(1)
    def interior(self,name,v,faces):
        groups={k:[] for k in ('floor','ceiling','left','right')}
        for face in faces:
            n=cross(sub(v[face[1]],v[face[0]]),sub(v[face[2]],v[face[0]]))
            length=math.sqrt(dot(n,n)); n=tuple(a/length for a in n)
            k='floor' if n[1]>.65 else 'ceiling' if n[1]<-.65 else 'left' if n[0]>0 else 'right'
            groups[k].append(face)
        for k,fs in groups.items():
            if fs:self.surface(name+'_'+k,v,fs,{'floor':2,'ceiling':3,'left':0,'right':1}[k],k)
    def light(self,name,p,intensity=.45,distance=1.5):
        self.i(0); self.transform(name,20,p); self.i(23,2)
        self.f(intensity,distance,.78,.91,1,1); self.i((1<<16)|(1<<20)); self.f(30); self.i(1)
    def finish(self,path):
        materials,textures=compact_material_table(self.b,self.materials,self.material_sites)
        self.i(10,len(materials))
        for name,shader,texture in materials:
            self.s(name);self.s(shader);self.i(2)
            self.s('_Color');self.i(0);self.f(1,1,1,1)
            self.s('_MainTex');self.i(4,textures.index(texture));self.f(1,1,0,0)
        self.i(12,len(textures))
        for texture in textures:self.s(texture);self.i(0)
        path.write_bytes(self.b)


def center_at_z(start,end,z):
    t=(z-start[2])/(end[2]-start[2])
    return tuple(a+t*(b-a) for a,b in zip(start,end))


def polygon_ceiling(x):
    # The exported pressure skin is a 32-gon, not a smooth cylinder. Follow
    # its actual top facets so every backplate strip meets the visible shell.
    upper=sorted((RADIUS*math.cos(math.pi*i/N*2),RADIUS*math.sin(math.pi*i/N*2))
                 for i in range(N//2+1))
    for (xa,ya),(xb,yb) in zip(upper,upper[1:]):
        if xa-1e-10<=x<=xb+1e-10:
            return ya+(yb-ya)*(x-xa)/(xb-xa)
    raise ValueError('fixture exceeds upper pressure-skin semicircle')


def roof_strip(writer,name,start,end,zcenter,half_width,length,rear_offset,thickness,material):
    # Build a closed curved saddle. Include every pressure-skin facet break
    # inside its width; rear_offset=+1mm embeds the mounting face in the shell.
    xs=sorted(set([-half_width,half_width]+[RADIUS*math.cos(2*math.pi*i/N)
                  for i in range(N//2+1)
                  if -half_width+1e-8<RADIUS*math.cos(2*math.pi*i/N)<half_width-1e-8]))
    verts=[]
    for depth in (0,thickness):
        for z in (zcenter-length/2,zcenter+length/2):
            axis=center_at_z(start,end,z)
            for x in xs:
                verts.append((axis[0]+x,axis[1]+polygon_ceiling(x)+rear_offset-depth,z))
    n=len(xs);quads=[]
    for i in range(n-1):
        quads.extend([(i,n+i,n+i+1,i+1),
                      (2*n+i,2*n+i+1,3*n+i+1,3*n+i),
                      (i,i+1,2*n+i+1,2*n+i),
                      (n+i,3*n+i,3*n+i+1,n+i+1)])
    i=n-1
    quads.extend([(0,2*n,3*n,n),(i,n+i,3*n+i,2*n+i)])
    faces=[tri for a,b,c,d in quads for tri in ((a,b,c),(a,c,d))]
    writer.surface(name,verts,faces,material,'lamp' if material==4 else 'ceiling')
    return {'mesh':name,'rear_offset_from_polygon_metres':rear_offset,
            'thickness_metres':thickness,'half_width_metres':half_width,
            'length_metres':length,'z_center':zcenter,
            'follows_longitudinal_axis_slope':True,
            'cross_section_follows_exported_32_gon':True}


def fixture(writer,name,start,end,zcenter,length=.24,half_width=.12):
    # Mount the metal housing onto the pressure skin; put a smaller opaque
    # white diffuser on its inward face with a 1mm overlap into the housing.
    writer.i(0);writer.transform(name,20)
    housing=roof_strip(writer,name+'_Housing',start,end,zcenter,half_width,length,.001,.022,5)
    diffuser=roof_strip(writer,name+'_Diffuser',start,end,zcenter,half_width-.035,length-.06,-.020,.003,4)
    writer.i(1)
    return {'root':name,'housing':housing,'diffuser':diffuser,
            'housing_shell_overlap_metres':.001,
            'diffuser_housing_overlap_metres':.001,
            'solid_colliders_added':False}


report={'in_game_tested':False,'geometry_source':'original parametric circular pressure skins; no upstream art read',
        'coordinate_space':'Unity INTERNAL local metres','models':{}}
v,f=tube(PROBE_REAR,PROBE_FRONT)
w=Writer('Mk33ProbeCorePassage')
w.collider('Mk33ProbeCoreShell',v,f);w.interior('Mk33ProbeCoreSurface',v,f)
probe_fixtures=[]
for i,t in enumerate((.18,.50,.82)):
    p=tuple(a+t*(b-a) for a,b in zip(PROBE_REAR,PROBE_FRONT))
    probe_fixtures.append(fixture(w,'Mk33ProbeFixture'+str(i),PROBE_REAR,PROBE_FRONT,p[2]))
    w.light('Mk33ProbeLight'+str(i),(p[0],p[1]+.43,p[2]))
w.finish(OUT/'ProbeCorePassage.mu')
report['models']['ProbeCorePassage']={'collider':'Mk33ProbeCoreShell','ports':[PROBE_REAR,PROBE_FRONT],
                                   'radius':RADIUS,'vertices':v,'triangles':f,'expected_boundary_loops':2,
                                   'axis_direction':'rear to front is negative local Z','fixtures':probe_fixtures}

v,f=tube(NOSE_REAR,NOSE_OUTLET)
w=Writer('Mk33NoseDockPassage')
w.collider('Mk33NoseDockShell',v,f);w.interior('Mk33NoseDockSurface',v,f)
nose_fixtures=[fixture(w,'Mk33NoseFixture',NOSE_REAR,NOSE_OUTLET,-.12,length=.13,half_width=.10)]
w.light('Mk33NoseLight',(0,.41,-.12),.3,1.)
# Native tube length is unit negative Y. Rotate it into outward local -Z.
# Its collider, rendered skin and lights are all children of the scaled node.
w.i(0);w.transform('Mk33NoseDockTube',16,NOSE_OUTLET,(math.sqrt(.5),0,0,math.sqrt(.5)))
tv=[(RADIUS*math.cos(2*math.pi*i/N),y,RADIUS*math.sin(2*math.pi*i/N)) for y in (0,-1) for i in range(N)]
tf=[]
for i in range(N):
    j=(i+1)%N
    for face in ((i,N+i,j),(j,N+i,N+j)):
        p=tuple(sum(tv[k][a] for k in face)/3 for a in range(3))
        n=cross(sub(tv[face[1]],tv[face[0]]),sub(tv[face[2]],tv[face[0]]))
        radial=(p[0],0,p[2])
        tf.append(tuple(reversed(face)) if dot(n,radial)>0 else face)
w.i(25);w.bytes(0,0);w.mesh(tv,tf)
# The native tube's local Y is longitudinal. Map that axis along the
# corridor markings, and keep the floor/ceiling materials on their real sides
# after the +90-degree X rotation (local +Z becomes downward IVA Y).
groups={k:[] for k in ('floor','ceiling','left','right')}
for face in tf:
    n=cross(sub(tv[face[1]],tv[face[0]]),sub(tv[face[2]],tv[face[0]]))
    length=math.sqrt(dot(n,n));n=tuple(a/length for a in n)
    key='floor' if n[2]<-.65 else 'ceiling' if n[2]>.65 else 'left' if n[0]>0 else 'right'
    groups[key].append(face)
for key,faces in groups.items():
    if faces:w.surface('Mk33NoseDynamicSurface_'+key,tv,faces,
                       {'floor':2,'ceiling':3,'left':0,'right':1}[key],
                       'tube-floor' if key in ('floor','ceiling') else 'tube-left' if key=='left' else 'tube-wall')
w.i(1)
w.finish(OUT/'NoseDockPassage.mu')
report['models']['NoseDockPassage']={'collider':'Mk33NoseDockShell','ports':[NOSE_REAR,NOSE_OUTLET],
                                  'radius':RADIUS,'vertices':v,'triangles':f,'expected_boundary_loops':2,
                                  'fixtures':nose_fixtures,'dynamic_tube':{'name':'Mk33NoseDockTube','origin':NOSE_OUTLET,
                                                  'quaternion_xyzw':[math.sqrt(.5),0,0,math.sqrt(.5)],
                                                  'local_axis':[0,-1,0],'local_length':1.,
                                                  'radius':RADIUS}}
(ROOT/'Tests'/'nose-passage-geometry.json').write_text(json.dumps(report,indent=2)+'\n')
print('Built ProbeCorePassage.mu and NoseDockPassage.mu')
