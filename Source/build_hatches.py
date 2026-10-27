"""Original functional hatch/rail assets. SPDX-License-Identifier: MIT.
Run with Python 3; all geometry below is original parametric geometry.
Unity local +Y points into the room; hatch lies in XZ. No cutout or auto tube.
"""
import math, struct, zlib
from pathlib import Path
OUT=Path(__file__).resolve().parent.parent/'Models'
OUT.mkdir(parents=True,exist_ok=True)
class W:
    def __init__(self,name):
        self.data=bytearray();self.i(76543,5);self.s(name);self.transform(name,20)
    def i(self,*v):self.data.extend(struct.pack('<'+'i'*len(v),*v))
    def f(self,*v):self.data.extend(struct.pack('<'+'f'*len(v),*v))
    def b(self,*v):self.data.extend(v)
    def s(self,s):
        raw=s.encode();n=len(raw)
        while n>=128:self.b((n&127)|128);n>>=7
        self.b(n);self.data.extend(raw)
    def transform(self,name,layer,pos=(0,0,0),rotation=(0,0,0,1)):
        self.s(name);self.f(*pos,*rotation,1,1,1);self.i(24);self.s('Untagged');self.i(layer)
    def mesh(self,vertices,faces):
        self.i(13,len(vertices),1,14)
        for p in vertices:self.f(*p)
        self.i(15)
        for x,y,z in vertices:self.f(.5+x,.5+z)
        self.i(19,len(faces)*3)
        for face in faces:self.i(*face)
        self.i(22)
    def geometry(self,name,v,f,layer=20,collider=False,convex=False):
        self.i(0);self.transform(name,layer)
        if collider:self.i(25);self.b(0,int(convex));self.mesh(v,f)
        self.i(7);self.mesh(v,f);self.i(8);self.b(0,0);self.i(1,0);self.i(1)
    def handle(self,name,y):
        self.i(0);self.transform(name,20,(0,y,0))
        self.i(28);self.b(0);self.f(.32,.025,.10,0,0,0);self.i(1)
    def finish(self,name):
        self.i(10,1);self.s('Mk33FunctionalHatch');self.s('KSP/Unlit');self.i(2)
        self.s('_Color');self.i(0);self.f(1,1,1,1)
        self.s('_MainTex');self.i(4,0);self.f(1,1,0,0)
        self.i(12,1);self.s('hatchGrey');self.i(0)
        (OUT/name).write_bytes(self.data)
def disc(r=.545,thickness=.035,n=32):
    v=[(r*math.cos(2*math.pi*i/n),y,r*math.sin(2*math.pi*i/n)) for y in [-thickness/2,thickness/2] for i in range(n)]
    v.extend([(0,-thickness/2,0),(0,thickness/2,0)])
    f=[]
    for i in range(n):
        j=(i+1)%n
        f.extend([(i,j,n+i),(j,n+j,n+i),(2*n,j,i),(2*n+1,n+i,n+j)])
    # The cylinder is solid; its faces must point outward (unlike the tunnel).
    return v,[(a,c,b) for a,b,c in f]
w=W('Mk33CircularHatch');v,f=disc();w.geometry('door',v,f,16,True,True)
w.handle('handleInside',.04);w.handle('handleOutside',-.04);w.finish('CircularHatch.mu')
# Simple rectangular dock tube for the original Krew roof door. Local negative
# Y extends outward; native FreeIVA scales it only while connected to a peer.
w=W('Mk33KrewDockTubeModel')
w.i(0);w.transform('Mk33KrewDockTubeRoot',20,(1.11893,1.82830,.76054),(1,0,0,0))
v=[(x,y,z) for y in [0,-1] for x,z in [(-.31,-.35),(.31,-.35),(.31,.35),(-.31,.35)]]
f=[]
for i in range(4):
    j=(i+1)%4;f.extend([(i,4+i,j),(j,4+i,4+j)])
w.geometry('Mk33KrewDockTube',v,f,16,True,False);w.i(1);w.finish('KrewDockTube.mu')
w=W('Mk33InteractionPoints')
for name in ['Mk33DoorHandle','Mk33RailOne','Mk33RailTwo']:
    w.i(0);w.transform(name,20);w.i(1)
w.finish('InteractionPoints.mu')
def chunk(k,d):return struct.pack('>I',len(d))+k+d+struct.pack('>I',zlib.crc32(k+d)&0xffffffff)
raw=b'\0'+bytes([165,174,181,255])*2+b'\0'+bytes([143,151,158,255])*2
(OUT/'hatchGrey.png').write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>2I5B',2,2,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b''))
print('Built CircularHatch.mu and KrewDockTube.mu')
