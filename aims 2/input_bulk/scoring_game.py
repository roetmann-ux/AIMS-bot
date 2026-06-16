"""The 'scoring' loading screen — a serious, proprietary progress view with optional motive games.

The real work (the proprietary implicit-motive engine) is shown honestly as live progress. Below
that, three OPTIONAL mini-games — Achievement, Power, Affiliation — are hidden by default; opening
one shows a short teaching blurb about that motive plus a themed game. The games have zero effect on
the report and say so. Live mode polls /bulk/{id}/progress; demo mode (/play) ramps client-side.
"""
from __future__ import annotations

GAME = """
<style>
.scene{max-width:600px;margin:0 auto;font-family:var(--font-body)}
.scene h2.title{font-family:var(--font-display);color:var(--ink-charcoal);margin:0 0 2px}
.scene .sub{color:var(--ink-gray);margin:0 0 14px;font-size:14px;line-height:1.55}
.progress-pro{margin:0 0 16px}
.progress-pro .plabel{font-family:var(--font-display);font-size:13px;color:var(--ink-charcoal);font-weight:600;margin-bottom:6px}
.progress-pro .plabel b{color:var(--maroon)}
.progress-pro .bar{height:11px;background:var(--band-gray);border-radius:6px;overflow:hidden}
.progress-pro .bar>i{display:block;height:100%;width:0;background:var(--azure);transition:width .45s ease}
.optnote{background:var(--azure-tint);border:1px solid #cfe6f2;border-left:4px solid var(--azure-deep);
  border-radius:10px;padding:14px 18px;font-size:15px;line-height:1.55;color:var(--ink-charcoal);margin:0 0 16px}
.optnote b{color:var(--maroon-alt)}
.gamepick{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-bottom:6px}
.gamepick .gpl{font-family:var(--font-display);font-size:11px;font-weight:600;text-transform:uppercase;
  letter-spacing:.1em;color:#9a9a9a;margin-right:4px}
.gbtn{font-family:var(--font-display);font-weight:600;font-size:13px;background:#eef0f2;color:var(--ink-charcoal);
  border:1px solid var(--rule);border-radius:20px;padding:7px 14px;cursor:pointer}
.gbtn:hover{background:#e4e7ea}
.gbtn.on{background:var(--maroon);color:#fff;border-color:var(--maroon)}
#gamewrap{margin-top:10px}
.gdesc{background:#fff;border:1px solid var(--rule);border-radius:10px;padding:12px 15px;font-size:14px;
  line-height:1.5;color:var(--ink-gray);margin:0 0 10px}
.gdesc b{color:var(--ink-charcoal)}
.gdesc .gtip{display:block;margin-top:5px;font-size:12.5px;color:var(--azure-deep)}
.gamehead{display:flex;align-items:baseline;gap:12px;margin-bottom:6px}
.gamehead .playlabel{font-family:var(--font-display);font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.1em;color:#9a9a9a}
.gamehead .score{font-family:var(--font-display);font-weight:800;font-size:22px;color:var(--maroon);line-height:1}
.gamehead .combo{font-size:12px;color:var(--azure-deep);font-weight:600;min-height:14px}
#game{width:100%;height:360px;background:radial-gradient(120% 100% at 50% 0%,#fcfdff,#eaf1f6);
  border:1px solid var(--rule);border-radius:12px;display:block;touch-action:none}
.overlay{position:fixed;inset:0;background:rgba(22,16,16,.62);display:flex;align-items:center;
  justify-content:center;z-index:60;padding:20px}
.panel{background:#fff;border-radius:14px;padding:28px 32px;max-width:460px;text-align:center;box-shadow:0 22px 70px rgba(0,0,0,.4)}
.panel h2{font-family:var(--font-display);color:var(--maroon);margin:0 0 8px;font-size:22px}
.panel p{color:var(--ink-gray);font-size:13.5px;line-height:1.5;margin:6px 0}
.panel .big{font-family:var(--font-display);font-weight:800;font-size:44px;color:var(--ink-charcoal);margin:8px 0 2px}
.panel a.btn{display:inline-block;background:var(--maroon);color:#fff;text-decoration:none;padding:11px 22px;
  border-radius:8px;font-family:var(--font-display);font-weight:600;margin-top:12px;font-size:14px}
.hidden{display:none}
</style>
<div class=scene>
  <h2 class=title>Scoring in progress</h2>
  <p class=sub>Our proprietary implicit-motive engine is analyzing each story across Achievement,
  Power &amp; Affiliation. This usually takes a minute or two — your report opens automatically the
  moment it's ready.</p>

  <div class=progress-pro>
    <div class=plabel>Engine progress — <b id=mp>…</b> story-motives scored</div>
    <div class=bar><i id=barfill></i></div>
  </div>

  <div class=optnote>
    <b>Optional:</b> the games below are just to pass the time and <b>have no effect on the results</b> —
    ignore them entirely and your report will be exactly the same. They're also a quick, playful way to
    get a feel for what each of the three motives is about.
  </div>

  <div class=gamepick>
    <span class=gpl>Optional games:</span>
    <button class=gbtn id=btn-achievement>🎯 Achievement game</button>
    <button class=gbtn id=btn-power>👑 Power game</button>
    <button class=gbtn id=btn-affiliation>🤝 Affiliation game</button>
  </div>

  <div id=gamewrap class=hidden>
    <p class=gdesc id=gdesc></p>
    <div class=gamehead>
      <span class=playlabel>Optional · does not affect scoring</span>
      <span class=score id=score>0</span>
      <span class=combo id=combo></span>
    </div>
    <canvas id=game></canvas>
  </div>
</div>
<div id=over class="overlay hidden"><div class=panel id=panel></div></div>
<script>
(function(){
const BID="__BID__", MODE="__MODE__", $=function(i){return document.getElementById(i);};
const cvs=$('game'), ctx=cvs.getContext('2d');
let DPR=Math.min(2,window.devicePixelRatio||1), W=600, H=360;
function fit(){ W=cvs.clientWidth||600; cvs.width=W*DPR; cvs.height=H*DPR; ctx.setTransform(DPR,0,0,DPR,0,0); }
window.addEventListener('resize',fit); fit();
function col(v){ return (getComputedStyle(document.documentElement).getPropertyValue(v)||'').trim()||'#740000'; }
function rr(x,y,w,h,r){ ctx.beginPath();ctx.moveTo(x+r,y);ctx.arcTo(x+w,y,x+w,y+h,r);ctx.arcTo(x+w,y+h,x,y+h,r);ctx.arcTo(x,y+h,x,y,r);ctx.arcTo(x,y,x+w,y,r);ctx.closePath(); }
function dist(ax,ay,bx,by){ return Math.hypot(ax-bx,ay-by); }

let running=true, frac=0, total=(MODE==='demo'?18:0), t0=performance.now(), last=t0, active=null, played=false;
function el(){ return performance.now()-t0; }

// ---- input routed to the active game ----
cvs.addEventListener('pointermove',function(e){ const r=cvs.getBoundingClientRect(); const x=e.clientX-r.left,y=e.clientY-r.top; if(active&&active.point) active.point(x,y); });
cvs.addEventListener('pointerdown',function(e){ const r=cvs.getBoundingClientRect(); const x=e.clientX-r.left,y=e.clientY-r.top; if(active&&active.tap) active.tap(x,y); });
cvs.addEventListener('touchmove',function(e){ e.preventDefault(); },{passive:false});

// =================================================================== GAMES
const ACH={
  cursor:'none',
  desc:"<b>Achievement</b> — the drive to meet a standard of excellence: setting goals, improving, and doing things <i>better</i>. People high in it pursue mastery and measurable progress."+
       "<span class=gtip>Catch the goals 🎯 and improvements ⭐ — dodge distractions 🚫.</span>",
  reset(){ this.toks=[];this.pops=[];this.score=0;this.combo='catch 🎯 / ⭐, dodge 🚫';this.bx=W/2;this.btx=W/2;this.sp=0;this.t=0; },
  point(x){ this.btx=x; },
  _spawn(){ const r=Math.random(); let e,p,bad=false; if(r<0.18){e='🚫';p=-5;bad=true;} else if(r<0.5){e='⭐';p=2;} else {e='🎯';p=3;}
    this.toks.push({x:26+Math.random()*(W-52),y:-22,vy:(95+frac*235)*(0.9+Math.random()*0.3),e:e,p:p,bad:bad}); },
  step(dt){ this.t+=dt; const bw=84; this.btx=Math.max(bw/2,Math.min(W-bw/2,this.btx)); this.bx+=(this.btx-this.bx)*Math.min(1,dt*14);
    this.sp-=dt*1000; if(this.sp<=0){ this._spawn(); this.sp=Math.max(260,820-frac*430-Math.min(this.t*7,190)); }
    const cy=H-26;
    for(const k of this.toks){ if(k.gone)continue; k.y+=k.vy*dt;
      if(k.y>=cy-9&&k.y<=cy+16&&Math.abs(k.x-this.bx)<bw/2+10){ k.gone=true; if(k.bad){this.score=Math.max(0,this.score-5);this.pops.push({x:k.x,y:k.y,t:'−5',c:col('--maroon'),a:1});} else {this.score+=k.p;this.pops.push({x:k.x,y:k.y,t:'+'+k.p,c:col('--azure-deep'),a:1});} }
      else if(k.y>H+26){ k.gone=true; } }
    this.toks=this.toks.filter(k=>!k.gone);
    for(const p of this.pops){p.y-=27*dt;p.a-=dt*1.25;} this.pops=this.pops.filter(p=>p.a>0); },
  draw(){ ctx.textAlign='center';ctx.textBaseline='middle';ctx.font='27px serif';
    for(const k of this.toks) ctx.fillText(k.e,k.x,k.y);
    const by=H-26,bw=84; ctx.fillStyle=col('--maroon'); rr(this.bx-bw/2,by,bw,15,7); ctx.fill();
    ctx.strokeStyle=col('--azure');ctx.lineWidth=3;ctx.beginPath();ctx.moveTo(this.bx-bw/2,by);ctx.lineTo(this.bx+bw/2,by);ctx.stroke();
    ctx.fillStyle='#fff';ctx.font='700 9px sans-serif';ctx.fillText('YOU',this.bx,by+8);
    ctx.font='700 14px sans-serif'; for(const p of this.pops){ctx.globalAlpha=Math.max(0,p.a);ctx.fillStyle=p.c;ctx.fillText(p.t,p.x,p.y);} ctx.globalAlpha=1; }
};
const POW={
  cursor:'pointer',
  desc:"<b>Power / Influence</b> — the drive to have impact on others: leading, persuading, and shaping what people do. People high in it want to move groups and outcomes."+
       "<span class=gtip>Tap people to win them over — your supporters then sway others nearby.</span>",
  reset(){ this.pe=[];this.pops=[];this.score=0;this.combo='tap to win people over';this.t=0; for(let i=0;i<7;i++)this._add(); },
  _add(){ this.pe.push({x:24+Math.random()*(W-48),y:24+Math.random()*(H-48),vx:(Math.random()*2-1)*42,vy:(Math.random()*2-1)*42,mine:false,pulse:0}); },
  _convert(p){ p.mine=true;p.pulse=1;this.score++;this.pops.push({x:p.x,y:p.y,t:'+1',c:col('--azure-deep'),a:1}); },
  tap(x,y){ let best=null,bd=36*36; for(const p of this.pe){ if(p.mine)continue; const d=(p.x-x)*(p.x-x)+(p.y-y)*(p.y-y); if(d<bd){bd=d;best=p;} } if(best)this._convert(best); },
  step(dt){ this.t+=dt;
    for(const p of this.pe){ p.x+=p.vx*dt;p.y+=p.vy*dt;
      if(p.x<14||p.x>W-14){p.vx*=-1;p.x=Math.max(14,Math.min(W-14,p.x));}
      if(p.y<14||p.y>H-14){p.vy*=-1;p.y=Math.max(14,Math.min(H-14,p.y));}
      if(p.pulse>0)p.pulse-=dt*1.6; }
    for(const p of this.pe){ if(!p.mine)continue; if(Math.random()<dt*0.4){ let best=null,bd=72*72; for(const q of this.pe){ if(q.mine)continue; const d=(q.x-p.x)*(q.x-p.x)+(q.y-p.y)*(q.y-p.y); if(d<bd){bd=d;best=q;} } if(best)this._convert(best); } }
    if(this.pe.length<7+Math.floor(frac*10) && Math.random()<dt*1.1) this._add();
    const m=this.pe.filter(p=>p.mine).length; this.combo='won over '+m+' of '+this.pe.length;
    for(const p of this.pops){p.y-=24*dt;p.a-=dt*1.2;} this.pops=this.pops.filter(p=>p.a>0); },
  draw(){ for(const p of this.pe){ if(p.pulse>0){ ctx.globalAlpha=p.pulse*0.4;ctx.fillStyle=col('--azure');ctx.beginPath();ctx.arc(p.x,p.y,11+(1-p.pulse)*18,0,7);ctx.fill();ctx.globalAlpha=1; }
      ctx.fillStyle=p.mine?col('--maroon'):'#c7cbd1'; ctx.beginPath();ctx.arc(p.x,p.y,10,0,7);ctx.fill(); }
    ctx.font='700 14px sans-serif'; for(const p of this.pops){ctx.globalAlpha=Math.max(0,p.a);ctx.fillStyle=p.c;ctx.fillText(p.t,p.x,p.y);} ctx.globalAlpha=1; }
};
const AFF={
  cursor:'none',
  desc:"<b>Affiliation</b> — the drive for warm, friendly relationships: belonging, connecting, and being liked. People high in it value closeness and keeping bonds intact."+
       "<span class=gtip>Move near friends to bond with them — keep as many connected as you can.</span>",
  reset(){ this.fr=[];this.score=0;this.combo='move near friends to connect';this.t=0;this.x=W/2;this.y=H/2;this.tx=W/2;this.ty=H/2;this.acc=0; for(let i=0;i<6;i++)this._add(); },
  _add(){ this.fr.push({x:24+Math.random()*(W-48),y:24+Math.random()*(H-48),vx:(Math.random()*2-1)*32,vy:(Math.random()*2-1)*32,linked:false}); },
  point(x,y){ this.tx=x;this.ty=y; },
  step(dt){ this.t+=dt; this.x+=(this.tx-this.x)*Math.min(1,dt*12); this.y+=(this.ty-this.y)*Math.min(1,dt*12); let linked=0;
    for(const f of this.fr){ f.x+=f.vx*dt;f.y+=f.vy*dt;
      if(f.x<14||f.x>W-14){f.vx*=-1;f.x=Math.max(14,Math.min(W-14,f.x));}
      if(f.y<14||f.y>H-14){f.vy*=-1;f.y=Math.max(14,Math.min(H-14,f.y));}
      f.linked = dist(f.x,f.y,this.x,this.y)<72;
      if(f.linked){ linked++; f.vx+=(this.x-f.x)*dt*0.8; f.vy+=(this.y-f.y)*dt*0.8;
        const sp=Math.hypot(f.vx,f.vy); if(sp>90){ f.vx=f.vx/sp*90; f.vy=f.vy/sp*90; } } }
    this.acc+=linked*dt*2; if(this.acc>=1){ const a=Math.floor(this.acc); this.score+=a; this.acc-=a; }
    if(this.fr.length<6+Math.floor(frac*8) && Math.random()<dt*0.7) this._add();
    this.combo = linked? ('connected with '+linked+' friend'+(linked>1?'s':'')) : 'move near friends to connect'; },
  draw(){ ctx.strokeStyle=col('--azure');ctx.lineWidth=2;
    for(const f of this.fr){ if(f.linked){ ctx.globalAlpha=0.5;ctx.beginPath();ctx.moveTo(this.x,this.y);ctx.lineTo(f.x,f.y);ctx.stroke();ctx.globalAlpha=1; } }
    ctx.textAlign='center';ctx.textBaseline='middle';ctx.font='22px serif';
    for(const f of this.fr) ctx.fillText(f.linked?'😊':'🙂',f.x,f.y);
    ctx.fillStyle=col('--maroon');ctx.beginPath();ctx.arc(this.x,this.y,13,0,7);ctx.fill();
    ctx.fillStyle='#fff';ctx.font='700 9px sans-serif';ctx.fillText('YOU',this.x,this.y); }
};
const GAMES={achievement:ACH, power:POW, affiliation:AFF};

// =================================================================== harness
function loop(now){ const dt=Math.min(50,now-last)/1000; last=now; ctx.clearRect(0,0,W,H);
  if(active){ active.step(dt); active.draw(); $('score').textContent=active.score; $('combo').textContent=active.combo||''; }
  if(running) requestAnimationFrame(loop); }
requestAnimationFrame(loop);

function select(key){ const g=GAMES[key];
  if(active===g){ hide(); return; }
  active=g; played=true; g.reset();
  $('gamewrap').classList.remove('hidden'); $('gdesc').innerHTML=g.desc; cvs.style.cursor=g.cursor;
  ['achievement','power','affiliation'].forEach(k=> $('btn-'+k).classList.toggle('on', GAMES[k]===g));
  fit(); }
function hide(){ active=null; $('gamewrap').classList.add('hidden'); ['achievement','power','affiliation'].forEach(k=>$('btn-'+k).classList.remove('on')); }
$('btn-achievement').onclick=function(){select('achievement');};
$('btn-power').onclick=function(){select('power');};
$('btn-affiliation').onclick=function(){select('affiliation');};

// =================================================================== progress + finish
function setProg(done,tot){ if(tot)total=tot; frac= tot? Math.min(1,done/tot):frac; $('mp').textContent= done+' / '+(tot||'…'); $('barfill').style.width=Math.round(frac*100)+'%'; }
function over(kind){ if(!running) return; running=false;
  const tot=($('mp').textContent.split('/').pop()||'').trim(); const score=active?active.score:0; let html;
  if(kind==='error'){ html=`<h2>The model hit a snag</h2><p>Scoring stopped before finishing.</p><a class=btn href="/bulk/${BID}">See what happened →</a>`; }
  else if(!played){ html=`<h2>Scoring complete</h2><p>Your report has been generated by the engine across all ${tot} story-motives.</p><a class=btn href="${MODE==='demo'?'/evaluate':'/bulk/'+BID}">Open your report →</a>`; }
  else if(MODE==='demo'){ html=`<h2>GAME OVER</h2><p>The (pretend) engine finished first. It always does — it doesn't chase falling emoji.</p><div class=big>${score}</div><p>your score · the report was produced entirely by the engine.</p><a class=btn href="/evaluate">Score a real candidate →</a>`; }
  else { html=`<h2>GAME OVER — the engine won</h2><p>It scored all ${tot} story-motives before you cracked the leaderboard. Your game score changed nothing — the report was produced entirely by the engine, exactly as promised.</p><div class=big>${score}</div><a class=btn href="/bulk/${BID}">Claim your report →</a>`; }
  $('panel').innerHTML=html; $('over').classList.remove('hidden'); }
function poll(){ if(MODE==='demo'){ const d=Math.min(total,Math.round(el()/26000*total)); setProg(d,total); if(el()>=26000) return over('done'); setTimeout(poll,300); return; }
  fetch('/bulk/'+BID+'/progress').then(function(r){return r.json();}).then(function(j){ const p=j.progress||{done:0,total:1}; setProg(p.done,p.total);
    if(j.status==='done') return over('done'); if(j.status==='error') return over('error'); setTimeout(poll,650); }).catch(function(){ setTimeout(poll,800); }); }
poll();
})();
</script>
"""


def render_game(bid: str, mode: str = "live") -> str:
    return GAME.replace("__BID__", bid).replace("__MODE__", mode)
