// Shared by every cockpit page. All motion is a function of the wall clock (Date.now),
// so separate browser sources stay in step: the sky, the reflections, the cockpit sway
// and the music-driven lights all agree without talking to each other.
const W=1920,H=1080,CX=960,CY=300,SKY_SCALE=.56;
const NOW=()=>Date.now()/1000;
const cl=(v,a=0,b=1)=>Math.max(a,Math.min(b,v));
const ss=(a,b,t)=>{t=cl((t-a)/(b-a));return t*t*(3-2*t)};
function hash(n){n=Math.sin(n*127.1+311.7)*43758.5453;return n-Math.floor(n)}
function vnoise(t){const i=Math.floor(t),f=t-i,u=f*f*(3-2*f);return (hash(i)*(1-u)+hash(i+1)*u)*2-1}
function loadImg(src){return new Promise(r=>{const i=new Image();i.onload=()=>r(i);i.src=src})}
const AMBER='255,176,64',CYAN='110,220,255';

// ---- simulated music (stands in for the Bitwig bus until JStream can feed audio in) ----
// 118 BPM: a kick on every beat, a snare on 2 and 4, eighth-note hats, a bass line, a
// slow pad, and a 4-bar breakdown without the kick every 16 bars.
const BPM=118,BEAT=60/BPM;
function audio(s){
 const b=s/BEAT,ph=b%1,beat=Math.floor(b),bar=Math.floor(beat/4),brk=bar%16>=12;
 const kick=brk?0:Math.exp(-ph*8);
 const snare=(beat%2==1)?Math.exp(-ph*6):0;
 const hat=Math.exp(-((b*2)%1)*22)*(.55+.45*((beat*2+Math.floor((b*2)%2))%2));
 const bass=(brk?.35:.75)*(.5+.5*Math.exp(-ph*3))*(.7+.3*hash(beat%8));
 const pad=.5+.5*Math.sin(s*.37)*Math.sin(s*.11+1);
 const bands=[];const q=Math.floor(s*30);
 for(let i=0;i<32;i++){const f=i/31;
  let v=kick*Math.exp(-f*9)+bass*Math.exp(-(((f-.09)/.07)**2))*.8+snare*Math.exp(-(((f-.45)/.22)**2))*.75
   +hat*Math.exp(-(((f-.86)/.13)**2))*.7+pad*Math.exp(-(((f-.3)/.18)**2))*.35;
  v+= .1*(hash(q*37+i)-.5)+.06;bands.push(cl(v*(1-.25*f)))}
 const level=cl(.25+.45*kick+.25*snare+.15*bass+.1*pad);
 return {kick,snare,hat,bass,pad,bands,level,brk,beat}}

// ---- motion ----
// The pilot's head in the cockpit: a slow float, a little noise, and the kick drum
// felt through the hull. Pixels and radians, about the canvas centre.
function sway(s){const a=audio(s);
 return {x:2.6*Math.sin(s*2*Math.PI/7.3)+1.4*vnoise(s*.6)+.5*vnoise(s*2.1+4),
         y:2.0*Math.sin(s*2*Math.PI/5.9+.7)+1.1*vnoise(s*.5+9)+.4*vnoise(s*2.3+3)+.7*a.kick,
         r:.0018*Math.sin(s*2*Math.PI/11.3)+.0008*vnoise(s*.4+5)}}
function applySway(x,s,k=1){const v=sway(s);x.translate(CX+v.x*k,540+v.y*k);x.rotate(v.r*k);x.translate(-CX,-540)}
// The ship's slow drift against the sky.
function attitude(s){return {x:46*Math.sin(s*2*Math.PI/140)+12*vnoise(s*.05),y:20*Math.sin(s*2*Math.PI/110+1),
 r:.012*Math.sin(s*2*Math.PI/170),z:1+.015*Math.sin(s*2*Math.PI/95)}}
function drawPlate(x,plate,s,zoom=1){const a=attitude(s);x.save();x.translate(CX+a.x,CY+a.y);x.rotate(a.r);
 const k=SKY_SCALE*a.z*zoom;x.scale(k,k);x.drawImage(plate,-1920,-1080);x.restore()}

// ---- near stars: soft sprites flying past for depth ----
let seed=9;const rnd=()=>(seed=(seed*16807)%2147483647)/2147483647;
function sprite(r,g,b){const c=document.createElement('canvas');c.width=c.height=64;const x=c.getContext('2d');
 const gr=x.createRadialGradient(32,32,0,32,32,32);gr.addColorStop(0,'rgba(255,255,255,1)');gr.addColorStop(.08,`rgba(${r},${g},${b},.95)`);
 gr.addColorStop(.22,`rgba(${r},${g},${b},.28)`);gr.addColorStop(.5,`rgba(${r},${g},${b},.06)`);gr.addColorStop(1,'rgba(0,0,0,0)');x.fillStyle=gr;x.fillRect(0,0,64,64);return c}
const SPR=[sprite(255,236,210),sprite(210,225,255),sprite(255,214,170),sprite(235,240,255)];
const NEAR=[];for(let i=0;i<380;i++)NEAR.push({x:(rnd()-.5)*5200,y:(rnd()-.5)*3200,z:rnd()*3000,m:Math.pow(rnd(),3),k:Math.floor(rnd()*4)});
function drawNear(x,s,a=1){const at=attitude(s);x.globalCompositeOperation='lighter';
 for(const st of NEAR){const zz=((st.z-s*120)%3000+3000)%3000+20,k=700/zz,sx=CX+at.x+st.x*k,sy=CY+at.y+st.y*k;
  if(sx<-40||sx>W+40||sy<-40||sy>H+40)continue;const al=Math.min(1,(3000-zz)/900)*(.25+.75*st.m)*a,r=4+26*k*(.3+st.m);
  x.globalAlpha=al;x.drawImage(SPR[st.k],sx-r,sy-r,2*r,2*r)}
 x.globalAlpha=1;x.globalCompositeOperation='source-over'}

// ---- the outside compositor ----
// A page that shows something outside draws it in two parts: `sky` (what is out there)
// and `light` (anything that glows: streaks, flashes, lasers, fire). This masks both to
// the windows, which move with the cockpit sway, mirrors a blurred copy into the gloss
// of the dash and frames as a reflection (the sky only when `reflectSky`, so a layer on
// top of a sky page doesn't reflect the same stars twice), and then draws `spill`, the
// light thrown into the cockpit, unmasked.
class Outside{
 constructor(canvas,opt={}){this.c=canvas;this.x=canvas.getContext('2d');this.reflect=opt.reflect??.55;this.reflectSky=!!opt.reflectSky;
  const mk=(w,h)=>{const c=document.createElement('canvas');c.width=w;c.height=h;return [c,c.getContext('2d')]};
  [this.out,this.ox]=mk(W,H);[this.lt,this.lx]=mk(W,H);[this.ref,this.rx]=mk(W/2,H/2)}
 async load(){[this.win,this.gloss]=await Promise.all([loadImg('m-window.png'),loadImg('m-gloss.png')]);
  for(const k of ['win','gloss']){const i=this[k],c=document.createElement('canvas');c.width=W;c.height=H;const x=c.getContext('2d');x.drawImage(i,0,0);
   const d=x.getImageData(0,0,W,H);for(let p=0;p<d.data.length;p+=4){d.data[p+3]=d.data[p];d.data[p]=d.data[p+1]=d.data[p+2]=255}x.putImageData(d,0,0);this[k]=c}}
 render(s,sky,light,spill,alpha=1){const {x,ox,lx,rx}=this;
  for(const c of [ox,lx]){c.setTransform(1,0,0,1,0,0);c.globalAlpha=1;c.globalCompositeOperation='source-over';c.clearRect(0,0,W,H)}
  if(sky)sky(ox);if(light){light(lx);ox.globalCompositeOperation='lighter';ox.drawImage(this.lt,0,0);ox.globalCompositeOperation='source-over'}
  x.setTransform(1,0,0,1,0,0);x.globalAlpha=1;x.clearRect(0,0,W,H);x.globalCompositeOperation='source-over';
  if(alpha<=0)return;
  x.globalAlpha=alpha;x.drawImage(this.out,0,0);x.globalAlpha=1;
  x.globalCompositeOperation='destination-in';x.save();applySway(x,s);x.drawImage(this.win,0,0);x.restore();
  if(this.reflect>0){rx.setTransform(1,0,0,1,0,0);rx.globalCompositeOperation='source-over';rx.clearRect(0,0,W/2,H/2);
   rx.save();rx.scale(.5,.5);rx.filter='blur(5px)';rx.translate(0,1210);rx.scale(1,-1);rx.drawImage(this.reflectSky?this.out:this.lt,0,0);rx.restore();rx.filter='none';
   rx.globalCompositeOperation='destination-in';rx.save();rx.scale(.5,.5);applySway(rx,s);rx.drawImage(this.gloss,0,0);rx.restore();
   x.globalCompositeOperation='lighter';let r=this.reflect*alpha;while(r>0){x.globalAlpha=Math.min(1,r);x.drawImage(this.ref,0,0,W,H);r-=1}x.globalAlpha=1}
  x.globalCompositeOperation='source-over';if(spill)spill(x)}}
// Runs `frame(s, t)` every animation frame: s is the shared clock in seconds, t is ms
// since this page loaded (for effects that play from the start when shown).
function run(frame){let t0=null;function f(){const n=performance.now();if(t0===null)t0=n;frame(NOW(),n-t0);requestAnimationFrame(f)}requestAnimationFrame(f)}
