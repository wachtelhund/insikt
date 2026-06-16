"""Render the whole-system dashboard to a single self-contained HTML file."""

from __future__ import annotations

import html as _html
import json


def render_dashboard(state: dict, live: bool = False) -> str:
    data = json.dumps(state, default=str).replace("</", "<\\/")
    return (
        _TEMPLATE
        .replace("__TITLE__", _html.escape(f"Insikt — {state.get('meta', {}).get('host', 'system')}"))
        .replace("__LIVE__", "true" if live else "false")
        .replace("__DATA__", data)
    )


_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="color-scheme" content="dark">
<title>__TITLE__</title>
<style>
  :root{
    --bg:#0a1024; --sc:#141b3b; --sc2:#1c2552; --sc3:#28326e;
    --on:#eaf0ff; --on2:#9aa4d4; --on3:#6a73a8;
    --primary:#ff3d77;
    --ok:#2ee6a8; --warn:#ffb648; --crit:#ff4d6d; --off:#5b6291;
    --line:rgba(150,162,224,.10);
    --grad:linear-gradient(135deg,#ff3d77 0%,#b06cff 100%);
    --grad-cyan:linear-gradient(135deg,#16d6c4 0%,#3ad6e0 100%);
    --r:18px; --r2:14px; --r3:10px; --pad:22px;
  }
  *{box-sizing:border-box}
  html,body{overflow-x:hidden;max-width:100%}
  body{margin:0;background:var(--bg);color:var(--on);
    background-image:radial-gradient(130% 105% at 88% -12%,#1c2858 0%,rgba(28,40,88,0) 52%),radial-gradient(120% 120% at 0% 0%,#161d49 0%,rgba(22,29,73,0) 45%);
    background-attachment:fixed;
    font:14.5px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,system-ui,Arial,sans-serif;
    -webkit-font-smoothing:antialiased;padding-bottom:calc(48px + env(safe-area-inset-bottom))}
  .num{font-variant-numeric:tabular-nums;font-feature-settings:"tnum" 1}
  .wrap{max-width:1080px;margin:0 auto;padding:0 22px}
  svg.ic{width:17px;height:17px;vertical-align:-3px}

  .top{position:sticky;top:0;z-index:30;background:rgba(10,16,36,.72);backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);border-bottom:1px solid var(--line)}
  .appbar{display:flex;align-items:center;gap:13px;flex-wrap:wrap;padding:16px 0}
  .brand{display:flex;align-items:center;gap:10px;font-size:16px;font-weight:680;letter-spacing:-.01em}
  .brand .mk{width:13px;height:13px;border-radius:50%;background:var(--grad);box-shadow:0 0 12px rgba(255,61,119,.55)}
  .hmeta{color:var(--on2);font-size:12.5px;flex:1;min-width:140px}
  .live{display:inline-flex;align-items:center;gap:6px;font-size:11.5px;color:var(--on3)}
  .live .pulse{width:7px;height:7px;border-radius:50%;background:var(--off)}
  .live.on .pulse{background:var(--ok);box-shadow:0 0 8px var(--ok);animation:pulse 2s infinite}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.35}}
  .chip{display:inline-flex;align-items:center;gap:7px;font-weight:600;font-size:12.5px;padding:6px 13px;border-radius:999px}
  .chip .d{width:7px;height:7px;border-radius:50%}
  .chip.ok{background:rgba(46,230,168,.15);color:var(--ok)} .chip.ok .d{background:var(--ok);box-shadow:0 0 7px var(--ok)}
  .chip.warn{background:rgba(255,182,72,.16);color:var(--warn)} .chip.warn .d{background:var(--warn);box-shadow:0 0 7px var(--warn)}
  .chip.crit{background:rgba(255,77,109,.17);color:var(--crit)} .chip.crit .d{background:var(--crit);box-shadow:0 0 7px var(--crit)}
  .chip.off{background:rgba(91,98,145,.2);color:var(--on2)} .chip.off .d{background:var(--off)}
  nav{overflow-x:auto;-webkit-overflow-scrolling:touch;scrollbar-width:none;border-top:1px solid var(--line)}
  nav::-webkit-scrollbar{display:none}
  nav .wrap{display:flex;gap:0}
  nav button{flex:0 0 auto;background:none;border:none;color:var(--on2);padding:13px 0 12px;margin:0 14px;
    font-size:13.5px;font-weight:550;cursor:pointer;position:relative;white-space:nowrap;display:flex;align-items:center;gap:7px}
  nav button:first-child{margin-left:0}
  nav button:hover{color:var(--on)}
  nav button.active{color:#fff}
  nav button.active::after{content:"";position:absolute;left:0;right:0;bottom:0;height:3px;background:var(--grad);border-radius:3px 3px 0 0}
  nav button .sd{width:7px;height:7px;border-radius:50%}

  main{padding:24px 0 48px}
  section.tab{display:none;animation:f .16s ease}
  section.tab.active{display:block}
  @keyframes f{from{opacity:0;transform:translateY(3px)}to{opacity:1;transform:none}}
  .stitle{font-size:14px;font-weight:650;color:var(--on);margin:30px 0 14px;display:flex;align-items:center;gap:9px}
  .stitle:first-child{margin-top:2px}
  .stitle .ic{color:var(--on3);width:15px;height:15px}

  .grid{display:grid;gap:14px}
  .g-gauges{grid-template-columns:repeat(auto-fit,minmax(min(150px,100%),1fr))}
  .g-cards{grid-template-columns:repeat(auto-fit,minmax(min(240px,100%),1fr))}
  .g-stats{grid-template-columns:repeat(auto-fit,minmax(min(120px,100%),1fr))}

  .card{background:linear-gradient(180deg,rgba(255,255,255,.022),rgba(255,255,255,0)) ,var(--sc);border:1px solid var(--line);border-radius:var(--r);padding:var(--pad)}
  .card-t{font-size:13px;font-weight:600;color:var(--on2);margin-bottom:14px}
  .gauge{display:flex;flex-direction:column;align-items:center;text-align:center;background:linear-gradient(180deg,rgba(255,255,255,.022),rgba(255,255,255,0)) ,var(--sc);border:1px solid var(--line);border-radius:var(--r2);padding:18px 10px 15px}
  .gauge .lab{color:var(--on2);font-size:12.5px;margin-top:9px;letter-spacing:.01em}
  .gv{fill:#fff;font-size:22px;font-weight:700;font-variant-numeric:tabular-nums}
  .gu{fill:var(--on3);font-size:10px}
  .g-ok{filter:drop-shadow(0 0 5px rgba(46,230,168,.5))}
  .g-warn{filter:drop-shadow(0 0 5px rgba(255,182,72,.5))}
  .g-crit{filter:drop-shadow(0 0 6px rgba(255,77,109,.55))}
  .g-off{filter:none}
  .stat{background:linear-gradient(180deg,rgba(255,255,255,.022),rgba(255,255,255,0)) ,var(--sc);border:1px solid var(--line);border-radius:var(--r2);padding:16px 18px}
  .stat .n{font-size:23px;font-weight:700;letter-spacing:-.02em}
  .stat .l{color:var(--on2);font-size:12.5px;margin-top:4px}

  .srccard{background:linear-gradient(180deg,rgba(255,255,255,.022),rgba(255,255,255,0)) ,var(--sc);border:1px solid var(--line);border-radius:var(--r);padding:18px 20px;display:flex;flex-direction:column;gap:9px}
  .srccard .h{display:flex;align-items:center;gap:9px}
  .srccard .nm{font-weight:600;font-size:15px}
  .srccard .sm{color:var(--on2);font-size:13px;line-height:1.5}
  .srccard.clickable{cursor:pointer;transition:border-color .14s,transform .14s}
  .srccard.clickable:hover{border-color:rgba(176,108,255,.45);transform:translateY(-1px)}

  .pill{display:inline-flex;align-items:center;gap:6px;padding:2px 10px;border-radius:999px;font-size:11px;font-weight:600;text-transform:capitalize}
  .pill .d{width:6px;height:6px;border-radius:50%}
  .p-ok{background:rgba(46,230,168,.15);color:var(--ok)} .p-ok .d{background:var(--ok)}
  .p-warn{background:rgba(255,182,72,.16);color:var(--warn)} .p-warn .d{background:var(--warn)}
  .p-crit{background:rgba(255,77,109,.17);color:var(--crit)} .p-crit .d{background:var(--crit)}
  .p-off{background:rgba(91,98,145,.2);color:var(--on2)} .p-off .d{background:var(--off)}
  .p-critical{background:rgba(255,77,109,.17);color:var(--crit)} .p-critical .d{background:var(--crit)}
  .p-high{background:rgba(255,182,72,.16);color:var(--warn)} .p-high .d{background:var(--warn)}
  .p-medium{background:rgba(255,126,179,.16);color:#ff7eb3} .p-medium .d{background:#ff7eb3}
  .p-low{background:rgba(46,230,168,.15);color:var(--ok)} .p-low .d{background:var(--ok)}
  .p-info{background:rgba(122,140,255,.16);color:#9aa8ff} .p-info .d{background:#7c8cff}
  .tag{display:inline-block;background:var(--sc2);color:var(--on2);border-radius:8px;padding:2px 9px;font-size:11.5px;margin:2px 4px 0 0}
  .tag.self{background:rgba(176,108,255,.18);color:#c79bff}
  .tag.warn{background:rgba(255,77,109,.16);color:var(--crit)}
  .tag.cap{background:rgba(91,140,255,.16);color:#8fb0ff}
  .tag.config{background:rgba(255,182,72,.15);color:var(--warn)}
  .tag.alert{background:rgba(255,77,109,.17);color:var(--crit)}
  .muted{color:var(--on2)} .faint{color:var(--on3)}
  .empty{color:var(--on2);padding:26px;text-align:center;background:var(--sc);border:1px solid var(--line);border-radius:var(--r)}
  .kv{display:flex;gap:11px;margin-top:10px;font-size:13px}
  .kv .k{color:var(--on3);min-width:80px;flex:0 0 auto;font-size:12px;padding-top:2px}
  .kv .v{flex:1;min-width:0;display:flex;flex-wrap:wrap;gap:5px}

  /* recommended steps + findings */
  .rec{display:flex;gap:12px;padding:14px 0}
  .rec+.rec{border-top:1px solid var(--line)}
  .rec .sd{width:8px;height:8px;border-radius:50%;margin-top:6px;flex:0 0 auto}
  .rec .rt{font-size:14px;font-weight:550}
  .rec .rm{color:var(--on3);font-size:12.5px;margin-top:3px}
  details.grp{background:var(--sc);border:1px solid var(--line);border-radius:var(--r);margin-bottom:12px;overflow:hidden}
  details.grp>summary{list-style:none;cursor:pointer;padding:16px var(--pad);display:flex;align-items:center;gap:11px;font-weight:600;font-size:13.5px}
  details.grp>summary::-webkit-details-marker{display:none}
  details.grp>summary .gc{color:var(--on3);font-weight:500}
  details.grp>summary .cv{margin-left:auto;color:var(--on3);transition:transform .15s}
  details.grp[open]>summary .cv{transform:rotate(90deg)}
  .finding{padding:15px var(--pad);display:flex;gap:12px}
  .finding+.finding{border-top:1px solid var(--line)}
  .finding .sd{width:8px;height:8px;border-radius:50%;margin-top:6px;flex:0 0 auto}
  .finding .fn{font-weight:600;font-size:14px}
  .finding .fd{color:var(--on2);font-size:13px;margin-top:5px}
  .finding .ff{margin-top:8px;color:var(--on3);font-size:12px}
  .rem{margin-top:10px;display:flex;gap:8px;background:rgba(46,230,168,.08);border:1px solid rgba(46,230,168,.18);border-radius:9px;padding:9px 12px;font-size:13px}
  .rem .ic{color:var(--ok);flex:0 0 auto;margin-top:1px;width:15px;height:15px}

  /* donut + legend */
  svg.donut{flex:0 0 auto}
  .dn{fill:#fff;font-size:24px;font-weight:700} .dl{fill:var(--on3);font-size:10px;letter-spacing:.1em}
  .chart-body{display:flex;gap:22px;align-items:center;flex-wrap:wrap}
  .legend{display:flex;flex-direction:column;gap:10px;flex:1;min-width:130px}
  .lg{display:flex;align-items:center;gap:11px;font-size:13.5px}
  .lg .sw{width:11px;height:11px;border-radius:4px} .lg .lt{color:var(--on2);flex:1;text-transform:capitalize}
  .lg .lv{font-weight:600;font-variant-numeric:tabular-nums}

  /* timeline + table + graph (Hermes subviews) */
  .ev{display:flex;gap:14px;padding:13px 0}
  .ev+.ev{border-top:1px solid var(--line)}
  .ev .wn{color:var(--on3);font-size:12px;flex:0 0 92px;white-space:nowrap;padding-top:2px;font-variant-numeric:tabular-nums}
  .ev .es{font-size:13.5px;display:flex;gap:7px;align-items:center;flex-wrap:wrap}
  .ev .em{color:var(--on3);font-size:12px;margin-top:4px}
  .tbl{background:var(--sc);border:1px solid var(--line);border-radius:var(--r);overflow:hidden}.scroll{overflow-x:auto}
  table{width:100%;border-collapse:collapse;min-width:420px}
  th,td{text-align:left;padding:13px 16px;font-size:13.5px;white-space:nowrap}
  td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
  th{color:var(--on3);font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.05em}
  tbody tr+tr td{border-top:1px solid var(--line)}
  .subnav{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:16px}
  .subnav button{background:var(--sc);border:1px solid var(--line);color:var(--on2);padding:9px 14px;border-radius:999px;font-size:13px;cursor:pointer;transition:.14s}
  .subnav button:hover{color:var(--on);border-color:rgba(176,108,255,.4)}
  .subnav button.active{background:var(--grad);border-color:transparent;color:#fff;box-shadow:0 4px 14px rgba(176,108,255,.3)}
  .filters{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px}
  select{background:var(--sc);color:var(--on);border:1px solid var(--line);border-radius:var(--r3);padding:10px 32px 10px 13px;font-size:13.5px;min-height:42px;cursor:pointer;appearance:none;
    background-image:url("data:image/svg+xml,%3Csvg width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%239aa4d4' stroke-width='2.5' stroke-linecap='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:right 12px center}
  #gw{position:relative;height:70vh;min-height:420px;border:1px solid var(--line);border-radius:var(--r);overflow:hidden;background:radial-gradient(120% 90% at 50% 25%,#161d49,#0a1024);touch-action:none}
  #graph{width:100%;height:100%;display:block;cursor:grab}
  #glegend{position:absolute;top:12px;left:12px;background:rgba(10,16,36,.78);border:1px solid var(--line);border-radius:10px;padding:9px 11px;font-size:11px;color:var(--on2)}
  #glegend .r{display:flex;align-items:center;gap:8px;margin:2px 0}.gsw{width:9px;height:9px;border-radius:50%}
  code{background:var(--sc2);padding:1px 6px;border-radius:5px;font-size:12px}

  @media (max-width:560px){
    .wrap{padding:0 15px}
    .hmeta{flex-basis:100%;order:9}
    .g-gauges{grid-template-columns:repeat(2,1fr)}
    .g-stats{grid-template-columns:repeat(2,1fr)}
  }
</style>
</head>
<body>
<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs>
  <linearGradient id="gg-ok" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#13c9b6"/><stop offset="1" stop-color="#3ad6e0"/></linearGradient>
  <linearGradient id="gg-warn" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ff9f45"/><stop offset="1" stop-color="#ffce4b"/></linearGradient>
  <linearGradient id="gg-crit" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ff2d6f"/><stop offset="1" stop-color="#ff7a6b"/></linearGradient>
  <linearGradient id="gg-off" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#4a5290"/><stop offset="1" stop-color="#6a73a8"/></linearGradient>
</defs></svg>
<div class="top"><div class="wrap">
  <div class="appbar">
    <span class="brand"><span class="mk"></span>Insikt</span>
    <span class="hmeta num" id="hmeta"></span>
    <span class="live" id="live"><span class="pulse"></span><span id="liveT">snapshot</span></span>
    <span class="chip" id="chip"></span>
  </div></div>
  <nav><div class="wrap" id="nav"></div></nav>
</div>
<main class="wrap" id="main"></main>

<script id="d" type="application/json">__DATA__</script>
<script>
"use strict";
const DATA=JSON.parse(document.getElementById("d").textContent);
const LIVE=__LIVE__;
const S=()=>DATA.sections||{};
const A=()=>DATA.agent;
const esc=s=>(s==null?"":String(s)).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const $=id=>document.getElementById(id);
const fmtN=n=>(n==null?"—":Number(n).toLocaleString());
const STC={ok:"var(--ok)",warn:"var(--warn)",crit:"var(--crit)",off:"var(--off)"};
const chip=(st,txt)=>`<span class="chip ${st}"><span class="d"></span>${esc(txt)}</span>`;
const sevpill=s=>`<span class="pill p-${esc(s||"info")}"><span class="d"></span>${esc(s||"info")}</span>`;
const dot=st=>`<span class="sd" style="background:${STC[st]||"var(--off)"}"></span>`;
const I={
  check:'<path d="M20 6 9 17l-5-5"/>',alert:'<path d="M10.9 3.6 1.8 18.5A1.5 1.5 0 0 0 3.1 21h17.8a1.5 1.5 0 0 0 1.3-2.5L13.1 3.6a1.5 1.5 0 0 0-2.2 0Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
  cpu:'<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 1v3M15 1v3M9 20v3M15 20v3M1 9h3M1 15h3M20 9h3M20 15h3"/>',
  chip:'<rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/>',
  brain:'<path d="M12 5a3 3 0 0 0-5.6-1.5A2.5 2.5 0 0 0 4 8a2.5 2.5 0 0 0 0 4 2.5 2.5 0 0 0 2 4 3 3 0 0 0 6 0V5Z"/>',
  home:'<path d="m3 11 9-7 9 7"/><path d="M5 10v10h14V10"/>',
  shield:'<path d="M12 21s7.5-3.6 7.5-9.4V5.3L12 2.6 4.5 5.3v6.3C4.5 17.4 12 21 12 21Z"/>',
  clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7.5V12l3 2"/>',layers:'<path d="M12 2.6 2.6 7 12 11.4 21.4 7 12 2.6Z"/><path d="m2.6 16.5 9.4 4.4 9.4-4.4"/><path d="m2.6 11.7 9.4 4.4 9.4-4.4"/>',
  chart:'<path d="M3.5 3.5v17h17"/><path d="m7 14 3.2-3.4 3 2.6L21 7"/>',gauge:'<path d="M12 13 16 9"/><path d="M4 18a8 8 0 1 1 16 0"/>',
};
const ic=n=>`<svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${I[n]||""}</svg>`;
const fmtTs=t=>(t||"").replace("T"," ").replace(/[.+Z].*/,"");
const PAL=["#5b8cff","#2ee6a8","#ffc24b","#ff4d6d","#b06cff","#22d3ee","#ff7eb3","#7c8cff"];

function gauge(label,valTxt,unit,pct,status){
  status=STC[status]?status:"off";const grad=`url(#gg-${status})`;
  pct=Math.max(0,Math.min(100,pct||0));const r=52,c=2*Math.PI*r,len=pct/100*c;
  return `<div class="gauge"><svg viewBox="0 0 140 140" width="116" height="116">`+
    `<circle cx="70" cy="70" r="${r}" fill="none" stroke="rgba(150,162,224,.13)" stroke-width="13"/>`+
    `<circle class="g-${status}" cx="70" cy="70" r="${r}" fill="none" stroke="${grad}" stroke-width="13" stroke-linecap="round" stroke-dasharray="${len.toFixed(1)} ${(c-len).toFixed(1)}" transform="rotate(-90 70 70)"/>`+
    `<text x="70" y="69" text-anchor="middle" class="gv">${esc(valTxt)}</text>`+
    (unit?`<text x="70" y="88" text-anchor="middle" class="gu">${esc(unit)}</text>`:"")+
    `</svg><div class="lab">${esc(label)}</div></div>`;
}
function donut(segs,center){segs=segs.filter(s=>s.value>0);const t=segs.reduce((a,s)=>a+s.value,0);
  const r=54,c=2*Math.PI*r,gap=segs.length>1?c*0.02:0;let off=0,arcs="";
  if(!t)arcs=`<circle cx="70" cy="70" r="${r}" fill="none" stroke="var(--sc2)" stroke-width="16"/>`;
  segs.forEach(s=>{const seg=s.value/t*c,len=Math.max(.1,seg-gap);
    arcs+=`<circle cx="70" cy="70" r="${r}" fill="none" stroke="${s.color}" stroke-width="16" ${segs.length>1?'stroke-linecap="round"':''} stroke-dasharray="${len.toFixed(1)} ${(c-len).toFixed(1)}" stroke-dashoffset="${(-off-(segs.length>1?gap/2:0)).toFixed(1)}" transform="rotate(-90 70 70)"/>`;off+=seg;});
  return `<svg class="donut" viewBox="0 0 140 140" width="132" height="132">${arcs}<text x="70" y="67" text-anchor="middle" class="dn">${fmtN(t)}</text><text x="70" y="84" text-anchor="middle" class="dl">${esc(center||"")}</text></svg>`;}
const legend=segs=>{const t=segs.reduce((a,s)=>a+s.value,0)||1;return `<div class="legend">`+segs.filter(s=>s.value>0).map(s=>`<div class="lg"><span class="sw" style="background:${s.color}"></span><span class="lt">${esc(s.label)}</span><span class="lv">${fmtN(s.value)}</span></div>`).join("")+`</div>`;};
const fmtBytes=b=>{if(b==null)return"—";const u=["B","KB","MB","GB","TB"];let i=0,v=b;while(v>=1024&&i<u.length-1){v/=1024;i++;}return v.toFixed(v<10&&i>0?1:0)+" "+u[i];};

/* ---------- app bar ---------- */
function renderBar(){
  const m=DATA.meta;
  $("hmeta").textContent=[m.host,m.model&&m.model!=="unknown host"?m.model:null,fmtTs(m.generated)].filter(Boolean).join("  ·  ");
  const c=$("chip");const st=DATA.status||"ok";
  c.className="chip "+st;c.innerHTML=`<span class="d"></span>${st==="ok"?"all healthy":st==="warn"?"needs a look":st==="crit"?"attention":st}`;
  if(LIVE){$("live").className="live on";$("liveT").textContent="live";}
}

/* ---------- tabs ---------- */
const TABS=[["overview","Overview","gauge"],["host","Host","cpu"],["hermes","Hermes","brain"],["honcho","Honcho","layers"],["homeassistant","Home Assistant","home"]];
function buildNav(){
  const nav=$("nav");nav.innerHTML="";
  TABS.forEach(([id,label,icn],i)=>{
    const sec=S()[id]; const st=sec?sec.status:null;
    const b=document.createElement("button");b.dataset.tab=id;
    b.innerHTML=`${st&&st!=="ok"?`<span class="sd" style="background:${STC[st]}"></span>`:""}${esc(label)}`;
    if(i===0)b.classList.add("active");b.onclick=()=>activate(id);nav.appendChild(b);
  });
}
let CURRENT="overview";
function activate(id){CURRENT=id;
  document.querySelectorAll("#nav button").forEach(b=>b.classList.toggle("active",b.dataset.tab===id));
  render();window.scrollTo(0,0);
  if(id==="hermes")initAgentGraphIfNeeded();
}
function render(){
  const f={overview:renderOverview,host:renderHost,hermes:renderHermes,honcho:()=>renderSource("honcho"),homeassistant:()=>renderSource("homeassistant")}[CURRENT];
  $("main").innerHTML=`<section class="tab active">${f?f():""}</section>`;
  if(CURRENT==="hermes")wireHermes();
}

/* ---------- overview ---------- */
function hostGauges(){
  const d=(S().system||{}).data||{};const g=[];
  if(d.temp_c!=null)g.push(gauge("Temp",d.temp_c.toFixed(1),"°C",d.temp_c,(S().system||{}).status==="crit"?"crit":d.temp_c>=70?"warn":"ok"));
  if(d.cpu_percent!=null)g.push(gauge("CPU",d.cpu_percent.toFixed(0),"%",d.cpu_percent,d.cpu_percent>=90?"crit":d.cpu_percent>=70?"warn":"ok"));
  if(d.mem)g.push(gauge("Memory",d.mem.percent.toFixed(0),"%",d.mem.percent,d.mem.percent>=90?"crit":d.mem.percent>=85?"warn":"ok"));
  if(d.disk)g.push(gauge("Disk",d.disk.percent.toFixed(0),"%",d.disk.percent,d.disk.percent>=95?"crit":d.disk.percent>=85?"warn":"ok"));
  return g.length?`<div class="grid g-gauges" id="ovg">${g.join("")}</div>`:"";
}
function renderOverview(){
  let h=`<div class="stitle">${ic("gauge")} Host</div>`+(hostGauges()||`<div class="empty">No host metrics.</div>`);
  // source status cards
  h+=`<div class="stitle">${ic("layers")} Sources</div><div class="grid g-cards">`;
  TABS.filter(t=>t[0]!=="overview"&&t[0]!=="host").forEach(([id,label,icn])=>{
    const s=S()[id];if(!s)return;
    h+=`<div class="srccard clickable" onclick="activate('${id}')"><div class="h">${ic(icn)}<span class="nm">${esc(label)}</span>${chip(s.status,s.status==="off"?"off":s.status)}</div><div class="sm">${esc(s.summary||"")}</div></div>`;
  });
  h+=`</div>`;
  // recommended next steps from Hermes hygiene
  const ag=A();
  if(ag&&ag.hygiene&&ag.hygiene.findings){
    const sevr=["critical","high","medium","low","info"];
    const recs=[],seen=new Set();
    ag.hygiene.findings.slice().sort((a,b)=>sevr.indexOf(a.severity)-sevr.indexOf(b.severity)).forEach(f=>{if(f.remediation&&!seen.has(f.remediation)){seen.add(f.remediation);recs.push(f);}});
    if(recs.length){h+=`<div class="stitle">${ic("check")} Recommended next steps</div><div class="card">`+recs.slice(0,6).map(f=>`<div class="rec">${dot(f.severity==="critical"?"crit":f.severity==="high"?"warn":"off")}<div><div class="rt">${esc(f.remediation)}</div><div class="rm">${esc(f.title)}</div></div></div>`).join("")+`</div>`;}
  }
  return h;
}

/* ---------- host ---------- */
function renderHost(){
  const s=S().system||{},d=s.data||{};
  let h=`<div class="stitle">${ic("cpu")} ${esc(d.model||"Host")} ${s.status&&s.status!=="ok"?sevpill(s.status):""}</div>`;
  h+=hostGauges();
  const stats=[];
  if(d.load)stats.push(["Load (1m)",d.load[0].toFixed(2)]);
  if(d.cores!=null)stats.push(["Cores",d.cores]);
  if(d.mem)stats.push(["Memory",fmtBytes(d.mem.used)+" / "+fmtBytes(d.mem.total)]);
  if(d.disk)stats.push(["Disk",fmtBytes(d.disk.used)+" / "+fmtBytes(d.disk.total)]);
  if(d.uptime_s!=null)stats.push(["Uptime",fmtUp(d.uptime_s)]);
  if(stats.length)h+=`<div class="grid g-stats" style="margin-top:14px">`+stats.map(([l,v])=>`<div class="stat"><div class="n num">${esc(v)}</div><div class="l">${esc(l)}</div></div>`).join("")+`</div>`;
  if(d.throttle){const t=d.throttle;h+=`<div class="stitle">${ic("alert")} Power / throttle</div><div class="card"><div class="kv"><span class="k">state</span><span class="v">${t.now?'<span class="tag warn">throttled now</span>':t.ever?'<span class="tag warn">under-voltage / throttle in history</span>':'<span class="tag">healthy</span>'}</span></div>`+(t.flags&&t.flags.length?`<div class="kv"><span class="k">flags</span><span class="v">${t.flags.map(f=>`<span class="tag">${esc(f)}</span>`).join("")}</span></div>`:"")+`</div>`;}
  return h;
}
function fmtUp(s){const d=Math.floor(s/86400),h=Math.floor(s%86400/3600),m=Math.floor(s%3600/60);return d?`${d}d ${h}h`:h?`${h}h ${m}m`:`${m}m`;}

/* ---------- generic source (honcho / HA) ---------- */
function renderSource(id){
  const s=S()[id];if(!s)return `<div class="empty">No data.</div>`;
  if(!s.available)return `<div class="empty">${esc(s.title)} is ${esc(s.status==="off"?"not configured or not reachable":s.status)}.<div class="muted" style="margin-top:8px;font-size:13px">${esc(s.summary||"")}</div></div>`;
  const d=s.data||{};
  let h=`<div class="stitle">${ic(id==="honcho"?"layers":"home")} ${esc(s.title)} ${sevpill(s.status)}</div>`;
  const tiles=[];
  const push=(l,v)=>{if(v!=null&&v!=="")tiles.push([l,v]);};
  if(id==="honcho"){push("Version",d.version);push("Workspaces",d.workspaces);push("Peers",d.peers);push("Sessions",d.sessions);}
  else{push("Version",d.version);push("State",d.state);push("Components",d.components);push("Entities",d.entities);}
  if(tiles.length)h+=`<div class="grid g-stats">`+tiles.map(([l,v])=>`<div class="stat"><div class="n num">${esc(fmtMaybeN(v))}</div><div class="l">${esc(l)}</div></div>`).join("")+`</div>`;
  if(id==="homeassistant"&&d.domains&&Object.keys(d.domains).length){
    const segs=Object.entries(d.domains).slice(0,8).map(([k,v],i)=>({label:k,value:v,color:PAL[i%PAL.length]}));
    h+=`<div class="stitle">${ic("chart")} Entities by domain</div><div class="card"><div class="chart-body">${donut(segs,"entities")}${legend(segs)}</div></div>`;
  }
  if(id==="honcho"&&d.queue&&Object.keys(d.queue).length){
    h+=`<div class="stitle">Queue</div><div class="card">`+Object.entries(d.queue).map(([k,v])=>`<div class="kv"><span class="k">${esc(k)}</span><span class="v">${esc(v)}</span></div>`).join("")+`</div>`;
  }
  return h;
}
const fmtMaybeN=v=>typeof v==="number"?v.toLocaleString():v;

/* ---------- hermes (summary + agent subviews) ---------- */
let HSUB="summary";
function renderHermes(){
  const s=S().hermes;if(!s)return `<div class="empty">No Hermes data.</div>`;
  if(!s.available)return `<div class="empty">Hermes not found at <code>${esc((s.data||{}).home||"~/.hermes")}</code>. Run <code>insikt configure</code>.</div>`;
  const subs=[["summary","Summary"]];const ag=A();
  if(ag){subs.push(["capability","Capabilities"],["timeline","Timeline"],["cost","Models"],["hygiene","Hygiene"],["graph","Graph"]);}
  let h=`<div class="subnav">`+subs.map(([k,l])=>`<button class="${k===HSUB?"active":""}" data-sub="${k}">${esc(l)}</button>`).join("")+`</div><div id="hsub">${renderHermesSub()}</div>`;
  return h;
}
function wireHermes(){document.querySelectorAll(".subnav button").forEach(b=>b.onclick=()=>{HSUB=b.dataset.sub;document.querySelectorAll(".subnav button").forEach(x=>x.classList.toggle("active",x===b));$("hsub").innerHTML=renderHermesSub();if(HSUB==="graph")initAgentGraph();if(HSUB==="timeline")wireTimeline();});}
function renderHermesSub(){
  const s=S().hermes,d=s.data||{},ag=A();
  if(HSUB==="summary"){
    const tiles=[["Memories",d.memories],["Skills",d.skills],["Self-authored",d.self_authored],["Models",d.models],["Connectors",d.connectors],["Actions",d.actions]];
    let h=`<div class="grid g-stats">`+tiles.map(([l,v])=>`<div class="stat"><div class="n num">${fmtN(v)}</div><div class="l">${esc(l)}</div></div>`).join("")+`</div>`;
    const meta=[d.default_model&&("model "+d.default_model),d.gateway_platforms&&("via "+(d.gateway_platforms||[]).join(", ")),d.open_connectors&&d.open_connectors.length&&("open: "+d.open_connectors.join(", "))].filter(Boolean);
    if(meta.length)h+=`<div class="card" style="margin-top:14px"><div class="sm muted">${meta.map(esc).join("  ·  ")}</div></div>`;
    return h;
  }
  if(!ag)return `<div class="empty">No agent data.</div>`;
  if(HSUB==="capability")return renderCap(ag.capability);
  if(HSUB==="timeline")return renderTimeline(ag.timeline);
  if(HSUB==="cost")return renderCost(ag.cost);
  if(HSUB==="hygiene")return renderHygiene(ag.hygiene);
  if(HSUB==="graph")return `<div id="gw"><canvas id="graph"></canvas><div id="glegend"></div></div>`;
  return "";
}
function renderCap(cap){
  if(!cap||!cap.agents.length)return `<div class="empty">No capabilities.</div>`;
  let h="";cap.agents.forEach(a=>{(a.skills||[]).forEach(sk=>{
    const badges=[sk.self_authored?'<span class="tag self">self-authored</span>':"",sk.use_count===0?'<span class="tag">never used</span>':(sk.use_count>0?`<span class="tag">used ${sk.use_count}&times;</span>`:""),sk.risk?sevpill(sk.risk):""].join("");
    h+=`<div class="card" style="margin-bottom:10px"><div style="display:flex;gap:9px;align-items:center;flex-wrap:wrap"><span style="font-weight:600">${esc(sk.name)}</span>${badges}<span class="faint" style="margin-left:auto;font-size:12px">${esc(sk.kind||sk.source||"")}</span></div>`;
    if((sk.tools||[]).length)h+=`<div class="kv"><span class="k">can use</span><span class="v">${sk.tools.map(t=>`<span class="tag">${esc(t)}</span>`).join("")}</span></div>`;
    if((sk.reaches||[]).length)h+=`<div class="kv"><span class="k">can reach</span><span class="v">${sk.reaches.map(r=>`<span class="tag">${esc(r.value)}</span>`).join("")}</span></div>`;
    if((sk.credential_reads||[]).length)h+=`<div class="kv"><span class="k">reads</span><span class="v">${sk.credential_reads.map(c=>`<span class="tag">${esc(c)}</span>`).join("")}</span></div>`;
    h+=`</div>`;});});
  return h;
}
function renderTimeline(tl){
  if(!tl||!tl.actions.length)return `<div class="empty">No actions.</div>`;
  const types=[...new Set(tl.actions.map(a=>a.type))].sort();
  let h=`<div class="filters"><select id="ft"><option value="">All types</option>${types.map(t=>`<option>${esc(t)}</option>`).join("")}</select></div><div id="tlb"></div>`;
  return h;
}
function wireTimeline(){const sel=$("ft");if(!sel)return;const tl=A().timeline;
  const draw=()=>{const ft=sel.value;const rows=tl.actions.filter(a=>!ft||a.type===ft);
    $("tlb").innerHTML=rows.length?`<div class="card">`+rows.map(a=>{const meta=[a.agent,a.skill&&("via "+a.skill),a.model,a.connector&&("→ "+a.connector),a.resource&&("→ "+a.resource)].filter(Boolean).map(esc).join("  ·  ");return `<div class="ev"><div class="wn">${esc(fmtTs(a.ts))||"—"}</div><div><div class="es"><span class="pill p-info"><span class="d"></span>${esc(a.type)}</span> ${esc(a.summary)}</div><div class="em">${meta}${a.tokens?" · "+fmtN(a.tokens)+" tok":""}${a.cost!=null?" · $"+Number(a.cost).toFixed(4):""}</div></div></div>`;}).join("")+`</div>`:`<div class="empty">No actions.</div>`;};
  sel.onchange=draw;draw();}
function renderCost(c){
  if(!c)return "";const role=m=>[m.default?'<span class="tag self">default</span>':"",(m.used||m.calls)?'<span class="tag">used</span>':'<span class="tag">unused</span>'].join(" ");
  let h=`<div class="grid g-stats"><div class="stat"><div class="n num">$${(c.total_cost||0).toFixed(4)}</div><div class="l">Recorded spend</div></div><div class="stat"><div class="n num">${fmtN(c.total_tokens)}</div><div class="l">Tokens</div></div></div>`;
  h+=(c.models||[]).length?`<div class="tbl scroll" style="margin-top:14px"><table><thead><tr><th>Model</th><th>Role</th><th class="n">Calls</th><th class="n">Tokens</th><th class="n">Cost</th></tr></thead><tbody>`+c.models.map(m=>`<tr><td>${esc(m.model)}</td><td>${role(m)}</td><td class="n">${fmtN(m.calls)}</td><td class="n">${fmtN(m.tokens||0)}</td><td class="n">$${(m.cost||0).toFixed(4)}</td></tr>`).join("")+`</tbody></table></div>`:`<div class="empty">No models.</div>`;
  return h;
}
function renderHygiene(hy){
  if(!hy||!hy.findings.length)return `<div class="empty">No findings.</div>`;
  const sevr=["critical","high","medium","low","info"];const KC={capability:"cap",config:"config",alert:"alert"};
  const fs=hy.findings.slice().sort((a,b)=>sevr.indexOf(a.severity)-sevr.indexOf(b.severity));
  const cnt={};fs.forEach(f=>cnt[f.severity]=(cnt[f.severity]||0)+1);
  let h=`<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px">`+sevr.filter(s=>cnt[s]).map(s=>`<span class="pill p-${s}"><span class="d"></span>${cnt[s]} ${s}</span>`).join("")+`</div>`;
  sevr.forEach(sv=>{const g=fs.filter(f=>f.severity===sv);if(!g.length)return;const open=(sv==="critical"||sv==="high")?" open":"";
    h+=`<details class="grp"${open}><summary><span class="pill p-${sv}"><span class="d"></span>${sv}</span><span class="gc">${g.length} finding${g.length>1?"s":""}</span><span class="cv">›</span></summary>`;
    g.forEach(f=>{const kd=f.kind||"capability";h+=`<div class="finding">${dot(sv==="critical"?"crit":sv==="high"?"warn":"off")}<div><div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap"><span class="fn">${esc(f.title)}</span><span class="tag ${KC[kd]||"cap"}">${esc(kd)}</span></div><div class="fd">${esc(f.detail)}</div>${(f.factors||[]).length?`<div class="ff">${f.factors.map(esc).join(" · ")}</div>`:""}${f.remediation?`<div class="rem">${ic("check")}<span>${esc(f.remediation)}</span></div>`:""}</div></div>`;});
    h+=`</details>`;});
  return h;
}

/* ---------- agent graph (canvas) ---------- */
let GRAPH_INIT=false;
function initAgentGraphIfNeeded(){}
function initAgentGraph(){
  const ag=A();if(!ag||!ag.graph)return;const canvas=$("graph");if(!canvas)return;
  const TC={agent:"#ff3d77",skill:"#5b8cff",tool:"#b06cff",model:"#2ee6a8",connector:"#ffb648",resource:"#7c8cff",credential_ref:"#ff7eb3",action:"#5b6291"};
  const RISK={critical:"#ff4d6d",high:"#ffb648",medium:"#ff7eb3"};
  $("glegend").innerHTML=Object.entries(TC).map(([t,c])=>`<div class="r"><span class="gsw" style="background:${c}"></span>${t.replace("_"," ")}</div>`).join("");
  const ctx=canvas.getContext("2d"),nm=new Map();
  const nodes=ag.graph.nodes.map((n,i)=>{const a=i*2.39996,r=40+8*Math.sqrt(i);const o={...n,x:Math.cos(a)*r,y:Math.sin(a)*r,vx:0,vy:0};nm.set(n.id,o);return o;});
  const edges=ag.graph.edges.filter(e=>nm.has(e.src)&&nm.has(e.dst)).map(e=>({s:nm.get(e.src),t:nm.get(e.dst)}));
  const deg=new Map();edges.forEach(e=>{deg.set(e.s.id,(deg.get(e.s.id)||0)+1);deg.set(e.t.id,(deg.get(e.t.id)||0)+1);});
  const rad=n=>n.type==="agent"?12:n.type==="action"?3.2:6+Math.min(4,(deg.get(n.id)||0));
  let view={k:1,x:0,y:0},alpha=1,dpr=Math.max(1,window.devicePixelRatio||1);
  function tick(){const rep=2200,spr=.02,rest=46,cen=.012;for(let i=0;i<nodes.length;i++){const a=nodes[i];for(let j=i+1;j<nodes.length;j++){const b=nodes[j];let dx=a.x-b.x,dy=a.y-b.y,d2=dx*dx+dy*dy;if(d2<.01)d2=.01;const f=rep/d2,d=Math.sqrt(d2),fx=f*dx/d,fy=f*dy/d;a.vx+=fx;a.vy+=fy;b.vx-=fx;b.vy-=fy;}a.vx-=a.x*cen;a.vy-=a.y*cen;}edges.forEach(e=>{let dx=e.t.x-e.s.x,dy=e.t.y-e.s.y,d=Math.sqrt(dx*dx+dy*dy)||.01;const f=spr*(d-rest),fx=f*dx/d,fy=f*dy/d;e.s.vx+=fx;e.s.vy+=fy;e.t.vx-=fx;e.t.vy-=fy;});nodes.forEach(n=>{if(n.fixed)return;n.vx*=.86;n.vy*=.86;n.x+=n.vx*alpha;n.y+=n.vy*alpha;});alpha*=.992;if(alpha<.02)alpha=.02;}
  function fit(){let a=1e9,b=1e9,c=-1e9,d=-1e9;nodes.forEach(n=>{a=Math.min(a,n.x);b=Math.min(b,n.y);c=Math.max(c,n.x);d=Math.max(d,n.y);});const w=canvas.clientWidth,h=canvas.clientHeight;view.k=Math.min(w/(Math.max(1,c-a)+80),h/(Math.max(1,d-b)+80),2.2);view.x=w/2-(a+c)/2*view.k;view.y=h/2-(b+d)/2*view.k;}
  function resize(){dpr=Math.max(1,window.devicePixelRatio||1);canvas.width=canvas.clientWidth*dpr;canvas.height=canvas.clientHeight*dpr;}
  function draw(){ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,canvas.clientWidth,canvas.clientHeight);ctx.save();ctx.translate(view.x,view.y);ctx.scale(view.k,view.k);ctx.lineWidth=.6/view.k;ctx.strokeStyle="rgba(140,150,170,.2)";ctx.beginPath();edges.forEach(e=>{ctx.moveTo(e.s.x,e.s.y);ctx.lineTo(e.t.x,e.t.y);});ctx.stroke();nodes.forEach(n=>{const r=rad(n);ctx.beginPath();ctx.arc(n.x,n.y,r,0,6.2832);ctx.fillStyle=TC[n.type]||"#999";ctx.fill();if(RISK[n.risk]){ctx.lineWidth=2/view.k;ctx.strokeStyle=RISK[n.risk];ctx.stroke();}if(view.k>.85&&n.type!=="action"&&n.type!=="resource"){ctx.fillStyle="rgba(230,226,232,.8)";ctx.font=`${10/view.k}px sans-serif`;ctx.fillText(n.label,n.x+r+1.5,n.y+3/view.k);}});ctx.restore();}
  let loop=false;function run(){let n=0;const r=()=>{for(let s=0;s<3;s++)tick();draw();if(alpha>.025&&n++<1500)requestAnimationFrame(r);else{loop=false;draw();}};if(!loop){loop=true;requestAnimationFrame(r);}}
  resize();fit();run();window.addEventListener("resize",()=>{resize();draw();});
  // drag/pan/zoom
  function pt(ev){const r=canvas.getBoundingClientRect();const t=ev.touches?ev.touches[0]:ev;return{x:t.clientX-r.left,y:t.clientY-r.top};}
  function tw(p){return{x:(p.x-view.x)/view.k,y:(p.y-view.y)/view.k};}
  function pick(w){let best=null,bd=1e9;nodes.forEach(n=>{const dx=n.x-w.x,dy=n.y-w.y,d=dx*dx+dy*dy,r=rad(n)+6;if(d<r*r&&d<bd){bd=d;best=n;}});return best;}
  let drag=null,pan=null;
  canvas.addEventListener("mousedown",e=>{const p=pt(e),n=pick(tw(p));if(n){drag=n;n.fixed=true;}else pan={x:p.x,y:p.y,ox:view.x,oy:view.y};});
  window.addEventListener("mousemove",e=>{if(drag){const w=tw(pt(e));drag.x=w.x;drag.y=w.y;drag.vx=drag.vy=0;alpha=Math.max(alpha,.3);run();}else if(pan){const p=pt(e);view.x=pan.ox+(p.x-pan.x);view.y=pan.oy+(p.y-pan.y);draw();}});
  window.addEventListener("mouseup",()=>{if(drag)drag.fixed=false;drag=pan=null;});
  canvas.addEventListener("wheel",e=>{e.preventDefault();const r=canvas.getBoundingClientRect(),mx=e.clientX-r.left,my=e.clientY-r.top,f=e.deltaY<0?1.1:.9,wx=(mx-view.x)/view.k,wy=(my-view.y)/view.k;view.k=Math.min(6,Math.max(.15,view.k*f));view.x=mx-wx*view.k;view.y=my-wy*view.k;draw();},{passive:false});
}

/* ---------- live (SSE) ---------- */
function startLive(){
  if(!LIVE||!window.EventSource)return;
  try{
    const es=new EventSource("/events");
    es.onmessage=ev=>{try{const m=JSON.parse(ev.data);if(m.host)DATA.sections.system=m.host;if(m.status)DATA.status=m.status;if(m.generated)DATA.meta.generated=m.generated;
      renderBar();
      // refresh nav status dots + the active host/overview view
      buildNav();document.querySelector(`#nav button[data-tab="${CURRENT}"]`)?.classList.add("active");
      if(CURRENT==="overview"||CURRENT==="host")render();
    }catch(e){}};
  }catch(e){}
}

renderBar();buildNav();render();startLive();
</script>
</body>
</html>"""
