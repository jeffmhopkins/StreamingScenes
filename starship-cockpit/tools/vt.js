// Virtual clock for frame-exact capture. rAF, performance.now and CSS animations follow
// __step(g). g is the global time in ms. Date.now returns the global clock, so every page
// shares it as the wall clock would. performance.now starts at 0 when the page first steps.
(()=>{let now=0,g0=null,gl=0,q=[],id=0;const st=new Map();
performance.now=()=>now;Date.now=()=>1.7e12+gl;
window.requestAnimationFrame=cb=>{q.push([++id,cb]);return id};
window.cancelAnimationFrame=i=>{q=q.filter(e=>e[0]!==i)};
window.__step=g=>{if(g0===null)g0=g;gl=g;now=g-g0;const cur=q;q=[];for(const[,cb]of cur){try{cb(now)}catch(e){console.error(e)}}
 for(const a of document.getAnimations()){if(!st.has(a))st.set(a,now);a.pause();a.currentTime=now-st.get(a)}};})();
