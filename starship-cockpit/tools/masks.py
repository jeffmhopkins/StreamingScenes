# Usage, from starship-cockpit/: python3 tools/masks.py
# From the keyed cockpit (site/cockpit.png): the window mask (what the outside shows
# through), the gloss mask (smooth dark surfaces that pick up reflections), and the
# lights layer (the amber indicator lights alone, to pulse with the music).
import numpy as np
from scipy import ndimage as nd
from PIL import Image
im=np.asarray(Image.open('pages/cockpit.png')).astype(np.float32)/255
rgb,a=im[...,:3],im[...,3]
H,W=a.shape
yy,xx=np.mgrid[0:H,0:W]
scr=np.zeros_like(a,bool)
for x,y,w,h in [(490,531,329,168),(843,531,317,167),(1182,531,326,168)]:scr[y-6:y+h+6,x-6:x+w+6]=True
win=(1-a)*(~scr)
Image.fromarray((win*255).astype(np.uint8),'L').save('pages/m-window.png')
Image.fromarray(((1-a)*scr*255).astype(np.uint8),'L').save('pages/m-screens.png')
lum=rgb@np.array([.3,.59,.11],np.float32)
# lights: bright, saturated amber pixels on the cockpit
sat=rgb.max(-1)-rgb.min(-1)
L=np.clip((lum-.28)/.25,0,1)*np.clip((sat-.15)/.2,0,1)*(rgb[...,0]>rgb[...,2])*a
Lg=np.clip(L+nd.gaussian_filter(L,3)*1.5,0,1)
out=np.zeros((H,W,4),np.float32);out[...,:3]=rgb*.6+np.array([1,.55,.15])*.4;out[...,3]=Lg
Image.fromarray((np.clip(out,0,1)*255).astype(np.uint8),'RGBA').save('pages/lights.png')
# gloss: smooth (low local contrast), not a light, opaque cockpit; strongest on the
# dash top and the window frames, which face the windows
m=nd.uniform_filter(lum,9);v=np.sqrt(np.clip(nd.uniform_filter(lum*lum,9)-m*m,0,None))
smooth=np.clip(1-v/.05,0,1)
edge=nd.gaussian_filter(win,18);near=np.clip(edge*3,0,1)   # close to the glass
dash=np.exp(-((yy-735)/70.)**2)*nd.gaussian_filter((np.abs(xx-960)<760).astype(np.float32),60)
g=smooth*a*(1-L)*np.clip(.15+near*.9+dash*.8,0,1)*(lum<.35)
g=nd.gaussian_filter(g,1.2)
Image.fromarray((np.clip(g,0,1)*255).astype(np.uint8),'L').save('pages/m-gloss.png')
print(L.sum(),g.mean())
