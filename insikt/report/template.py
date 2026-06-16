"""The single-file HTML shell. Data is inlined as JSON; all CSS/JS is inline so
the report is fully offline (README §9 v0)."""

from __future__ import annotations

import html as _html


def render_page(title: str, data_json: str) -> str:
    # Safely embed JSON inside a <script> block. json.dumps(ensure_ascii=True)
    # escapes U+2028/U+2029 already; we only neutralize the "</script>" sequence.
    safe = data_json.replace("</", "<\\/")
    return (
        _TEMPLATE
        .replace("__INSIKT_TITLE__", _html.escape(title))
        .replace("__INSIKT_DATA__", safe)
    )


_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__INSIKT_TITLE__</title>
<style>
  :root{
    --bg:#0e1116; --panel:#161b22; --panel2:#1c2230; --line:#2a3340;
    --fg:#e6edf3; --muted:#8b98a5; --accent:#e0b341;
    --crit:#ff4d4f; --high:#ff7a45; --med:#ffc53d; --low:#73d13d; --info:#8c8c8c;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
  header{padding:16px 22px;border-bottom:1px solid var(--line);display:flex;flex-wrap:wrap;align-items:baseline;gap:14px}
  header h1{margin:0;font-size:18px;letter-spacing:.3px}
  header h1 .dot{color:var(--accent)}
  header .meta{color:var(--muted);font-size:12px}
  .banner{padding:8px 22px;font-size:13px}
  .banner.warn{background:#3a2a12;color:#ffd591;border-bottom:1px solid #5a4520}
  .banner.note{background:#10242e;color:#9fe0ef;border-bottom:1px solid #20414e}
  nav{display:flex;gap:2px;padding:0 14px;border-bottom:1px solid var(--line);flex-wrap:wrap}
  nav button{background:none;border:none;color:var(--muted);padding:11px 14px;cursor:pointer;font-size:13px;border-bottom:2px solid transparent}
  nav button:hover{color:var(--fg)}
  nav button.active{color:var(--fg);border-bottom-color:var(--accent)}
  main{padding:18px 22px;max-width:1300px}
  section{display:none}
  section.active{display:block}
  .cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px;margin-bottom:18px}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px}
  .card .n{font-size:24px;font-weight:600}
  .card .l{color:var(--muted);font-size:12px;margin-top:2px}
  table{width:100%;border-collapse:collapse;margin:8px 0 18px}
  th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}
  th{color:var(--muted);font-weight:500;font-size:12px;text-transform:uppercase;letter-spacing:.4px}
  tr:hover td{background:var(--panel)}
  code{background:var(--panel2);padding:1px 6px;border-radius:5px;font-size:12px}
  .pill{display:inline-block;padding:1px 8px;border-radius:999px;font-size:11px;font-weight:600;line-height:1.7}
  .sev-critical{background:rgba(255,77,79,.16);color:var(--crit)}
  .sev-high{background:rgba(255,122,69,.16);color:var(--high)}
  .sev-medium{background:rgba(255,197,61,.16);color:var(--med)}
  .sev-low{background:rgba(115,209,61,.16);color:var(--low)}
  .sev-info{background:rgba(140,140,140,.16);color:var(--info)}
  .tag{display:inline-block;background:var(--panel2);color:var(--muted);border-radius:5px;padding:0 7px;margin:2px 3px 0 0;font-size:11px}
  .tag.self{background:rgba(224,179,65,.16);color:var(--accent)}
  .muted{color:var(--muted)}
  h2{font-size:15px;margin:22px 0 4px;border-left:3px solid var(--accent);padding-left:10px}
  h3{font-size:13px;margin:16px 0 4px;color:var(--fg)}
  .agentcard{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin-bottom:14px}
  .agentcard .head{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap}
  .filters{display:flex;gap:8px;margin-bottom:10px;flex-wrap:wrap}
  select,input{background:var(--panel2);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:6px 8px;font-size:13px}
  #graphwrap{position:relative;height:70vh;border:1px solid var(--line);border-radius:10px;overflow:hidden;background:radial-gradient(circle at 50% 40%,#11161d,#0b0e12)}
  #graph{width:100%;height:100%;display:block;cursor:grab}
  #legend{position:absolute;top:10px;left:10px;background:rgba(13,17,23,.82);border:1px solid var(--line);border-radius:8px;padding:8px 10px;font-size:11px}
  #legend .row{display:flex;align-items:center;gap:7px;margin:2px 0}
  #legend .sw{width:11px;height:11px;border-radius:50%}
  #detail{position:absolute;top:10px;right:10px;width:290px;max-height:calc(70vh - 20px);overflow:auto;background:rgba(13,17,23,.94);border:1px solid var(--line);border-radius:8px;padding:12px;font-size:12px;display:none}
  #detail h4{margin:0 0 6px}
  #detail .k{color:var(--muted)}
  #ghelp{position:absolute;bottom:10px;left:10px;color:var(--muted);font-size:11px}
  .factor{font-size:11px;color:var(--muted)}
  .empty{color:var(--muted);padding:12px 0}
  a{color:#6aa9ff}
</style>
</head>
<body>
<header>
  <h1><span class="dot">●</span> Insikt</h1>
  <span class="meta" id="hmeta"></span>
</header>
<div id="banners"></div>
<nav id="nav"></nav>
<main>
  <section id="tab-overview" class="active"></section>
  <section id="tab-graph">
    <div id="graphwrap">
      <canvas id="graph"></canvas>
      <div id="legend"></div>
      <div id="detail"></div>
      <div id="ghelp">drag node · scroll to zoom · drag background to pan · double-click to re-layout</div>
    </div>
  </section>
  <section id="tab-capability"></section>
  <section id="tab-timeline"></section>
  <section id="tab-cost"></section>
  <section id="tab-hygiene"></section>
  <section id="tab-diff"></section>
</main>

<script id="insikt-data" type="application/json">__INSIKT_DATA__</script>
<script>
"use strict";
const DATA = JSON.parse(document.getElementById("insikt-data").textContent);
const TYPE_COLORS = {agent:"#e0b341",skill:"#6aa9ff",tool:"#9b8cff",model:"#4fd0c0",
  connector:"#f08a5d",resource:"#8d99ae",credential_ref:"#d65db1",action:"#56707f"};
const SEV_ORDER = ["critical","high","medium","low","info"];
const esc = s => (s==null?"":String(s)).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const sev = s => `<span class="pill sev-${esc(s||"info")}">${esc(s||"info")}</span>`;
const $ = id => document.getElementById(id);

/* ---------- header + banners ---------- */
(function(){
  const m = DATA.meta;
  const bits = [];
  if(m.frameworks) bits.push(esc(m.frameworks.join(", ")));
  if(m.host) bits.push("host "+esc(m.host));
  if(m.snapshot_id) bits.push("snapshot #"+esc(m.snapshot_id));
  if(m.scan_ts) bits.push(esc(m.scan_ts));
  bits.push("by "+esc(m.generated_by));
  $("hmeta").textContent = bits.join("  ·  ");
  const b = $("banners");
  if(m.partial){
    b.insertAdjacentHTML("beforeend",
      `<div class="banner warn">⚠ Partial scan — some sources were missing or unreadable: ${esc((m.partial_reasons||[]).join("; "))||"see collectors"}. Figures are a lower bound, not a complete record.</div>`);
  }
  if(DATA.backfill_note){
    b.insertAdjacentHTML("beforeend", `<div class="banner note">↺ ${esc(DATA.backfill_note)}</div>`);
  }
})();

/* ---------- tabs ---------- */
const TABS = [["overview","Overview"],["graph","Graph"],["capability","Capability surface"],
  ["timeline","Action timeline"],["cost","Model + cost"],["hygiene","Hygiene"],["diff","Diff"]];
(function(){
  const nav = $("nav");
  TABS.forEach(([id,label],i)=>{
    if(id==="diff" && !DATA.diff) return;
    const btn=document.createElement("button");
    btn.textContent=label; btn.dataset.tab=id; if(i===0) btn.classList.add("active");
    btn.onclick=()=>activate(id);
    nav.appendChild(btn);
  });
})();
function activate(id){
  document.querySelectorAll("nav button").forEach(b=>b.classList.toggle("active",b.dataset.tab===id));
  document.querySelectorAll("main section").forEach(s=>s.classList.remove("active"));
  $("tab-"+id).classList.add("active");
  if(id==="graph") ensureGraph();
}

/* ---------- overview ---------- */
(function(){
  const s=DATA.summary;
  const cards=[["agents","Agents"],["skills","Skills"],["self_authored_skills","Self-authored"],
    ["tools","Tools"],["connectors","Connectors"],["models","Models"],
    ["credential_refs","Credential refs"],["actions","Actions"]];
  let h=`<div class="cards">`+
    cards.map(([k,l])=>`<div class="card"><div class="n">${esc(s[k])}</div><div class="l">${l}</div></div>`).join("")+
    `<div class="card"><div class="n">$${esc((s.total_cost||0).toFixed(4))}</div><div class="l">Model spend</div></div>`+
    `<div class="card"><div class="n">${esc(s.total_tokens.toLocaleString())}</div><div class="l">Tokens</div></div>`+
    `</div>`;
  h+=`<h2>Risk by agent</h2>`;
  if(!s.risk.length){ h+=`<div class="empty">No agents scored.</div>`; }
  else{
    h+=`<table><tr><th>Agent</th><th>Score</th><th>Worst</th><th>Top contributing factors</th></tr>`;
    s.risk.forEach(r=>{
      h+=`<tr><td><b>${esc(r.label)}</b></td><td>${esc(r.score)}</td><td>${sev(r.worst)}</td>
        <td>${r.top_findings.map(esc).join("<br>")||'<span class="muted">none</span>'}</td></tr>`;
    });
    h+=`</table>`;
  }
  $("tab-overview").innerHTML=h;
})();

/* ---------- capability surface ---------- */
(function(){
  const root=$("tab-capability"); const cap=DATA.capability;
  if(!cap.agents.length){root.innerHTML=`<div class="empty">No agents found.</div>`;return;}
  root.innerHTML=cap.agents.map(a=>{
    const skills=a.skills.map(sk=>{
      const tools=sk.tools.map(t=>`<span class="tag">${esc(t)}</span>`).join("")||'<span class="muted">—</span>';
      const reaches=(sk.reaches||[]).map(r=>`<span class="tag">${esc(r.kind)}:${esc(r.value)}</span>`).join("")||'<span class="muted">—</span>';
      const creds=(sk.credential_reads||[]).map(c=>`<span class="tag">${esc(c)}</span>`).join("")||'<span class="muted">—</span>';
      return `<tr>
        <td><b>${esc(sk.name)}</b> ${sk.self_authored?'<span class="tag self">self-authored</span>':''}<br><span class="muted">${esc(sk.source||'')}</span></td>
        <td>${tools}</td><td>${reaches}</td><td>${creds}</td>
        <td>${sk.risk?sev(sk.risk):'<span class="muted">—</span>'}</td></tr>`;
    }).join("")||`<tr><td colspan="5" class="muted">no skills</td></tr>`;
    const conns=a.connectors.map(c=>`<span class="tag">${esc(c.platform)}${c.accepts_strangers?' ⚠ strangers':''}</span>`).join("")||'<span class="muted">none</span>';
    const models=a.models.map(m=>`<span class="tag">${esc(m.provider)}/${esc(m.model_name)}</span>`).join("")||'<span class="muted">none</span>';
    const mcp=(a.mcp_servers||[]).map(s=>`<span class="tag">${esc(s.name)}</span>`).join("");
    return `<div class="agentcard">
      <div class="head"><h3 style="margin:0">${esc(a.label)} ${a.risk?sev(a.risk):''}</h3>
        <span class="muted">${esc(a.framework||'')} · ${esc(a.version||'?')} · bind ${esc(a.gateway_bind||'?')} · auth ${esc(a.auth_mode||'?')}${a.memory_items!=null?' · '+esc(a.memory_items)+' memories':''}</span></div>
      <div style="margin:6px 0"><span class="muted">Connectors:</span> ${conns} &nbsp; <span class="muted">Models:</span> ${models}${mcp?' &nbsp; <span class="muted">MCP:</span> '+mcp:''}</div>
      <table><tr><th>Skill</th><th>Tools</th><th>Reaches</th><th>Credential reads</th><th>Risk</th></tr>${skills}</table>
    </div>`;
  }).join("");
})();

/* ---------- timeline ---------- */
(function(){
  const root=$("tab-timeline"); const tl=DATA.timeline;
  const types=[...new Set(tl.actions.map(a=>a.type))].sort();
  const agents=[...new Set(tl.actions.map(a=>a.agent).filter(Boolean))].sort();
  root.innerHTML=`<div class="filters">
      <select id="f-type"><option value="">all types</option>${types.map(t=>`<option>${esc(t)}</option>`).join("")}</select>
      <select id="f-agent"><option value="">all agents</option>${agents.map(a=>`<option>${esc(a)}</option>`).join("")}</select>
      <span class="muted" id="f-count"></span>
    </div><div id="tl-body"></div>`;
  function draw(){
    const ft=$("f-type").value, fa=$("f-agent").value;
    const rows=tl.actions.filter(a=>(!ft||a.type===ft)&&(!fa||a.agent===fa));
    $("f-count").textContent=`${rows.length} action(s)`;
    if(!rows.length){$("tl-body").innerHTML=`<div class="empty">No actions in window.</div>`;return;}
    let h=`<table><tr><th>When</th><th>Type</th><th>Summary</th><th>Agent</th><th>Skill</th><th>Model / cost</th><th>Src</th></tr>`;
    rows.forEach(a=>{
      const drift=a.type==="skill_written";
      const cost=a.cost!=null?`$${Number(a.cost).toFixed(4)}`:"";
      const mc=[a.model,a.tokens?esc(a.tokens)+" tok":"",cost].filter(Boolean).join("<br>");
      h+=`<tr${drift?' style="background:rgba(224,179,65,.07)"':''}>
        <td class="muted" style="white-space:nowrap">${esc(a.ts||'')}</td>
        <td>${drift?'✎ ':''}<code>${esc(a.type)}</code></td>
        <td>${esc(a.summary)}${a.resource?'<br><span class="muted">→ '+esc(a.resource)+'</span>':''}${a.connector?'<br><span class="muted">via '+esc(a.connector)+'</span>':''}</td>
        <td>${esc(a.agent||'')}</td><td>${esc(a.skill||'')}</td><td>${mc||'<span class="muted">—</span>'}</td>
        <td><span class="tag">${esc(a.source||'')}</span></td></tr>`;
    });
    h+=`</table>`;
    if(tl.truncated) h+=`<div class="muted">Showing first ${tl.actions.length}; older actions omitted from this view.</div>`;
    $("tl-body").innerHTML=h;
  }
  $("f-type").onchange=draw; $("f-agent").onchange=draw; draw();
})();

/* ---------- cost ---------- */
(function(){
  const root=$("tab-cost"); const c=DATA.cost;
  let h=`<div class="cards">
     <div class="card"><div class="n">$${esc((c.total_cost||0).toFixed(4))}</div><div class="l">Total spend</div></div>
     <div class="card"><div class="n">${esc(c.total_tokens.toLocaleString())}</div><div class="l">Total tokens</div></div></div>`;
  h+=`<h2>Per model</h2>`;
  const role=m=>[m.default?'<span class="tag self">default</span>':'',
                 (m.configured&&!m.default)?'<span class="tag">configured</span>':'',
                 (m.used||m.calls)?'<span class="tag">used</span>':''].join('')||'<span class="muted">—</span>';
  h+= c.models.length?`<table><tr><th>Model</th><th>Provider</th><th>Role</th><th>Calls</th><th>Tokens</th><th>Cost</th></tr>`+
     c.models.map(m=>`<tr><td>${esc(m.model)}</td><td>${esc(m.provider||'')}</td><td>${role(m)}</td><td>${esc(m.calls)}</td><td>${esc((m.tokens||0).toLocaleString())}</td><td>$${esc((m.cost||0).toFixed(4))}</td></tr>`).join("")+`</table>`
     :`<div class="empty">No models configured or used.</div>`;
  if(c.total_tokens>0 && c.total_cost===0) h+=`<div class="muted">Token volume is recorded but per-call cost isn't — some frameworks don't persist cost. A model shown with 0 calls is configured but had no usage recorded.</div>`;
  h+=`<h2>Per agent</h2>`;
  h+= c.agents.length?`<table><tr><th>Agent</th><th>Calls</th><th>Tokens</th><th>Cost</th></tr>`+
     c.agents.map(a=>`<tr><td>${esc(a.agent)}</td><td>${esc(a.calls)}</td><td>${esc(a.tokens.toLocaleString())}</td><td>$${esc(a.cost.toFixed(4))}</td></tr>`).join("")+`</table>`
     :``;
  root.innerHTML=h;
})();

/* ---------- hygiene ---------- */
(function(){
  const root=$("tab-hygiene"); const hy=DATA.hygiene;
  const fs=hy.findings.slice().sort((a,b)=>SEV_ORDER.indexOf(a.severity)-SEV_ORDER.indexOf(b.severity));
  let h=`<h2>Findings (${fs.length})</h2>`;
  if(!fs.length){h+=`<div class="empty">No hygiene findings. ✓</div>`;}
  else{
    h+=`<table><tr><th>Severity</th><th>Finding</th><th>Detail</th><th>Factors</th></tr>`;
    fs.forEach(f=>{h+=`<tr><td>${sev(f.severity)}</td><td><b>${esc(f.title)}</b></td><td>${esc(f.detail)}</td>
      <td class="factor">${(f.factors||[]).map(esc).join(", ")}</td></tr>`;});
    h+=`</table>`;
  }
  h+=`<h2>Risk score by agent</h2>`;
  const scores=Object.values(hy.scores).sort((a,b)=>b.score-a.score);
  if(!scores.length){h+=`<div class="empty">No agents.</div>`;}
  else scores.forEach(rs=>{
    const lbl=(DATA.capability.agents.find(a=>a.id===rs.agent_id)||{}).label||rs.agent_id;
    h+=`<div class="agentcard"><div class="head"><h3 style="margin:0">${esc(lbl)}</h3><b>score ${esc(rs.score)}</b></div>`;
    h+= rs.findings.length?`<ul style="margin:8px 0 0;padding-left:18px">`+rs.findings.map(f=>`<li>${sev(f.severity)} ${esc(f.title)}</li>`).join("")+`</ul>`:`<div class="muted">no findings</div>`;
    h+=`</div>`;
  });
  root.innerHTML=h;
})();

/* ---------- diff ---------- */
(function(){
  if(!DATA.diff) return;
  const d=DATA.diff; const root=$("tab-diff");
  const list=(title,arr,fmt)=> `<h3>${esc(title)} (${arr.length})</h3>`+(arr.length?`<ul>`+arr.map(fmt).join("")+`</ul>`:`<div class="muted">none</div>`);
  let h=`<h2>Since snapshot #${esc(d.since.id)} → #${esc(d.to.id)}</h2><p>${esc(d.summary)}</p>`;
  h+=list("New skills",d.new_skills,x=>`<li>${esc(x.label)}</li>`);
  h+=list("Capability drift (self-authored skills gaining shell/network)",d.capability_drift,x=>`<li>${esc(x.skill)} → gained <code>${esc(x.gained_tool)}</code></li>`);
  h+=list("New credential reads",d.new_credential_reads,x=>`<li>${esc(x.skill)} reads ${esc(x.credential)}</li>`);
  h+=list("New connectors",d.new_connectors,x=>`<li>${esc(x.label)}</li>`);
  h+=list("New reachable hosts",d.new_reachable_hosts,x=>`<li>${esc(x.label)}</li>`);
  h+=list("New models",d.new_models,x=>`<li>${esc(x.label)}</li>`);
  h+=list("Removed skills",d.removed_skills,x=>`<li>${esc(x.label)}</li>`);
  root.innerHTML=h;
})();

/* ---------- graph (canvas force layout) ---------- */
let graphReady=false;
function ensureGraph(){ if(graphReady) return; graphReady=true; initGraph(); }
function initGraph(){
  const canvas=$("graph"), ctx=canvas.getContext("2d");
  const RISK_STROKE={critical:"#ff4d4f",high:"#ff7a45",medium:"#ffc53d"};
  // build legend
  $("legend").innerHTML=Object.entries(TYPE_COLORS).map(([t,c])=>
    `<div class="row"><span class="sw" style="background:${c}"></span>${t.replace("_"," ")}</div>`).join("");

  const nmap=new Map();
  const nodes=DATA.graph.nodes.map(n=>{const o={...n,x:0,y:0,vx:0,vy:0}; nmap.set(n.id,o); return o;});
  const edges=DATA.graph.edges.filter(e=>nmap.has(e.src)&&nmap.has(e.dst))
    .map(e=>({s:nmap.get(e.src),t:nmap.get(e.dst)}));
  // seed positions on a circle (deterministic; no Math.random dependence on order)
  nodes.forEach((n,i)=>{const a=i*2.399963; const r=40+8*Math.sqrt(i); n.x=Math.cos(a)*r; n.y=Math.sin(a)*r;});
  const deg=new Map(); edges.forEach(e=>{deg.set(e.s.id,(deg.get(e.s.id)||0)+1);deg.set(e.t.id,(deg.get(e.t.id)||0)+1);});
  const radius=n=> n.type==="agent"?12 : n.type==="action"?3.5 : 6+Math.min(4,(deg.get(n.id)||0));

  let view={k:1,x:0,y:0}, alpha=1;
  function tick(){
    const k_rep=2200, k_spr=0.02, rest=46, center=0.012;
    for(let i=0;i<nodes.length;i++){
      const a=nodes[i];
      for(let j=i+1;j<nodes.length;j++){
        const b=nodes[j]; let dx=a.x-b.x, dy=a.y-b.y; let d2=dx*dx+dy*dy; if(d2<0.01)d2=0.01;
        const f=k_rep/d2; const d=Math.sqrt(d2); const fx=f*dx/d, fy=f*dy/d;
        a.vx+=fx; a.vy+=fy; b.vx-=fx; b.vy-=fy;
      }
      a.vx-=a.x*center; a.vy-=a.y*center;
    }
    edges.forEach(e=>{
      let dx=e.t.x-e.s.x, dy=e.t.y-e.s.y; let d=Math.sqrt(dx*dx+dy*dy)||0.01;
      const f=k_spr*(d-rest); const fx=f*dx/d, fy=f*dy/d;
      e.s.vx+=fx; e.s.vy+=fy; e.t.vx-=fx; e.t.vy-=fy;
    });
    nodes.forEach(n=>{ if(n.fixed) return; n.vx*=0.86; n.vy*=0.86; n.x+=n.vx*alpha; n.y+=n.vy*alpha;});
    alpha*=0.992; if(alpha<0.02) alpha=0.02;
  }
  function fit(){
    let minx=1e9,miny=1e9,maxx=-1e9,maxy=-1e9;
    nodes.forEach(n=>{minx=Math.min(minx,n.x);miny=Math.min(miny,n.y);maxx=Math.max(maxx,n.x);maxy=Math.max(maxy,n.y);});
    const w=canvas.clientWidth,h=canvas.clientHeight;
    const gw=Math.max(1,maxx-minx), gh=Math.max(1,maxy-miny);
    view.k=Math.min(w/(gw+80),h/(gh+80),2.2);
    view.x=w/2-(minx+maxx)/2*view.k; view.y=h/2-(miny+maxy)/2*view.k;
  }
  let dpr=Math.max(1,window.devicePixelRatio||1);
  function resize(){
    dpr=Math.max(1,window.devicePixelRatio||1);
    canvas.width=canvas.clientWidth*dpr; canvas.height=canvas.clientHeight*dpr;
  }
  function draw(){
    ctx.setTransform(dpr,0,0,dpr,0,0);
    ctx.clearRect(0,0,canvas.clientWidth,canvas.clientHeight);
    ctx.save(); ctx.translate(view.x,view.y); ctx.scale(view.k,view.k);
    ctx.lineWidth=0.6/view.k; ctx.strokeStyle="rgba(120,140,160,.28)";
    ctx.beginPath();
    edges.forEach(e=>{ctx.moveTo(e.s.x,e.s.y);ctx.lineTo(e.t.x,e.t.y);}); ctx.stroke();
    nodes.forEach(n=>{
      const r=radius(n);
      ctx.beginPath(); ctx.arc(n.x,n.y,r,0,6.2832);
      ctx.fillStyle=TYPE_COLORS[n.type]||"#999"; ctx.fill();
      const rs=RISK_STROKE[n.risk];
      if(rs){ctx.lineWidth=2/view.k;ctx.strokeStyle=rs;ctx.stroke();}
      if(view.k>0.85 && n.type!=="action" && n.type!=="resource"){
        ctx.fillStyle="rgba(230,237,243,.85)"; ctx.font=`${10/view.k}px sans-serif`;
        ctx.fillText(n.label, n.x+r+1.5, n.y+3/view.k);
      }
    });
    ctx.restore();
  }
  function loop(){ for(let s=0;s<3;s++) tick(); draw(); if(alpha>0.025) requestAnimationFrame(loop); else draw(); }
  resize(); fit(); requestAnimationFrame(loop);
  window.addEventListener("resize",()=>{resize();draw();});

  // interaction
  function toWorld(ev){const r=canvas.getBoundingClientRect();return{x:(ev.clientX-r.left-view.x)/view.k,y:(ev.clientY-r.top-view.y)/view.k};}
  function pick(w){let best=null,bd=1e9;nodes.forEach(n=>{const dx=n.x-w.x,dy=n.y-w.y,d=dx*dx+dy*dy;const r=radius(n)+4;if(d<r*r&&d<bd){bd=d;best=n;}});return best;}
  let drag=null,pan=null,moved=false;
  canvas.addEventListener("mousedown",ev=>{
    const w=toWorld(ev); const n=pick(w); moved=false;
    if(n){drag=n;n.fixed=true;canvas.style.cursor="grabbing";}
    else{pan={x:ev.clientX,y:ev.clientY,ox:view.x,oy:view.y};canvas.style.cursor="grabbing";}
  });
  window.addEventListener("mousemove",ev=>{
    if(drag){const w=toWorld(ev);drag.x=w.x;drag.y=w.y;drag.vx=drag.vy=0;alpha=Math.max(alpha,.3);moved=true;ensureLoop();}
    else if(pan){view.x=pan.ox+(ev.clientX-pan.x);view.y=pan.oy+(ev.clientY-pan.y);moved=true;draw();}
  });
  window.addEventListener("mouseup",ev=>{
    if(drag){drag.fixed=false;if(!moved)showDetail(drag);drag=null;}
    else if(pan){if(!moved){const n=pick(toWorld(ev));if(n)showDetail(n);else hideDetail();}pan=null;}
    canvas.style.cursor="grab";
  });
  let looping=false;
  function ensureLoop(){if(!looping){looping=true;const r=()=>{for(let s=0;s<3;s++)tick();draw();if(alpha>0.025)requestAnimationFrame(r);else{looping=false;draw();}};requestAnimationFrame(r);}}
  canvas.addEventListener("wheel",ev=>{
    ev.preventDefault();const r=canvas.getBoundingClientRect();const mx=ev.clientX-r.left,my=ev.clientY-r.top;
    const f=ev.deltaY<0?1.1:0.9;const wx=(mx-view.x)/view.k,wy=(my-view.y)/view.k;
    view.k=Math.min(6,Math.max(0.15,view.k*f));view.x=mx-wx*view.k;view.y=my-wy*view.k;draw();
  },{passive:false});
  canvas.addEventListener("dblclick",()=>{nodes.forEach(n=>n.fixed=false);alpha=1;ensureLoop();setTimeout(()=>{fit();draw();},400);});

  function showDetail(n){
    const d=$("detail");d.style.display="block";
    let rows=`<h4>${esc(n.label)}</h4><div class="k">${esc(n.type)}</div>`;
    const skip={body:1,risk:1};
    Object.entries(n.props||{}).forEach(([k,v])=>{
      if(skip[k]||v==null||v===""||(Array.isArray(v)&&!v.length))return;
      rows+=`<div style="margin-top:6px"><span class="k">${esc(k)}:</span> ${esc(Array.isArray(v)?v.join(", "):v)}</div>`;
    });
    if(n.risk) rows+=`<div style="margin-top:6px">${sev(n.risk)}</div>`;
    d.innerHTML=rows;
  }
  function hideDetail(){$("detail").style.display="none";}
}
</script>
</body>
</html>"""
