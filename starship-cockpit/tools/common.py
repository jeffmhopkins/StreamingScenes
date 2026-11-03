import numpy as np
from scipy import ndimage as nd
from PIL import Image
W,H=3840,2160
def fbm(octaves=7, base=6, persist=.55, lac=2.0, seed=0):
    r=np.random.default_rng(seed)
    out=np.zeros((H,W),np.float32); amp=1; tot=0; f=base
    for o in range(octaves):
        gh,gw=int(f*H/W)+3,int(f)+3
        g=r.standard_normal((gh,gw)).astype(np.float32)
        up=nd.zoom(g,(H/(gh-3),W/(gw-3)),order=3)[:H,:W]
        out+=amp*up; tot+=amp; amp*=persist; f*=lac
    return out/tot
def warp(img,s=60,seed=11):
    a=fbm(5,3,seed=seed)*s; b=fbm(5,3,seed=seed+1)*s
    yy,xx=np.mgrid[0:H,0:W].astype(np.float32)
    return nd.map_coordinates(img,[yy+a,xx+b],order=1,mode='reflect')
def bb(T):
    t=T/100.
    r=np.where(t<=66,1.0,np.clip(1.292936*((t-60)**-0.1332),0,1))
    g=np.where(t<=66,np.clip(.39008*np.log(t)-.63184,0,1),np.clip(1.129891*((t-60)**-0.0755),0,1))
    b=np.where(t>=66,1.0,np.where(t<=19,0,np.clip(.543207*np.log(np.maximum(t-10,1e-3))-1.196254,0,1)))
    c=np.stack([r,g,b],1)**2.2; return c/c.max(1,keepdims=True)
def stars(N,prob=None,seed=4,bright=6.0,temp=5600):
    rng=np.random.default_rng(seed)
    if prob is None: idx=rng.integers(0,H*W,N)
    else:
        p=prob.ravel()/prob.sum(); idx=rng.choice(H*W,size=N,p=p)
    sy,sx=(idx//W),(idx%W)
    m=rng.power(3.2,N)*10; flux=10**(-0.4*m)*bright
    col=bb(np.clip(rng.lognormal(np.log(temp),.35,N),2800,25000))
    st=np.zeros((H,W,3),np.float32)
    for c in range(3): np.add.at(st[...,c],(sy,sx),flux*col[:,c])
    psf=np.zeros_like(st)
    for c in range(3):
        ch=st[...,c]
        psf[...,c]=nd.gaussian_filter(ch,.75)+.035*nd.gaussian_filter(ch,4)+.008*nd.gaussian_filter(ch,22)
        sp=nd.uniform_filter1d(ch,61,axis=1)+nd.uniform_filter1d(ch,61,axis=0)
        psf[...,c]+=.025*nd.gaussian_filter(sp,.6)
    return psf
def save(img,path,seed=0):
    x=np.arcsinh(np.maximum(img,0)*14)/np.arcsinh(14)
    out=np.clip(x,0,1)**(1/1.8)
    out+=np.random.default_rng(seed).normal(0,.006,out.shape)
    Image.fromarray((np.clip(out,0,1)*255).astype(np.uint8)).save(path,quality=92)
