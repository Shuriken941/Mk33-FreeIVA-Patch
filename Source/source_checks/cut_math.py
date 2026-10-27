# SPDX-License-Identifier: GPL-2.0-or-later
import sys,json,math
from pathlib import Path
import numpy as np
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

