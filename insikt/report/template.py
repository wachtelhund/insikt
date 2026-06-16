"""The single-file HTML report shell — Material-inspired, clean, offline.

Design: filled tonal surfaces instead of borders (elevation by colour + space),
generous padding, a calm neutral palette with one accent, Google-style
categorical colours for simple donut charts, and clear copy that keeps
"capability" (could do) distinct from "action" (did). All CSS/JS inline; the
data is embedded as JSON so the file is fully offline.
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
    --bg:#121317; --sc:#1c1d22; --sc-2:#24262c; --sc-3:#2e3036;
    --on:#e6e2e8; --on-var:#a6a4ac; --on-faint:#74727b;
    --primary:#e7c25c; --divider:rgba(255,255,255,.06);
    --crit:#ff6b63; --high:#ffa257; --med:#f4cd57; --low:#5fd08a; --info:#9aa0aa;
    --cap:#7aa9ff; --cfg:#f4cd57; --alert:#ff6b63;
    --r:18px; --r-md:14px; --r-sm:10px;
    --pad:22px;
  }
  *{box-sizing:border-box}
  html{-webkit-text-size-adjust:100%}
  html,body{overflow-x:hidden;max-width:100%}
  body{margin:0;background:var(--bg);color:var(--on);
    font:14.5px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,system-ui,Helvetica,Arial,sans-serif;
    -webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility;
    padding-bottom:calc(56px + env(safe-area-inset-bottom))}
  .num{font-variant-numeric:tabular-nums;font-feature-settings:"tnum" 1}
  a{color:var(--cap);text-decoration:none}
  ::selection{background:rgba(231,194,92,.22)}
  .wrap{max-width:960px;margin:0 auto;padding:0 24px}
  svg.ic{width:18px;height:18px;display:inline-block;vertical-align:-3px}

  /* app bar + tabs */
  .top{position:sticky;top:0;z-index:30;background:var(--bg)}
  .appbar{display:flex;align-items:center;gap:14px;flex-wrap:wrap;padding:16px 0}
  .brand{display:flex;align-items:center;gap:9px;font-size:16px;font-weight:650;letter-spacing:-.01em}
  .brand .mk{width:10px;height:10px;border-radius:50%;background:var(--primary)}
  .hmeta{color:var(--on-var);font-size:12.5px;flex:1;min-width:150px}
  .chip{margin-left:auto;display:inline-flex;align-items:center;gap:7px;font-weight:600;font-size:12.5px;
    padding:7px 14px;border-radius:999px}
  .chip .d{width:7px;height:7px;border-radius:50%}
  .chip.ok{background:rgba(95,208,138,.14);color:var(--low)} .chip.ok .d{background:var(--low)}
  .chip.warn{background:rgba(255,107,99,.15);color:var(--crit)} .chip.warn .d{background:var(--crit)}
  nav{overflow-x:auto;-webkit-overflow-scrolling:touch;scrollbar-width:none}
  nav::-webkit-scrollbar{display:none}
  nav .wrap{display:flex;gap:4px}
  nav button{flex:0 0 auto;background:none;border:none;color:var(--on-var);
    padding:0 4px 13px;margin:0 10px;min-height:30px;font-size:14px;font-weight:550;cursor:pointer;
    position:relative;white-space:nowrap;transition:color .15s}
  nav button:first-child{margin-left:0}
  nav button:hover{color:var(--on)}
  nav button.active{color:var(--on)}
  nav button.active::after{content:"";position:absolute;left:0;right:0;bottom:0;height:3px;
    background:var(--primary);border-radius:3px 3px 0 0}
  .top::after{content:"";display:block;height:1px;background:var(--divider)}

  .banners{margin-top:18px;display:flex;flex-direction:column;gap:10px}
  .banner{display:flex;gap:11px;align-items:flex-start;border-radius:var(--r-md);padding:13px 16px;font-size:13px;line-height:1.55}
  .banner .ic{margin-top:1px;flex:0 0 auto}
  .banner.warn{background:rgba(244,205,87,.08);color:#e8cf86}
  .banner.note{background:rgba(122,169,255,.08);color:#bcd2f5}

  main{padding:22px 0 48px}
  section{display:none;animation:fade .18s ease}
  section.active{display:block}
  @keyframes fade{from{opacity:0;transform:translateY(3px)}to{opacity:1;transform:none}}

  .stitle{font-size:14px;font-weight:650;letter-spacing:-.01em;color:var(--on);margin:30px 0 14px;display:flex;align-items:center;gap:9px}
  .stitle .ic{color:var(--on-faint);width:16px;height:16px}
  .stitle:first-child{margin-top:4px}

  /* card */
  .card{background:var(--sc);border-radius:var(--r);padding:var(--pad);margin-bottom:16px}
  .card-title{font-size:13px;font-weight:600;color:var(--on-var);margin-bottom:16px;letter-spacing:.01em}

  /* hero */
  .hero{display:flex;gap:18px;align-items:flex-start;background:var(--sc);border-radius:var(--r);padding:24px;margin-bottom:20px}
  .hero .hi{width:46px;height:46px;border-radius:14px;display:flex;align-items:center;justify-content:center;flex:0 0 auto}
  .hero .hi .ic{width:24px;height:24px}
  .hero.good .hi{background:rgba(95,208,138,.16);color:var(--low)}
  .hero.warn .hi{background:rgba(255,162,87,.16);color:var(--high)}
  .hero .ht{font-size:19px;font-weight:650;letter-spacing:-.015em;line-height:1.3}
  .hero .hs{color:var(--on-var);font-size:14px;margin-top:8px;line-height:1.6}
  .hero b{color:var(--on);font-weight:600}

  /* stat scorecards */
  .stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(150px,100%),1fr));gap:14px}
  .stat{background:var(--sc);border-radius:var(--r-md);padding:18px 20px}
  .stat .n{font-size:27px;font-weight:680;letter-spacing:-.02em;line-height:1.05}
  .stat .l{color:var(--on-var);font-size:13px;margin-top:6px}

  /* charts */
  .charts{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(290px,100%),1fr));gap:16px}
  .chart-body{display:flex;gap:22px;align-items:center;flex-wrap:wrap}
  svg.donut{flex:0 0 auto}
  .donut-n{fill:var(--on);font-size:26px;font-weight:680;font-variant-numeric:tabular-nums}
  .donut-l{fill:var(--on-faint);font-size:10.5px;letter-spacing:.12em;text-transform:uppercase}
  .legend{display:flex;flex-direction:column;gap:11px;flex:1;min-width:130px}
  .lg{display:flex;align-items:center;gap:11px;font-size:13.5px}
  .lg .sw{width:11px;height:11px;border-radius:4px;flex:0 0 auto}
  .lg .lt{color:var(--on-var);flex:1;min-width:0;text-transform:capitalize}
  .lg .lv{color:var(--on);font-weight:600;font-variant-numeric:tabular-nums}

  /* generic rows */
  .ct{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
  .title{font-weight:600;font-size:15.5px;letter-spacing:-.01em}
  .meta{color:var(--on-faint);font-size:12.5px}
  .spacer{margin-left:auto}
  .kv{display:flex;gap:12px;margin-top:11px;font-size:13.5px}
  .kv:first-of-type{margin-top:14px}
  .kv .k{color:var(--on-faint);min-width:84px;flex:0 0 auto;font-size:12.5px;padding-top:2px}
  .kv .v{flex:1;min-width:0;display:flex;flex-wrap:wrap;gap:6px;align-items:center}

  /* chips / tags (no borders) */
  .pill{display:inline-flex;align-items:center;gap:6px;padding:3px 11px;border-radius:999px;
    font-size:11.5px;font-weight:600;line-height:1.7;white-space:nowrap;text-transform:capitalize}
  .pill .d{width:6px;height:6px;border-radius:50%}
  .s-critical{background:rgba(255,107,99,.15);color:var(--crit)} .s-critical .d{background:var(--crit)}
  .s-high{background:rgba(255,162,87,.15);color:var(--high)} .s-high .d{background:var(--high)}
  .s-medium{background:rgba(244,205,87,.15);color:var(--med)} .s-medium .d{background:var(--med)}
  .s-low{background:rgba(95,208,138,.15);color:var(--low)} .s-low .d{background:var(--low)}
  .s-info{background:rgba(154,160,170,.16);color:#b3b9c2} .s-info .d{background:var(--info)}
  .tag{display:inline-block;background:var(--sc-2);color:var(--on-var);border-radius:8px;padding:3px 10px;font-size:12px;line-height:1.6;white-space:nowrap}
  .tag.self{background:rgba(231,194,92,.14);color:var(--primary)}
  .tag.warn{background:rgba(255,107,99,.14);color:var(--crit)}
  .tag.cap{background:rgba(122,169,255,.14);color:var(--cap)}
  .tag.cfg{background:rgba(244,205,87,.14);color:var(--cfg)}
  .tag.alert{background:rgba(255,107,99,.16);color:var(--alert)}
  .muted{color:var(--on-var)} .faint{color:var(--on-faint)}
  .empty{color:var(--on-var);padding:30px;text-align:center;background:var(--sc);border-radius:var(--r);font-size:14px}

  /* callout */
  .callout{display:flex;gap:13px;background:var(--sc);border-radius:var(--r);padding:16px 18px;margin-bottom:20px;
    font-size:13.5px;color:var(--on-var);line-height:1.6}
  .callout .ic{margin-top:1px;color:var(--on-faint);flex:0 0 auto}
  .callout b{color:var(--on);font-weight:600}

  /* severity groups */
  details.grp{background:var(--sc);border-radius:var(--r);margin-bottom:14px;overflow:hidden}
  details.grp>summary{list-style:none;cursor:pointer;padding:18px var(--pad);display:flex;align-items:center;gap:12px;font-weight:600;font-size:14px;user-select:none}
  details.grp>summary::-webkit-details-marker{display:none}
  details.grp>summary .gc{color:var(--on-faint);font-weight:500}
  details.grp>summary .cv{margin-left:auto;color:var(--on-faint);transition:transform .18s}
  details.grp[open]>summary .cv{transform:rotate(90deg)}
  .finding{padding:16px var(--pad);display:flex;gap:13px;margin:0 0 0 0}
  .finding+.finding{border-top:1px solid var(--divider)}
  .finding .sd{width:8px;height:8px;border-radius:50%;margin-top:6px;flex:0 0 auto}
  .finding .fb{flex:1;min-width:0}
  .finding .ft{display:flex;align-items:center;gap:9px;flex-wrap:wrap}
  .finding .fn{font-weight:600;font-size:14.5px;letter-spacing:-.005em}
  .finding .fd{color:var(--on-var);font-size:13.5px;margin-top:6px;line-height:1.55}
  .finding .ff{margin-top:9px;color:var(--on-faint);font-size:12px}

  /* timeline */
  .ev{display:flex;gap:16px;padding:15px var(--pad)}
  .ev+.ev{border-top:1px solid var(--divider)}
  .ev .wn{color:var(--on-faint);font-size:12px;flex:0 0 96px;white-space:nowrap;padding-top:3px;font-variant-numeric:tabular-nums}
  .ev .eb{flex:1;min-width:0}
  .ev .eb .s{font-size:14px;display:flex;align-items:center;gap:9px;flex-wrap:wrap}
  .ev .eb .m{color:var(--on-faint);font-size:12.5px;margin-top:5px}

  /* table */
  .tbl{background:var(--sc);border-radius:var(--r);overflow:hidden}
  .scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
  table{width:100%;border-collapse:collapse;min-width:440px}
  th,td{text-align:left;padding:15px 20px;font-size:14px;white-space:nowrap}
  td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
  th{color:var(--on-faint);font-weight:600;font-size:11.5px;text-transform:uppercase;letter-spacing:.05em}
  tbody tr+tr td{border-top:1px solid var(--divider)}

  .filters{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:16px}
  select{background:var(--sc);color:var(--on);border:none;border-radius:var(--r-sm);
    padding:11px 36px 11px 14px;font-size:14px;min-height:44px;cursor:pointer;appearance:none;
    background-image:url("data:image/svg+xml,%3Csvg width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%23a6a4ac' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E");
    background-repeat:no-repeat;background-position:right 13px center}

  /* graph */
  #gw{position:relative;height:74vh;min-height:440px;border-radius:var(--r);overflow:hidden;
    background:radial-gradient(120% 90% at 50% 30%,#171a20 0%,#101116 70%);touch-action:none}
  #graph{width:100%;height:100%;display:block;cursor:grab}
  #legend{position:absolute;top:14px;left:14px;background:rgba(18,19,23,.82);border-radius:var(--r-sm);
    padding:11px 13px;font-size:11.5px;color:var(--on-var)}
  #legend .row{display:flex;align-items:center;gap:9px;margin:3px 0}
  #legend .sw{width:10px;height:10px;border-radius:50%;flex:0 0 auto}
  #detail{position:absolute;top:14px;right:14px;width:min(290px,72vw);max-height:calc(74vh - 28px);overflow:auto;
    background:rgba(26,27,32,.97);border-radius:var(--r-sm);padding:16px;font-size:12.5px;display:none;
    box-shadow:0 10px 32px rgba(0,0,0,.5)}
  #detail h4{margin:0 0 9px;font-size:14.5px}
  #detail .k{color:var(--on-faint)}
  #ghelp{position:absolute;bottom:13px;left:14px;color:var(--on-faint);font-size:11.5px}
  code{background:var(--sc-2);padding:2px 7px;border-radius:6px;font-size:12.5px;word-break:break-word}

  @media (max-width:560px){
    .wrap{padding:0 16px}
    .appbar{gap:8px 12px}
    .hmeta{flex-basis:100%;order:3}
    .chip{margin-left:auto}
    .stats{grid-template-columns:repeat(2,1fr);gap:12px}
    .stat .n{font-size:23px}
    .hero{padding:18px}
    .ev .wn{flex-basis:80px}
  }
</style>
</head>
<body>
<div class="top">
  <div class="wrap"><div class="appbar">
    <span class="brand"><span class="mk"></span>Insikt</span>
    <span class="hmeta num" id="hmeta"></span>
    <span class="chip" id="chip"></span>
  </div></div>
  <nav><div class="wrap" id="nav"></div></nav>
</div>
<div class="wrap"><div class="banners" id="banners"></div></div>
<main class="wrap">
  <section id="tab-overview" class="active"></section>
  <section id="tab-graph">
    <div id="gw"><canvas id="graph"></canvas><div id="legend"></div><div id="detail"></div>
      <div id="ghelp">drag &middot; scroll / pinch to zoom &middot; tap a node</div></div>
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
const TYPE_COLORS={agent:"#e7c25c",skill:"#7aa9ff",tool:"#b39ddb",model:"#4dd0c4",
  connector:"#ffa257",resource:"#90a4ae",credential_ref:"#e07fb0",action:"#5d6b7d"};
const PALETTE=["#7aa9ff","#5fd08a","#f4cd57","#ff6b63","#b39ddb","#4dd0c4","#ffa257","#90a4ae"];
const SEV=["critical","high","medium","low","info"];
const SEVCOL={critical:"#ff6b63",high:"#ffa257",medium:"#f4cd57",low:"#5fd08a",info:"#9aa0aa"};
const esc=s=>(s==null?"":String(s)).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const $=id=>document.getElementById(id);
const fmtN=n=>(n==null?0:n).toLocaleString();
const pill=s=>`<span class="pill s-${esc(s||"info")}"><span class="d"></span>${esc(s||"info")}</span>`;
const tpill=t=>`<span class="pill s-info"><span class="d"></span>${esc(t)}</span>`;
const fmtTs=t=>(t||"").replace("T"," ").replace(/[.+Z].*/,"");
const I={
  check:'<path d="M20 6 9 17l-5-5"/>',
  alert:'<path d="M10.9 3.6 1.8 18.5A1.5 1.5 0 0 0 3.1 21h17.8a1.5 1.5 0 0 0 1.3-2.5L13.1 3.6a1.5 1.5 0 0 0-2.2 0Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
  info:'<circle cx="12" cy="12" r="9"/><path d="M12 11.5v4.5"/><path d="M12 8h.01"/>',
  shield:'<path d="M12 21s7.5-3.6 7.5-9.4V5.3L12 2.6 4.5 5.3v6.3C4.5 17.4 12 21 12 21Z"/>',
  clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7.5V12l3 2"/>',
  layers:'<path d="M12 2.6 2.6 7 12 11.4 21.4 7 12 2.6Z"/><path d="m2.6 16.5 9.4 4.4 9.4-4.4"/><path d="m2.6 11.7 9.4 4.4 9.4-4.4"/>',
  chart:'<path d="M3.5 3.5v17h17"/><path d="m7 14 3.2-3.4 3 2.6L21 7"/>',
  branch:'<circle cx="6.5" cy="6" r="2.3"/><circle cx="6.5" cy="18" r="2.3"/><circle cx="17.5" cy="7.2" r="2.3"/><path d="M6.5 8.3v7.4"/><path d="M17.5 9.5c0 4.2-4.4 4-7 5.4"/>',
};
const ic=n=>`<svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${I[n]||""}</svg>`;

function fclass(id){const p=String(id).split(":")[0];
  if(p==="fp"||p==="drift")return{k:"alert",label:"alert"};
  if(p==="posture"||p==="stranger"||p==="exposure"||p==="overlay")return{k:"cfg",label:"config"};
  return{k:"cap",label:"capability"};}
const SKILLUSE={};
(DATA.capability.agents||[]).forEach(a=>(a.skills||[]).forEach(s=>{SKILLUSE[s.id]={u:s.use_count};}));
function useBadge(id){const x=SKILLUSE[id];if(!x)return"";
  if(x.u===0)return`<span class="tag">never used</span>`;
  if(x.u>0)return`<span class="tag">used ${x.u}&times;</span>`;return"";}

/* donut chart */
function donut(segs,centerLabel){
  segs=segs.filter(s=>s.value>0);
  const total=segs.reduce((a,s)=>a+s.value,0);
  const cx=80,cy=80,rad=58,sw=20,circ=2*Math.PI*rad;
  let off=0,arcs="";
  if(!total){arcs=`<circle cx="${cx}" cy="${cy}" r="${rad}" fill="none" stroke="var(--sc-2)" stroke-width="${sw}"/>`;}
  segs.forEach(s=>{const len=s.value/total*circ;
    arcs+=`<circle cx="${cx}" cy="${cy}" r="${rad}" fill="none" stroke="${s.color}" stroke-width="${sw}" stroke-dasharray="${len.toFixed(2)} ${(circ-len).toFixed(2)}" stroke-dashoffset="${(-off).toFixed(2)}" transform="rotate(-90 ${cx} ${cy})"/>`;
    off+=len;});
  return `<svg class="donut" viewBox="0 0 160 160" width="148" height="148">${arcs}
    <text x="${cx}" y="${cy-3}" text-anchor="middle" class="donut-n">${fmtN(total)}</text>
    <text x="${cx}" y="${cy+15}" text-anchor="middle" class="donut-l">${esc(centerLabel||"")}</text></svg>`;
}
const legend=segs=>`<div class="legend">`+segs.filter(s=>s.value>0).map(s=>`<div class="lg"><span class="sw" style="background:${s.color}"></span><span class="lt">${esc(s.label)}</span><span class="lv">${fmtN(s.value)}</span></div>`).join("")+`</div>`;
const chartCard=(title,segs,center)=>`<div class="card"><div class="card-title">${esc(title)}</div><div class="chart-body">${donut(segs,center)}${legend(segs)}</div></div>`;

/* app bar + banners */
(function(){
  const m=DATA.meta,s=DATA.summary,bits=[];
  if(m.frameworks)bits.push(esc(m.frameworks.join(", ")));
  if(m.host)bits.push("host "+esc(m.host));
  if(m.scan_ts)bits.push(esc(fmtTs(m.scan_ts)));
  $("hmeta").textContent=bits.join("  ·  ");
  const need=(s.risk||[]).filter(r=>r.worst==="critical"||r.worst==="high").length;
  const c=$("chip");
  if(need){c.className="chip warn";c.innerHTML=`<span class="d"></span>${need} agent${need>1?"s":""} to review`;}
  else{c.className="chip ok";c.innerHTML=`<span class="d"></span>no high-risk findings`;}
  const b=$("banners");
  if(m.partial)b.insertAdjacentHTML("beforeend",`<div class="banner warn">${ic("alert")}<div>Partial scan — ${esc((m.partial_reasons||[]).join("; "))||"some sources unreadable"}. Figures are a lower bound.</div></div>`);
  if(DATA.backfill_note)b.insertAdjacentHTML("beforeend",`<div class="banner note">${ic("clock")}<div>${esc(DATA.backfill_note)}</div></div>`);
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
  const worst=(DATA.hygiene.findings||[]).filter(f=>fclass(f.id).k==="alert"||f.severity==="critical"||f.severity==="high");
  const neverUsed=Object.values(SKILLUSE).filter(x=>x.u===0).length;
  let hero;
  if(!worst.length){
    hero=`<div class="hero good"><div class="hi">${ic("check")}</div><div>
      <div class="ht">No incidents in the action log</div>
      <div class="hs">Reconstructed <b>${fmtN(acts)}</b> action(s); no verified incidents. The Hygiene tab lists <b>capabilities</b> (what installed skills could do), not events.${neverUsed?` <b>${neverUsed}</b> skill(s) have never been used.`:""}</div></div></div>`;
  }else{
    hero=`<div class="hero warn"><div class="hi">${ic("alert")}</div><div>
      <div class="ht">${worst.length} finding(s) to review</div>
      <div class="hs">Mostly capability &amp; configuration, not confirmed incidents. Open <b>Hygiene</b> for detail and <b>Timeline</b> for what actually ran.</div></div></div>`;
  }
  let h=hero;
  // charts: actions by type + findings by kind
  const byType=DATA.timeline.by_type||{};
  const actSegs=Object.keys(byType).map((t,i)=>({label:t.replace(/_/g," "),value:byType[t],color:PALETTE[i%PALETTE.length]}));
  const kinds={capability:0,config:0,alert:0};
  (DATA.hygiene.findings||[]).forEach(f=>{const k=fclass(f.id);kinds[k.k==="cap"?"capability":k.k==="cfg"?"config":"alert"]++;});
  const findSegs=[{label:"capability",value:kinds.capability,color:"#7aa9ff"},{label:"config",value:kinds.config,color:"#f4cd57"},{label:"alert",value:kinds.alert,color:"#ff6b63"}];
  const charts=[];
  if(actSegs.some(s=>s.value))charts.push(chartCard("Actions by type",actSegs,"actions"));
  if(findSegs.some(s=>s.value))charts.push(chartCard("Findings by kind",findSegs,"findings"));
  if(charts.length)h+=`<div class="charts">${charts.join("")}</div>`;
  // scorecards
  const tiles=[["agents","Agents"],["skills","Skills"],["self_authored_skills","Self-authored"],["connectors","Connectors"],
    ["models","Models"],["credential_refs","Credentials"],["actions","Actions"],["total_tokens","Tokens"]];
  h+=`<div class="stitle">${ic("chart")} At a glance</div><div class="stats">`+
    tiles.map(([k,l])=>`<div class="stat"><div class="n num">${fmtN(s[k])}</div><div class="l">${l}</div></div>`).join("")+`</div>`;
  h+=`<div class="stitle">${ic("shield")} Risk by agent</div>`;
  if(!(s.risk||[]).length)h+=`<div class="empty">No agents scored.</div>`;
  else s.risk.forEach(r=>{
    h+=`<div class="card"><div class="ct"><span class="title">${esc(r.label)}</span>${pill(r.worst)}<span class="spacer meta">score ${esc(r.score)}</span></div>
      <div class="kv"><span class="k">top factors</span><span class="v muted" style="display:block">${(r.top_findings||[]).map(esc).join(" · ")||"none"}</span></div></div>`;
  });
  root.innerHTML=h;
})();

/* capabilities */
(function(){
  const root=$("tab-capability"),cap=DATA.capability;
  let h=`<div class="callout">${ic("layers")}<div><b>Capabilities</b> are what each skill could do — installed and available, not necessarily used. "never used" means it has never been invoked; see <b>Timeline</b> for what actually ran.</div></div>`;
  if(!cap.agents.length){root.innerHTML=h+`<div class="empty">No agents found.</div>`;return;}
  const used=Object.values(SKILLUSE).filter(x=>x.u>0).length, never=Object.values(SKILLUSE).filter(x=>x.u===0).length;
  if(used+never>0)h+=`<div class="charts"><div class="card"><div class="card-title">Skill usage</div><div class="chart-body">${donut([{label:"used",value:used,color:"#5fd08a"},{label:"never used",value:never,color:"#90a4ae"}],"skills")}${legend([{label:"used",value:used,color:"#5fd08a"},{label:"never used",value:never,color:"#90a4ae"}])}</div></div></div>`;
  cap.agents.forEach(a=>{
    h+=`<div class="stitle">${ic("shield")} ${esc(a.label)} ${a.risk?pill(a.risk):""}</div>`;
    const meta=[a.framework,a.version,a.host&&("host "+a.host),a.memory_items!=null&&(a.memory_items+" memories")].filter(Boolean).map(esc).join("  ·  ");
    h+=`<div class="card"><div class="meta">${meta}</div>`;
    const conns=(a.connectors||[]).map(c=>`<span class="tag${c.accepts_strangers?" warn":""}">${esc(c.platform)}${c.accepts_strangers?" · no allowlist":""}</span>`).join("")||'<span class="faint">none</span>';
    const models=(a.models||[]).map(m=>`<span class="tag">${esc(m.provider)}/${esc(m.model_name)}</span>`).join("")||'<span class="faint">none</span>';
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
  root.innerHTML=`<div class="callout">${ic("clock")}<div><b>What actually ran</b> — reconstructed from the agents' own logs. ${esc(tl.count)} action(s).</div></div>
    <div class="filters"><select id="f-type"><option value="">All types</option>${types.map(t=>`<option>${esc(t)}</option>`).join("")}</select>
    ${agents.length>1?`<select id="f-agent"><option value="">All agents</option>${agents.map(a=>`<option>${esc(a)}</option>`).join("")}</select>`:""}</div>
    <div id="tlb"></div>`;
  function draw(){
    const ft=$("f-type").value,fa=($("f-agent")||{}).value||"";
    const rows=tl.actions.filter(a=>(!ft||a.type===ft)&&(!fa||a.agent===fa));
    if(!rows.length){$("tlb").innerHTML=`<div class="empty">No actions in this view.</div>`;return;}
    let h=`<div class="card" style="padding:6px var(--pad)">`;
    rows.forEach(a=>{
      const cost=a.cost!=null?` · $${Number(a.cost).toFixed(4)}`:"",tok=a.tokens?` · ${a.tokens.toLocaleString()} tok`:"";
      const meta=[a.agent,a.skill&&("via "+a.skill),a.model,a.connector&&("→ "+a.connector),a.resource&&("→ "+a.resource)].filter(Boolean).map(esc).join("  ·  ");
      h+=`<div class="ev"><div class="wn">${esc(fmtTs(a.ts))||"—"}</div><div class="eb">
        <div class="s">${tpill(a.type)} <span>${esc(a.summary)}</span></div>
        <div class="m">${meta}${esc(tok)}${esc(cost)} · ${esc(a.source||"")}</div></div></div>`;
    });
    h+=`</div>`;
    if(tl.truncated)h+=`<div class="muted" style="margin-top:12px;font-size:13px">Showing the most recent ${tl.actions.length}.</div>`;
    $("tlb").innerHTML=h;
  }
  $("f-type").onchange=draw;if($("f-agent"))$("f-agent").onchange=draw;draw();
})();

/* models & cost */
(function(){
  const root=$("tab-cost"),c=DATA.cost;
  let h=`<div class="stats" style="grid-template-columns:repeat(auto-fit,minmax(min(180px,100%),1fr))">
    <div class="stat"><div class="n num">$${(c.total_cost||0).toFixed(4)}</div><div class="l">Recorded spend</div></div>
    <div class="stat"><div class="n num">${fmtN(c.total_tokens)}</div><div class="l">Recorded tokens</div></div></div>`;
  const tokSegs=(c.models||[]).filter(m=>m.tokens>0).map((m,i)=>({label:m.model,value:m.tokens,color:PALETTE[i%PALETTE.length]}));
  if(tokSegs.length){h+=`<div class="stitle">${ic("chart")} Tokens by model</div>`+chartCard("",tokSegs,"tokens").replace('<div class="card-title"></div>','');}
  h+=`<div class="stitle">${ic("chart")} All models</div>`;
  const role=m=>[m.default?'<span class="tag self">default</span>':"",(m.configured&&!m.default)?'<span class="tag">configured</span>':"",(m.used||m.calls)?'<span class="tag">used</span>':'<span class="tag">unused</span>'].join(" ");
  h+=(c.models||[]).length?`<div class="tbl scroll"><table><thead><tr><th>Model</th><th>Role</th><th class="n">Calls</th><th class="n">Tokens</th><th class="n">Cost</th></tr></thead><tbody>`+
    c.models.map(m=>`<tr><td>${esc(m.model)}</td><td>${role(m)}</td><td class="n">${fmtN(m.calls)}</td><td class="n">${fmtN(m.tokens||0)}</td><td class="n">$${(m.cost||0).toFixed(4)}</td></tr>`).join("")+`</tbody></table></div>`
    :`<div class="empty">No models configured or used.</div>`;
  if(c.total_tokens>0&&c.total_cost===0)h+=`<div class="muted" style="margin-top:12px;font-size:13px">Token volume is recorded but per-call cost isn't — some frameworks don't persist cost. A model with 0 calls is configured but had no usage recorded.</div>`;
  root.innerHTML=h;
})();

/* hygiene */
(function(){
  const root=$("tab-hygiene"),hy=DATA.hygiene;
  const fs=(hy.findings||[]).slice().sort((a,b)=>SEV.indexOf(a.severity)-SEV.indexOf(b.severity));
  let h=`<div class="callout">${ic("shield")}<div><b>Capabilities &amp; configuration — not incidents.</b>
    <span class="tag cap">capability</span> what a skill could do ·
    <span class="tag cfg">config</span> a setting worth knowing ·
    <span class="tag alert">alert</span> a verified problem.
    Nothing here means it happened — the <b>Timeline</b> shows that.</div></div>`;
  if(!fs.length){root.innerHTML=h+`<div class="empty">No hygiene findings.</div>`;return;}
  const counts={};fs.forEach(f=>counts[f.severity]=(counts[f.severity]||0)+1);
  h+=`<div style="display:flex;gap:9px;flex-wrap:wrap;margin-bottom:18px">`+SEV.filter(s=>counts[s]).map(s=>`<span class="pill s-${s}"><span class="d"></span>${counts[s]} ${s}</span>`).join("")+`</div>`;
  SEV.forEach(sv=>{const g=fs.filter(f=>f.severity===sv);if(!g.length)return;
    const open=(sv==="critical"||sv==="high")?" open":"";
    h+=`<details class="grp"${open}><summary>${pill(sv)}<span class="gc">${g.length} finding${g.length>1?"s":""}</span><span class="cv">›</span></summary>`;
    g.forEach(f=>{const cl=fclass(f.id);
      h+=`<div class="finding"><span class="sd" style="background:${SEVCOL[sv]}"></span><div class="fb">
        <div class="ft"><span class="fn">${esc(f.title)}</span><span class="tag ${cl.k}">${cl.label}</span>${useBadge(f.node_id)}</div>
        <div class="fd">${esc(f.detail)}</div>
        ${(f.factors||[]).length?`<div class="ff">${f.factors.map(esc).join(" · ")}</div>`:""}</div></div>`;});
    h+=`</details>`;});
  root.innerHTML=h;
})();

/* diff */
(function(){
  if(!DATA.diff)return;const d=DATA.diff,root=$("tab-diff");
  const list=(t,arr,fmt)=>`<div class="stitle">${esc(t)} <span class="faint" style="font-weight:500">(${arr.length})</span></div>`+(arr.length?`<div class="card">`+arr.map(fmt).join('<div style="height:8px"></div>')+`</div>`:`<div class="empty">none</div>`);
  let h=`<div class="callout">${ic("branch")}<div>Since snapshot #${esc(d.since.id)} → #${esc(d.to.id)}: <b>${esc(d.summary)}</b></div></div>`;
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
  const RISK={critical:"#ff6b63",high:"#ffa257",medium:"#f4cd57"};
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
    ctx.lineWidth=.6/view.k;ctx.strokeStyle="rgba(140,150,170,.2)";ctx.beginPath();
    edges.forEach(e=>{ctx.moveTo(e.s.x,e.s.y);ctx.lineTo(e.t.x,e.t.y);});ctx.stroke();
    nodes.forEach(n=>{const r=radius(n);ctx.beginPath();ctx.arc(n.x,n.y,r,0,6.2832);ctx.fillStyle=TYPE_COLORS[n.type]||"#999";ctx.fill();
      if(RISK[n.risk]){ctx.lineWidth=2/view.k;ctx.strokeStyle=RISK[n.risk];ctx.stroke();}
      if(view.k>.85&&n.type!=="action"&&n.type!=="resource"){ctx.fillStyle="rgba(230,226,232,.82)";ctx.font=`${10/view.k}px -apple-system,sans-serif`;ctx.fillText(n.label,n.x+r+1.5,n.y+3/view.k);}});
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
    if(n.risk)h+=`<div style="margin-top:9px">${pill(n.risk)}</div>`;d.innerHTML=h;}
  function hideDetail(){$("detail").style.display="none";}
}
</script>
</body>
</html>"""
