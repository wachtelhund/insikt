"""Render the whole-system dashboard to a single self-contained HTML file."""

from __future__ import annotations

import html as _html
import json


def render_dashboard(state: dict, live: bool = False) -> str:
    data = json.dumps(state, default=str).replace("</", "<\\/")
    # The terminal (xterm.js) is a live-server-only feature; its assets are
    # served by the server, so the offline `scan` HTML stays a single file.
    assets = ""
    if live and (state.get("meta") or {}).get("terminal"):
        assets = ('<link rel="stylesheet" href="/assets/xterm.css">'
                  '<script src="/assets/xterm.js"></script>'
                  '<script src="/assets/addon-fit.js"></script>')
    return (
        _TEMPLATE
        .replace("__TITLE__", _html.escape(f"Insikt — {state.get('meta', {}).get('host', 'system')}"))
        .replace("__ASSETS__", assets)
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
__ASSETS__
<style>
  :root{
    /* brand palette — Color 800..100 neutral ramp + primary/secondary accents */
    --bg:#080F25; --sc:#101935; --sc2:#212C4D; --sc3:#37446B;
    --on:#FFFFFF; --on2:#AEB9E1; --on3:#7E89AC;
    --primary:#6C72FF; --cyan:#57C3FF; --lav:#9A91FB; --amber:#FDB52A;
    --ok:#57C3FF; --warn:#FDB52A; --crit:#FF5C7C; --off:#7E89AC;
    --line:rgba(55,68,107,.45);
    --grad:linear-gradient(135deg,#C95CFF 0%,#6C72FF 100%);
    --r:18px; --r2:14px; --r3:10px; --pad:22px;
  }
  *{box-sizing:border-box}
  html,body{overflow-x:hidden;max-width:100%}
  body{margin:0;background:var(--bg);color:var(--on);
    background-image:radial-gradient(130% 105% at 88% -12%,rgba(108,114,255,.15) 0%,rgba(8,15,37,0) 52%),radial-gradient(120% 120% at 0% 0%,rgba(154,145,251,.10) 0%,rgba(8,15,37,0) 45%);
    background-attachment:fixed;
    font:14.5px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,system-ui,Arial,sans-serif;
    -webkit-font-smoothing:antialiased;padding-bottom:calc(48px + env(safe-area-inset-bottom))}
  .num{font-variant-numeric:tabular-nums;font-feature-settings:"tnum" 1}
  .wrap{max-width:1080px;margin:0 auto;padding:0 22px}
  svg.ic{width:17px;height:17px;vertical-align:-3px}

  .top{position:sticky;top:0;z-index:30;background:rgba(8,15,37,.72);backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);border-bottom:1px solid var(--line)}
  .appbar{display:flex;align-items:center;gap:13px;flex-wrap:wrap;padding:16px 0}
  .brand{display:flex;align-items:center;gap:10px;font-size:16px;font-weight:680;letter-spacing:-.01em}
  .brand .mk{width:13px;height:13px;border-radius:50%;background:var(--grad);box-shadow:0 0 12px rgba(108,114,255,.55)}
  .hmeta{color:var(--on2);font-size:12.5px;flex:1;min-width:140px;overflow-wrap:anywhere}
  .live{display:inline-flex;align-items:center;gap:6px;font-size:11.5px;color:var(--on3)}
  .live .pulse{width:7px;height:7px;border-radius:50%;background:var(--off)}
  .live.on .pulse{background:var(--ok);box-shadow:0 0 8px var(--ok);animation:pulse 2s infinite}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.35}}
  .rbtn{background:var(--sc2);border:1px solid var(--line);color:var(--on2);width:34px;height:34px;border-radius:9px;cursor:pointer;display:inline-flex;align-items:center;justify-content:center;padding:0}
  .rbtn:hover{color:var(--on);border-color:rgba(108,114,255,.55)}
  .rbtn .ic{width:16px;height:16px}
  .rbtn.spin .ic{animation:rot .8s linear infinite;transform-origin:50% 50%}
  @keyframes rot{to{transform:rotate(360deg)}}
  .chip{display:inline-flex;align-items:center;gap:7px;font-weight:600;font-size:12.5px;padding:6px 13px;border-radius:999px}
  .chip .d{width:7px;height:7px;border-radius:50%}
  .chip.ok{background:rgba(87,195,255,.16);color:var(--ok)} .chip.ok .d{background:var(--ok);box-shadow:0 0 7px var(--ok)}
  .chip.warn{background:rgba(253,181,42,.16);color:var(--warn)} .chip.warn .d{background:var(--warn);box-shadow:0 0 7px var(--warn)}
  .chip.crit{background:rgba(255,92,124,.17);color:var(--crit)} .chip.crit .d{background:var(--crit);box-shadow:0 0 7px var(--crit)}
  .chip.off{background:rgba(126,137,172,.18);color:var(--on2)} .chip.off .d{background:var(--off)}
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

  main{padding:36px 0 56px}
  section.tab{display:none;animation:f .16s ease}
  section.tab.active{display:block}
  @keyframes f{from{opacity:0;transform:translateY(3px)}to{opacity:1;transform:none}}
  .stitle{font-size:14px;font-weight:650;color:var(--on);margin:32px 0 20px;display:flex;align-items:center;gap:9px;flex-wrap:wrap;min-width:0;overflow-wrap:anywhere}
  .stitle:first-child{margin-top:4px}
  .stitle .ic{color:var(--on3);width:15px;height:15px}

  .grid{display:grid;gap:14px}
  .g-gauges{grid-template-columns:repeat(auto-fit,minmax(min(150px,100%),1fr))}
  .g-cards{grid-template-columns:repeat(auto-fit,minmax(min(240px,100%),1fr))}
  .g-stats{grid-template-columns:repeat(auto-fit,minmax(min(120px,100%),1fr))}

  .card{background:linear-gradient(180deg,rgba(255,255,255,.022),rgba(255,255,255,0)) ,var(--sc);border:1px solid var(--line);border-radius:var(--r);padding:var(--pad)}
  .card-t{font-size:13px;font-weight:600;color:var(--on2);margin-bottom:14px}
  .gauge{display:flex;flex-direction:column;align-items:center;text-align:center;background:linear-gradient(180deg,rgba(255,255,255,.022),rgba(255,255,255,0)) ,var(--sc);border:1px solid var(--line);border-radius:var(--r2);padding:18px 10px 15px}
  .gauge .lab{color:var(--on2);font-size:12.5px;margin-top:9px;letter-spacing:.01em}
  .gv{fill:#fff;font-size:23px;font-weight:700;font-variant-numeric:tabular-nums}
  .gu{fill:var(--on3);font-size:10px}
  .g-ok{filter:drop-shadow(0 0 5px rgba(87,195,255,.5))}
  .g-warn{filter:drop-shadow(0 0 5px rgba(253,181,42,.5))}
  .g-crit{filter:drop-shadow(0 0 6px rgba(255,92,124,.55))}
  .g-off{filter:none}
  .garc{transition:stroke-dasharray .7s cubic-bezier(.4,0,.2,1)}  /* animate gauges on value change */
  .gv{transition:none}
  .stat{background:linear-gradient(180deg,rgba(255,255,255,.022),rgba(255,255,255,0)) ,var(--sc);border:1px solid var(--line);border-radius:var(--r2);padding:16px 18px}
  .stat .n{font-size:23px;font-weight:700;letter-spacing:-.02em}
  .stat .l{color:var(--on2);font-size:12.5px;margin-top:4px}

  .srccard{background:linear-gradient(180deg,rgba(255,255,255,.022),rgba(255,255,255,0)) ,var(--sc);border:1px solid var(--line);border-radius:var(--r);padding:18px 20px;display:flex;flex-direction:column;gap:9px}
  .srccard .h{display:flex;align-items:center;gap:9px}
  .srccard .nm{font-weight:600;font-size:15px}
  .sm{color:var(--on2);font-size:13px;line-height:1.5}
  .srccard.clickable{cursor:pointer;transition:border-color .14s,transform .14s}
  .srccard.clickable:hover{border-color:rgba(108,114,255,.5);transform:translateY(-1px)}

  .pill{display:inline-flex;align-items:center;gap:6px;padding:2px 10px;border-radius:999px;font-size:11px;font-weight:600;text-transform:capitalize}
  .pill .d{width:6px;height:6px;border-radius:50%}
  .p-ok{background:rgba(87,195,255,.16);color:var(--ok)} .p-ok .d{background:var(--ok)}
  .p-warn{background:rgba(253,181,42,.16);color:var(--warn)} .p-warn .d{background:var(--warn)}
  .p-crit{background:rgba(255,92,124,.17);color:var(--crit)} .p-crit .d{background:var(--crit)}
  .p-off{background:rgba(126,137,172,.18);color:var(--on2)} .p-off .d{background:var(--off)}
  .p-critical{background:rgba(255,92,124,.17);color:var(--crit)} .p-critical .d{background:var(--crit)}
  .p-high{background:rgba(253,181,42,.16);color:var(--warn)} .p-high .d{background:var(--warn)}
  .p-medium{background:rgba(154,145,251,.18);color:var(--lav)} .p-medium .d{background:var(--lav)}
  .p-low{background:rgba(87,195,255,.16);color:var(--ok)} .p-low .d{background:var(--ok)}
  .p-info{background:rgba(126,137,172,.18);color:var(--on2)} .p-info .d{background:var(--on3)}
  .tag{display:inline-block;background:var(--sc2);color:var(--on2);border-radius:8px;padding:2px 9px;font-size:11.5px;margin:2px 4px 0 0;overflow-wrap:anywhere;word-break:break-word;max-width:100%}
  .tag.self{background:rgba(201,92,255,.18);color:#d49bff}
  .tag.warn{background:rgba(255,92,124,.16);color:var(--crit)}
  .tag.cap{background:rgba(108,114,255,.18);color:#aab0ff}
  .tag.config{background:rgba(253,181,42,.15);color:var(--warn)}
  .tag.alert{background:rgba(255,92,124,.17);color:var(--crit)}
  .muted{color:var(--on2)} .faint{color:var(--on3)}
  .hrow{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
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
  .rem{margin-top:10px;display:flex;gap:8px;background:rgba(87,195,255,.08);border:1px solid rgba(87,195,255,.2);border-radius:9px;padding:9px 12px;font-size:13px}
  .rem .ic{color:var(--cyan);flex:0 0 auto;margin-top:1px;width:15px;height:15px}

  /* donut + legend */
  svg.donut{flex:0 0 auto}
  .dn{fill:#fff;font-size:23px;font-weight:700} .dl{fill:var(--on3);font-size:10px;letter-spacing:.1em}
  .chart-body{display:flex;gap:30px;align-items:center;justify-content:center;flex-wrap:wrap;padding:6px 0}
  .legend{display:grid;grid-template-columns:1fr 1fr;gap:9px 22px;flex:0 1 360px;min-width:200px}
  .lg{display:flex;align-items:center;gap:11px;font-size:13.5px}
  .lg .sw{width:11px;height:11px;border-radius:4px} .lg .lt{color:var(--on2);flex:1;text-transform:capitalize}
  .lg .lv{font-weight:600;font-variant-numeric:tabular-nums}

  /* host history (area/line charts) */
  .hist .hh{display:flex;align-items:baseline;justify-content:space-between;gap:10px}
  .hist .ht{color:var(--on2);font-size:13px;font-weight:600}
  .hist .hv{font-size:19px;font-weight:700;font-variant-numeric:tabular-nums}
  .hist .hr{color:var(--on3);font-size:11.5px;font-variant-numeric:tabular-nums}
  .spark{width:100%;height:88px;display:block;margin-top:10px}
  .hint{color:var(--on3);font-size:12px;font-weight:400;margin-left:4px}
  .card.hist.clickable{cursor:pointer;transition:border-color .14s,transform .14s}
  .card.hist.clickable:hover{border-color:rgba(108,114,255,.5);transform:translateY(-1px)}

  /* metric detail modal */
  .modal{position:fixed;inset:0;z-index:50;display:flex;align-items:center;justify-content:center;padding:20px}
  .modal[hidden]{display:none}
  .mbg{position:absolute;inset:0;background:rgba(8,15,37,.72);backdrop-filter:blur(4px);-webkit-backdrop-filter:blur(4px)}
  .sheet{position:relative;background:var(--sc);border:1px solid var(--line);border-radius:var(--r);padding:var(--pad);width:min(720px,100%);max-height:88vh;overflow:auto;box-shadow:0 24px 60px rgba(0,0,0,.5);animation:pop .18s ease}
  @keyframes pop{from{opacity:0;transform:translateY(10px) scale(.99)}to{opacity:1;transform:none}}
  .shead{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;gap:12px}
  .shead .st{font-weight:680;font-size:15px;display:flex;align-items:center;gap:8px}
  .mx{flex:0 0 auto;background:var(--sc2);border:none;color:var(--on2);width:32px;height:32px;border-radius:9px;cursor:pointer;font-size:14px}
  .mx:hover{color:var(--on);background:var(--sc3)}
  .bigwrap{position:relative;height:230px;padding-left:48px;margin:4px 0 0}
  .bigwrap .spark.big{height:230px;margin:0}
  .chgrid{position:absolute;left:0;right:0;top:0;height:230px;pointer-events:none}
  .gridrow{position:absolute;left:48px;right:0;border-top:1px dashed rgba(126,137,172,.16)}
  .gridrow .yl{position:absolute;left:-48px;top:0;transform:translateY(-50%);width:42px;text-align:right;font-size:10.5px;color:var(--on3)}
  .xlabels{display:flex;justify-content:space-between;color:var(--on3);font-size:11px;padding-left:48px;margin:8px 0 18px}

  /* timeline + table + graph (Hermes subviews) */
  .ev{display:flex;gap:14px;padding:13px 0}
  .ev+.ev{border-top:1px solid var(--line)}
  .ev>div:last-child{min-width:0}
  .ev .wn{color:var(--on3);font-size:12px;flex:0 0 92px;white-space:nowrap;padding-top:2px;font-variant-numeric:tabular-nums}
  .ev .es{font-size:13.5px;display:flex;gap:7px;align-items:center;flex-wrap:wrap}
  .ev .em{color:var(--on3);font-size:12px;margin-top:4px;overflow-wrap:anywhere}
  .tbl{background:var(--sc);border:1px solid var(--line);border-radius:var(--r);overflow:hidden}.scroll{overflow-x:auto}
  table{width:100%;border-collapse:collapse}
  .scroll table{min-width:420px}
  th,td{text-align:left;padding:13px 16px;font-size:13.5px;white-space:nowrap}
  td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
  th{color:var(--on3);font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.05em}
  tbody tr+tr td{border-top:1px solid var(--line)}
  .subnav{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:16px}
  .subnav button{background:var(--sc);border:1px solid var(--line);color:var(--on2);padding:9px 14px;border-radius:999px;font-size:13px;cursor:pointer;transition:.14s}
  .subnav button:hover{color:var(--on);border-color:rgba(108,114,255,.45)}
  .subnav button.active{background:var(--grad);border-color:transparent;color:#fff;font-weight:650;box-shadow:0 4px 14px rgba(108,114,255,.35)}
  nav button:focus-visible,.subnav button:focus-visible,select:focus-visible,.srccard.clickable:focus-visible,details.grp>summary:focus-visible{outline:2px solid var(--cyan);outline-offset:2px;border-radius:8px}
  .filters{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px}
  select{background:var(--sc);color:var(--on);border:1px solid var(--line);border-radius:var(--r3);padding:10px 32px 10px 13px;font-size:13.5px;min-height:42px;cursor:pointer;appearance:none;
    background-image:url("data:image/svg+xml,%3Csvg width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%23AEB9E1' stroke-width='2.5' stroke-linecap='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:right 12px center}
  #gw{position:relative;height:70vh;min-height:420px;border:1px solid var(--line);border-radius:var(--r);overflow:hidden;background:radial-gradient(120% 90% at 50% 25%,var(--sc2),var(--bg));touch-action:none}
  #graph{width:100%;height:100%;display:block;cursor:grab}
  #glegend{position:absolute;top:12px;left:12px;background:rgba(8,15,37,.8);border:1px solid var(--line);border-radius:10px;padding:9px 11px;font-size:11px;color:var(--on2)}
  #glegend .r{display:flex;align-items:center;gap:8px;margin:2px 0}.gsw{width:9px;height:9px;border-radius:50%}
  code{background:var(--sc2);padding:1px 6px;border-radius:6px;font-size:12px;overflow-wrap:anywhere;word-break:break-word}

  /* chat with Hermes */
  .chat{display:flex;flex-direction:column;gap:12px;height:min(520px,68vh);background:var(--sc);border:1px solid var(--line);border-radius:var(--r);padding:16px}
  .clog{flex:1;min-height:0;display:flex;flex-direction:column;gap:10px;overflow-y:auto;padding:2px 4px}
  .cempty{color:var(--on3);text-align:center;margin:auto;padding:16px}
  .cmsg{display:flex}.cmsg.you{justify-content:flex-end}
  .cmsg .cb{max-width:82%;padding:10px 13px;border-radius:14px;font-size:13.5px;line-height:1.55;white-space:pre-wrap;overflow-wrap:anywhere}
  .cmsg.you .cb{background:var(--grad);color:#fff;border-bottom-right-radius:4px}
  .cmsg.hermes .cb{background:var(--sc2);color:var(--on);border:1px solid var(--line);border-bottom-left-radius:4px}
  .cmsg.pending .cb{color:var(--on3)}
  .cform{flex:0 0 auto;display:flex;gap:9px}
  .cform input{flex:1;min-width:0;background:var(--sc);color:var(--on);border:1px solid var(--line);border-radius:var(--r3);padding:11px 14px;font-size:14px;min-height:46px}
  .cform input:focus{outline:none;border-color:var(--primary)}
  .cform button{background:var(--grad);color:#fff;border:none;border-radius:var(--r3);padding:0 22px;font-weight:600;font-size:14px;cursor:pointer;min-height:46px}
  .cform button:disabled{opacity:.5;cursor:default}
  .cclear{display:block;margin-top:10px;background:none;border:none;color:var(--on3);font-size:12px;cursor:pointer;padding:0}
  .cclear:hover{color:var(--on2);text-decoration:underline}

  /* web terminal (xterm.js, opt-in) */
  .term{height:min(560px,72vh);background:#0a0f22;border:1px solid var(--line);border-radius:var(--r);overflow:hidden;padding:8px 6px 6px 12px}
  .xtwrap{width:100%;height:100%}
  .xtwrap .xterm{height:100%}

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
  <linearGradient id="gg-ok" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#57C3FF"/><stop offset="1" stop-color="#6C72FF"/></linearGradient>
  <linearGradient id="gg-warn" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FDB52A"/><stop offset="1" stop-color="#FFD36A"/></linearGradient>
  <linearGradient id="gg-crit" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FF5C7C"/><stop offset="1" stop-color="#C95CFF"/></linearGradient>
  <linearGradient id="gg-off" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#37446B"/><stop offset="1" stop-color="#7E89AC"/></linearGradient>
</defs></svg>
<div class="top"><div class="wrap">
  <div class="appbar">
    <span class="brand"><span class="mk"></span>Insikt</span>
    <span class="hmeta num" id="hmeta"></span>
    <span class="live" id="live"><span class="pulse"></span><span id="liveT">snapshot</span></span>
    <button class="rbtn" id="refresh" title="Refresh now" aria-label="Refresh" hidden><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-2.64-6.36"/><path d="M21 4v5h-5"/></svg></button>
    <span class="chip" id="chip"></span>
  </div></div>
  <nav><div class="wrap" id="nav"></div></nav>
</div>
<main class="wrap" id="main"></main>
<div id="modal" class="modal" hidden><div class="mbg" onclick="closeModal()"></div><div class="sheet" id="sheet"></div></div>

<script id="d" type="application/json">__DATA__</script>
<script>
"use strict";
const DATA=JSON.parse(document.getElementById("d").textContent);
const LIVE=__LIVE__;
const S=()=>DATA.sections||{};
const A=()=>DATA.agent;
const secOf=id=>(id==="host"?S().system:S()[id])||null;  // the "host" tab maps to the "system" section
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
  terminal:'<rect x="3" y="4" width="18" height="16" rx="2"/><path d="m7 9 3 3-3 3"/><line x1="13" y1="15" x2="17" y2="15"/>',
};
const ic=n=>`<svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${I[n]||""}</svg>`;
const fmtTs=t=>(t||"").replace("T"," ").replace(/[.+Z].*/,"");
const PAL=["#6C72FF","#57C3FF","#9A91FB","#FDB52A","#C95CFF","#4FB0FF","#FF8FB1","#7E89AC"];

function gauge(label,valTxt,unit,pct,status,key){
  status=STC[status]?status:"off";const grad=`url(#gg-${status})`;
  pct=Math.max(0,Math.min(100,pct||0));const r=52,c=2*Math.PI*r,len=pct/100*c;
  return `<div class="gauge"${key?` data-g="${key}"`:""}><svg viewBox="0 0 140 140" width="116" height="116">`+
    `<circle cx="70" cy="70" r="${r}" fill="none" stroke="rgba(126,137,172,.16)" stroke-width="13"/>`+
    `<circle class="garc g-${status}" cx="70" cy="70" r="${r}" fill="none" stroke="${grad}" stroke-width="13" stroke-linecap="round" stroke-dasharray="${len.toFixed(1)} ${(c-len).toFixed(1)}" transform="rotate(-90 70 70)"/>`+
    `<text x="70" y="69" text-anchor="middle" class="gv">${esc(valTxt)}</text>`+
    (unit?`<text x="70" y="88" text-anchor="middle" class="gu">${esc(unit)}</text>`:"")+
    `</svg><div class="lab">${esc(label)}</div></div>`;
}
function donut(segs,center){segs=segs.filter(s=>s.value>0);const t=segs.reduce((a,s)=>a+s.value,0);
  const r=52,c=2*Math.PI*r,gap=segs.length>1?c*0.02:0;let off=0,arcs="";  // geometry matches gauge()
  if(!t)arcs=`<circle cx="70" cy="70" r="${r}" fill="none" stroke="rgba(126,137,172,.16)" stroke-width="13"/>`;
  segs.forEach(s=>{const seg=s.value/t*c,len=Math.max(.1,seg-gap);
    arcs+=`<circle cx="70" cy="70" r="${r}" fill="none" stroke="${s.color}" stroke-width="13" ${segs.length>1?'stroke-linecap="round"':''} stroke-dasharray="${len.toFixed(1)} ${(c-len).toFixed(1)}" stroke-dashoffset="${(-off-(segs.length>1?gap/2:0)).toFixed(1)}" transform="rotate(-90 70 70)"/>`;off+=seg;});
  return `<svg class="donut" viewBox="0 0 140 140" width="116" height="116">${arcs}<text x="70" y="69" text-anchor="middle" class="dn">${fmtN(t)}</text><text x="70" y="88" text-anchor="middle" class="dl">${esc(center||"")}</text></svg>`;}
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
    const sec=secOf(id); const st=sec?sec.status:null;
    const b=document.createElement("button");b.dataset.tab=id;
    b.innerHTML=`${st&&st!=="ok"?`<span class="sd" style="background:${STC[st]}"></span>`:""}${esc(label)}`;
    if(i===0)b.classList.add("active");b.onclick=()=>activate(id);nav.appendChild(b);
  });
}
let CURRENT="overview";
function activate(id){
  if(CURRENT==="overview"&&id!=="overview")teardownTerminal();  // close the PTY shell on leave
  CURRENT=id;
  document.querySelectorAll("#nav button").forEach(b=>b.classList.toggle("active",b.dataset.tab===id));
  render(true);window.scrollTo(0,0);
  if(id==="hermes")initAgentGraphIfNeeded();
}
function render(animate){
  const f={overview:renderOverview,host:renderHost,hermes:renderHermes,honcho:()=>renderSource("honcho"),homeassistant:()=>renderSource("homeassistant")}[CURRENT];
  const inner=f?f():"";
  const sec=$("main").firstElementChild;
  if(animate||!sec){$("main").innerHTML=`<section class="tab active">${inner}</section>`;}
  else{sec.innerHTML=inner;}  // in-place on live ticks: no entrance-animation flash
  if(CURRENT==="hermes")wireHermes();
  if($("cform"))wireChat();      // chat box (overview or Hermes tab)
  if($("xterm"))wireTerminal();  // terminal (overview)
}
// reconcile the nav status dots in place (no rebuild) so live ticks don't flicker the navbar
function updateNavDots(){
  document.querySelectorAll("#nav button").forEach(b=>{
    const st=(secOf(b.dataset.tab)||{}).status; let dot=b.querySelector(".sd");
    if(st&&st!=="ok"){if(!dot){dot=document.createElement("span");dot.className="sd";b.insertBefore(dot,b.firstChild);}dot.style.background=STC[st]||"var(--off)";}
    else if(dot){dot.remove();}
  });
}

/* ---------- host gauges (shared spec → render + live animate) ---------- */
function hostGaugeData(d){
  const g=[];
  if(d.temp_c!=null)g.push({key:"temp",label:"Temp",val:d.temp_c.toFixed(1),unit:"°C",pct:d.temp_c,status:d.temp_c>=80?"crit":d.temp_c>=70?"warn":"ok"});
  if(d.cpu_percent!=null)g.push({key:"cpu",label:"CPU",val:d.cpu_percent.toFixed(0),unit:"%",pct:d.cpu_percent,status:d.cpu_percent>=90?"crit":d.cpu_percent>=70?"warn":"ok"});
  if(d.mem&&d.mem.percent!=null)g.push({key:"mem",label:"Memory",val:d.mem.percent.toFixed(0),unit:"%",pct:d.mem.percent,status:d.mem.percent>=90?"crit":d.mem.percent>=85?"warn":"ok"});
  if(d.disk&&d.disk.percent!=null)g.push({key:"disk",label:"Disk",val:d.disk.percent.toFixed(0),unit:"%",pct:d.disk.percent,status:d.disk.percent>=95?"crit":d.disk.percent>=85?"warn":"ok"});
  return g;
}
function hostGauges(){
  const g=hostGaugeData((S().system||{}).data||{});
  return g.length?`<div class="grid g-gauges" id="ovg">${g.map(x=>gauge(x.label,x.val,x.unit,x.pct,x.status,x.key)).join("")}</div>`:"";
}
// animate the existing gauge arcs in place (no re-render → smooth sweep, no flicker)
function updateHostLive(){
  hostGaugeData((S().system||{}).data||{}).forEach(x=>{
    const el=document.querySelector(`.gauge[data-g="${x.key}"]`);if(!el)return;
    const st=STC[x.status]?x.status:"off",r=52,c=2*Math.PI*r,len=Math.max(0,Math.min(100,x.pct||0))/100*c;
    const arc=el.querySelector(".garc");
    if(arc){arc.setAttribute("stroke-dasharray",`${len.toFixed(1)} ${(c-len).toFixed(1)}`);arc.setAttribute("stroke",`url(#gg-${st})`);arc.setAttribute("class",`garc g-${st}`);}
    const gv=el.querySelector(".gv");if(gv)gv.textContent=x.val;
  });
}
/* ---------- area/line history charts (animated, clickable) ---------- */
let HIST=(DATA.history||[]).slice();
const CW=600,CH=88,CPAD=6;
function _cpts(vals){const mn=Math.min(...vals),mx=Math.max(...vals),rng=(mx-mn)||1,n=vals.length;
  return vals.map((v,i)=>({x:CPAD+(n>1?i/(n-1):0)*(CW-2*CPAD),y:CPAD+(1-(v-mn)/rng)*(CH-2*CPAD)}));}
function _ptsStr(p){return p.map(q=>q.x.toFixed(1)+","+q.y.toFixed(1)).join(" ");}
function _applyChart(id,pts){const ln=document.getElementById(id+"_l"),ar=document.getElementById(id+"_a");
  if(!ln&&!ar)return false;const line=_ptsStr(pts);
  if(ln)ln.setAttribute("points",line);
  if(ar)ar.setAttribute("points",`${CPAD},${CH-CPAD} ${line} ${CW-CPAD},${CH-CPAD}`);return true;}
const CHARTPTS={};  // id -> currently-rendered points (tween baseline)
function tweenChart(id,target){
  let from=CHARTPTS[id];
  if(!from){CHARTPTS[id]=target;_applyChart(id,target);return;}
  if(from.length!==target.length){  // align lengths to the newest end so the line "grows in"
    from = from.length<target.length
      ? Array.from({length:target.length-from.length},()=>from[0]).concat(from)
      : from.slice(from.length-target.length);
  }
  const start=performance.now(),dur=480,f0=from;
  (function fr(t){const e=Math.min(1,(t-start)/dur),k=e<.5?2*e*e:1-Math.pow(-2*e+2,2)/2;
    const pts=target.map((p,i)=>({x:f0[i].x+(p.x-f0[i].x)*k,y:f0[i].y+(p.y-f0[i].y)*k}));
    if(!_applyChart(id,pts))return;
    if(e<1)requestAnimationFrame(fr);else CHARTPTS[id]=target;})(performance.now());
}
function areaChart(id,vals,color){
  if(!vals||vals.length<2)return `<div class="muted" style="font-size:12.5px;padding:18px 0">collecting…</div>`;
  const pts=_cpts(vals),line=_ptsStr(pts);
  if(id.indexOf("ar_")===0)CHARTPTS[id]=pts;  // seed tween baseline for the inline host charts
  return `<svg class="spark" viewBox="0 0 ${CW} ${CH}" preserveAspectRatio="none">`+
    `<defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${color}" stop-opacity=".34"/><stop offset="1" stop-color="${color}" stop-opacity="0"/></linearGradient></defs>`+
    `<polygon id="${id}_a" points="${CPAD},${CH-CPAD} ${line} ${CW-CPAD},${CH-CPAD}" fill="url(#${id})"/>`+
    `<polyline id="${id}_l" points="${line}" fill="none" stroke="${color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/></svg>`;
}
const HSERIES=[["temp","Temp","°C","#FDB52A",1],["cpu","CPU","%","#6C72FF",0],["mem","Memory","%","#57C3FF",0]];
const SMALL_N=30;  // small host charts show at most the last 30 samples
const _vals=k=>HIST.map(s=>s[k]).filter(v=>v!=null);
const _recent=k=>_vals(k).slice(-SMALL_N);
function hostHistory(){
  if(!HIST||HIST.length<2)return "";
  let h=`<div class="stitle">${ic("chart")} History <span class="hint">tap a chart for detail</span></div><div class="grid g-cards">`;
  HSERIES.forEach(([k,label,unit,color,dp])=>{
    const vals=_recent(k);if(vals.length<2)return;
    const cur=vals[vals.length-1],mn=Math.min(...vals),mx=Math.max(...vals);
    h+=`<div class="card hist clickable" data-k="${k}" onclick="openMetric('${k}')"><div class="hh"><span class="ht">${label}</span><span class="hv num">${cur.toFixed(dp)}${unit}</span></div>`+
       areaChart("ar_"+k,vals,color)+
       `<div class="hr">min ${mn.toFixed(dp)}${unit} · max ${mx.toFixed(dp)}${unit} · last ${vals.length}</div></div>`;
  });
  return h+`</div>`;
}
function updateHistCharts(){
  HSERIES.forEach(([k,label,unit,color,dp])=>{
    const vals=_recent(k);if(vals.length<2)return;
    tweenChart("ar_"+k,_cpts(vals));
    const card=document.querySelector(`.hist[data-k="${k}"]`);
    if(card){const mn=Math.min(...vals),mx=Math.max(...vals),hv=card.querySelector(".hv"),hr=card.querySelector(".hr");
      if(hv)hv.textContent=vals[vals.length-1].toFixed(dp)+unit;
      if(hr)hr.textContent=`min ${mn.toFixed(dp)}${unit} · max ${mx.toFixed(dp)}${unit} · last ${vals.length}`;}
  });
  if(OPENM)refreshModal();
}
/* ---------- metric detail modal ---------- */
let OPENM=null;
function openMetric(k){const m=HSERIES.find(s=>s[0]===k);if(!m)return;OPENM=k;
  $("sheet").innerHTML=metricSheet(m);$("modal").hidden=false;document.body.style.overflow="hidden";}
function closeModal(){OPENM=null;$("modal").hidden=true;document.body.style.overflow="";}
function _spanLabel(n){const r=(DATA.meta&&DATA.meta.refresh)||5,s=(n-1)*r,m=Math.round(s/60);return m>=1?`${m} min ago`:`${s}s ago`;}
function _gridRows(mn,mx,rng,unit,dp){let r="";const T=4;
  for(let i=0;i<=T;i++){const tv=mn+rng*(i/T),Yv=CPAD+(1-(tv-mn)/rng)*(CH-2*CPAD);
    r+=`<div class="gridrow" style="top:${(Yv/CH*100).toFixed(2)}%"><span class="yl">${tv.toFixed(dp)}${unit}</span></div>`;}
  return r;}
// large, gridded, labelled, animatable chart for the detail modal
function bigChart(id,vals,color,unit,dp){
  const mn=Math.min(...vals),mx=Math.max(...vals),rng=(mx-mn)||1,pts=_cpts(vals),line=_ptsStr(pts);
  CHARTPTS[id]=pts;
  return `<div class="bigwrap"><div class="chgrid" id="grid_${id}">${_gridRows(mn,mx,rng,unit,dp)}</div>`+
    `<svg class="spark big" viewBox="0 0 ${CW} ${CH}" preserveAspectRatio="none">`+
      `<defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${color}" stop-opacity=".30"/><stop offset="1" stop-color="${color}" stop-opacity="0"/></linearGradient></defs>`+
      `<polygon id="${id}_a" points="${CPAD},${CH-CPAD} ${line} ${CW-CPAD},${CH-CPAD}" fill="url(#${id})"/>`+
      `<polyline id="${id}_l" points="${line}" fill="none" stroke="${color}" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/>`+
    `</svg></div><div class="xlabels" id="xl_${id}"><span>${_spanLabel(vals.length)}</span><span>now</span></div>`;
}
function metricSheet(m){
  const [k,label,unit,color,dp]=m,vals=_vals(k);
  const head=`<div class="shead"><span class="st">${ic("chart")} ${esc(label)} — history</span><button class="mx" onclick="closeModal()" aria-label="Close">✕</button></div>`;
  if(vals.length<2)return head+`<div class="empty">Not enough history yet — give it a moment.</div>`;
  const cur=vals[vals.length-1],mn=Math.min(...vals),mx=Math.max(...vals),avg=vals.reduce((a,b)=>a+b,0)/vals.length;
  const tiles=[["Current",cur],["Min",mn],["Max",mx],["Average",avg]];
  return head+bigChart("mar_"+k,vals,color,unit,dp)+
    `<div class="grid g-stats">`+tiles.map(([l,v])=>`<div class="stat"><div class="n num" style="color:${color}">${v.toFixed(dp)}${esc(unit)}</div><div class="l">${esc(l)}</div></div>`).join("")+
    `<div class="stat"><div class="n num">${vals.length}</div><div class="l">Samples</div></div></div>`;
}
function refreshModal(){if(!OPENM)return;const m=HSERIES.find(s=>s[0]===OPENM);if(!m)return;
  const [k,label,unit,color,dp]=m,vals=_vals(k);if(vals.length<2)return;const id="mar_"+k;
  tweenChart(id,_cpts(vals));   // animate the expanded chart too
  const mn=Math.min(...vals),mx=Math.max(...vals),rng=(mx-mn)||1;
  const g=document.getElementById("grid_"+id);if(g)g.innerHTML=_gridRows(mn,mx,rng,unit,dp);
  const xl=document.getElementById("xl_"+id);if(xl){const sp=xl.querySelector("span");if(sp)sp.textContent=_spanLabel(vals.length);}
  const ns=$("sheet")?$("sheet").querySelectorAll(".g-stats .stat .n"):[];
  if(ns.length>=5){const cur=vals[vals.length-1],avg=vals.reduce((a,b)=>a+b,0)/vals.length;
    [cur,mn,mx,avg].forEach((v,i)=>ns[i].textContent=v.toFixed(dp)+unit);ns[4].textContent=vals.length;}
}
function renderOverview(){
  // Sources — every section (Host included) as a clickable status card.
  let h=`<div class="stitle">${ic("layers")} Sources</div><div class="grid g-cards">`;
  TABS.filter(t=>t[0]!=="overview").forEach(([id,label,icn])=>{
    const s=secOf(id);if(!s)return;
    h+=`<div class="srccard clickable" data-src="${id}" onclick="activate('${id}')"><div class="h">${ic(icn)}<span class="nm">${esc(label)}</span>${chip(s.status,s.status==="off"?"off":s.status)}</div><div class="sm">${esc(s.summary||"")}</div></div>`;
  });
  h+=`</div>`;
  // Terminal (preferred) or chat — both opt-in, live-server only.
  const m=DATA.meta||{};
  if(LIVE&&m.terminal)
    h+=`<div class="stitle">${ic("terminal")} Terminal <span class="hint">runs shell commands on this host</span></div>`+renderTerminal();
  else if(LIVE&&m.chat&&(S().hermes||{}).available)
    h+=`<div class="stitle">${ic("brain")} Chat with Hermes</div>`+renderChat();
  return h;
}
// live, in-place refresh of the Host source card on the overview (SSE only sends host)
function updateOverviewLive(){
  const s=S().system,card=document.querySelector('.srccard[data-src="host"]');
  if(!s||!card)return;
  const sm=card.querySelector(".sm");if(sm)sm.textContent=s.summary||"";
  const ch=card.querySelector(".chip");if(ch){const t=s.status==="off"?"off":s.status;ch.className="chip "+s.status;ch.innerHTML=`<span class="d"></span>${t}`;}
}

/* ---------- host ---------- */
function hostStats(d){
  const stats=[];
  if(d.load&&d.load[0]!=null)stats.push(["load","Load (1m)",d.load[0].toFixed(2)]);
  if(d.cores!=null)stats.push(["cores","Cores",String(d.cores)]);
  if(d.mem)stats.push(["mem","Memory",fmtBytes(d.mem.used)+" / "+fmtBytes(d.mem.total)]);
  if(d.disk)stats.push(["disk","Disk",fmtBytes(d.disk.used)+" / "+fmtBytes(d.disk.total)]);
  if(d.uptime_s!=null)stats.push(["uptime","Uptime",fmtUp(d.uptime_s)]);
  return stats.length?`<div class="grid g-stats" style="margin-top:16px">`+stats.map(([k,l,v])=>`<div class="stat" data-st="${k}"><div class="n num">${esc(v)}</div><div class="l">${esc(l)}</div></div>`).join("")+`</div>`:"";
}
function updateHostStats(){
  const d=(S().system||{}).data||{},set=(k,v)=>{const e=document.querySelector(`.stat[data-st="${k}"] .n`);if(e&&v!=null)e.textContent=v;};
  if(d.load&&d.load[0]!=null)set("load",d.load[0].toFixed(2));
  if(d.mem)set("mem",fmtBytes(d.mem.used)+" / "+fmtBytes(d.mem.total));
  if(d.disk)set("disk",fmtBytes(d.disk.used)+" / "+fmtBytes(d.disk.total));
  if(d.uptime_s!=null)set("uptime",fmtUp(d.uptime_s));
}
function renderHost(){
  const s=S().system||{},d=s.data||{};
  let h=`<div class="stitle">${ic("cpu")} ${esc(d.model||"Host")} ${s.status&&s.status!=="ok"?sevpill(s.status):""}</div>`;
  h+=hostGauges()+hostStats(d)+hostHistory();
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
  if(LIVE&&DATA.meta&&DATA.meta.chat)subs.push(["chat","Chat"]);
  if(!subs.some(s=>s[0]===HSUB))HSUB="summary";
  let h=`<div class="subnav">`+subs.map(([k,l])=>`<button class="${k===HSUB?"active":""}" data-sub="${k}">${esc(l)}</button>`).join("")+`</div><div id="hsub">${renderHermesSub()}</div>`;
  return h;
}
function wireHermes(){document.querySelectorAll(".subnav button").forEach(b=>b.onclick=()=>{HSUB=b.dataset.sub;document.querySelectorAll(".subnav button").forEach(x=>x.classList.toggle("active",x===b));$("hsub").innerHTML=renderHermesSub();if(HSUB==="graph")initAgentGraph();if(HSUB==="timeline")wireTimeline();if(HSUB==="chat")wireChat();});if(HSUB==="chat")wireChat();}
/* ---------- chat with Hermes (live server only, opt-in) ---------- */
let CHATLOG=[];
try{const _s=localStorage.getItem("insikt_chat");if(_s)CHATLOG=JSON.parse(_s)||[];}catch(e){}  // persists across refreshes
function saveChat(){try{localStorage.setItem("insikt_chat",JSON.stringify(CHATLOG.slice(-100)));}catch(e){}}
const chatBubble=m=>`<div class="cmsg ${m.role}${m.pending?" pending":""}"><div class="cb">${esc(m.text)}</div></div>`;
const _cempty='<div class="cempty">Ask your Hermes instance anything — replies run on the Pi.</div>';
function renderChat(){
  return `<div class="chat">`+
    `<div class="clog" id="clog">${CHATLOG.length?CHATLOG.map(chatBubble).join(""):_cempty}</div>`+
    `<form class="cform" id="cform"><input id="cin" placeholder="Message Hermes…" autocomplete="off" maxlength="4000"><button type="submit" id="csend">Send</button></form>`+
    `</div>`+
    `<button type="button" class="cclear" id="cclear" style="${CHATLOG.length?"":"display:none"}">Clear conversation</button>`;
}
function redrawChat(){const c=$("clog");if(c){c.innerHTML=CHATLOG.length?CHATLOG.map(chatBubble).join(""):_cempty;c.scrollTop=c.scrollHeight;}
  const clr=$("cclear");if(clr)clr.style.display=CHATLOG.length?"":"none";}
function wireChat(){
  const form=$("cform");if(!form)return;
  const inp=$("cin"),btn=$("csend"),clr=$("cclear");
  form.onsubmit=async e=>{e.preventDefault();const msg=(inp.value||"").trim();if(!msg)return;
    CHATLOG.push({role:"you",text:msg});CHATLOG.push({role:"hermes",text:"thinking…",pending:true});
    inp.value="";inp.disabled=btn.disabled=true;saveChat();redrawChat();
    try{
      const r=await fetch("/api/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message:msg})});
      const d=await r.json().catch(()=>({}));
      CHATLOG[CHATLOG.length-1]={role:"hermes",text:(d&&(d.reply||d.message||d.error))||"(no reply)"};
    }catch(err){CHATLOG[CHATLOG.length-1]={role:"hermes",text:"(request failed — is the agent reachable?)"};}
    inp.disabled=btn.disabled=false;saveChat();redrawChat();inp.focus();
  };
  if(clr)clr.onclick=()=>{CHATLOG=[];saveChat();redrawChat();};
  inp&&inp.focus();
}
/* ---------- web terminal (xterm.js + PTY over WebSocket, opt-in) ---------- */
let TERM=null,TWS=null,TFIT=null,_termResize=null;
function renderTerminal(){return `<div class="term"><div class="xtwrap" id="xterm"></div></div>`;}
function _fitTerm(){try{if(TFIT)TFIT.fit();}catch(e){}}
function teardownTerminal(){
  if(_termResize){window.removeEventListener("resize",_termResize);_termResize=null;}
  try{if(TWS){TWS.onclose=null;TWS.close();}}catch(e){}TWS=null;
  try{if(TERM){TERM.dispose();}}catch(e){}TERM=null;
}
function wireTerminal(){
  const el=$("xterm");if(!el)return;
  if(typeof Terminal==="undefined"){el.innerHTML='<div style="padding:18px;color:var(--on3);font-size:13px">Terminal assets failed to load.</div>';return;}
  teardownTerminal();
  TERM=new Terminal({fontSize:13,fontFamily:'ui-monospace,SFMono-Regular,Menlo,Consolas,monospace',cursorBlink:true,scrollback:3000,
    theme:{background:'#0a0f22',foreground:'#eaf0ff',cursor:'#57C3FF',selectionBackground:'rgba(108,114,255,.35)'}});
  try{TFIT=new FitAddon.FitAddon();TERM.loadAddon(TFIT);}catch(e){TFIT=null;}
  TERM.open(el);_fitTerm();
  const enc=new TextEncoder();
  let ws;try{ws=new WebSocket((location.protocol==="https:"?"wss:":"ws:")+"//"+location.host+"/ws/term");}
  catch(e){TERM.write("\r\n[cannot open websocket]\r\n");return;}
  ws.binaryType="arraybuffer";TWS=ws;
  function sendResize(){if(ws.readyState===1){_fitTerm();ws.send(JSON.stringify({cols:TERM.cols,rows:TERM.rows}));}}
  _termResize=sendResize;window.addEventListener("resize",sendResize);
  ws.onopen=()=>{sendResize();TERM.focus();};
  ws.onmessage=ev=>{if(typeof ev.data==="string")TERM.write(ev.data);else TERM.write(new Uint8Array(ev.data));};
  ws.onclose=()=>{try{TERM&&TERM.write("\r\n\x1b[2m[session ended — reopen the tab to reconnect]\x1b[0m\r\n");}catch(e){}};
  TERM.onData(d=>{if(ws.readyState===1)ws.send(enc.encode(d));});  // keystrokes → pty (binary)
  setTimeout(sendResize,80);
}
function renderHermesSub(){
  const s=S().hermes,d=s.data||{},ag=A();
  if(HSUB==="summary"){
    const tiles=[["Memories",d.memories],["Skills",d.skills],["Self-authored",d.self_authored],["Models",d.models],["Connectors",d.connectors],["Actions",d.actions]];
    let h=`<div class="grid g-stats">`+tiles.map(([l,v])=>`<div class="stat"><div class="n num">${fmtN(v)}</div><div class="l">${esc(l)}</div></div>`).join("")+`</div>`;
    const meta=[d.default_model&&("model "+d.default_model),d.gateway_platforms&&("via "+(d.gateway_platforms||[]).join(", ")),d.open_connectors&&d.open_connectors.length&&("open: "+d.open_connectors.join(", "))].filter(Boolean);
    if(meta.length)h+=`<div class="card" style="margin-top:14px"><div class="sm muted">${meta.map(esc).join("  ·  ")}</div></div>`;
    return h;
  }
  if(HSUB==="chat")return renderChat();
  if(!ag)return `<div class="empty">No agent data.</div>`;
  if(HSUB==="capability")return renderCap(ag.capability);
  if(HSUB==="timeline")return renderTimeline(ag.timeline);
  if(HSUB==="cost")return renderCost(ag.cost);
  if(HSUB==="hygiene")return renderHygiene(ag.hygiene);
  if(HSUB==="graph")return `<div id="gw"><canvas id="graph"></canvas><div id="glegend"></div></div>`;
  return "";
}
function renderCap(cap){
  if(!cap||!(cap.agents||[]).length)return `<div class="empty">No capabilities.</div>`;
  let h="";cap.agents.forEach(a=>{(a.skills||[]).forEach(sk=>{
    const badges=[sk.self_authored?'<span class="tag self">self-authored</span>':"",sk.use_count===0?'<span class="tag">never used</span>':(sk.use_count>0?`<span class="tag">used ${sk.use_count}&times;</span>`:""),sk.risk?sevpill(sk.risk):""].join("");
    h+=`<div class="card" style="margin-bottom:10px"><div class="hrow"><span style="font-weight:600">${esc(sk.name)}</span>${badges}<span class="faint" style="margin-left:auto;font-size:12px">${esc(sk.kind||sk.source||"")}</span></div>`;
    if((sk.tools||[]).length)h+=`<div class="kv"><span class="k">can use</span><span class="v">${sk.tools.map(t=>`<span class="tag">${esc(t)}</span>`).join("")}</span></div>`;
    if((sk.reaches||[]).length)h+=`<div class="kv"><span class="k">can reach</span><span class="v">${sk.reaches.map(r=>`<span class="tag">${esc(r.value)}</span>`).join("")}</span></div>`;
    if((sk.credential_reads||[]).length)h+=`<div class="kv"><span class="k">reads</span><span class="v">${sk.credential_reads.map(c=>`<span class="tag">${esc(c)}</span>`).join("")}</span></div>`;
    h+=`</div>`;});});
  return h;
}
function renderTimeline(tl){
  if(!tl||!(tl.actions||[]).length)return `<div class="empty">No actions.</div>`;
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
  if(!hy||!(hy.findings||[]).length)return `<div class="empty">No findings.</div>`;
  const sevr=["critical","high","medium","low","info"];const KC={capability:"cap",config:"config",alert:"alert"};
  const fs=hy.findings.slice().sort((a,b)=>sevr.indexOf(a.severity)-sevr.indexOf(b.severity));
  const cnt={};fs.forEach(f=>cnt[f.severity]=(cnt[f.severity]||0)+1);
  let h=`<div class="hrow" style="margin-bottom:16px">`+sevr.filter(s=>cnt[s]).map(s=>`<span class="pill p-${s}"><span class="d"></span>${cnt[s]} ${s}</span>`).join("")+`</div>`;
  sevr.forEach(sv=>{const g=fs.filter(f=>f.severity===sv);if(!g.length)return;const open=(sv==="critical"||sv==="high")?" open":"";
    h+=`<details class="grp"${open}><summary><span class="pill p-${sv}"><span class="d"></span>${sv}</span><span class="gc">${g.length} finding${g.length>1?"s":""}</span><span class="cv">›</span></summary>`;
    g.forEach(f=>{const kd=f.kind||"capability";h+=`<div class="finding">${dot(sv==="critical"?"crit":sv==="high"?"warn":"off")}<div><div class="hrow"><span class="fn">${esc(f.title)}</span><span class="tag ${KC[kd]||"cap"}">${esc(kd)}</span></div><div class="fd">${esc(f.detail)}</div>${(f.factors||[]).length?`<div class="ff">${f.factors.map(esc).join(" · ")}</div>`:""}${f.remediation?`<div class="rem">${ic("check")}<span>${esc(f.remediation)}</span></div>`:""}</div></div>`;});
    h+=`</details>`;});
  return h;
}

/* ---------- agent graph (canvas) ---------- */
let GRAPH_INIT=false;
function initAgentGraphIfNeeded(){}
function initAgentGraph(){
  const ag=A();if(!ag||!ag.graph)return;const canvas=$("graph");if(!canvas)return;
  const TC={agent:"#C95CFF",skill:"#6C72FF",tool:"#9A91FB",model:"#57C3FF",connector:"#FDB52A",resource:"#7E89AC",credential_ref:"#FF5C7C",action:"#4A5790"};
  const RISK={critical:"#FF5C7C",high:"#FDB52A",medium:"#9A91FB"};
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
  function draw(){ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,canvas.clientWidth,canvas.clientHeight);ctx.save();ctx.translate(view.x,view.y);ctx.scale(view.k,view.k);ctx.lineWidth=.6/view.k;ctx.strokeStyle="rgba(126,137,172,.28)";ctx.beginPath();edges.forEach(e=>{ctx.moveTo(e.s.x,e.s.y);ctx.lineTo(e.t.x,e.t.y);});ctx.stroke();nodes.forEach(n=>{const r=rad(n);ctx.beginPath();ctx.arc(n.x,n.y,r,0,6.2832);ctx.fillStyle=TC[n.type]||"#7E89AC";ctx.fill();if(RISK[n.risk]){ctx.lineWidth=2/view.k;ctx.strokeStyle=RISK[n.risk];ctx.stroke();}if(view.k>.85&&n.type!=="action"&&n.type!=="resource"){ctx.fillStyle="rgba(255,255,255,.82)";ctx.font=`${10/view.k}px sans-serif`;ctx.fillText(n.label,n.x+r+1.5,n.y+3/view.k);}});ctx.restore();}
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

/* ---------- manual refresh (force a full re-collect) ---------- */
async function doRefresh(){
  const b=$("refresh");if(!b||b.disabled)return;b.classList.add("spin");b.disabled=true;
  try{
    const r=await fetch("/api/refresh");const st=await r.json();
    if(st&&st.sections){DATA.meta=st.meta;DATA.status=st.status;DATA.sections=st.sections;DATA.agent=st.agent;if(st.history)HIST=st.history.slice();}
    renderBar();buildNav();render(true);
  }catch(e){}
  b.classList.remove("spin");b.disabled=false;
}
/* ---------- live (SSE) ---------- */
function pushHist(host){
  const d=(host&&host.data)||{};
  HIST.push({t:DATA.meta.generated,temp:d.temp_c,cpu:d.cpu_percent,mem:d.mem&&d.mem.percent,disk:d.disk&&d.disk.percent});
  if(HIST.length>360)HIST.shift();
}
function startLive(){
  if(!LIVE||!window.EventSource)return;
  try{
    const es=new EventSource("/events");
    es.onmessage=ev=>{try{const m=JSON.parse(ev.data);
      if(m.host){DATA.sections.system=m.host;pushHist(m.host);}
      if(m.status)DATA.status=m.status;if(m.generated)DATA.meta.generated=m.generated;
      renderBar();updateNavDots();updateHostLive();   // gauges animate in place
      if(CURRENT==="host"){updateHostStats();updateHistCharts();}
      else if(CURRENT==="overview")updateOverviewLive();
    }catch(e){}};
  }catch(e){}
}

document.addEventListener("keydown",e=>{if(e.key==="Escape"&&OPENM)closeModal();});
if(LIVE){const _rb=$("refresh");if(_rb){_rb.hidden=false;_rb.onclick=doRefresh;}}
renderBar();buildNav();render(true);startLive();
</script>
</body>
</html>"""
