// The cockpit itself: the keyed plate, moving with the pilot's head, and its amber
// indicator lights pulsing with the music (left console with the bass, centre with the
// snare and pads, right with the hats, the ceiling strip with the overall level).
const x=document.getElementById('c').getContext('2d');
Promise.all([loadImg('cockpit.png'),loadImg('lights.png')]).then(([ck,li])=>{
 const bloom=document.createElement('canvas');bloom.width=W;bloom.height=H;const b=bloom.getContext('2d');b.filter='blur(10px)';b.drawImage(li,0,0);b.filter='blur(3px)';b.drawImage(li,0,0);
 const ZONES=[[0,140,700,940,'bass'],[700,140,520,940,'mid'],[1220,140,700,940,'hat'],[0,0,W,140,'level']];
 run(s=>{const a=audio(s);a.mid=cl(.6*a.snare+.5*a.pad);a.hat=cl(a.hat*1.2);
  x.setTransform(1,0,0,1,0,0);x.clearRect(0,0,W,H);x.save();applySway(x,s);
  x.drawImage(ck,0,0);
  x.globalCompositeOperation='lighter';
  for(const [zx,zy,zw,zh,k] of ZONES){const v=a[k];x.save();x.beginPath();x.rect(zx,zy,zw,zh);x.clip();
   x.globalAlpha=.12+.55*v;x.drawImage(li,0,0);x.globalAlpha=.25*v;x.drawImage(bloom,0,0);x.restore()}
  x.restore()})});
