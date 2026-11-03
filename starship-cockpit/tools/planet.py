# Usage: python3 tools/planet.py pages/<name>.jpg
# A location beside a ringed gas giant, lit from the left, with a small moon.
import sys;sys.path.insert(0,__import__('os').path.dirname(__file__))
from common import *
yy,xx=np.mgrid[0:H,0:W].astype(np.float32)
img=stars(26000,seed=41,bright=5)
# a faint distant galaxy band
d=(xx-W*.5)*.3+(yy-H*.2)*.95
img+=(np.exp(-(d/500)**2)*np.clip(fbm(6,5,seed=42)+.4,0,None))[...,None]*np.array([.6,.7,1.])*.012
def planet(img,cx,cy,R,L,seed,pal,rings=None,tilt=(.0,0)):
    X=(xx-cx)/R;Y=(yy-cy)/R;rr=X*X+Y*Y;inside=rr<1
    Z=np.sqrt(np.clip(1-rr,0,1))
    # rotate so the bands follow a tilted axis
    a=np.deg2rad(tilt[0]);Xr=X*np.cos(a)+Y*np.sin(a);Yr=-X*np.sin(a)+Y*np.cos(a)
    lat=np.arcsin(np.clip(Yr,-1,1));lon=np.arctan2(Xr,Z)
    turb=fbm(6,8,seed=seed)
    band=np.sin(lat*14+turb*1.6+np.sin(lat*5)*1.2)*.5+.5
    fine=fbm(7,30,seed=seed+1)
    t=np.clip(band*.8+fine*.25,0,1)
    col=pal[0][None,None]*(1-t[...,None])+pal[1][None,None]*t[...,None]
    storm=np.exp(-(((lon-.35)/.12)**2+((lat+.32)/.06)**2))
    col=col*(1-storm[...,None])+pal[2][None,None]*storm[...,None]
    N=np.stack([X,Y,Z],-1)
    lam=np.clip((N@L),0,None)
    lit=np.clip((N@L)*3+.4,0,1)*lam**.8
    limb=Z**.35
    shade=lit*limb
    if rings is not None:
        n,r0,r1,dens=rings
        # ring shadow on the planet: march from the surface toward the sun to the ring plane
        tt=-(N@n)/(L@n+1e-6);q=N+tt[...,None]*L;qr=np.linalg.norm(q,axis=-1)
        sh=np.where((tt>0)&(qr>r0)&(qr<r1),dens(qr),0)
        shade=shade*(1-.8*sh)
    p=col*shade[...,None]
    atm=np.clip(1-Z,0,1)**3*np.clip(N@L+.3,0,1)
    p+=atm[...,None]*np.array([.9,.8,.6])*.5
    out=img*(~inside)[...,None]+p*inside[...,None]*.16
    # a thin glow around the lit limb
    edge=np.exp(-((np.sqrt(rr)-1)*R/10)**2)*(np.sqrt(rr)>1)*np.clip(((np.stack([X,Y,np.zeros_like(X)],-1)/np.maximum(np.sqrt(rr),1e-6)[...,None])@L)+.2,0,1)
    out+=edge[...,None]*np.array([1.,.85,.6])*.05
    if rings is not None:
        n,r0,r1,dens=rings
        Zp=-(n[0]*X+n[1]*Y)/n[2]
        P=np.stack([X,Y,Zp],-1);pr=np.linalg.norm(P,axis=-1)
        on=(pr>r0)&(pr<r1);dd=np.where(on,dens(pr),0)
        front=(~inside)|(Zp>Z)
        # planet shadow on the rings
        pl=P@L;perp=np.linalg.norm(P-pl[...,None]*L,axis=-1);psh=(pl<0)&(perp<1)
        light=np.where(psh,.05,1.)*(.55+.45*abs(L@n))
        rc=np.array([1.,.88,.7])*.17*(.7+.3*fbm(4,60,seed=seed+3))[...,None]
        a=(dd*front)[...,None]
        out=out*(1-a*.8)+rc*light[...,None]*a
    return out
L=np.array([-.8,-.25,.55]);L/=np.linalg.norm(L)
def dens(r):
    d=np.clip(np.sin((r-1.3)*23)*.18+.62+.08*np.sin(r*97)+.05*np.sin(r*211),0,1)
    d*=np.where((r>1.83)&(r<1.9),.08,1)*np.where((r>1.55)&(r<1.58),.3,1)
    return d*np.clip((r-1.28)*12,0,1)*np.clip((2.25-r)*10,0,1)
n=np.array([0,-.96,.27]);n/=np.linalg.norm(n)
pal=(np.array([.62,.48,.32]),np.array([.95,.85,.66]),np.array([.85,.45,.28]))
img=planet(img,2900,1120,380,L,51,pal,(n,1.28,2.25,dens),tilt=(-14,0))
moon=(np.array([.45,.45,.47]),np.array([.62,.6,.58]),np.array([.5,.5,.5]))
img=planet(img,1350,900,55,L,61,moon)
save(img,sys.argv[1],seed=6)
