# Usage: python3 tools/plate.py pages/<name>.jpg
# A photographic star plate: Milky Way band with dust lanes, an emission nebula, and
# ~70k stars with blackbody colours and a real PSF (core, halo, faint spikes). Linear light.
import numpy as np, sys
from scipy import ndimage as nd
from PIL import Image
rng=np.random.default_rng(int(sys.argv[2]) if len(sys.argv)>2 else 4)
W,H=3840,2160
def fbm(octaves=7, base=6, persist=.55, lac=2.0, seed=None):
    r=np.random.default_rng(seed) if seed is not None else rng
    out=np.zeros((H,W),np.float32); amp=1; tot=0; f=base
    for o in range(octaves):
        gh,gw=int(f*H/W)+3,int(f)+3
        g=r.standard_normal((gh,gw)).astype(np.float32)
        up=nd.zoom(g,(H/(gh-3),W/(gw-3)),order=3)[:H,:W]
        out+=amp*up; tot+=amp; amp*=persist; f*=lac
    return out/tot
def warp(img,s=60):
    a=fbm(5,3,seed=11)*s; b=fbm(5,3,seed=12)*s
    yy,xx=np.mgrid[0:H,0:W].astype(np.float32)
    return nd.map_coordinates(img,[yy+a,xx+b],order=1,mode='reflect')
yy,xx=np.mgrid[0:H,0:W].astype(np.float32)
# the Milky Way: a band across the frame at an angle
ang=np.deg2rad(-24); nx,ny=-np.sin(ang),np.cos(ang)
d=((xx-W*.5)*nx+(yy-H*.55)*ny)
n1=warp(fbm(8,4,seed=1),90)
width=380*(1+.35*fbm(4,2,seed=2))
band=np.exp(-(d/width)**2)
core=np.exp(-(d/(width*.35))**2)
along=((xx-W*.5)*ny-(yy-H*.55)*nx)/W
bulge=np.exp(-((along+.12)/.32)**2)
glow=band*(.55+.9*np.clip(n1+.25,0,None))*(0.35+0.9*bulge)
dust=np.clip(warp(fbm(8,5,seed=3),70)*1.6+.15,0,1)
lane=np.exp(-((d+40*fbm(4,3,seed=5))/(width*.22))**2)
glow*=1-.85*dust*np.clip(core*1.4+lane,0,1)
fine=np.clip(fbm(6,40,seed=6)+.1,0,None)
glow*=.75+.6*fine
warm=np.array([1.0,.78,.55],np.float32); cool=np.array([.55,.68,1.0],np.float32)
mix=np.clip(core*bulge*1.6,0,1)[...,None]
img=(glow[...,None]*(cool*(1-mix)+warm*mix))*.055
# an emission nebula off the band
cx,cy=W*.78,H*.30
blob=np.exp(-(((xx-cx)/700)**2+((yy-cy)/480)**2))
ha=np.clip(warp(fbm(8,6,seed=7),120)+.05,0,None)**1.6*blob
o3=np.clip(warp(fbm(8,7,seed=8),100)-.05,0,None)**1.8*np.exp(-(((xx-cx-90)/420)**2+((yy-cy+40)/300)**2))
img+=ha[...,None]*np.array([1.0,.22,.30])*.09+o3[...,None]*np.array([.25,.85,.9])*.06
img*= (1-.6*np.clip(dust*blob*1.5,0,1))[...,None]
# stars
N=70000
pb=(band*0.85+0.15).ravel(); pb/=pb.sum()
idx=rng.choice(H*W,size=N,p=pb)
sy,sx=(idx//W).astype(np.float32)+rng.random(N),(idx%W).astype(np.float32)+rng.random(N)
m=rng.power(3.2,N)*10  # mostly faint
flux=10**(-0.4*m)*6.0
T=np.clip(rng.lognormal(np.log(5600),.35,N),2800,25000)
def bb(T):  # rough blackbody → linear sRGB
    t=T/100.
    r=np.where(t<=66,1.0,np.clip(1.292936*((t-60)**-0.1332),0,1))
    g=np.where(t<=66,np.clip(.39008*np.log(t)-.63184,0,1),np.clip(1.129891*((t-60)**-0.0755),0,1))
    b=np.where(t>=66,1.0,np.where(t<=19,0,np.clip(.543207*np.log(t-10)-1.196254,0,1)))
    c=np.stack([r,g,b],1)**2.2; return c/c.max(1,keepdims=True)
col=bb(T)
st=np.zeros((H,W,3),np.float32)
ix,iy=sx.astype(int).clip(0,W-1),sy.astype(int).clip(0,H-1)
for c in range(3): np.add.at(st[...,c],(iy,ix),flux*col[:,c])
psf=np.zeros_like(st)
for c in range(3):
    ch=st[...,c]
    psf[...,c]=nd.gaussian_filter(ch,.75)+.035*nd.gaussian_filter(ch,4)+.008*nd.gaussian_filter(ch,22)
    sp=nd.uniform_filter1d(nd.uniform_filter1d(ch,1,axis=0),61,axis=1)+nd.uniform_filter1d(ch,61,axis=0)
    psf[...,c]+=.025*nd.gaussian_filter(sp,.6)
img+=psf
def tone(x):
    x=np.arcsinh(x*14)/np.arcsinh(14)
    return np.clip(x,0,1)**(1/1.8)
out=tone(img)
out+=rng.normal(0,.006,out.shape)
Image.fromarray((np.clip(out,0,1)*255).astype(np.uint8)).save(sys.argv[1],quality=92)
