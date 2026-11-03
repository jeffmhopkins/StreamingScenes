// A still of demo.html: shows the named layers and steps them to `at` ms after showing.
const {chromium}=require('playwright');
const [,,out,at,...ids]=process.argv;
const SRC={m1radar:'screen-radar',m3spec:'screen-spectrum',win_deep:'warp-in-deep',wout_nebula:'warp-out-nebula',attack:'attack',hit:'hit',tx:'transmission',bitwig:'bitwig',wout_planet:'warp-out-planet',wout_n:'warp-out-nebula'};
(async()=>{const b=await chromium.launch();const p=await (await b.newContext({viewport:{width:1920,height:1080}})).newPage();
await p.addInitScript({path:__dirname+'/vt.js'});p.on('pageerror',e=>console.log('ERR',e.message));
await p.goto('http://127.0.0.1:8767/demo.html');await p.waitForLoadState('load');
for(const id of ids){if(id.startsWith('sky_')){await p.evaluate(id=>{for(const s of ['sky_deep','sky_nebula','sky_planet'])document.getElementById(s).classList.toggle('hide',s!==id)},id);continue}
 if(id==='caller'||id==='daw'){await p.evaluate(id=>document.getElementById(id).style.opacity=.8,id);continue}
 await p.evaluate(([id,s])=>{const f=document.getElementById(id);f.classList.remove('hide');f.src=s+'.html'},[id,SRC[id]]);
 await p.waitForFunction(id=>{const w=document.getElementById(id).contentWindow;return w&&w.__step&&w.document.readyState==='complete'},id,{polling:100})}
await p.waitForTimeout(500);
const G=100000;for(let t=0;t<=+at;t+=33.3){for(const f of p.frames())await f.evaluate(t=>window.__step&&__step(t),G+t).catch(()=>{});await p.evaluate(()=>window.__refl&&__refl())}
await p.screenshot({path:out,type:'jpeg',quality:90});await b.close()})();
