// A monitor's picture, drawn at twice its size for crispness. Place it under the cockpit
// over the screen's hole, 8 px larger on every side so the cockpit's sway never shows an
// edge. MODE picks the picture. Each powers on like a CRT when it's shown.
const cv=document.getElementById('c'),x=cv.getContext('2d'),SW=cv.width,SH=cv.height,P=16; // P: the bleed, in canvas pixels
const A=`rgba(${AMBER},`,C=`rgba(${CYAN},`,R='rgba(255,80,70,';
const FONT='"JetBrains Mono",Consolas,"DejaVu Sans Mono",monospace';
const IX=P+18,IY=P+14,IW=SW-2*P-36,IH=SH-2*P-28;  // the inner area
function txt(t,px,py,size=18,col=A+'.9)',al='left',wt=600){x.font=`${wt} ${size}px ${FONT}`;x.textAlign=al;x.fillStyle=col;x.fillText(t,px,py)}
function header(t,right){txt(t,IX,IY+16,17,A+'.95)');if(right)txt(right,IX+IW,IY+16,17,A+'.6)','right');x.fillStyle=A+'.25)';x.fillRect(IX,IY+26,IW,1.5)}
const hist={};function series(k,s,v,n=120){const h=hist[k]||(hist[k]=[]);const q=Math.floor(s*15);if(h.q!==q){h.q=q;h.push(v);if(h.length>n)h.shift()}return h}
const MODES={
 radar(s){header('LONG RANGE SCAN','RNG 40 KM');const cx=IX+IW*.33,cy=IY+26+(IH-26)/2+4,r=(IH-34)/2;
  x.strokeStyle=A+'.28)';x.lineWidth=1.5;for(const k of [1,.66,.33]){x.beginPath();x.arc(cx,cy,r*k,0,7);x.stroke()}
  x.beginPath();x.moveTo(cx-r,cy);x.lineTo(cx+r,cy);x.moveTo(cx,cy-r);x.lineTo(cx,cy+r);x.stroke();
  const ang=(s*Math.PI*2/4)%(Math.PI*2);
  for(let i=0;i<40;i++){const a0=ang-i*.03;x.strokeStyle=A+(.5*(1-i/40))+')';x.lineWidth=3;x.beginPath();x.moveTo(cx,cy);x.lineTo(cx+Math.cos(a0)*r,cy+Math.sin(a0)*r);x.stroke()}
  const C2=[[.3,.6,1],[2.1,.82,0],[3.9,.45,0],[4.6,.7,1],[5.6,.28,0]];
  for(const [ca,cr,hostile] of C2){const a=ca+.05*Math.sin(s*.2+ca),d=((ang-a)%(Math.PI*2)+Math.PI*2)%(Math.PI*2),f=Math.exp(-d*1.1);
   const px=cx+Math.cos(a)*r*cr,py=cy+Math.sin(a)*r*cr;x.fillStyle=(hostile?R:C)+(.25+.75*f)+')';x.beginPath();x.arc(px,py,hostile?6:4.5,0,7);x.fill()}
  const lx=cx+r+28;txt('CONTACTS',lx,cy-r+28,15,A+'.6)');
  [['FRIENDLY','3',C+'.9)'],['UNKNOWN','1',A+'.9)'],['HOSTILE','2',R+'.95)']].forEach(([k,v,c],i)=>{txt(k,lx,cy-r+58+i*30,16,c);txt(v,IX+IW,cy-r+58+i*30,16,c,'right')});
  txt('SWEEP '+String(Math.floor(ang*180/Math.PI)).padStart(3,'0')+'°',lx,cy+r-6,15,A+'.6)')},
 telemetry(s){header('ENGINEERING','REACTOR 2');const a=audio(s);
  const rows=[['REACTOR',.72+.06*Math.sin(s*.7)+.03*vnoise(s*3),C],['THRUST',.55+.25*Math.sin(s*.23)+.05*a.bass,A],['HULL TEMP',.4+.08*Math.sin(s*.11)+.02*vnoise(s*2),A]];
  const gw=IW*.62,rh=(IH-40)/3;
  rows.forEach(([k,v,c],i)=>{const y0=IY+40+i*rh,h=series(k,s,v);txt(k,IX,y0+16,14,A+'.6)');txt((v*100).toFixed(1)+'%',IX+gw,y0+16,14,c+'.95)','right');
   x.strokeStyle=c+'.9)';x.lineWidth=2;x.beginPath();h.forEach((u,j)=>{const px=IX+gw*j/119,py=y0+rh-8-(rh-30)*u;j?x.lineTo(px,py):x.moveTo(px,py)});x.stroke();
   x.fillStyle=c+'.08)';x.lineTo(IX+gw*(h.length-1)/119,y0+rh-8);x.lineTo(IX,y0+rh-8);x.fill()});
  const bx=IX+gw+30,bw=IW-gw-30;txt('POWER BUS',bx,IY+56,14,A+'.6)');
  for(let i=0;i<6;i++){const v=cl(.45+.4*Math.sin(s*.9+i*1.3)*.5+.25*a.bands[i*5]);const y=IY+72+i*((IH-80)/6);
   x.fillStyle=A+'.15)';x.fillRect(bx,y,bw,10);x.fillStyle=(i==4&&v>.8?R:A)+'.85)';x.fillRect(bx,y,bw*v,10)}},
 spectrum(s){const a=audio(s);header('AUDIO · BITWIG BUS',`${BPM} BPM`);
  const n=32,gw=IW/n,base=IY+IH-34,hh=IH-80;
  for(let i=0;i<n;i++){const v=a.bands[i],h=hh*v,segs=Math.floor(h/7);
   for(let k=0;k<segs;k++){const f=k*7/hh;x.fillStyle=(f>.82?R:f>.6?A:C)+(.85)+')';x.fillRect(IX+i*gw+2,base-k*7-5,gw-4,5)}}
  // the waveform under it
  x.strokeStyle=C+'.7)';x.lineWidth=1.5;x.beginPath();for(let i=0;i<=200;i++){const u=i/200,ph=s*7+u*20;const v=Math.sin(ph*3.1)*.5*a.bass+Math.sin(ph*11.7)*.25*a.snare+(hash(Math.floor(s*30)*999+i)-.5)*.4*a.hat;
   const px=IX+IW*u,py=IY+IH-14+v*12;i?x.lineTo(px,py):x.moveTo(px,py)}x.stroke();
  txt(a.brk?'BREAKDOWN':'BAR '+(Math.floor(a.beat/4)%16+1)+'/16',IX+IW,IY+44,14,A+'.6)','right')},
 nav(s){header('NAVIGATION','ROUTE 7');const cx=IX+IW*.38,cy=IY+26+(IH-26)/2;
  x.strokeStyle=A+'.12)';x.lineWidth=1;for(let g=-6;g<=6;g++){x.beginPath();x.moveTo(cx+g*40,IY+30);x.lineTo(cx+g*40,IY+IH);x.stroke()}
  for(let g=-3;g<=3;g++){x.beginPath();x.moveTo(IX,cy+g*40);x.lineTo(IX+IW*.76,cy+g*40);x.stroke()}
  for(let i=0;i<70;i++){const px=IX+hash(i)*IW*.76,py=IY+30+hash(i+99)*(IH-30);x.fillStyle=`rgba(255,240,220,${.2+.5*hash(i+7)})`;x.fillRect(px,py,2,2)}
  const pts=[[-170,60],[-60,10],[40,-30],[150,-70]];
  x.setLineDash([8,8]);x.lineDashOffset=-s*20;x.strokeStyle=C+'.8)';x.lineWidth=2;x.beginPath();pts.forEach(([px,py],i)=>i?x.lineTo(cx+px,cy+py):x.moveTo(cx+px,cy+py));x.stroke();x.setLineDash([]);
  const names=['SOL GATE','DEEP SPACE','KESTREL NEB.','TYR VII'];
  pts.forEach(([px,py],i)=>{x.strokeStyle=C+'.9)';x.lineWidth=2;x.beginPath();x.arc(cx+px,cy+py,7,0,7);x.stroke();txt(names[i],cx+px+12,cy+py-10,13,C+'.85)')});
  const u=(s*.02)%1,seg=Math.min(2,Math.floor(u*3)),f=u*3-seg,[ax,ay]=pts[seg],[bx,by]=pts[seg+1];
  const sx=cx+ax+(bx-ax)*f,sy=cy+ay+(by-ay)*f;x.fillStyle=A+'1)';x.beginPath();x.moveTo(sx+10,sy);x.lineTo(sx-7,sy-6);x.lineTo(sx-7,sy+6);x.fill();
  const rx=IX+IW*.8;txt('ETA',rx,IY+60,14,A+'.6)');txt(`${String(59-Math.floor(s/60)%60).padStart(2,'0')}:${String(59-Math.floor(s)%60).padStart(2,'0')}`,rx,IY+86,22,A+'.95)');
  txt('WARP',rx,IY+124,14,A+'.6)');txt('READY',rx,IY+150,20,C+'.95)')},
 shields(s){header('DEFENSE','SHIELDS UP');const cx=IX+IW*.33,cy=IY+26+(IH-26)/2+4;const a=audio(s);
  x.save();x.translate(cx,cy);x.strokeStyle=A+'.9)';x.lineWidth=2;x.beginPath();
  x.moveTo(0,-62);x.lineTo(18,-20);x.lineTo(58,22);x.lineTo(58,36);x.lineTo(16,28);x.lineTo(10,52);x.lineTo(-10,52);x.lineTo(-16,28);x.lineTo(-58,36);x.lineTo(-58,22);x.lineTo(-18,-20);x.closePath();x.stroke();
  const q=[.96,.88,.64,.91];for(let i=0;i<4;i++){const v=q[i],pulse=.5+.5*Math.sin(s*3+i);x.strokeStyle=(v<.7?A:C)+(.35+.45*pulse)+')';x.lineWidth=5;x.beginPath();x.arc(0,0,92,-Math.PI/2+i*Math.PI/2-.62,-Math.PI/2+i*Math.PI/2+.62);x.stroke()}
  x.restore();const lx=IX+IW*.68;['FORE','STARBOARD','AFT','PORT'].forEach((k,i)=>{txt(k,lx,IY+62+i*34,14,A+'.6)');txt(Math.round(q[i]*100)+'%',IX+IW,IY+62+i*34,16,(q[i]<.7?A:C)+'.95)','right')})},
 camhud(s){ // a transparent frame over a live camera
  x.clearRect(0,0,SW,SH);const L=28;x.strokeStyle=A+'.9)';x.lineWidth=3;
  for(const [px,py,dx,dy] of [[IX,IY,1,1],[IX+IW,IY,-1,1],[IX,IY+IH,1,-1],[IX+IW,IY+IH,-1,-1]]){x.beginPath();x.moveTo(px+dx*L,py);x.lineTo(px,py);x.lineTo(px,py+dy*L);x.stroke()}
  txt(LABEL,IX+12,IY+28,17,A+'.95)');if(Math.floor(s*1.2)%2==0){x.fillStyle=R+'.95)';x.beginPath();x.arc(IX+IW-62,IY+22,6,0,7);x.fill()}txt('REC',IX+IW-12,IY+28,15,A+'.9)','right');
  const tc=new Date(s*1000);txt(tc.toISOString().substr(11,8),IX+IW-12,IY+IH-12,14,A+'.7)','right');
  const sy=IY+((s*90)%IH);const g=x.createLinearGradient(0,sy-20,0,sy+20);g.addColorStop(0,'rgba(255,255,255,0)');g.addColorStop(.5,`rgba(255,255,255,${.05*Math.min(1,SPILL)})`);g.addColorStop(1,'rgba(255,255,255,0)');x.fillStyle=g;x.fillRect(P,sy-20,SW-2*P,40)}
};
let t0=null;
run((s,t)=>{x.setTransform(1,0,0,1,0,0);
 if(MODE!=='camhud'){x.fillStyle='#050709';x.fillRect(0,0,SW,SH);const g=x.createRadialGradient(SW/2,SH/2,0,SW/2,SH/2,SW*.6);g.addColorStop(0,'rgba(40,30,15,.25)');g.addColorStop(1,'rgba(0,0,0,0)');x.fillStyle=g;x.fillRect(0,0,SW,SH)}
 // power on: a bright line opens into the picture
 const on=ss(0,450,t);x.save();
 if(on<1){x.beginPath();const hh=Math.max(2,SH*on*on);x.rect(0,SH/2-hh/2,SW,hh);x.clip()}
 x.shadowColor=A+'.6)';x.shadowBlur=6;MODES[MODE](s);x.shadowBlur=0;x.restore();
 if(on<1){x.fillStyle=`rgba(255,240,220,${(1-on)*.8})`;x.fillRect(0,SH/2-2,SW,4)}
 if(MODE!=='camhud'){for(let y=0;y<SH;y+=4){x.fillStyle='rgba(0,0,0,.22)';x.fillRect(0,y,SW,2)}}});
