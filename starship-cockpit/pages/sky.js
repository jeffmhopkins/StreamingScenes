// A location's sky outside the windows: its plate drifting with the ship's attitude and
// near stars passing for depth, masked to the windows, with its reflection on the dash.
const O=new Outside(document.getElementById('c'),{reflect:1.2,reflectSky:true});
Promise.all([loadImg(PLATE),O.load()]).then(([plate])=>run(s=>O.render(s,x=>{
 x.fillStyle='#000';x.fillRect(0,0,W,H);drawPlate(x,plate,s);drawNear(x,s,NEAR_STARS)})));
