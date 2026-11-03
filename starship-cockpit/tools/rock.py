# Usage: python3 tools/rock.py pages
# An asteroid sprite and debris chunks, lit from the upper left, on transparent.
import sys
import numpy as np
from scipy import ndimage as nd
from PIL import Image
def noise(n,base,oct,seed):
    r=np.random.default_rng(seed);out=np.zeros((n,n),np.float32);a=1;f=base;t=0
    for o in range(oct):
        g=r.standard_normal((f+3,f+3)).astype(np.float32);out+=a*nd.zoom(g,n/f,order=3)[:n,:n];t+=a;a*=.5;f*=2
    return out/t
def rock(n,seed,lump=.18,crater=14):
    yy,xx=np.mgrid[0:n,0:n].astype(np.float32);c=n/2;X=(xx-c)/(n*.42);Y=(yy-c)/(n*.42)
    th=np.arctan2(Y,X);rng=np.random.default_rng(seed)
    R=1+sum(lump/(k)*np.sin(k*th+rng.random()*6) for k in range(2,7))
    rr=np.hypot(X,Y)/R
    inside=rr<1
    h=np.sqrt(np.clip(1-rr**2,1e-4,1))
    h+=noise(n,5,6,seed)*.05+noise(n,20,4,seed+1)*.012
    for i in range(crater):
        cx,cy=rng.uniform(-.7,.7,2);cr=rng.uniform(.05,.22)
        d=np.hypot(X-cx,Y-cy)/cr
        h+=-.25*cr*np.exp(-d**2*2.2)+.08*cr*np.exp(-((d-1.1)/.18)**2)
    gy,gx=np.gradient(nd.gaussian_filter(h,1.2))
    N=np.stack([-gx*n*.42,-gy*n*.42,np.ones_like(h)],-1);N/=np.linalg.norm(N,axis=-1,keepdims=True)
    L=np.array([-.6,-.55,.58]);L/=np.linalg.norm(L)
    lam=np.clip(N@L,0,1)
    base=np.array([.42,.38,.34])*(.8+.4*noise(n,24,4,seed+2)[...,None])
    col=np.clip(base*(lam[...,None]**1.2*1.1+.004),0,1)
    a=np.clip((1-rr)*n*.12,0,1)*inside
    out=np.zeros((n,n,4),np.float32);out[...,:3]=col**(1/2.2);out[...,3]=a
    return Image.fromarray((np.clip(out,0,1)*255).astype(np.uint8),'RGBA')
rock(512,3).save(sys.argv[1]+'/rock.png')
chunks=[rock(128,10+i,lump=.35,crater=3) for i in range(8)]
sheet=Image.new('RGBA',(128*8,128))
for i,c in enumerate(chunks):sheet.paste(c,(128*i,0))
sheet.save(sys.argv[1]+'/debris.png')
