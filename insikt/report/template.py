"""The single-file HTML report shell — professional, mobile-first, offline.

Design language: restrained, near-monochrome surfaces with a single accent;
semantic colour only for severity; real type scale with tabular numbers;
hairline borders, no gradients, no emoji (subtle stroke icons instead). The
"capability vs. action" distinction is built into the layout and copy so a
capability can't be misread as an incident.

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
    --bg:#0b0d11; --surface:#101319; --surface-2:#151922; --raise:#1b2029;
    --line:#222835; --line-2:#2c3340;
    --fg:#e9edf2; --muted:#9aa3b0; --subtle:#6b7280;
    --accent:#e0b54a;
    --critical:#f0616d; --high:#f0883e; --medium:#dcad3a; --low:#56b870; --info:#7d8694;
    --cap:#5aa2f0; --cfg:#dcad3a; --alert:#f0616d;
    --r:11px; --r-sm:8px;
    --sp:16px;
    --shadow:0 1px 2px rgba(0,0,0,.25);
  }
  *{box-sizing:border-box}
  html{-webkit-text-size-adjust:100%}
  html,body{overflow-x:hidden;max-width:100%}
  body{margin:0;background:var(--bg);color:var(--fg);
    font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Inter,Helvetica,Arial,sans-serif;
    -webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility;
    padding-bottom:calc(48px + env(safe-area-inset-bottom));font-variant-ligatures:none}
  .num,.stat .n,td.n,th.n{font-variant-numeric:tabular-nums;font-feature-settings:"tnum" 1}
  a{color:var(--cap);text-decoration:none}
  ::selection{background:rgba(224,181,74,.25)}
  .wrap{max-width:1040px;margin:0 auto;padding:0 20px}
  .ico{width:15px;height:15px;flex:0 0 auto}
  svg.ico{display:inline-block;vertical-align:-2px}

  /* top bar */
  .topbar{position:sticky;top:0;z-index:30;background:rgba(11,13,17,.85);
    backdrop-filter:saturate(140%) blur(12px);border-bottom:1px solid var(--line)}
  header .wrap{display:flex;align-items:center;gap:12px;flex-wrap:wrap;padding-top:13px;padding-bottom:13px}
  .brand{display:flex;align-items:center;gap:8px;font-size:15px;font-weight:650;letter-spacing:-.01em;white-space:nowrap}
  .brand .mark{width:9px;height:9px;border-radius:50%;background:var(--accent);box-shadow:0 0 0 3px rgba(224,181,74,.16)}
  .hmeta{color:var(--muted);font-size:12.5px;letter-spacing:.01em;flex:1;min-width:140px}
  .chip{margin-left:auto;display:inline-flex;align-items:center;gap:6px;font-weight:600;font-size:12px;
    padding:5px 11px;border-radius:999px;border:1px solid transparent;white-space:nowrap}
  .chip .dot{width:7px;height:7px;border-radius:50%}
  .chip.ok{background:rgba(86,184,112,.1);color:var(--low);border-color:rgba(86,184,112,.25)}
  .chip.ok .dot{background:var(--low)}
  .chip.warn{background:rgba(240,97,109,.1);color:var(--critical);border-color:rgba(240,97,109,.28)}
  .chip.warn .dot{background:var(--critical)}

  nav{border-top:1px solid var(--line);overflow-x:auto;-webkit-overflow-scrolling:touch;scrollbar-width:none}
  nav::-webkit-scrollbar{display:none}
  nav .wrap{display:flex;gap:2px;padding-top:0;padding-bottom:0}
  nav button{flex:0 0 auto;background:none;border:none;color:var(--muted);
    padding:12px 13px;min-height:44px;font-size:13.5px;font-weight:550;cursor:pointer;position:relative;
    letter-spacing:-.005em;white-space:nowrap;transition:color .12s}
  nav button:hover{color:var(--fg)}
  nav button.active{color:var(--fg)}
  nav button.active::after{content:"";position:absolute;left:13px;right:13px;bottom:-1px;height:2px;
    background:var(--accent);border-radius:2px 2px 0 0}

  .banner{font-size:13px;border-bottom:1px solid transparent}
  .banner .wrap{display:flex;gap:9px;align-items:flex-start;padding:10px 20px}
  .banner .ico{margin-top:2px}
  .banner.warn{background:#1c1808;color:#e9cf86;border-bottom-color:#352c10}
  .banner.note{background:#0a1820;color:#9bd2e3;border-bottom-color:#163240}

  main{padding:24px 0 40px}
  section{display:none;animation:fade .16s ease}
  section.active{display:block}
  @keyframes fade{from{opacity:0;transform:translateY(2px)}to{opacity:1;transform:none}}
  .h2{display:flex;align-items:center;gap:8px;font-size:11.5px;text-transform:uppercase;
    letter-spacing:.08em;color:var(--subtle);font-weight:650;margin:28px 0 12px}
  .h2 .ico{color:var(--subtle);width:14px;height:14px}
  .h2:first-child{margin-top:2px}

  /* headline */
  .headline{display:flex;gap:14px;background:var(--surface);border:1px solid var(--line);
    border-radius:var(--r);padding:18px 18px;margin-bottom:18px}
  .headline .hi{width:34px;height:34px;border-radius:9px;display:flex;align-items:center;justify-content:center;flex:0 0 auto}
  .headline .hi .ico{width:19px;height:19px}
  .headline.good .hi{background:rgba(86,184,112,.12);color:var(--low)}
  .headline.warn .hi{background:rgba(240,136,62,.12);color:var(--high)}
  .headline .big{font-size:16px;font-weight:600;letter-spacing:-.01em}
  .headline .sub{color:var(--muted);font-size:13.5px;margin-top:6px;line-height:1.6}
  .headline b{color:var(--fg);font-weight:600}

  /* stat tiles */
  .stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(110px,100%),1fr));gap:10px}
  .stat{background:var(--surface);border:1px solid var(--line);border-radius:var(--r-sm);padding:14px 15px}
  .stat .n{font-size:22px;font-weight:680;letter-spacing:-.02em;line-height:1.1}
  .stat .l{color:var(--muted);font-size:12px;margin-top:3px}

  /* cards */
  .card{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);padding:var(--sp);margin-bottom:12px}
  .card.row{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
  .ct{display:flex;align-items:center;gap:9px;flex-wrap:wrap}
  .title{font-weight:600;font-size:15px;letter-spacing:-.01em}
  .meta{color:var(--subtle);font-size:12.5px}
  .spacer{margin-left:auto}
  .kv{display:flex;gap:10px;margin-top:9px;font-size:13px}
  .kv .k{color:var(--subtle);min-width:74px;flex:0 0 auto;font-size:12px;padding-top:1px}
  .kv .v{flex:1;min-width:0;word-break:break-word;display:flex;flex-wrap:wrap;gap:5px;align-items:center}

  /* pills / tags */
  .pill{display:inline-flex;align-items:center;gap:5px;padding:2px 9px;border-radius:999px;
    font-size:11px;font-weight:600;line-height:1.7;white-space:nowrap;text-transform:capitalize}
  .pill .dot{width:6px;height:6px;border-radius:50%}
  .sev-critical{background:rgba(240,97,109,.13);color:var(--critical)} .sev-critical .dot{background:var(--critical)}
  .sev-high{background:rgba(240,136,62,.13);color:var(--high)} .sev-high .dot{background:var(--high)}
  .sev-medium{background:rgba(220,173,58,.13);color:var(--medium)} .sev-medium .dot{background:var(--medium)}
  .sev-low{background:rgba(86,184,112,.13);color:var(--low)} .sev-low .dot{background:var(--low)}
  .sev-info{background:rgba(125,134,148,.15);color:#aab2be} .sev-info .dot{background:var(--info)}
  .tag{display:inline-block;background:var(--surface-2);color:var(--muted);border:1px solid var(--line-2);
    border-radius:6px;padding:1px 7px;font-size:11.5px;line-height:1.7;white-space:nowrap}
  .tag.self{background:rgba(224,181,74,.1);color:var(--accent);border-color:rgba(224,181,74,.28)}
  .tag.warn{background:rgba(240,97,109,.1);color:var(--critical);border-color:rgba(240,97,109,.28)}
  .tag.k-capability{color:var(--cap);border-color:rgba(90,162,240,.35);background:rgba(90,162,240,.08)}
  .tag.k-exposure{color:var(--cfg);border-color:rgba(220,173,58,.32);background:rgba(220,173,58,.08)}
  .tag.k-alert{color:var(--alert);border-color:rgba(240,97,109,.4);background:rgba(240,97,109,.1)}
  .muted{color:var(--muted)} .subtle{color:var(--subtle)}
  .empty{color:var(--muted);padding:22px;text-align:center;background:var(--surface);border:1px solid var(--line);border-radius:var(--r);font-size:13.5px}

  /* callout */
  .callout{display:flex;gap:11px;background:var(--surface);border:1px solid var(--line);
    border-radius:var(--r);padding:13px 15px;margin-bottom:18px;font-size:13px;color:var(--muted);line-height:1.6}
  .callout .ico{margin-top:2px;color:var(--subtle);width:16px;height:16px}
  .callout b{color:var(--fg);font-weight:600} .callout .lead{color:var(--fg)}

  /* severity groups */
  details.grp{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);margin-bottom:10px;overflow:hidden}
  details.grp>summary{list-style:none;cursor:pointer;padding:13px var(--sp);display:flex;align-items:center;gap:10px;
    font-weight:600;font-size:13.5px;user-select:none}
  details.grp>summary::-webkit-details-marker{display:none}
  details.grp>summary .gcount{color:var(--subtle);font-weight:500}
  details.grp>summary .chev{margin-left:auto;color:var(--subtle);transition:transform .15s}
  details.grp[open]>summary .chev{transform:rotate(90deg)}
  .finding{border-top:1px solid var(--line);padding:14px var(--sp);display:flex;gap:11px}
  .finding .sd{width:7px;height:7px;border-radius:50%;margin-top:6px;flex:0 0 auto}
  .finding .fbody{flex:1;min-width:0}
  .finding .ft{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
  .finding .fname{font-weight:600;font-size:14px;letter-spacing:-.005em}
  .finding .fd{color:var(--muted);font-size:13px;margin-top:5px;line-height:1.55}
  .finding .ff{margin-top:8px;display:flex;flex-wrap:wrap;gap:5px}

  /* timeline */
  .ev{display:flex;gap:14px;padding:13px 0;border-bottom:1px solid var(--line)}
  .ev:last-child{border-bottom:none}
  .ev .when{color:var(--subtle);font-size:12px;flex:0 0 96px;white-space:nowrap;padding-top:2px;font-variant-numeric:tabular-nums}
  .ev .b{flex:1;min-width:0}
  .ev .b .s{font-size:13.5px;display:flex;align-items:center;gap:7px;flex-wrap:wrap}
  .ev .b .m{color:var(--subtle);font-size:12px;margin-top:4px}
  .ev.drift{background:rgba(224,181,74,.04);margin:0 -10px;padding:13px 10px;border-radius:var(--r-sm)}

  /* table */
  .panel{border:1px solid var(--line);border-radius:var(--r);overflow:hidden}
  .scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
  table{width:100%;border-collapse:collapse;min-width:420px}
  th,td{text-align:left;padding:12px 15px;border-bottom:1px solid var(--line);font-size:13.5px;white-space:nowrap}
  td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
  th{color:var(--subtle);font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.06em;background:var(--surface-2)}
  tbody tr:last-child td{border-bottom:none}
  tbody tr:hover td{background:var(--surface-2)}

  .filters{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px}
  select{background:var(--surface);color:var(--fg);border:1px solid var(--line-2);border-radius:var(--r-sm);
    padding:9px 32px 9px 12px;font-size:13.5px;min-height:40px;cursor:pointer;
    appearance:none;background-image:url("data:image/svg+xml,%3Csvg width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%239aa3b0' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E");
    background-repeat:no-repeat;background-position:right 11px center}

  /* graph */
  #graphwrap{position:relative;height:74vh;min-height:440px;border:1px solid var(--line);
    border-radius:var(--r);overflow:hidden;background:radial-gradient(120% 90% at 50% 30%,#12161d 0%,#0a0c10 70%);touch-action:none}
  #graph{width:100%;height:100%;display:block;cursor:grab}
  #legend{position:absolute;top:12px;left:12px;background:rgba(11,13,17,.78);border:1px solid var(--line);
    border-radius:var(--r-sm);padding:9px 11px;font-size:11px;color:var(--muted);max-width:46%}
  #legend .row{display:flex;align-items:center;gap:8px;margin:3px 0}
  #legend .sw{width:9px;height:9px;border-radius:50%;flex:0 0 auto}
  #detail{position:absolute;top:12px;right:12px;width:min(286px,72vw);max-height:calc(74vh - 24px);
    overflow:auto;background:rgba(13,16,21,.97);border:1px solid var(--line-2);border-radius:var(--r-sm);
    padding:14px;font-size:12.5px;display:none;box-shadow:0 8px 28px rgba(0,0,0,.45)}
  #detail h4{margin:0 0 8px;font-size:14px}
  #detail .k{color:var(--subtle)}
  #ghelp{position:absolute;bottom:11px;left:12px;color:var(--subtle);font-size:11px}
  code{background:var(--surface-2);padding:1px 6px;border-radius:5px;font-size:12px;word-break:break-word}

  @media (max-width:560px){
    .wrap{padding:0 14px}
    header .wrap{gap:7px 10px}
    .hmeta{flex-basis:100%;order:3}
    .chip{margin-left:auto}
    .banner .wrap{padding:10px 14px}
    .stats{grid-template-columns:repeat(2,1fr)}
    .stat .n{font-size:19px}
    .ev .when{flex-basis:78px}
    .headline{padding:15px}
  }
</style>
</head>
<body>
<div class="topbar">
  <header><div class="wrap">
    <span class="brand"><span class="mark"></span>Insikt</span>
    <span class="hmeta num" id="hmeta"></span>
    <span class="chip" id="chip"></span>
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
      <div id="ghelp">drag &middot; scroll / pinch to zoom &middot; tap a node</div>
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
const DATA=JSON.parse(document.getElementById("insikt-data").textContent);
const TYPE_COLORS={agent:"#e0b54a",skill:"#5aa2f0",tool:"#9b8cff",model:"#4fd0c0",
  connector:"#f0883e",resource:"#8d99ae",credential_ref:"#d272c0",action:"#5d6b7d"};
const SEV=["critical","high","medium","low","info"];
const esc=s=>(s==null?"":String(s)).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const pill=s=>`<span class="pill sev-${esc(s||"info")}"><span class="dot"></span>${esc(s||"info")}</span>`;
const tpill=t=>`<span class="pill sev-info"><span class="dot"></span>${esc(t)}</span>`;
const $=id=>document.getElementById(id);
const num=n=>`<span class="num">${(n==null?0:n).toLocaleString()}</span>`;
const I={
  check:'<path d="M20 6 9 17l-5-5"/>',
  alert:'<path d="M10.9 3.6 1.8 18.5A1.5 1.5 0 0 0 3.1 21h17.8a1.5 1.5 0 0 0 1.3-2.5L13.1 3.6a1.5 1.5 0 0 0-2.2 0Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
  info:'<circle cx="12" cy="12" r="9"/><path d="M12 11.5v4.5"/><path d="M12 8h.01"/>',
  shield:'<path d="M12 21s7.5-3.6 7.5-9.4V5.3L12 2.6 4.5 5.3v6.3C4.5 17.4 12 21 12 21Z"/>',
  clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7.5V12l3 2"/>',
  layers:'<path d="M12 2.6 2.6 7 12 11.4 21.4 7 12 2.6Z"/><path d="m2.6 16.5 9.4 4.4 9.4-4.4"/><path d="m2.6 11.7 9.4 4.4 9.4-4.4"/>',
  chart:'<path d="M3.5 3.5v17h17"/><path d="m7 14 3.2-3.4 3 2.6L21 7"/>',
  branch:'<circle cx="6.5" cy="6" r="2.3"/><circle cx="6.5" cy="18" r="2.3"/><circle cx="17.5" cy="7.2" r="2.3"/><path d="M6.5 8.3v7.4"/><path d="M17.5 9.5c0 4.2-4.4 4-7 5.4"/>',
  cog:'<circle cx="12" cy="12" r="3"/><path d="M19 12a7 7 0 0 0-.1-1.3l2-1.5-2-3.4-2.3.9a7 7 0 0 0-2.2-1.3L14 2h-4l-.4 2.4a7 7 0 0 0-2.2 1.3l-2.3-.9-2 3.4 2 1.5A7 7 0 0 0 5 12a7 7 0 0 0 .1 1.3l-2 1.5 2 3.4 2.3-.9a7 7 0 0 0 2.2 1.3L10 22h4l.4-2.4a7 7 0 0 0 2.2-1.3l2.3.9 2-3.4-2-1.5A7 7 0 0 0 19 12Z"/>',
};
const ico=(n,extra)=>`<svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"${extra||""}>${I[n]||""}</svg>`;
const fmtTs=t=>(t||"").replace("T"," ").replace(/[.+Z].*/,"");

function fclass(id){const p=String(id).split(":")[0];
  if(p==="fp"||p==="drift")return{k:"alert",label:"alert"};
  if(p==="posture"||p==="stranger"||p==="exposure"||p==="overlay")return{k:"exposure",label:"config"};
  return{k:"capability",label:"capability"};}
const SKILLUSE={};
(DATA.capability.agents||[]).forEach(a=>(a.skills||[]).forEach(s=>{SKILLUSE[s.id]={u:s.use_count};}));
function useBadge(id){const x=SKILLUSE[id];if(!x)return"";
  if(x.u===0)return`<span class="tag">never used</span>`;
  if(x.u>0)return`<span class="tag">used ${x.u}&times;</span>`;return"";}

/* header + banners */
(function(){
  const m=DATA.meta,s=DATA.summary,bits=[];
  if(m.frameworks)bits.push(esc(m.frameworks.join(", ")));
  if(m.host)bits.push("host "+esc(m.host));
  if(m.scan_ts)bits.push(esc(fmtTs(m.scan_ts)));
  $("hmeta").textContent=bits.join("  ·  ");
  const need=(s.risk||[]).filter(r=>r.worst==="critical"||r.worst==="high").length;
  const c=$("chip");
  if(need){c.className="chip warn";c.innerHTML=`<span class="dot"></span>${need} agent${need>1?"s":""} to review`;}
  else{c.className="chip ok";c.innerHTML=`<span class="dot"></span>no high-risk findings`;}
  const b=$("banners");
  if(m.partial)b.insertAdjacentHTML("beforeend",`<div class="banner warn"><div class="wrap">${ico("alert")}<div>Partial scan — ${esc((m.partial_reasons||[]).join("; "))||"some sources unreadable"}. Figures are a lower bound.</div></div></div>`);
  if(DATA.backfill_note)b.insertAdjacentHTML("beforeend",`<div class="banner note"><div class="wrap">${ico("clock")}<div>${esc(DATA.backfill_note)}</div></div></div>`);
})();

/* tabs */
const TABS=[["overview","Overview"],["graph","Graph"],["capability","Capabilities"],
  ["timeline","Timeline"],["cost","Models & cost"],["hygiene","Hygiene"],["diff","Diff"]];
(function(){const nav=$("nav");
  TABS.forEach(([id,label],i)=>{if(id==="diff"&&!DATA.diff)return;
    const b=document.createElement("button");b.textContent=label;b.dataset.tab=id;
    if(i===0)b.classList.add("active");b.onclick=()=>activate(id);nav.appendChild(b);});})();
function activate(id){
  document.querySelectorAll("nav button").forEach(b=>b.classList.toggle("active",b.dataset.tab===id));
  document.querySelectorAll("main section").forEach(s=>s.classList.remove("active"));
  $("tab-"+id).classList.add("active");window.scrollTo(0,0);
  if(id==="graph")ensureGraph();}

/* overview */
(function(){
  const s=DATA.summary,root=$("tab-overview");
  const acts=DATA.timeline.count||0;
  const neverUsed=Object.values(SKILLUSE).filter(x=>x.u===0).length;
  const worst=(DATA.hygiene.findings||[]).filter(f=>fclass(f.id).k==="alert"||f.severity==="critical"||f.severity==="high");
  let head;
  if(!worst.length){
    head=`<div class="headline good"><div class="hi">${ico("check")}</div><div>
      <div class="big">No incidents in the action log</div>
      <div class="sub">Reconstructed <b>${num(acts)}</b> action(s); no verified incidents found.
      The Hygiene tab lists <b>capabilities</b> (what installed skills could do), not events.${neverUsed?` <b>${neverUsed}</b> installed skill(s) have never been used.`:""}</div></div></div>`;
  }else{
    head=`<div class="headline warn"><div class="hi">${ico("alert")}</div><div>
      <div class="big">${worst.length} finding(s) to review</div>
      <div class="sub">Mostly capability &amp; exposure, not confirmed incidents. Open <b>Hygiene</b> for detail and <b>Timeline</b> for what actually ran.</div></div></div>`;
  }
  let h=head;
  const tiles=[["agents","Agents"],["skills","Skills"],["self_authored_skills","Self-authored"],
    ["connectors","Connectors"],["models","Models"],["credential_refs","Credentials"],["actions","Actions"],["total_tokens","Tokens"]];
  h+=`<div class="stats">`+tiles.map(([k,l])=>`<div class="stat"><div class="n">${num(s[k])}</div><div class="l">${l}</div></div>`).join("")+`</div>`;
  h+=`<div class="h2">${ico("shield")} Risk by agent</div>`;
  if(!(s.risk||[]).length)h+=`<div class="empty">No agents scored.</div>`;
  else s.risk.forEach(r=>{
    h+=`<div class="card"><div class="ct"><span class="title">${esc(r.label)}</span>${pill(r.worst)}<span class="spacer meta">score ${esc(r.score)}</span></div>
      <div class="kv"><span class="k">top factors</span><span class="v muted">${(r.top_findings||[]).map(esc).join(" · ")||"none"}</span></div></div>`;
  });
  root.innerHTML=h;
})();

/* capabilities */
(function(){
  const root=$("tab-capability"),cap=DATA.capability;
  let h=`<div class="callout">${ico("layers")}<div><span class="lead"><b>Capabilities</b> are what each skill could do</span> — installed and available, not necessarily used. "never used" means it has never been invoked. See <b>Timeline</b> for what actually ran.</div></div>`;
  if(!cap.agents.length){root.innerHTML=h+`<div class="empty">No agents found.</div>`;return;}
  cap.agents.forEach(a=>{
    h+=`<div class="h2">${ico("cog")} ${esc(a.label)} ${a.risk?pill(a.risk):""}</div>`;
    const meta=[a.framework,a.version,a.host&&("host "+a.host),a.memory_items!=null&&(a.memory_items+" memories")].filter(Boolean).map(esc).join("  ·  ");
    h+=`<div class="card"><div class="meta">${meta}</div>`;
    const conns=(a.connectors||[]).map(c=>`<span class="tag${c.accepts_strangers?" warn":""}">${esc(c.platform)}${c.accepts_strangers?" · no allowlist":""}</span>`).join("")||'<span class="subtle">none</span>';
    const models=(a.models||[]).map(m=>`<span class="tag">${esc(m.provider)}/${esc(m.model_name)}</span>`).join("")||'<span class="subtle">none</span>';
    h+=`<div class="kv"><span class="k">connectors</span><span class="v">${conns}</span></div>`;
    h+=`<div class="kv"><span class="k">models</span><span class="v">${models}</span></div>`;
    if((a.mcp_servers||[]).length)h+=`<div class="kv"><span class="k">MCP</span><span class="v">${a.mcp_servers.map(x=>`<span class="tag">${esc(x.name)}</span>`).join("")}</span></div>`;
    h+=`</div>`;
    (a.skills||[]).forEach(sk=>{
      const badges=[sk.self_authored?'<span class="tag self">self-authored</span>':"",
        sk.use_count===0?'<span class="tag">never used</span>':(sk.use_count>0?`<span class="tag">used ${sk.use_count}&times;</span>`:""),
        sk.risk?pill(sk.risk):""].join("");
      h+=`<div class="card"><div class="ct"><span class="title">${esc(sk.name)}</span>${badges}<span class="spacer meta">${esc(sk.kind||sk.source||"")}</span></div>`;
      if((sk.tools||[]).length)h+=`<div class="kv"><span class="k">can use</span><span class="v">${sk.tools.map(t=>`<span class="tag">${esc(t)}</span>`).join("")}</span></div>`;
      if((sk.reaches||[]).length)h+=`<div class="kv"><span class="k">can reach</span><span class="v">${sk.reaches.map(r=>`<span class="tag">${esc(r.value)}</span>`).join("")}</span></div>`;
      if((sk.credential_reads||[]).length)h+=`<div class="kv"><span class="k">reads</span><span class="v">${sk.credential_reads.map(c=>`<span class="tag">${esc(c)}</span>`).join("")}</span></div>`;
      h+=`</div>`;
    });
  });
  root.innerHTML=h;
})();

/* timeline */
(function(){
  const root=$("tab-timeline"),tl=DATA.timeline;
  const types=[...new Set(tl.actions.map(a=>a.type))].sort();
  const agents=[...new Set(tl.actions.map(a=>a.agent).filter(Boolean))].sort();
  root.innerHTML=`<div class="callout">${ico("clock")}<div><span class="lead"><b>What actually ran</b></span> — reconstructed from the agents' own logs. ${esc(tl.count)} action(s).</div></div>
    <div class="filters"><select id="f-type"><option value="">All types</option>${types.map(t=>`<option>${esc(t)}</option>`).join("")}</select>
    ${agents.length>1?`<select id="f-agent"><option value="">All agents</option>${agents.map(a=>`<option>${esc(a)}</option>`).join("")}</select>`:""}</div>
    <div id="tl-body"></div>`;
  function draw(){
    const ft=$("f-type").value,fa=($("f-agent")||{}).value||"";
    const rows=tl.actions.filter(a=>(!ft||a.type===ft)&&(!fa||a.agent===fa));
    if(!rows.length){$("tl-body").innerHTML=`<div class="empty">No actions in this view.</div>`;return;}
    let h=`<div class="card">`;
    rows.forEach(a=>{
      const drift=a.type==="skill_written",cost=a.cost!=null?` · $${Number(a.cost).toFixed(4)}`:"",tok=a.tokens?` · ${a.tokens.toLocaleString()} tok`:"";
      const meta=[a.agent,a.skill&&("via "+a.skill),a.model,a.connector&&("→ "+a.connector),a.resource&&("→ "+a.resource)].filter(Boolean).map(esc).join("  ·  ");
      h+=`<div class="ev${drift?" drift":""}"><div class="when">${esc(fmtTs(a.ts))||"—"}</div><div class="b">
        <div class="s">${tpill(a.type)} <span>${esc(a.summary)}</span></div>
        <div class="m">${meta}${esc(tok)}${esc(cost)} · <span class="subtle">${esc(a.source||"")}</span></div></div></div>`;
    });
    h+=`</div>`;
    if(tl.truncated)h+=`<div class="muted" style="margin-top:10px;font-size:12.5px">Showing the most recent ${tl.actions.length}.</div>`;
    $("tl-body").innerHTML=h;
  }
  $("f-type").onchange=draw;if($("f-agent"))$("f-agent").onchange=draw;draw();
})();

/* models & cost */
(function(){
  const root=$("tab-cost"),c=DATA.cost;
  let h=`<div class="stats"><div class="stat"><div class="n">$${(c.total_cost||0).toFixed(4)}</div><div class="l">Recorded spend</div></div>
    <div class="stat"><div class="n">${num(c.total_tokens)}</div><div class="l">Recorded tokens</div></div></div>`;
  const role=m=>[m.default?'<span class="tag self">default</span>':"",(m.configured&&!m.default)?'<span class="tag">configured</span>':"",(m.used||m.calls)?'<span class="tag">used</span>':'<span class="tag">unused</span>'].join(" ");
  h+=`<div class="h2">${ico("chart")} Models</div>`;
  h+=(c.models||[]).length?`<div class="panel scroll"><table><thead><tr><th>Model</th><th>Role</th><th class="n">Calls</th><th class="n">Tokens</th><th class="n">Cost</th></tr></thead><tbody>`+
    c.models.map(m=>`<tr><td>${esc(m.model)}</td><td>${role(m)}</td><td class="n">${(m.calls||0).toLocaleString()}</td><td class="n">${(m.tokens||0).toLocaleString()}</td><td class="n">$${(m.cost||0).toFixed(4)}</td></tr>`).join("")+`</tbody></table></div>`
    :`<div class="empty">No models configured or used.</div>`;
  if(c.total_tokens>0&&c.total_cost===0)h+=`<div class="muted" style="margin-top:10px;font-size:12.5px">Token volume is recorded but per-call cost isn't — some frameworks don't persist cost. A model with 0 calls is configured but had no usage recorded.</div>`;
  root.innerHTML=h;
})();

/* hygiene */
(function(){
  const root=$("tab-hygiene"),hy=DATA.hygiene;
  const fs=(hy.findings||[]).slice().sort((a,b)=>SEV.indexOf(a.severity)-SEV.indexOf(b.severity));
  let h=`<div class="callout">${ico("shield")}<div><span class="lead"><b>Capabilities &amp; configuration — not incidents.</b></span>
    <span class="tag k-capability">capability</span> what a skill could do ·
    <span class="tag k-exposure">config</span> a setting worth knowing ·
    <span class="tag k-alert">alert</span> a verified problem.
    Nothing here means it happened — the <b>Timeline</b> shows that.</div></div>`;
  if(!fs.length){root.innerHTML=h+`<div class="empty">No hygiene findings.</div>`;return;}
  const counts={};fs.forEach(f=>counts[f.severity]=(counts[f.severity]||0)+1);
  h+=`<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px">`+SEV.filter(s=>counts[s]).map(s=>`<span class="pill sev-${s}"><span class="dot"></span>${counts[s]} ${s}</span>`).join("")+`</div>`;
  const SEVC={critical:"var(--critical)",high:"var(--high)",medium:"var(--medium)",low:"var(--low)",info:"var(--info)"};
  SEV.forEach(sv=>{const g=fs.filter(f=>f.severity===sv);if(!g.length)return;
    const open=(sv==="critical"||sv==="high")?" open":"";
    h+=`<details class="grp"${open}><summary>${pill(sv)}<span class="gcount">${g.length} finding${g.length>1?"s":""}</span><span class="chev">›</span></summary>`;
    g.forEach(f=>{const cl=fclass(f.id);
      h+=`<div class="finding"><span class="sd" style="background:${SEVC[sv]}"></span><div class="fbody">
        <div class="ft"><span class="fname">${esc(f.title)}</span><span class="tag k-${cl.k}">${cl.label}</span>${useBadge(f.node_id)}</div>
        <div class="fd">${esc(f.detail)}</div>
        ${(f.factors||[]).length?`<div class="ff">${f.factors.map(x=>`<span class="tag">${esc(x)}</span>`).join("")}</div>`:""}</div></div>`;});
    h+=`</details>`;});
  root.innerHTML=h;
})();

/* diff */
(function(){
  if(!DATA.diff)return;const d=DATA.diff,root=$("tab-diff");
  const list=(t,arr,fmt)=>`<div class="h2">${esc(t)} <span class="subtle">(${arr.length})</span></div>`+(arr.length?`<div class="card">`+arr.map(fmt).join('<div style="height:6px"></div>')+`</div>`:`<div class="empty">none</div>`);
  let h=`<div class="callout">${ico("branch")}<div>Since snapshot #${esc(d.since.id)} → #${esc(d.to.id)}: <b>${esc(d.summary)}</b></div></div>`;
  h+=list("Capability drift",d.capability_drift||[],x=>`${esc(x.skill)} → gained <code>${esc(x.gained_tool)}</code>`);
  h+=list("New skills",d.new_skills||[],x=>esc(x.label));
  h+=list("New credential reads",d.new_credential_reads||[],x=>`${esc(x.skill)} reads ${esc(x.credential)}`);
  h+=list("New connectors",d.new_connectors||[],x=>esc(x.label));
  h+=list("New reachable hosts",d.new_reachable_hosts||[],x=>esc(x.label));
  h+=list("Removed skills",d.removed_skills||[],x=>esc(x.label));
  root.innerHTML=h;
})();

/* graph */
let graphReady=false;
function ensureGraph(){if(graphReady)return;graphReady=true;initGraph();}
function initGraph(){
  const canvas=$("graph"),ctx=canvas.getContext("2d");
  const RISK={critical:"#f0616d",high:"#f0883e",medium:"#dcad3a"};
  $("legend").innerHTML=Object.entries(TYPE_COLORS).map(([t,c])=>`<div class="row"><span class="sw" style="background:${c}"></span>${t.replace("_"," ")}</div>`).join("");
  const nmap=new Map();
  const nodes=DATA.graph.nodes.map((n,i)=>{const a=i*2.399963,r=40+8*Math.sqrt(i);const o={...n,x:Math.cos(a)*r,y:Math.sin(a)*r,vx:0,vy:0};nmap.set(n.id,o);return o;});
  const edges=DATA.graph.edges.filter(e=>nmap.has(e.src)&&nmap.has(e.dst)).map(e=>({s:nmap.get(e.src),t:nmap.get(e.dst)}));
  const deg=new Map();edges.forEach(e=>{deg.set(e.s.id,(deg.get(e.s.id)||0)+1);deg.set(e.t.id,(deg.get(e.t.id)||0)+1);});
  const radius=n=>n.type==="agent"?12:n.type==="action"?3.2:6+Math.min(4,(deg.get(n.id)||0));
  let view={k:1,x:0,y:0},alpha=1,dpr=Math.max(1,window.devicePixelRatio||1);
  function tick(){const rep=2200,spr=.02,rest=46,cen=.012;
    for(let i=0;i<nodes.length;i++){const a=nodes[i];
      for(let j=i+1;j<nodes.length;j++){const b=nodes[j];let dx=a.x-b.x,dy=a.y-b.y,d2=dx*dx+dy*dy;if(d2<.01)d2=.01;
        const f=rep/d2,d=Math.sqrt(d2),fx=f*dx/d,fy=f*dy/d;a.vx+=fx;a.vy+=fy;b.vx-=fx;b.vy-=fy;}
      a.vx-=a.x*cen;a.vy-=a.y*cen;}
    edges.forEach(e=>{let dx=e.t.x-e.s.x,dy=e.t.y-e.s.y,d=Math.sqrt(dx*dx+dy*dy)||.01;const f=spr*(d-rest),fx=f*dx/d,fy=f*dy/d;e.s.vx+=fx;e.s.vy+=fy;e.t.vx-=fx;e.t.vy-=fy;});
    nodes.forEach(n=>{if(n.fixed)return;n.vx*=.86;n.vy*=.86;n.x+=n.vx*alpha;n.y+=n.vy*alpha;});
    alpha*=.992;if(alpha<.02)alpha=.02;}
  function fit(){let a=1e9,b=1e9,c=-1e9,d=-1e9;nodes.forEach(n=>{a=Math.min(a,n.x);b=Math.min(b,n.y);c=Math.max(c,n.x);d=Math.max(d,n.y);});
    const w=canvas.clientWidth,h=canvas.clientHeight,gw=Math.max(1,c-a),gh=Math.max(1,d-b);
    view.k=Math.min(w/(gw+80),h/(gh+80),2.2);view.x=w/2-(a+c)/2*view.k;view.y=h/2-(b+d)/2*view.k;}
  function resize(){dpr=Math.max(1,window.devicePixelRatio||1);canvas.width=canvas.clientWidth*dpr;canvas.height=canvas.clientHeight*dpr;}
  function draw(){ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,canvas.clientWidth,canvas.clientHeight);
    ctx.save();ctx.translate(view.x,view.y);ctx.scale(view.k,view.k);
    ctx.lineWidth=.6/view.k;ctx.strokeStyle="rgba(120,140,160,.22)";ctx.beginPath();
    edges.forEach(e=>{ctx.moveTo(e.s.x,e.s.y);ctx.lineTo(e.t.x,e.t.y);});ctx.stroke();
    nodes.forEach(n=>{const r=radius(n);ctx.beginPath();ctx.arc(n.x,n.y,r,0,6.2832);ctx.fillStyle=TYPE_COLORS[n.type]||"#999";ctx.fill();
      if(RISK[n.risk]){ctx.lineWidth=2/view.k;ctx.strokeStyle=RISK[n.risk];ctx.stroke();}
      if(view.k>.85&&n.type!=="action"&&n.type!=="resource"){ctx.fillStyle="rgba(233,237,242,.82)";ctx.font=`${10/view.k}px -apple-system,sans-serif`;ctx.fillText(n.label,n.x+r+1.5,n.y+3/view.k);}});
    ctx.restore();}
  let looping=false;
  function loop(){let n=0;const r=()=>{for(let s=0;s<3;s++)tick();draw();if(alpha>.025&&n++<2000)requestAnimationFrame(r);else{looping=false;draw();}};if(!looping){looping=true;requestAnimationFrame(r);}}
  function reheat(a){alpha=Math.max(alpha,a||.3);loop();}
  resize();fit();loop();window.addEventListener("resize",()=>{resize();draw();});
  function pt(ev){const r=canvas.getBoundingClientRect();const t=ev.touches?ev.touches[0]:ev;return{x:t.clientX-r.left,y:t.clientY-r.top};}
  function toWorld(p){return{x:(p.x-view.x)/view.k,y:(p.y-view.y)/view.k};}
  function pick(w){let best=null,bd=1e9;nodes.forEach(n=>{const dx=n.x-w.x,dy=n.y-w.y,d=dx*dx+dy*dy,r=radius(n)+6;if(d<r*r&&d<bd){bd=d;best=n;}});return best;}
  let drag=null,pan=null,moved=false,pinch=null;
  function down(p){const w=toWorld(p),n=pick(w);moved=false;if(n){drag=n;n.fixed=true;}else pan={x:p.x,y:p.y,ox:view.x,oy:view.y};}
  function move(p){if(drag){const w=toWorld(p);drag.x=w.x;drag.y=w.y;drag.vx=drag.vy=0;moved=true;reheat(.3);}else if(pan){view.x=pan.ox+(p.x-pan.x);view.y=pan.oy+(p.y-pan.y);moved=true;draw();}}
  function up(p){if(drag){drag.fixed=false;if(!moved&&p)showDetail(drag);drag=null;}else if(pan){if(!moved&&p){const n=pick(toWorld(p));n?showDetail(n):hideDetail();}pan=null;}}
  canvas.addEventListener("mousedown",e=>down(pt(e)));
  window.addEventListener("mousemove",e=>{if(drag||pan)move(pt(e));});
  window.addEventListener("mouseup",e=>{if(drag||pan)up(pt(e));});
  function zoom(f,mx,my){const wx=(mx-view.x)/view.k,wy=(my-view.y)/view.k;view.k=Math.min(6,Math.max(.15,view.k*f));view.x=mx-wx*view.k;view.y=my-wy*view.k;draw();}
  canvas.addEventListener("wheel",e=>{e.preventDefault();const r=canvas.getBoundingClientRect();zoom(e.deltaY<0?1.1:.9,e.clientX-r.left,e.clientY-r.top);},{passive:false});
  canvas.addEventListener("touchstart",e=>{e.preventDefault();if(e.touches.length===2){const r=canvas.getBoundingClientRect(),a=e.touches[0],b=e.touches[1];pinch={d:Math.hypot(a.clientX-b.clientX,a.clientY-b.clientY),mx:(a.clientX+b.clientX)/2-r.left,my:(a.clientY+b.clientY)/2-r.top};drag=pan=null;}else down(pt(e));},{passive:false});
  canvas.addEventListener("touchmove",e=>{e.preventDefault();if(pinch&&e.touches.length===2){const a=e.touches[0],b=e.touches[1],nd=Math.hypot(a.clientX-b.clientX,a.clientY-b.clientY);zoom(nd/pinch.d,pinch.mx,pinch.my);pinch.d=nd;}else move(pt(e));},{passive:false});
  canvas.addEventListener("touchend",e=>{e.preventDefault();if(pinch){pinch=null;return;}let p=null;if(e.changedTouches&&e.changedTouches.length){const t=e.changedTouches[0],r=canvas.getBoundingClientRect();p={x:t.clientX-r.left,y:t.clientY-r.top};}up(p);},{passive:false});
  canvas.addEventListener("dblclick",()=>{nodes.forEach(n=>n.fixed=false);alpha=1;loop();setTimeout(()=>{fit();draw();},420);});
  function showDetail(n){const d=$("detail");d.style.display="block";let h=`<h4>${esc(n.label)}</h4><div class="k">${esc(n.type)}</div>`;
    const skip={body:1,body_excerpt:1,risk:1};
    Object.entries(n.props||{}).forEach(([k,v])=>{if(skip[k]||v==null||v===""||(Array.isArray(v)&&!v.length))return;h+=`<div style="margin-top:7px"><span class="k">${esc(k)}:</span> ${esc(Array.isArray(v)?v.join(", "):v)}</div>`;});
    if(n.risk)h+=`<div style="margin-top:8px">${pill(n.risk)}</div>`;d.innerHTML=h;}
  function hideDetail(){$("detail").style.display="none";}
}
</script>
</body>
</html>"""
