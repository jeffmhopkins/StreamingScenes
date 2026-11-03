# Usage: python3 tools/nebula.py pages/<name>.jpg
# A location inside an emission nebula: filaments of glowing hydrogen (red) and oxygen
# (teal), dark dust pillars rimmed with light from a young star cluster.
# The window shows roughly plate rows 650-1430, so the composition sits there.
import sys;sys.path.insert(0,__import__('os').path.dirname(__file__))
from common import *
yy,xx=np.mgrid[0:H,0:W].astype(np.float32)
cx,cy=2350,980
r=np.hypot((xx-cx)/1.4,(yy-cy))
ridge=lambda n:np.clip(1-np.abs(n)*2.2,0,1)**3
f1=warp(fbm(8,3,seed=21),180,seed=31);f2=warp(fbm(8,5,seed=22),120,seed=33)
ha=(np.clip(f1*1.2+.45,0,None)**1.4*.6+ridge(f2)*.9)*np.exp(-(r/1900)**2)
o3=(np.clip(warp(fbm(8,4,seed=23),140,seed=35)+.15,0,None)**1.6+ridge(warp(fbm(7,6,seed=24),90,seed=37))*.5)*np.exp(-(np.hypot(xx-cx,yy-cy)/900)**2)
img=ha[...,None]*np.array([1.0,.16,.26])*.13+o3[...,None]*np.array([.25,.85,.8])*.11
img+=np.exp(-(r/700)**2)[...,None]*np.array([1.,.75,.8])*.05
# pillars: columns rising toward the cluster, made from noise stretched vertically
def column(x0,y0,y1,w,seed):
    n=fbm(7,6,seed=seed);n=nd.zoom(n[:H//3,:],(3,1),order=1)[:H]
    m=fbm(7,40,seed=seed+9)
    t=np.clip((yy-y1)/(y0-y1),0,1)            # 0 at the tip, 1 at the base
    wid=w*(.25+.75*t**.7)*(1+.5*n+.12*m)
    lean=(1-t)*(cx-x0)*.12
    c=np.clip(1-np.abs(xx-x0-lean-90*n-12*m)/wid,0,1)*np.clip((yy-y1+120*n)/60,0,1)
    return np.clip(c*3,0,1)
pil=np.clip(column(1250,1900,880,190,61)+column(1650,1900,1120,120,62)+column(820,1900,1240,150,63),0,1)
pil=nd.gaussian_filter(pil,2.5)
img*=(1-.95*pil)[...,None]
# the rims: the side of each pillar that faces the cluster
gx=nd.sobel(nd.gaussian_filter(pil,3),1);gy=nd.sobel(nd.gaussian_filter(pil,3),0)
dx,dy=cx-xx,cy-yy;dn=np.hypot(dx,dy)+1
face=np.clip(-(gx*dx+gy*dy)/dn,0,None)
rim=np.clip(nd.gaussian_filter(face,3),0,.35)*np.exp(-(dn/2400)**2)*(.6+.8*np.clip(fbm(6,30,seed=64)+.5,0,1))
img+=rim[...,None]*np.array([1.,.62,.5])*1.4
img+=nd.gaussian_filter(rim,25)[...,None]*np.array([1.,.4,.4])*1.5
# the cluster
cl=np.exp(-(np.hypot(xx-cx,yy-cy)/200)**2)
img+=stars(1800,cl+1e-7,seed=26,bright=55,temp=16000)
img+=nd.gaussian_filter(cl,80)[...,None]*np.array([.7,.8,1.])*.08
st=stars(30000,seed=27,bright=5)
img+=st*(1-.9*pil)[...,None]
save(img,sys.argv[1],seed=5)
