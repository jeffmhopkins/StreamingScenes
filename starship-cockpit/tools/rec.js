// Records demo.html: the layers stacked as the JStream scene stacks them, switched on a
// timeline the way hotkeys switch the variants. Shown layers with restart_on_show reload.
const {chromium}=require('playwright');
const FPS=30,END=+process.env.END||55500,START=+process.env.START||0,OUT=process.env.OUT||'f';
const SRC={m1radar:'screen-radar',m1nav:'screen-nav',m3spec:'screen-spectrum',m3shield:'screen-shields',win_deep:'warp-in-deep',wout_nebula:'warp-out-nebula',
 win_nebula:'warp-in-nebula',wout_planet:'warp-out-planet',attack:'attack',hit:'hit',tx:'transmission',bitwig:'bitwig'};
const PERSIST={sky_deep:1,sky_nebula:1,sky_planet:1};
// [time ms, key, label, layers to show (the rest of the switchable ones hide)]
const EV=[
 [0,'F1','Cruise: deep space',['sky_deep']],
 [3000,'F6','Monitors: radar and audio',['sky_deep','m1radar','m3spec']],
 [6500,'F2','Warp to the Kestrel Nebula',['sky_deep','m1radar','m3spec','win_deep']],
 [11000,'F3','Arrive: Kestrel Nebula',['sky_nebula','m1radar','m3spec','wout_nebula']],
 [15000,'F7','Monitors: navigation',['sky_nebula','m1nav','m3spec','wout_nebula']],
 [17000,'F8','Weapons: destroy target',['sky_nebula','m1radar','m3spec','wout_nebula','attack']],
 [25000,'F4','Taking fire',['sky_nebula','m1radar','m3shield','wout_nebula','hit']],
 [30500,'F2','Warp to Tyr VII',['sky_nebula','m1nav','m3shield','wout_nebula','win_nebula']],
 [35000,'F3','Arrive: Tyr VII',['sky_planet','m1nav','m3spec','wout_planet']],
 [39000,'F5','Incoming transmission',['sky_planet','m1nav','m3spec','wout_planet','tx']],
 [47000,'F9','Bitwig hologram',['sky_planet','m1nav','m3spec','wout_planet','bitwig']],
];
const ALL=[...Object.keys(SRC),...Object.keys(PERSIST)];
(async()=>{const b=await chromium.launch();const ctx=await b.newContext({viewport:{width:1920,height:1080}});
await ctx.addInitScript({path:__dirname+'/vt.js'});const p=await ctx.newPage();
p.on('pageerror',e=>console.log('ERR',e.message));p.on('console',m=>{if(m.type()==='error')console.log('CONSOLE',m.text())});
await p.goto('http://127.0.0.1:8767/demo.html');await p.waitForLoadState('load');
let vis=[],knock={from:0,to:0,at:-1e9},fades={caller:{v:0,at:-1e9,on:0,delay:1700,dur:400,max:.75},daw:{v:0,at:-1e9,on:0,delay:1100,dur:500,max:.85}};
const spring=u=>u>=1?1:1-Math.exp(-6*u)*Math.cos(3*Math.PI*u);
const jolts=[];
for(let i=0,t=0;t<=END;i++,t=i*1000/FPS){
  for(const [at,k,label,next] of EV) if(t>=at&&t-1000/FPS<at){
    for(const id of ALL){const on=next.includes(id),was=vis.includes(id)||(at===0&&id==='sky_deep'&&false);
      if(on&&!was&&SRC[id]){await p.evaluate(([id,s])=>{const f=document.getElementById(id);f.classList.remove('hide');f.src=s+'.html?'+Math.random()},[id,SRC[id]]);
        await p.waitForFunction(id=>{const w=document.getElementById(id).contentWindow;return w&&w.location.href.includes('.html')&&w.__step&&w.document.readyState==='complete'},id,{polling:100})}
      else if(on) await p.evaluate(id=>document.getElementById(id).classList.remove('hide'),id);
      else if(!on&&(was||PERSIST[id])) await p.evaluate(id=>document.getElementById(id).classList.add('hide'),id)}
    vis=next;
    if(k==='F4')jolts.push(t);if(k==='F8')jolts.push(t+3300);
    fades.caller.on=next.includes('tx');fades.caller.at=t;fades.daw.on=next.includes('bitwig');fades.daw.at=t;
    await p.evaluate(([k,l,t])=>{const e=document.getElementById('key');e.dataset.at=t;e.innerHTML=`<b>${k}</b><span>${l}</span>`},[k,label,t]);
  }
  let kv=0;for(const j of jolts){const u=(t-j)/700;if(u>=0&&u<2)kv+=Math.exp(-4*u)*Math.sin(3*Math.PI*u)}
  const fv={};for(const [id,f] of Object.entries(fades)){const target=f.on?f.max:0;const u=f.on?cl01((t-f.at-f.delay)/f.dur):cl01((t-f.at)/250);
    if(f.on){f.v=f.max*u}else{f.v=Math.min(f.v,f.max*(1-u))}fv[id]=f.v}
  await p.evaluate(([kv,fv,t])=>{document.getElementById('knock').style.transform=`translate(${-12*kv}px,${8*kv}px) scale(${1+.02*Math.abs(kv)})`;
    for(const [id,v] of Object.entries(fv))document.getElementById(id).style.opacity=v;const e=document.getElementById('key'),a=+(e.dataset.at||-1e9),d=t-a;
    e.style.opacity=d<0?0:d<150?d/150:d<1800?1:Math.max(0,1-(d-1800)/300)},[kv,fv,t]);
  for(const f of p.frames()) await f.evaluate(t=>window.__step&&__step(t),t).catch(()=>{});
  if(t>=START&&i%(+process.env.EVERY||1)==0)await p.screenshot({path:`${OUT}/${String(i).padStart(4,"0")}.jpg`,type:"jpeg",quality:92});
  if(i%150==0)console.log('frame',i);
}
await b.close()})();
function cl01(v){return Math.max(0,Math.min(1,v))}
