// The reflections, done the way JStream would do them natively rather than by each page:
// one layer that mirrors the whole composite of what is outside into the cockpit, and
// the lit interior into the glass. In JStream this is a scene source of the outside
// layers placed with flip_v, a blur filter and an image_mask, blended additive; here
// demo.html stands in for it by reading the shown pages' canvases.
//  console: the outside, mirrored and squashed onto the ledge, sills and bolsters
//  edge:    the outside, blurred so it bleeds onto the frame bevels (rim light)
//  glass:   monitors and holograms, mirrored about the window's lower edge, faint
(()=>{const R=document.getElementById('refl'),x=R.getContext('2d'),HW=W/2,HH=H/2;
const mk=()=>{const c=document.createElement('canvas');c.width=HW;c.height=HH;return [c,c.getContext('2d')]};
const [O,ox]=mk(),[I,ix]=mk(),[T,tx]=mk();let M=null;
const OUT=['sky_deep','sky_nebula','sky_planet','win_deep','wout_nebula','win_nebula','wout_planet','attack'];
const HOLO=['tx','bitwig','hit'];
const asMask=i=>{const c=document.createElement('canvas');c.width=HW;c.height=HH;const g=c.getContext('2d');g.drawImage(i,0,0,HW,HH);
 const d=g.getImageData(0,0,HW,HH);for(let p=0;p<d.data.length;p+=4){d.data[p+3]=d.data[p];d.data[p]=d.data[p+1]=d.data[p+2]=255}g.putImageData(d,0,0);return c};
Promise.all(['m-window','m-console','m-edge','m-glass'].map(n=>loadImg(n+'.png'))).then(a=>{M={win:asMask(a[0]),con:asMask(a[1]),edge:asMask(a[2]),glass:asMask(a[3])}});
const shown=id=>{const f=document.getElementById(id);if(!f||f.classList.contains('hide'))return null;try{return f.contentDocument.getElementById('c')}catch(e){return null}};
function masked(src,mask,s,gain,blur,flip){ // flip=[axis y, squash]: y' = axis + (axis - y)*squash
 tx.setTransform(1,0,0,1,0,0);tx.globalCompositeOperation='source-over';tx.globalAlpha=1;tx.clearRect(0,0,HW,HH);
 tx.save();tx.filter=`blur(${blur}px)`;if(flip){const [a,k]=flip;tx.translate(0,a*(1+k));tx.scale(1,-k)}tx.drawImage(src,0,0);tx.restore();tx.filter='none';
 tx.globalCompositeOperation='destination-in';tx.save();tx.scale(.5,.5);applySway(tx,s);tx.drawImage(mask,0,0,W,H);tx.restore();
 x.globalCompositeOperation='lighter';for(let r=gain;r>0;r--){x.globalAlpha=Math.min(1,r);x.drawImage(T,0,0,W,H)}x.globalAlpha=1}
function frame(){const s=NOW();x.clearRect(0,0,W,H);if(!M)return;
 // the outside as seen through the windows
 ox.setTransform(1,0,0,1,0,0);ox.globalCompositeOperation='source-over';ox.clearRect(0,0,HW,HH);
 for(const id of OUT){const c=shown(id);if(c)ox.drawImage(c,0,0,HW,HH)}
 ox.globalCompositeOperation='destination-in';ox.save();ox.scale(.5,.5);applySway(ox,s);ox.drawImage(M.win,0,0,W,H);ox.restore();
 // the lit interior: the monitors as shown and the holograms
 ix.setTransform(1,0,0,1,0,0);ix.globalCompositeOperation='source-over';ix.clearRect(0,0,HW,HH);ix.save();ix.scale(.5,.5);
 for(const d of document.querySelectorAll('.mon')){const L=d.offsetLeft,Tp=d.offsetTop,w=d.offsetWidth,h=d.offsetHeight;ix.save();ix.beginPath();ix.rect(L,Tp,w,h);ix.clip();
  const im=d.querySelector('img');if(im&&im.complete)ix.drawImage(im,L,Tp,w,h);
  for(const f of d.querySelectorAll('iframe')){if(f.classList.contains('hide'))continue;let c=null;try{c=f.contentDocument.getElementById('c')}catch(e){}if(c)ix.drawImage(c,L,Tp,c.width/2,c.height/2)}ix.restore()}
 ix.globalCompositeOperation='lighter';
 for(const id of ['caller','daw']){const im=document.getElementById(id),o=+getComputedStyle(im).opacity;if(o>0&&im.complete){ix.globalAlpha=o;ix.drawImage(im,im.offsetLeft,im.offsetTop,im.offsetWidth,im.offsetHeight);ix.globalAlpha=1}}
 for(const id of HOLO){const c=shown(id);if(c)ix.drawImage(c,0,0)}ix.restore();
 masked(O,M.con,s,1.6,2,[715/2,.7]);   // mirrored outside on the ledge, sills, bolsters
 masked(O,M.edge,s,2.2,6,null);          // bevels lit by the glass beside them
 masked(I,M.glass,s,.18,1.5,[492/2,.8]);  // interior ghosted in the glass
 x.globalCompositeOperation='source-over'}
window.__refl=frame;run(frame)})();
