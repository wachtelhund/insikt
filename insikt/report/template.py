"""The single-file HTML report shell — mobile-first, self-contained (no CDN).

Design goals (set after a user mistook a *capability* for an *incident*):
* clear messaging — "what a skill COULD do" is visually distinct from "what
  actually ran", everywhere;
* clean + scannable — cards over dense tables, severity colour, generous spacing;
* mobile friendly — responsive layout, scrollable nav, touch-enabled graph.

Data is inlined as JSON; all CSS/JS is inline so the file works fully offline.
"""

from __future__ import annotations

import html as _html


def render_page(title: str, data_json: str) -> str:
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
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="color-scheme" content="dark">
<title>__INSIKT_TITLE__</title>
<style>
  :root{
    --bg:#0b0d10; --surface:#14171c; --surface2:#1b1f27; --line:#272d36;
    --fg:#e9eef4; --muted:#8b95a3; --faint:#5b6573; --accent:#e8b54a;
    --crit:#ff5c5c; --high:#ff924d; --med:#ffc53d; --low:#5fd08a; --info:#7b8794;
    --cap:#5aa9ff; --exp:#ffc53d; --alert:#ff5c5c;
    --r:14px; --pad:16px;
  }
  *{box-sizing:border-box}
  html{-webkit-text-size-adjust:100%}
  html,body{overflow-x:hidden;max-width:100%}
  body{margin:0;background:var(--bg);color:var(--fg);
    font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    -webkit-font-smoothing:antialiased;padding-bottom:env(safe-area-inset-bottom)}
  a{color:var(--cap)}
  .wrap{max-width:1100px;margin:0 auto;padding:0 var(--pad)}

  .topbar{position:sticky;top:0;z-index:20;background:rgba(11,13,16,.95);backdrop-filter:blur(10px)}
  header{border-bottom:1px solid var(--line)}
  header .wrap{display:flex;align-items:center;gap:12px;flex-wrap:wrap;padding-top:12px;padding-bottom:12px}
  .brand{font-size:18px;font-weight:700;letter-spacing:.2px;white-space:nowrap}
  .brand .dot{color:var(--accent)}
  .hmeta{color:var(--muted);font-size:12.5px;flex:1;min-width:160px}
  .statuschip{margin-left:auto;font-weight:600;font-size:12.5px;padding:5px 12px;border-radius:999px;white-space:nowrap}
  .statuschip.ok{background:rgba(95,208,138,.14);color:var(--low)}
  .statuschip.warn{background:rgba(255,92,92,.14);color:var(--crit)}

  .banner{font-size:13.5px;border-bottom:1px solid transparent}
  .banner .wrap{padding:9px var(--pad)}
  .banner.warn{background:#2c2310;color:#ffd98a;border-bottom-color:#4a3a17}
  .banner.note{background:#0f2630;color:#9fe0ef;border-bottom-color:#1d4250}

  nav{border-bottom:1px solid var(--line);overflow-x:auto;-webkit-overflow-scrolling:touch;scrollbar-width:none}
  nav::-webkit-scrollbar{display:none}
  nav .wrap{display:flex;gap:4px;padding:0 var(--pad)}
  nav button{flex:0 0 auto;background:none;border:none;color:var(--muted);
    padding:13px 12px;min-height:46px;font-size:14px;font-weight:500;cursor:pointer;
    border-bottom:2.5px solid transparent;white-space:nowrap}
  nav button.active{color:var(--fg);border-bottom-color:var(--accent)}

  main{padding:18px 0 60px}
  section{display:none;animation:fade .18s ease}
  section.active{display:block}
  @keyframes fade{from{opacity:0;transform:translateY(3px)}to{opacity:1;transform:none}}
  h2{font-size:13px;text-transform:uppercase;letter-spacing:.7px;color:var(--muted);
    margin:26px 0 12px;font-weight:600}
  h2:first-child{margin-top:4px}

  /* headline */
  .headline{background:linear-gradient(135deg,var(--surface),var(--surface2));
    border:1px solid var(--line);border-radius:var(--r);padding:18px 18px;margin-bottom:18px}
  .headline .big{font-size:17px;font-weight:600;display:flex;align-items:center;gap:9px}
  .headline .sub{color:var(--muted);font-size:13.5px;margin-top:7px;line-height:1.7}

  /* stat tiles */
  .stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(116px,100%),1fr));gap:10px}
  .stat{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:13px 14px}
  .stat .n{font-size:23px;font-weight:700;letter-spacing:-.3px}
  .stat .l{color:var(--muted);font-size:12px;margin-top:1px}

  /* cards */
  .card{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);
    padding:var(--pad);margin-bottom:12px}
  .card .top{display:flex;align-items:center;gap:9px;flex-wrap:wrap}
  .card .title{font-weight:600;font-size:15.5px}
  .card .meta{color:var(--muted);font-size:12.5px}
  .kv{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px;font-size:13px}
  .kv .k{color:var(--faint);min-width:78px;flex:0 0 auto}
  .kv .v{flex:1;min-width:0;word-break:break-word}

  /* pills / tags */
  .pill{display:inline-block;padding:2px 9px;border-radius:999px;font-size:11.5px;font-weight:600;line-height:1.7;white-space:nowrap}
  .sev-critical{background:rgba(255,92,92,.16);color:var(--crit)}
  .sev-high{background:rgba(255,146,77,.16);color:var(--high)}
  .sev-medium{background:rgba(255,197,61,.15);color:var(--med)}
  .sev-low{background:rgba(95,208,138,.15);color:var(--low)}
  .sev-info{background:rgba(123,135,148,.18);color:#aab4c0}
  .tag{display:inline-block;background:var(--surface2);color:var(--muted);border:1px solid var(--line);
    border-radius:7px;padding:1px 8px;margin:2px 4px 0 0;font-size:11.5px;white-space:nowrap}
  .tag.self{background:rgba(232,181,74,.14);color:var(--accent);border-color:transparent}
  .tag.warn{background:rgba(255,92,92,.13);color:var(--crit);border-color:transparent}
  .tag.kind-capability{color:var(--cap);border-color:rgba(90,169,255,.4)}
  .tag.kind-exposure{color:var(--exp);border-color:rgba(255,197,61,.4)}
  .tag.kind-alert{color:var(--alert);border-color:rgba(255,92,92,.5)}
  .muted{color:var(--muted)} .faint{color:var(--faint)}
  .empty{color:var(--muted);padding:14px;text-align:center;background:var(--surface);border:1px solid var(--line);border-radius:12px}

  /* callout */
  .callout{display:flex;gap:11px;background:var(--surface2);border:1px solid var(--line);
    border-left:3px solid var(--cap);border-radius:10px;padding:12px 14px;margin-bottom:16px;font-size:13.5px;color:#cdd6e0}
  .callout b{color:var(--fg)}

  /* severity group (collapsible) */
  details.grp{background:var(--surface);border:1px solid var(--line);border-radius:12px;margin-bottom:10px;overflow:hidden}
  details.grp>summary{list-style:none;cursor:pointer;padding:13px var(--pad);display:flex;align-items:center;gap:10px;font-weight:600}
  details.grp>summary::-webkit-details-marker{display:none}
  details.grp>summary .chev{margin-left:auto;color:var(--faint);transition:transform .15s}
  details.grp[open]>summary .chev{transform:rotate(90deg)}
  .finding{border-top:1px solid var(--line);padding:13px var(--pad)}
  .finding .ft{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
  .finding .fname{font-weight:600;font-size:14.5px}
  .finding .fd{color:var(--muted);font-size:13px;margin-top:5px}
  .finding .ff{margin-top:7px}

  /* timeline */
  .tl{display:flex;flex-direction:column;gap:0}
  .ev{display:flex;gap:12px;padding:11px 2px;border-bottom:1px solid var(--line)}
  .ev .when{color:var(--faint);font-size:12px;flex:0 0 92px;white-space:nowrap}
  .ev .body{flex:1;min-width:0}
  .ev .body .s{font-size:14px}
  .ev .body .m{color:var(--muted);font-size:12px;margin-top:3px}
  .ev.drift{background:rgba(232,181,74,.05);margin:0 -8px;padding:11px 8px;border-radius:8px}

  /* table (cost) — scrolls horizontally if needed */
  .scroll{overflow-x:auto;-webkit-overflow-scrolling:touch;border:1px solid var(--line);border-radius:12px}
  table{width:100%;border-collapse:collapse;min-width:380px}
  th,td{text-align:left;padding:11px 13px;border-bottom:1px solid var(--line);font-size:13.5px;white-space:nowrap}
  th{color:var(--muted);font-weight:500;font-size:11.5px;text-transform:uppercase;letter-spacing:.5px}
  tr:last-child td{border-bottom:none}

  .filters{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}
  select{background:var(--surface2);color:var(--fg);border:1px solid var(--line);border-radius:9px;
    padding:9px 11px;font-size:13.5px;min-height:40px}

  /* graph */
  #graphwrap{position:relative;height:74vh;min-height:420px;border:1px solid var(--line);
    border-radius:var(--r);overflow:hidden;background:radial-gradient(circle at 50% 38%,#11161d,#0a0c10);touch-action:none}
  #graph{width:100%;height:100%;display:block;cursor:grab}
  #legend{position:absolute;top:10px;left:10px;background:rgba(11,13,16,.82);border:1px solid var(--line);
    border-radius:10px;padding:8px 10px;font-size:11px;max-width:46%}
  #legend .row{display:flex;align-items:center;gap:7px;margin:2px 0}
  #legend .sw{width:10px;height:10px;border-radius:50%;flex:0 0 auto}
  #detail{position:absolute;top:10px;right:10px;width:min(280px,72vw);max-height:calc(74vh - 20px);
    overflow:auto;background:rgba(13,16,20,.96);border:1px solid var(--line);border-radius:10px;padding:13px;font-size:12.5px;display:none}
  #detail h4{margin:0 0 7px;font-size:14px}
  #detail .k{color:var(--faint)}
  #ghelp{position:absolute;bottom:9px;left:10px;color:var(--faint);font-size:11px}
  code{background:var(--surface2);padding:1px 6px;border-radius:6px;font-size:12px;word-break:break-word}

  @media (max-width:480px){
    .wrap{padding:0 13px}
    header .wrap{gap:6px 10px}
    .brand{font-size:17px}
    .hmeta{flex-basis:100%;order:3;font-size:12px}
    .statuschip{margin-left:auto;font-size:12px}
    .stats{grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}
    .stat .n{font-size:20px}
    .ev .when{flex-basis:74px}
  }
</style>
</head>
<body>
<div class="topbar">
<header><div class="wrap">
  <span class="brand"><span class="dot">●</span> Insikt</span>
  <span class="hmeta" id="hmeta"></span>
  <span class="statuschip" id="statuschip"></span>
</div></header>
<nav><div class="wrap" id="nav"></div></nav>
</div>
<div id="banners"></div>
<main class="wrap">
  <section id="tab-overview" class="active"></section>
  <section id="tab-graph">
    <div id="graphwrap">
      <canvas id="graph"></canvas>
      <div id="legend"></div>
      <div id="detail"></div>
      <div id="ghelp">drag · pinch / scroll to zoom · tap a node</div>
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
const TYPE_COLORS={agent:"#e8b54a",skill:"#5aa9ff",tool:"#9b8cff",model:"#4fd0c0",
  connector:"#f08a5d",resource:"#8d99ae",credential_ref:"#d65db1",action:"#56707f"};
const SEV=["critical","high","medium","low","info"];
const esc=s=>(s==null?"":String(s)).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const pill=s=>`<span class="pill sev-${esc(s||"info")}">${esc(s||"info")}</span>`;
const $=id=>document.getElementById(id);
const num=n=>(n==null?0:n).toLocaleString();

// classify a finding: capability (could-do) vs exposure (config) vs alert (verified-bad)
function fclass(id){
  const p=String(id).split(":")[0];
  if(p==="fp"||p==="drift") return {k:"alert",label:"alert"};
  if(p==="posture"||p==="stranger"||p==="exposure"||p==="overlay") return {k:"exposure",label:"config"};
  return {k:"capability",label:"capability"};
}
// skill use lookup (id -> {use_count,last_used,kind})
const SKILLUSE={};
(DATA.capability.agents||[]).forEach(a=>(a.skills||[]).forEach(s=>{SKILLUSE[s.id]={use_count:s.use_count,last_used:s.last_used,kind:s.kind};}));
function useBadge(nodeId){
  const u=SKILLUSE[nodeId]; if(!u) return "";
  if(u.use_count===0||u.use_count==null&&u.last_used==null) return `<span class="tag">never used</span>`;
  if(u.use_count>0) return `<span class="tag">used ${u.use_count}×</span>`;
  return "";
}

/* ---------- header + banners ---------- */
(function(){
  const m=DATA.meta, s=DATA.summary;
  const bits=[];
  if(m.frameworks) bits.push(esc(m.frameworks.join(", ")));
  if(m.host) bits.push("host "+esc(m.host));
  if(m.scan_ts) bits.push(esc((m.scan_ts||"").replace("T"," ").replace(/[+Z].*/,"")));
  $("hmeta").textContent=bits.join("  ·  ");
  const crit=(s.risk||[]).reduce((a,r)=>a+((r.worst==="critical"||r.worst==="high")?1:0),0);
  const chip=$("statuschip");
  if(crit){chip.className="statuschip warn";chip.textContent=`${crit} agent(s) need review`;}
  else{chip.className="statuschip ok";chip.textContent="no high-risk findings";}
  const b=$("banners");
  if(m.partial) b.insertAdjacentHTML("beforeend",`<div class="banner warn"><div class="wrap">⚠ Partial scan — ${esc((m.partial_reasons||[]).join("; "))||"some sources unreadable"}. Figures are a lower bound.</div></div>`);
  if(DATA.backfill_note) b.insertAdjacentHTML("beforeend",`<div class="banner note"><div class="wrap">↺ ${esc(DATA.backfill_note)}</div></div>`);
})();

/* ---------- tabs ---------- */
const TABS=[["overview","Overview"],["graph","Graph"],["capability","Capabilities"],
  ["timeline","Timeline"],["cost","Models & cost"],["hygiene","Hygiene"],["diff","Diff"]];
(function(){
  const nav=$("nav");
  TABS.forEach(([id,label],i)=>{
    if(id==="diff"&&!DATA.diff) return;
    const b=document.createElement("button");
    b.textContent=label;b.dataset.tab=id;if(i===0)b.classList.add("active");
    b.onclick=()=>activate(id);nav.appendChild(b);
  });
})();
function activate(id){
  document.querySelectorAll("nav button").forEach(b=>b.classList.toggle("active",b.dataset.tab===id));
  document.querySelectorAll("main section").forEach(s=>s.classList.remove("active"));
  $("tab-"+id).classList.add("active");
  window.scrollTo({top:0,behavior:"instant"});
  if(id==="graph") ensureGraph();
}

/* ---------- overview ---------- */
(function(){
  const s=DATA.summary, root=$("tab-overview");
  const acts=DATA.timeline.count||0;
  const neverUsed=Object.values(SKILLUSE).filter(u=>u.use_count===0).length;
  const worst=(DATA.hygiene.findings||[]).filter(f=>fclass(f.id).k==="alert"||f.severity==="critical"||f.severity==="high");
  let head;
  if(!worst.length){
    head=`<div class="big">✅ Nothing alarming in the action log</div>
      <div class="sub">Insikt reconstructed <b>${num(acts)}</b> action(s) and found no verified incidents.
      The Hygiene tab lists <b>capabilities</b> (what installed skills <i>could</i> do) — these are not things that happened.
      ${neverUsed?`<b>${neverUsed}</b> installed skill(s) have never been used.`:""}</div>`;
  } else {
    head=`<div class="big">⚠ ${worst.length} finding(s) worth a look</div>
      <div class="sub">Mostly capability/exposure, not confirmed incidents — open <b>Hygiene</b> for detail, and <b>Timeline</b> for what actually ran.</div>`;
  }
  let h=`<div class="headline">${head}</div>`;
  const tiles=[["agents","Agents"],["skills","Skills"],["self_authored_skills","Self-authored"],
    ["connectors","Connectors"],["models","Models"],["credential_refs","Credential refs"],["actions","Actions"]];
  h+=`<div class="stats">`+tiles.map(([k,l])=>`<div class="stat"><div class="n">${num(s[k])}</div><div class="l">${l}</div></div>`).join("")+
    `<div class="stat"><div class="n">${num(s.total_tokens)}</div><div class="l">Tokens</div></div></div>`;
  h+=`<h2>Risk by agent</h2>`;
  if(!(s.risk||[]).length){h+=`<div class="empty">No agents scored.</div>`;}
  else s.risk.forEach(r=>{
    h+=`<div class="card"><div class="top"><span class="title">${esc(r.label)}</span>${pill(r.worst)}
      <span class="meta" style="margin-left:auto">score ${esc(r.score)}</span></div>`;
    h+=`<div class="kv"><span class="k">top factors</span><span class="v muted">${(r.top_findings||[]).map(esc).join(" · ")||"none"}</span></div></div>`;
  });
  root.innerHTML=h;
})();

/* ---------- capabilities ---------- */
(function(){
  const root=$("tab-capability"), cap=DATA.capability;
  let h=`<div class="callout"><div>🧩</div><div><b>Capabilities = what each skill <i>could</i> do</b> — installed/available, not necessarily used. Check the <b>Timeline</b> for what actually ran. "never used" means it has never been invoked.</div></div>`;
  if(!cap.agents.length){root.innerHTML=h+`<div class="empty">No agents found.</div>`;return;}
  cap.agents.forEach(a=>{
    h+=`<h2>${esc(a.label)} ${a.risk?pill(a.risk):""}</h2>`;
    const meta=[a.framework,a.version,a.host&&("host "+a.host),a.memory_items!=null&&(a.memory_items+" memories")].filter(Boolean).map(esc).join(" · ");
    h+=`<div class="card"><div class="meta">${meta}</div>`;
    const conns=(a.connectors||[]).map(c=>`<span class="tag${c.accepts_strangers?' warn':''}">${esc(c.platform)}${c.accepts_strangers?' · no allowlist':''}</span>`).join("")||'<span class="muted">none</span>';
    const models=(a.models||[]).map(m=>`<span class="tag">${esc(m.provider)}/${esc(m.model_name)}</span>`).join("")||'<span class="muted">none</span>';
    h+=`<div class="kv"><span class="k">connectors</span><span class="v">${conns}</span></div>`;
    h+=`<div class="kv"><span class="k">models</span><span class="v">${models}</span></div>`;
    if((a.mcp_servers||[]).length) h+=`<div class="kv"><span class="k">MCP</span><span class="v">${a.mcp_servers.map(x=>`<span class="tag">${esc(x.name)}</span>`).join("")}</span></div>`;
    h+=`</div>`;
    (a.skills||[]).forEach(sk=>{
      const badges=[sk.self_authored?'<span class="tag self">self-authored</span>':'',
        (sk.use_count===0)?'<span class="tag">never used</span>':(sk.use_count>0?`<span class="tag">used ${sk.use_count}×</span>`:''),
        sk.risk?pill(sk.risk):''].join('');
      h+=`<div class="card"><div class="top"><span class="title">${esc(sk.name)}</span>${badges}</div>`;
      h+=`<div class="meta">${esc(sk.kind||sk.source||'')}</div>`;
      if((sk.tools||[]).length) h+=`<div class="kv"><span class="k">can use</span><span class="v">${sk.tools.map(t=>`<span class="tag">${esc(t)}</span>`).join("")}</span></div>`;
      if((sk.reaches||[]).length) h+=`<div class="kv"><span class="k">can reach</span><span class="v">${sk.reaches.map(r=>`<span class="tag">${esc(r.value)}</span>`).join("")}</span></div>`;
      if((sk.credential_reads||[]).length) h+=`<div class="kv"><span class="k">reads</span><span class="v">${sk.credential_reads.map(c=>`<span class="tag">${esc(c)}</span>`).join("")}</span></div>`;
      h+=`</div>`;
    });
  });
  root.innerHTML=h;
})();

/* ---------- timeline ---------- */
(function(){
  const root=$("tab-timeline"), tl=DATA.timeline;
  const types=[...new Set(tl.actions.map(a=>a.type))].sort();
  const agents=[...new Set(tl.actions.map(a=>a.agent).filter(Boolean))].sort();
  root.innerHTML=`<div class="callout"><div>📜</div><div><b>What actually ran</b> — reconstructed from the agents' own logs. ${esc(tl.count)} action(s).</div></div>
    <div class="filters">
      <select id="f-type"><option value="">all types</option>${types.map(t=>`<option>${esc(t)}</option>`).join("")}</select>
      ${agents.length>1?`<select id="f-agent"><option value="">all agents</option>${agents.map(a=>`<option>${esc(a)}</option>`).join("")}</select>`:""}
    </div><div id="tl-body"></div>`;
  function draw(){
    const ft=$("f-type").value, fa=($("f-agent")||{}).value||"";
    const rows=tl.actions.filter(a=>(!ft||a.type===ft)&&(!fa||a.agent===fa));
    if(!rows.length){$("tl-body").innerHTML=`<div class="empty">No actions in this view.</div>`;return;}
    let h=`<div class="tl">`;
    rows.forEach(a=>{
      const when=(a.ts||"").replace("T"," ").replace(/[+Z].*/,"")||"—";
      const drift=a.type==="skill_written";
      const cost=a.cost!=null?` · $${Number(a.cost).toFixed(4)}`:"";
      const tok=a.tokens?` · ${num(a.tokens)} tok`:"";
      const meta=[a.agent,a.skill&&("via "+a.skill),a.model,a.connector&&("→ "+a.connector),a.resource&&("→ "+a.resource)].filter(Boolean).map(esc).join(" · ");
      h+=`<div class="ev${drift?' drift':''}"><div class="when">${esc(when)}</div><div class="body">
        <div class="s">${drift?'✎ ':''}${pill(a.type)} ${esc(a.summary)}</div>
        <div class="m">${meta}${esc(tok)}${esc(cost)} · <span class="faint">${esc(a.source||'')}</span></div></div></div>`;
    });
    h+=`</div>`; if(tl.truncated)h+=`<div class="muted" style="margin-top:10px">Showing the most recent ${tl.actions.length}.</div>`;
    $("tl-body").innerHTML=h;
  }
  $("f-type").onchange=draw; if($("f-agent"))$("f-agent").onchange=draw; draw();
})();

/* ---------- models & cost ---------- */
(function(){
  const root=$("tab-cost"), c=DATA.cost;
  let h=`<div class="stats"><div class="stat"><div class="n">$${(c.total_cost||0).toFixed(4)}</div><div class="l">Recorded spend</div></div>
    <div class="stat"><div class="n">${num(c.total_tokens)}</div><div class="l">Recorded tokens</div></div></div>`;
  const roleTag=m=>[m.default?'<span class="tag self">default</span>':'',(m.configured&&!m.default)?'<span class="tag">configured</span>':'',(m.used||m.calls)?'<span class="tag">used</span>':'<span class="tag">unused</span>'].join('');
  h+=`<h2>Models</h2>`;
  h+= (c.models||[]).length?`<div class="scroll"><table><tr><th>Model</th><th>Role</th><th>Calls</th><th>Tokens</th><th>Cost</th></tr>`+
    c.models.map(m=>`<tr><td>${esc(m.model)}</td><td>${roleTag(m)}</td><td>${num(m.calls)}</td><td>${num(m.tokens||0)}</td><td>$${(m.cost||0).toFixed(4)}</td></tr>`).join("")+`</table></div>`
    :`<div class="empty">No models configured or used.</div>`;
  if(c.total_tokens>0&&c.total_cost===0) h+=`<div class="muted" style="margin-top:9px">Token volume is recorded but per-call cost isn't — some frameworks don't persist cost. A model with 0 calls is configured but had no usage recorded.</div>`;
  root.innerHTML=h;
})();

/* ---------- hygiene ---------- */
(function(){
  const root=$("tab-hygiene"), hy=DATA.hygiene;
  const fs=(hy.findings||[]).slice().sort((a,b)=>SEV.indexOf(a.severity)-SEV.indexOf(b.severity));
  let h=`<div class="callout"><div>🛡️</div><div><b>These are capabilities &amp; configuration — not incidents.</b>
    <span class="tag kind-capability">capability</span> = what a skill <i>could</i> do.
    <span class="tag kind-exposure">config</span> = a setting worth knowing.
    <span class="tag kind-alert">alert</span> = a verified problem.
    Nothing here means it <i>happened</i> — the <b>Timeline</b> shows that.</div></div>`;
  if(!fs.length){root.innerHTML=h+`<div class="empty">No hygiene findings. ✓</div>`;return;}
  const counts={}; fs.forEach(f=>counts[f.severity]=(counts[f.severity]||0)+1);
  h+=`<div style="margin-bottom:14px">`+SEV.filter(s=>counts[s]).map(s=>`${pill(s)} <span class="muted">${counts[s]}</span>`).join("&nbsp;&nbsp;")+`</div>`;
  SEV.forEach(sv=>{
    const group=fs.filter(f=>f.severity===sv); if(!group.length) return;
    const open=(sv==="critical"||sv==="high")?" open":"";
    h+=`<details class="grp"${open}><summary>${pill(sv)} <span>${group.length} ${sv}</span><span class="chev">›</span></summary>`;
    group.forEach(f=>{
      const cl=fclass(f.id);
      h+=`<div class="finding"><div class="ft"><span class="tag kind-${cl.k}">${cl.label}</span>
        <span class="fname">${esc(f.title)}</span>${useBadge(f.node_id)}</div>
        <div class="fd">${esc(f.detail)}</div>
        <div class="ff">${(f.factors||[]).map(x=>`<span class="tag">${esc(x)}</span>`).join("")}</div></div>`;
    });
    h+=`</details>`;
  });
  root.innerHTML=h;
})();

/* ---------- diff ---------- */
(function(){
  if(!DATA.diff) return;
  const d=DATA.diff, root=$("tab-diff");
  const list=(t,arr,fmt)=>`<h2>${esc(t)} (${arr.length})</h2>`+(arr.length?`<div class="card">`+arr.map(fmt).join("<br>")+`</div>`:`<div class="empty">none</div>`);
  let h=`<div class="callout"><div>Δ</div><div>Since snapshot #${esc(d.since.id)} → #${esc(d.to.id)}: <b>${esc(d.summary)}</b></div></div>`;
  h+=list("Capability drift (self-authored skill gained shell/network)",d.capability_drift||[],x=>`${esc(x.skill)} → gained <code>${esc(x.gained_tool)}</code>`);
  h+=list("New skills",d.new_skills||[],x=>esc(x.label));
  h+=list("New credential reads",d.new_credential_reads||[],x=>`${esc(x.skill)} reads ${esc(x.credential)}`);
  h+=list("New connectors",d.new_connectors||[],x=>esc(x.label));
  h+=list("New reachable hosts",d.new_reachable_hosts||[],x=>esc(x.label));
  h+=list("Removed skills",d.removed_skills||[],x=>esc(x.label));
  root.innerHTML=h;
})();

/* ---------- graph (canvas, mouse + touch) ---------- */
let graphReady=false;
function ensureGraph(){if(graphReady)return;graphReady=true;initGraph();}
function initGraph(){
  const canvas=$("graph"),ctx=canvas.getContext("2d");
  const RISK={critical:"#ff5c5c",high:"#ff924d",medium:"#ffc53d"};
  $("legend").innerHTML=Object.entries(TYPE_COLORS).map(([t,c])=>`<div class="row"><span class="sw" style="background:${c}"></span>${t.replace("_"," ")}</div>`).join("");
  const nmap=new Map();
  const nodes=DATA.graph.nodes.map((n,i)=>{const a=i*2.399963,r=40+8*Math.sqrt(i);const o={...n,x:Math.cos(a)*r,y:Math.sin(a)*r,vx:0,vy:0};nmap.set(n.id,o);return o;});
  const edges=DATA.graph.edges.filter(e=>nmap.has(e.src)&&nmap.has(e.dst)).map(e=>({s:nmap.get(e.src),t:nmap.get(e.dst)}));
  const deg=new Map();edges.forEach(e=>{deg.set(e.s.id,(deg.get(e.s.id)||0)+1);deg.set(e.t.id,(deg.get(e.t.id)||0)+1);});
  const radius=n=>n.type==="agent"?12:n.type==="action"?3.2:6+Math.min(4,(deg.get(n.id)||0));
  let view={k:1,x:0,y:0},alpha=1,dpr=Math.max(1,window.devicePixelRatio||1);
  function tick(){
    const rep=2200,spr=0.02,rest=46,cen=0.012;
    for(let i=0;i<nodes.length;i++){const a=nodes[i];
      for(let j=i+1;j<nodes.length;j++){const b=nodes[j];let dx=a.x-b.x,dy=a.y-b.y,d2=dx*dx+dy*dy;if(d2<.01)d2=.01;
        const f=rep/d2,d=Math.sqrt(d2),fx=f*dx/d,fy=f*dy/d;a.vx+=fx;a.vy+=fy;b.vx-=fx;b.vy-=fy;}
      a.vx-=a.x*cen;a.vy-=a.y*cen;}
    edges.forEach(e=>{let dx=e.t.x-e.s.x,dy=e.t.y-e.s.y,d=Math.sqrt(dx*dx+dy*dy)||.01;const f=spr*(d-rest),fx=f*dx/d,fy=f*dy/d;e.s.vx+=fx;e.s.vy+=fy;e.t.vx-=fx;e.t.vy-=fy;});
    nodes.forEach(n=>{if(n.fixed)return;n.vx*=.86;n.vy*=.86;n.x+=n.vx*alpha;n.y+=n.vy*alpha;});
    alpha*=.992;if(alpha<.02)alpha=.02;
  }
  function fit(){let mnx=1e9,mny=1e9,mxx=-1e9,mxy=-1e9;nodes.forEach(n=>{mnx=Math.min(mnx,n.x);mny=Math.min(mny,n.y);mxx=Math.max(mxx,n.x);mxy=Math.max(mxy,n.y);});
    const w=canvas.clientWidth,h=canvas.clientHeight,gw=Math.max(1,mxx-mnx),gh=Math.max(1,mxy-mny);
    view.k=Math.min(w/(gw+80),h/(gh+80),2.2);view.x=w/2-(mnx+mxx)/2*view.k;view.y=h/2-(mny+mxy)/2*view.k;}
  function resize(){dpr=Math.max(1,window.devicePixelRatio||1);canvas.width=canvas.clientWidth*dpr;canvas.height=canvas.clientHeight*dpr;}
  function draw(){
    ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,canvas.clientWidth,canvas.clientHeight);
    ctx.save();ctx.translate(view.x,view.y);ctx.scale(view.k,view.k);
    ctx.lineWidth=.6/view.k;ctx.strokeStyle="rgba(120,140,160,.26)";ctx.beginPath();
    edges.forEach(e=>{ctx.moveTo(e.s.x,e.s.y);ctx.lineTo(e.t.x,e.t.y);});ctx.stroke();
    nodes.forEach(n=>{const r=radius(n);ctx.beginPath();ctx.arc(n.x,n.y,r,0,6.2832);ctx.fillStyle=TYPE_COLORS[n.type]||"#999";ctx.fill();
      if(RISK[n.risk]){ctx.lineWidth=2/view.k;ctx.strokeStyle=RISK[n.risk];ctx.stroke();}
      if(view.k>.85&&n.type!=="action"&&n.type!=="resource"){ctx.fillStyle="rgba(233,238,244,.85)";ctx.font=`${10/view.k}px sans-serif`;ctx.fillText(n.label,n.x+r+1.5,n.y+3/view.k);}});
    ctx.restore();
  }
  let looping=false;
  function loop(){let n=0;const r=()=>{for(let s=0;s<3;s++)tick();draw();if(alpha>.025&&n++<2000)requestAnimationFrame(r);else{looping=false;draw();}};if(!looping){looping=true;requestAnimationFrame(r);}}
  function reheat(a){alpha=Math.max(alpha,a||.3);loop();}
  resize();fit();loop();
  window.addEventListener("resize",()=>{resize();draw();});
  // unified pointer (mouse+touch)
  function pt(ev){const r=canvas.getBoundingClientRect();const t=ev.touches?ev.touches[0]:ev;return{x:t.clientX-r.left,y:t.clientY-r.top};}
  function toWorld(p){return{x:(p.x-view.x)/view.k,y:(p.y-view.y)/view.k};}
  function pick(w){let best=null,bd=1e9;nodes.forEach(n=>{const dx=n.x-w.x,dy=n.y-w.y,d=dx*dx+dy*dy,r=radius(n)+6;if(d<r*r&&d<bd){bd=d;best=n;}});return best;}
  let drag=null,pan=null,moved=false,pinch=null;
  function down(p){const w=toWorld(p);const n=pick(w);moved=false;if(n){drag=n;n.fixed=true;}else{pan={x:p.x,y:p.y,ox:view.x,oy:view.y};}}
  function move(p){if(drag){const w=toWorld(p);drag.x=w.x;drag.y=w.y;drag.vx=drag.vy=0;moved=true;reheat(.3);}else if(pan){view.x=pan.ox+(p.x-pan.x);view.y=pan.oy+(p.y-pan.y);moved=true;draw();}}
  function up(p){if(drag){drag.fixed=false;if(!moved&&p)showDetail(drag);drag=null;}else if(pan){if(!moved&&p){const n=pick(toWorld(p));n?showDetail(n):hideDetail();}pan=null;}}
  canvas.addEventListener("mousedown",e=>{down(pt(e));});
  window.addEventListener("mousemove",e=>{if(drag||pan)move(pt(e));});
  window.addEventListener("mouseup",e=>{if(drag||pan)up(pt(e));});
  canvas.addEventListener("wheel",e=>{e.preventDefault();const r=canvas.getBoundingClientRect();zoom(e.deltaY<0?1.1:.9,e.clientX-r.left,e.clientY-r.top);},{passive:false});
  function zoom(f,mx,my){const wx=(mx-view.x)/view.k,wy=(my-view.y)/view.k;view.k=Math.min(6,Math.max(.15,view.k*f));view.x=mx-wx*view.k;view.y=my-wy*view.k;draw();}
  canvas.addEventListener("touchstart",e=>{e.preventDefault();if(e.touches.length===2){const r=canvas.getBoundingClientRect();const a=e.touches[0],b=e.touches[1];pinch={d:Math.hypot(a.clientX-b.clientX,a.clientY-b.clientY),mx:(a.clientX+b.clientX)/2-r.left,my:(a.clientY+b.clientY)/2-r.top};drag=pan=null;}else down(pt(e));},{passive:false});
  canvas.addEventListener("touchmove",e=>{e.preventDefault();if(pinch&&e.touches.length===2){const a=e.touches[0],b=e.touches[1];const nd=Math.hypot(a.clientX-b.clientX,a.clientY-b.clientY);zoom(nd/pinch.d,pinch.mx,pinch.my);pinch.d=nd;}else move(pt(e));},{passive:false});
  canvas.addEventListener("touchend",e=>{
    e.preventDefault();
    if(pinch){pinch=null;return;}
    let p=null;
    if(e.changedTouches&&e.changedTouches.length){const t=e.changedTouches[0];const r=canvas.getBoundingClientRect();p={x:t.clientX-r.left,y:t.clientY-r.top};}
    up(p);
  },{passive:false});
  canvas.addEventListener("dblclick",()=>{nodes.forEach(n=>n.fixed=false);alpha=1;loop();setTimeout(()=>{fit();draw();},420);});
  function showDetail(n){const d=$("detail");d.style.display="block";let h=`<h4>${esc(n.label)}</h4><div class="k">${esc(n.type)}</div>`;
    const skip={body:1,body_excerpt:1,risk:1};
    Object.entries(n.props||{}).forEach(([k,v])=>{if(skip[k]||v==null||v===""||(Array.isArray(v)&&!v.length))return;h+=`<div style="margin-top:6px"><span class="k">${esc(k)}:</span> ${esc(Array.isArray(v)?v.join(", "):v)}</div>`;});
    if(n.risk)h+=`<div style="margin-top:7px">${pill(n.risk)}</div>`;d.innerHTML=h;}
  function hideDetail(){$("detail").style.display="none";}
}
</script>
</body>
</html>"""
