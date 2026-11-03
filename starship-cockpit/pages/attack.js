// Weapons: an asteroid closes in, the canopy HUD locks on, twin lasers fire four volleys,
// and it blows apart: a flash, a fireball that cools to smoke, a shockwave, burning
// debris and sparks. Plays from the start each time it's shown, then clears.
const O=new Outside(document.getElementById('c'),{reflect:1.6,reflectSky:true});
const T={x:1150,y:265};       // where the target ends up, on the canopy
const GUNS=[[260,600],[1660,600]];
const VOLLEYS=[1500,1950,2400,2850],BOLT=230,BOOM=3300;
function puffAt(f,u){const dist=f.sp*u*Math.exp(-u/1400)*1.6;return [TGT.x+Math.cos(f.a)*dist,TGT.y+Math.sin(f.a)*dist*.8-u*.012,f.sz*(.4+1.6*Math.sqrt(Math.min(1,u/f.life)))]}
const TGT={x:0,y:0};
let sd=77;const r2=()=>(sd=(sd*16807)%2147483647)/2147483647;
function puff(seed){const c=document.createElement('canvas');c.width=c.height=128;const x=c.getContext('2d');let q=seed;const r=()=>(q=(q*16807)%2147483647)/2147483647;
 for(let i=0;i<26;i++){const px=64+(r()-.5)*60,py=64+(r()-.5)*60,rr=12+r()*30,g=x.createRadialGradient(px,py,0,px,py,rr);g.addColorStop(0,`rgba(255,255,255,${.25+.3*r()})`);g.addColorStop(1,'rgba(255,255,255,0)');x.fillStyle=g;x.fillRect(0,0,128,128)}return c}
function tint(src,col){const c=document.createElement('canvas');c.width=c.height=128;const x=c.getContext('2d');x.drawImage(src,0,0);x.globalCompositeOperation='source-in';x.fillStyle=col;x.fillRect(0,0,128,128);return c}
const PUFFS=[puff(3),puff(11),puff(29)];
const HEAT=['#fffbe8','#ffe08a','#ffa23a','#e8521c','#8a2410','#2a2420'];   // hot to cool
const TP=PUFFS.map(p=>HEAT.map(h=>tint(p,h)));
const FIRE=[];for(let i=0;i<120;i++){const a=r2()*Math.PI*2,sp=.03+.2*Math.pow(r2(),.8);FIRE.push({a,sp,sz:22+r2()*60,k:i%3,d:r2()*160,rot:r2()*6,cool:.6+r2()*1.1,life:2600+r2()*2600})}
const SPARK=[];for(let i=0;i<160;i++){const a=r2()*Math.PI*2,sp=.4+r2()*1.1;SPARK.push({vx:Math.cos(a)*sp,vy:Math.sin(a)*sp*.8,l:500+r2()*900})}
const DEB=[];for(let i=0;i<16;i++){const a=r2()*Math.PI*2,sp=.08+r2()*.25;DEB.push({vx:Math.cos(a)*sp,vy:Math.sin(a)*sp,vr:(r2()-.5)*.01,k:i%8,sz:14+r2()*34,burn:r2()<.5})}
Promise.all([loadImg('rock.png'),loadImg('debris.png'),O.load()]).then(([rock,deb])=>run((s,t)=>{
 const boom=t-BOOM;
 // the target's approach and the hits it takes
 const ap=ss(0,1500,t),sc=.04+.30*ap*ap*(3-2*ap),tx=T.x+90*(1-ap)+6*Math.sin(t/700),ty=T.y-40*(1-ap)+4*Math.sin(t/900);
 TGT.x=tx;TGT.y=ty;let jolt=0;for(const v of VOLLEYS){const d=t-v-BOLT;if(d>0&&d<250)jolt=Math.max(jolt,1-d/250)}
 const shots=[];for(const v of VOLLEYS)for(let g=0;g<2;g++){const d=t-v-g*70;if(d>=0&&d<BOLT)shots.push([g,d/BOLT])}
 let flash=0;for(const v of VOLLEYS){const d=t-v-BOLT;if(d>=0&&d<180)flash=Math.max(flash,1-d/180)}
 const bf=boom>=0?Math.exp(-boom/170):0;
 O.render(s,x=>{ // the asteroid (sky layer: it's lit, not glowing)
  if(boom<60){const k=rock.width*sc;x.save();x.translate(tx+(r2()-.5)*10*jolt,ty+(r2()-.5)*10*jolt);x.rotate(t/4000);x.globalAlpha=cl(t/300);x.drawImage(rock,-k/2,-k/2,k,k);
   if(jolt>0){x.globalCompositeOperation='lighter';x.globalAlpha=jolt*.5;x.drawImage(rock,-k/2,-k/2,k,k)}x.restore()}
  // the fireball: puffs cooling from white through orange to dark smoke, drawn over
  // each other (not added), so it keeps its shape and the smoke hides what's behind
  if(boom>0){for(const f of FIRE){const u=boom-f.d;if(u<0||u>f.life)continue;const life=u/f.life,[px,py,sz]=puffAt(f,u);
    const heat=Math.min(4.999,life*7*f.cool),hi=Math.floor(heat),fr=heat-hi,al=(1-life)*Math.min(1,u/60)*.85;
    x.save();x.translate(px,py);x.rotate(f.rot+u/3000);
    x.globalAlpha=al*(1-fr);x.drawImage(TP[f.k][hi],-sz,-sz,2*sz,2*sz);x.globalAlpha=al*fr;x.drawImage(TP[f.k][Math.min(5,hi+1)],-sz,-sz,2*sz,2*sz);
    x.restore()}}
  // the debris
  if(boom>0){for(const d of DEB){const u=boom,px=tx+d.vx*u,py=ty+d.vy*u+.00002*u*u,k=d.sz;if(u>6000)continue;
    x.save();x.translate(px,py);x.rotate(d.vr*u);x.globalAlpha=cl(1-(u-4000)/2000);x.drawImage(deb,d.k*128,0,128,128,-k/2,-k/2,k,k);x.restore()}}
 },x=>{ // light
  x.lineCap='round';
  // the HUD lock, projected on the canopy
  if(t>500&&boom<400){const lk=ss(500,1300,t),half=40+180*(1-lk)+rock.width*sc*.45,al=cl((t-500)/200)*(boom>0?1-boom/400:1);
   x.strokeStyle=`rgba(${AMBER},${.85*al})`;x.lineWidth=2.5;const L=26;
   for(const [dx,dy] of [[-1,-1],[1,-1],[-1,1],[1,1]]){const cx=tx+dx*half,cy=ty+dy*half;x.beginPath();x.moveTo(cx,cy-dy*L);x.lineTo(cx,cy);x.lineTo(cx-dx*L,cy);x.stroke()}
   x.font='600 16px "JetBrains Mono",Consolas,monospace';x.fillStyle=`rgba(${AMBER},${.9*al})`;x.textAlign='left';
   x.fillText(lk<1?'ACQUIRING':(Math.floor(t/220)%2?'TARGET LOCKED':''),tx+half+12,ty-half+14);x.fillText(`RNG ${(9.8-8.6*ap).toFixed(1)} KM`,tx+half+12,ty-half+36)}
  // laser bolts: bright cores with a red glow, shrinking into the distance
  for(const [g,u] of shots){const [gx,gy]=GUNS[g],e=u*u*(3-2*u)*.4+u*.6;
   const hx=gx+(tx-gx)*e,hy=gy+(ty-gy)*e,back=Math.max(0,e-.18),bx=gx+(tx-gx)*back,by=gy+(ty-gy)*back,w=1-e*.7;
   for(const [lw,col] of [[22*w,'255,40,30,.18'],[9*w,'255,70,50,.55'],[3.5*w,'255,235,225,1']]){x.strokeStyle=`rgba(${col})`;x.lineWidth=lw;x.beginPath();x.moveTo(bx,by);x.lineTo(hx,hy);x.stroke()}}
  // hits on the rock
  if(flash>0){const g=x.createRadialGradient(tx,ty,0,tx,ty,140);g.addColorStop(0,`rgba(255,230,200,${flash})`);g.addColorStop(.3,`rgba(255,120,60,${.5*flash})`);g.addColorStop(1,'rgba(0,0,0,0)');x.fillStyle=g;x.fillRect(tx-140,ty-140,280,280)}
  if(boom>=0){
   // the flash and an anamorphic streak
   if(bf>.01){const g=x.createRadialGradient(tx,ty,0,tx,ty,700);g.addColorStop(0,`rgba(255,255,240,${bf})`);g.addColorStop(.08,`rgba(255,220,160,${.8*bf})`);g.addColorStop(.3,`rgba(255,140,60,${.25*bf})`);g.addColorStop(1,'rgba(255,90,20,0)');x.fillStyle=g;x.fillRect(0,0,W,H);
    const h=x.createLinearGradient(tx-900,0,tx+900,0);h.addColorStop(0,'rgba(255,170,90,0)');h.addColorStop(.5,`rgba(255,240,220,${bf})`);h.addColorStop(1,'rgba(255,170,90,0)');x.fillStyle=h;x.fillRect(tx-900,ty-4,1800,8)}
   // the shockwave
   const sw=boom/700;if(sw<1){const rr=40+620*Math.pow(sw,.6);x.strokeStyle=`rgba(200,225,255,${.6*(1-sw)})`;x.lineWidth=10*(1-sw)+2;x.beginPath();x.ellipse(tx,ty,rr,rr*.35,-.15,0,7);x.stroke()}
   // the glow of the fireball's hottest puffs
   for(const f of FIRE){const u=boom-f.d;if(u<0)continue;const heat=u/f.life*7*f.cool;if(heat>2.2)continue;const [px,py,sz]=puffAt(f,u);
    const g=x.createRadialGradient(px,py,0,px,py,sz*1.3);g.addColorStop(0,`rgba(255,190,110,${.35*(1-heat/2.2)})`);g.addColorStop(1,'rgba(255,90,20,0)');x.fillStyle=g;x.fillRect(px-sz*1.3,py-sz*1.3,sz*2.6,sz*2.6)}
   // sparks
   for(const p of SPARK){const u=boom;if(u>p.l)continue;const a=1-u/p.l,dd=1-Math.exp(-u/500),px=tx+p.vx*500*dd,py=ty+p.vy*500*dd,vx=p.vx*Math.exp(-u/500),vy=p.vy*Math.exp(-u/500);
    x.strokeStyle=`rgba(255,${180+70*a|0},${90+150*a*a|0},${a})`;x.lineWidth=1.6;x.beginPath();x.moveTo(px,py);x.lineTo(px-vx*40,py-vy*40);x.stroke()}
   // burning debris trails
   for(const d of DEB){if(!d.burn)continue;const u=boom;if(u>2500)continue;const px=tx+d.vx*u,py=ty+d.vy*u,a=1-u/2500;const g=x.createRadialGradient(px,py,0,px,py,30);g.addColorStop(0,`rgba(255,180,90,${.8*a})`);g.addColorStop(1,'rgba(255,80,20,0)');x.fillStyle=g;x.fillRect(px-30,py-30,60,60)}}
 },x=>{ // spill: the lasers and the blast light the cockpit
  let k=0;for(const [g,u] of shots)k=Math.max(k,.12*(1-u));k=Math.max(k,.08*flash);
  x.globalCompositeOperation='lighter';
  if(k>0){const g=x.createRadialGradient(CX,700,0,CX,700,1300);g.addColorStop(0,`rgba(255,60,40,${k})`);g.addColorStop(1,'rgba(255,30,20,0)');x.fillStyle=g;x.fillRect(0,0,W,H)}
  if(bf>.01){const g=x.createRadialGradient(tx,ty,0,tx,ty,1700);g.addColorStop(0,`rgba(255,220,170,${.55*bf})`);g.addColorStop(.5,`rgba(255,140,60,${.25*bf})`);g.addColorStop(1,'rgba(255,90,30,0)');x.fillStyle=g;x.fillRect(0,0,W,H)}
  x.globalCompositeOperation='source-over'})}));
