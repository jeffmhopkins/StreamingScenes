// Jump to warp (MODE 'in', from PLATE's sky) or drop out of it (MODE 'out', into
// PLATE's sky). Built to stay smooth: every star moves less per frame than its own
// streak is long, the sky stretches with one continuous zoom blur (no repeating
// tiles), and the hyperspace tunnel turns slowly. Ends identical to the sky page, so
// the switch underneath is invisible.
const O=new Outside(document.getElementById('c'),{reflect:0});
const N=1100,ST=[];for(let i=0;i<N;i++)ST.push({x:(rnd()-.5)*7,y:(rnd()-.5)*4.4,z:.03+rnd(),w:Math.pow(rnd(),2),c:rnd()});
const F=380;
// speed in depth per second, and the shape of the effect over time t (ms)
function plan(t){
 if(MODE==='in'){const k=ss(250,2300,t);
  return {v:.03+4.2*k*k,zoom:1+.35*k*k,blur:ss(400,2000,t),sky:1-ss(1900,2450,t),near:1-ss(0,700,t),fl:Math.exp(-(((t-2350)/170)**2)),hyper:ss(2150,2700,t),fade:1}}
 const k=1-Math.pow(1-ss(500,2600,t),2.2);
 return {v:4.2+(.03-4.2)*k,zoom:1.35-.35*k,blur:1-ss(700,2500,t),sky:ss(650,1300,t),near:ss(1800,2700,t),fl:Math.exp(-(((t-700)/190)**2)),hyper:1-ss(550,1100,t),fade:1-ss(2700,3300,t)}}
// the sky, zoom-blurred once at load: 28 enlarged copies averaged
function zoomBlur(plate,s){const c=document.createElement('canvas');c.width=W;c.height=H;const x=c.getContext('2d');x.fillStyle='#000';x.fillRect(0,0,W,H);
 x.globalCompositeOperation='lighter';const n=28;for(let i=0;i<n;i++){x.globalAlpha=1.05/n*(1-i/n*.6);drawPlate(x,plate,s,1+.45*i/n)}return c}
// hyperspace walls: radial light streaks at random angles, made once, turned slowly
function tunnelTex(){const c=document.createElement('canvas');c.width=c.height=2400;const x=c.getContext('2d');x.translate(1200,1200);x.globalCompositeOperation='lighter';
 for(let i=0;i<700;i++){const a=rnd()*Math.PI*2,r0=60+Math.pow(rnd(),.6)*700,r1=r0+150+rnd()*700,bright=i<140,w=bright?.8+rnd()*1.4:1+rnd()*5;
  const g=x.createLinearGradient(Math.cos(a)*r0,Math.sin(a)*r0,Math.cos(a)*r1,Math.sin(a)*r1);const hue=rnd();
  const col=hue<.7?'120,170,255':hue<.9?'170,140,255':'220,235,255';g.addColorStop(0,`rgba(${col},0)`);g.addColorStop(.5,`rgba(${col},${bright?.25+.3*rnd():.025+.07*rnd()})`);g.addColorStop(1,`rgba(${col},0)`);
  x.strokeStyle=g;x.lineWidth=w;x.beginPath();x.moveTo(Math.cos(a)*r0,Math.sin(a)*r0);x.lineTo(Math.cos(a)*r1,Math.sin(a)*r1);x.stroke()}
 const fx=document.createElement('canvas');fx.width=fx.height=2400;const y=fx.getContext('2d');y.filter='blur(3px)';y.drawImage(c,0,0);return fx}
let last=null;
Promise.all([loadImg(PLATE),O.load()]).then(([plate])=>{
 const blurred=zoomBlur(plate,NOW()+(MODE==='in'?1.5:2)),tun=tunnelTex();
 run((s,t)=>{const p=plan(t),dt=last===null?0:Math.min(.05,(t-last)/1000);last=t;
  for(const st of ST){st.z-=p.v*dt;if(st.z<.03)st.z+=1}
  const trail=Math.min(.75,p.v*.17+.002);
  O.render(s,x=>{ // sky
   x.fillStyle='#000';x.fillRect(0,0,W,H);
   if(p.sky>0){x.save();x.globalAlpha=p.sky*(1-p.blur);drawPlate(x,plate,s,p.zoom);
    x.globalAlpha=p.sky*p.blur;x.translate(CX,CY);x.scale(p.zoom,p.zoom);x.translate(-CX,-CY);x.drawImage(blurred,0,0);x.restore()}
   if(p.near>0)drawNear(x,s,p.near);
   if(p.hyper>0){const g=x.createRadialGradient(CX,CY,0,CX,CY,1300);g.addColorStop(0,`rgba(26,48,130,${.95*p.hyper})`);g.addColorStop(.25,`rgba(8,16,60,${.95*p.hyper})`);g.addColorStop(1,`rgba(0,1,8,${.97*p.hyper})`);x.fillStyle=g;x.fillRect(0,0,W,H)}
  },x=>{ // light
   if(p.hyper>0){x.save();x.globalAlpha=p.hyper*(.85+.15*Math.sin(s*2.1));x.translate(CX,CY);x.rotate(s*.05);
    for(const [k,a] of [[1,.6],[1.6,.5]]){const sc=k*(1+.04*Math.sin(s*.7+k));x.save();x.scale(sc,sc);x.globalAlpha*=a;x.drawImage(tun,-1200,-1200);x.restore()}x.restore();
    const c=x.createRadialGradient(CX,CY,0,CX,CY,200);c.addColorStop(0,`rgba(225,235,255,${.7*p.hyper})`);c.addColorStop(.2,`rgba(120,160,255,${.25*p.hyper})`);c.addColorStop(1,'rgba(0,0,0,0)');x.fillStyle=c;x.fillRect(CX-200,CY-200,400,400)}
   x.lineCap='round';
   const vis=cl(p.v/.6);if(vis>0)for(const st of ST){
    const z1=st.z,z0=Math.min(1.03,st.z+trail),a=vis*cl((1.03-z1)/.3)*(.35+.65*st.w);
    const x1=CX+st.x/z1*F,y1=CY+st.y/z1*F,x0=CX+st.x/z0*F,y0=CY+st.y/z0*F;
    if((x1<-80||x1>W+80||y1<-80||y1>H+80)&&(x0<-80||x0>W+80||y0<-80||y0>H+80))continue;
    const lw=Math.min(3.2,.5+.07/z1*(.5+st.w));const col=st.c<.75?'200,220,255':st.c<.9?'255,225,200':'170,190,255';
    const g=x.createLinearGradient(x0,y0,x1,y1);g.addColorStop(0,`rgba(${col},0)`);g.addColorStop(1,`rgba(${col},${.95*a})`);
    x.strokeStyle=g;x.lineWidth=lw;x.beginPath();x.moveTo(x0,y0);x.lineTo(x1,y1);x.stroke()}
   if(p.fl>.003){const g=x.createRadialGradient(CX,CY,0,CX,CY,1500);g.addColorStop(0,`rgba(255,255,255,${p.fl})`);g.addColorStop(.3,`rgba(190,215,255,${.75*p.fl})`);g.addColorStop(1,`rgba(90,130,255,${.2*p.fl})`);x.fillStyle=g;x.fillRect(0,0,W,H);
    const h=x.createLinearGradient(0,0,W,0);h.addColorStop(0,'rgba(120,170,255,0)');h.addColorStop(.5,`rgba(225,238,255,${p.fl})`);h.addColorStop(1,'rgba(120,170,255,0)');x.fillStyle=h;x.fillRect(0,CY-5,W,10)}
  },x=>{ // spill: the jump flash and the blue of hyperspace light the cockpit
   const k=p.fl*.55+p.hyper*.10*p.fade;if(k>.003){x.globalCompositeOperation='lighter';const g=x.createRadialGradient(CX,CY,0,CX,CY,1500);g.addColorStop(0,`rgba(190,215,255,${k})`);g.addColorStop(1,`rgba(60,100,255,${k*.25})`);x.fillStyle=g;x.fillRect(0,0,W,H);x.globalCompositeOperation='source-over'}
  },p.fade)})});
