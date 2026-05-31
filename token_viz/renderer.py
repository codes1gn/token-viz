"""Standalone HTML report renderer for token-viz."""
from __future__ import annotations
import json
import os
from token_viz.analyzer import AnalysisResult, format_duration, format_tokens
from token_viz.pricing import format_cost

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>token-viz — /*SESSION_ID*/</title>
<style>
:root{--bg:#0d1117;--card:#161b22;--border:#30363d;--text:#e6edf3;--muted:#8b949e;
--blue:#58a6ff;--orange:#f0883e;--green:#3fb950;--red:#f85149;--yellow:#d29922;
--purple:#bc8cff;--cyan:#39d353;}
*{box-sizing:border-box;margin:0;padding:0;}
body{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,monospace;font-size:14px;}
a{color:var(--blue);text-decoration:none;}
.header{padding:24px 32px;border-bottom:1px solid var(--border);}
.header h1{font-size:22px;color:var(--text);}
.header p{color:var(--muted);margin-top:4px;font-size:12px;}
.tabs{display:flex;gap:0;border-bottom:1px solid var(--border);padding:0 32px;}
.tab{padding:12px 20px;cursor:pointer;color:var(--muted);border-bottom:2px solid transparent;font-size:13px;}
.tab.active{color:var(--text);border-bottom-color:var(--blue);}
.tab:hover{color:var(--text);}
.tab-content{display:none;padding:32px;max-width:1400px;margin:0 auto;}
.tab-content.active{display:block;}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:16px;margin-bottom:32px;}
.card{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:16px;}
.card-label{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.5px;}
.card-value{font-size:28px;font-weight:700;margin-top:4px;color:var(--text);}
.card-value.blue{color:var(--blue);}
.card-value.green{color:var(--green);}
.card-value.orange{color:var(--orange);}
.card-value.red{color:var(--red);}
.card-value.yellow{color:var(--yellow);}
.card-sub{font-size:11px;color:var(--muted);margin-top:4px;}
.section-title{font-size:16px;font-weight:600;margin-bottom:16px;color:var(--text);}
.bar-row{display:flex;align-items:center;gap:12px;margin-bottom:8px;}
.bar-label{width:200px;text-align:right;color:var(--muted);font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.bar-track{flex:1;height:20px;background:var(--card);border-radius:4px;overflow:hidden;border:1px solid var(--border);}
.bar-fill{height:100%;border-radius:4px;transition:width .3s;}
.bar-fill.blue{background:var(--blue);}
.bar-fill.orange{background:var(--orange);}
.bar-fill.green{background:var(--green);}
.bar-fill.purple{background:var(--purple);}
.bar-fill.yellow{background:var(--yellow);}
.bar-fill.cyan{background:var(--cyan);}
.bar-val{width:100px;font-size:12px;color:var(--text);}
table{width:100%;border-collapse:collapse;font-size:13px;}
th{text-align:left;color:var(--muted);font-size:11px;text-transform:uppercase;padding:8px 12px;border-bottom:1px solid var(--border);}
td{padding:8px 12px;border-bottom:1px solid rgba(48,54,61,.5);color:var(--text);}
tr:hover td{background:var(--card);}
.badge{display:inline-block;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600;}
.badge.subagent{background:rgba(88,166,255,.15);color:var(--blue);}
.badge.skill{background:rgba(63,185,80,.15);color:var(--green);}
.badge.tool{background:rgba(240,136,62,.15);color:var(--orange);}
.badge.system{background:rgba(188,140,255,.15);color:var(--purple);}
.badge.main{background:rgba(57,211,83,.15);color:var(--cyan);}
.badge.exact{background:rgba(63,185,80,.1);color:var(--green);font-size:10px;}
.badge.est{background:rgba(210,153,34,.1);color:var(--yellow);font-size:10px;}
svg text{fill:var(--text);}
.donut-wrap{display:flex;align-items:center;gap:32px;flex-wrap:wrap;}
.legend{display:flex;flex-direction:column;gap:8px;}
.legend-item{display:flex;align-items:center;gap:8px;font-size:13px;}
.legend-dot{width:12px;height:12px;border-radius:50%;}
.timeline-wrap{overflow-x:auto;}
.warning{background:rgba(210,153,34,.1);border:1px solid var(--yellow);border-radius:6px;padding:12px;margin-bottom:16px;color:var(--yellow);font-size:12px;}
.rank-item{display:flex;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid rgba(48,54,61,.4);}
.rank-num{width:24px;height:24px;border-radius:50%;background:var(--card);border:1px solid var(--border);display:flex;align-items:center;justify-content:center;font-size:11px;color:var(--muted);}
.rank-name{flex:1;font-size:13px;}
.rank-tokens{width:120px;text-align:right;font-size:13px;color:var(--blue);}
.rank-cost{width:90px;text-align:right;font-size:13px;color:var(--green);}
.progress-bar{width:100%;height:8px;background:var(--card);border-radius:4px;overflow:hidden;margin-top:4px;}
.progress-fill{height:100%;border-radius:4px;}
</style>
</head>
<body>
<div class="header">
  <h1>&#x1F4CA; token-viz report</h1>
  <p>Session <code>/*SESSION_ID*/</code> &middot; Model: <strong>/*MODEL*/</strong> &middot; Generated by token-viz v1.0.0</p>
</div>
<nav class="tabs">
  <div class="tab active" onclick="showTab('overview')">Overview</div>
  <div class="tab" onclick="showTab('context')">Context</div>
  <div class="tab" onclick="showTab('timeline')">Timeline</div>
  <div class="tab" onclick="showTab('components')">Components</div>
  <div class="tab" onclick="showTab('top')">Top Consumers</div>
</nav>

<div id="tab-overview" class="tab-content active"></div>
<div id="tab-context" class="tab-content"></div>
<div id="tab-timeline" class="tab-content"></div>
<div id="tab-components" class="tab-content"></div>
<div id="tab-top" class="tab-content"></div>

<script>
const DATA = /*__REPORT_DATA__*/;

function showTab(name){
  document.querySelectorAll('.tab').forEach((t,i)=>t.classList.toggle('active', ['overview','context','timeline','components','top'][i]===name));
  document.querySelectorAll('.tab-content').forEach(t=>t.classList.toggle('active', t.id==='tab-'+name));
}

function fmt(n,exact){return (exact?'':'\u007e')+n.toLocaleString();}
function fmtCost(c){if(c<0)return'unknown';if(c<0.001)return'$'+c.toFixed(6);if(c<1)return'$'+c.toFixed(4);return'$'+c.toFixed(2);}
function badge(cat){return `<span class="badge ${cat}">${cat}</span>`;}

// ── Overview ──────────────────────────────────────────────────────
function renderOverview(){
  const d=DATA;
  const cards=[
    {label:'Output Tokens',val:d.total_output_tokens.toLocaleString(),cls:'blue',sub:'exact'},
    {label:'Est. Total Cost',val:fmtCost(d.total_cost_usd),cls:'green',sub:d.model},
    {label:'Total Tokens',val:'\u007e'+d.total_tokens_estimate.toLocaleString(),cls:'yellow',sub:'input+output estimate'},
    {label:'Turns',val:d.turn_count.toLocaleString(),cls:'',sub:d.compaction_count+' compactions'},
    {label:'Duration',val:d.duration_str,cls:'',sub:d.start_time.substring(0,10)},
    {label:'Subagents',val:d.subagent_count.toLocaleString(),cls:'orange',sub:d.skill_count+' skills'},
  ];
  let html='<div class="cards">';
  cards.forEach(c=>{html+=`<div class="card"><div class="card-label">${c.label}</div><div class="card-value ${c.cls}">${c.val}</div><div class="card-sub">${c.sub}</div></div>`;});
  html+='</div>';

  // Top 5 cost breakdown bar
  const top5=d.components.slice(0,5);
  const maxT=top5.length?top5[0].tokens:1;
  const colors=['blue','orange','green','purple','yellow','cyan'];
  html+='<div class="section-title">Top 5 Token Consumers</div>';
  top5.forEach((c,i)=>{
    const pct=Math.round(c.tokens/Math.max(maxT,1)*100);
    html+=`<div class="bar-row"><div class="bar-label">${c.name}</div><div class="bar-track"><div class="bar-fill ${colors[i%colors.length]}" style="width:${pct}%"></div></div><div class="bar-val">${fmt(c.tokens,c.exact)} <span style="color:var(--muted)">${fmtCost(c.cost_usd)}</span></div></div>`;
  });

  if(d.warnings.length){
    html+='<br><div class="warning"><strong>Warnings:</strong><br>'+d.warnings.join('<br>')+'</div>';
  }
  document.getElementById('tab-overview').innerHTML=html;
}

// ── Context ───────────────────────────────────────────────────────
function renderContext(){
  const d=DATA;
  const slices=[
    {label:'System Prompt',val:d.system_tokens,color:'#bc8cff'},
    {label:'Conversation',val:d.conversation_tokens,color:'#58a6ff'},
    {label:'Tool Definitions',val:d.tool_defs_tokens,color:'#f0883e'},
  ];
  const total=slices.reduce((a,s)=>a+s.val,0)||1;
  let html='<div class="section-title">Context Breakdown (latest snapshot)</div><div class="donut-wrap">';

  // SVG donut
  const size=200,cx=100,cy=100,r=70,sw=30;
  let svgPaths='',angle=0;
  slices.forEach(s=>{
    const pct=s.val/total;
    const a1=angle*Math.PI/180;
    const a2=(angle+pct*360)*Math.PI/180;
    const laf=pct*360>180?1:0;
    const x1=cx+r*Math.sin(a1),y1=cy-r*Math.cos(a1);
    const x2=cx+r*Math.sin(a2),y2=cy-r*Math.cos(a2);
    svgPaths+=`<path d="M${cx},${cy} L${x1.toFixed(2)},${y1.toFixed(2)} A${r},${r} 0 ${laf},1 ${x2.toFixed(2)},${y2.toFixed(2)} Z" fill="${s.color}" opacity=".85"/>`;
    angle+=pct*360;
  });
  html+=`<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
    <circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="#30363d" stroke-width="${sw}"/>
    ${svgPaths}
    <circle cx="${cx}" cy="${cy}" r="${r-sw/2}" fill="#0d1117"/>
    <text x="${cx}" y="${cy-6}" text-anchor="middle" font-size="11" fill="#8b949e">Total</text>
    <text x="${cx}" y="${cy+10}" text-anchor="middle" font-size="14" font-weight="700" fill="#e6edf3">${(total/1000).toFixed(0)}K</text>
  </svg>`;

  html+='<div class="legend">';
  slices.forEach(s=>{
    const pct=(s.val/total*100).toFixed(1);
    html+=`<div class="legend-item"><div class="legend-dot" style="background:${s.color}"></div><div><div>${s.label}</div><div style="color:var(--muted);font-size:11px">${s.val.toLocaleString()} tokens (${pct}%)</div></div></div>`;
  });
  html+='</div></div>';

  if(d.context_snapshots.length>0){
    html+='<br><div class="section-title">Compaction History</div><table><tr><th>Time</th><th>System</th><th>Conversation</th><th>Tool Defs</th><th>Pre-Compact Total</th></tr>';
    d.context_snapshots.forEach(s=>{
      html+=`<tr><td>${s.timestamp.substring(11,19)}</td><td>${s.system_tokens.toLocaleString()}</td><td>${s.conversation_tokens.toLocaleString()}</td><td>${s.tool_defs_tokens.toLocaleString()}</td><td>${s.pre_compaction_tokens.toLocaleString()}</td></tr>`;
    });
    html+='</table>';
  }
  document.getElementById('tab-context').innerHTML=html;
}

// ── Timeline ──────────────────────────────────────────────────────
function renderTimeline(){
  const turns=DATA.turn_timeline;
  if(!turns.length){document.getElementById('tab-timeline').innerHTML='<p style="color:var(--muted)">No turn data.</p>';return;}
  const maxTok=Math.max(...turns.map(t=>t.output_tokens),1);
  const barH=14,gap=2,pad=40,svgW=Math.max(800,turns.length*4+pad*2);
  const svgH=turns.length*(barH+gap)+80;
  let bars='',labels='';
  turns.forEach((t,i)=>{
    const w=Math.max(2,Math.round(t.output_tokens/maxTok*(svgW-pad*2-100)));
    const y=pad+i*(barH+gap);
    const color=t.is_subagent?'var(--orange)':'var(--blue)';
    bars+=`<rect x="${pad}" y="${y}" width="${w}" height="${barH}" fill="${color}" rx="2" opacity=".85">
      <title>Turn ${t.i}: ${t.output_tokens.toLocaleString()} tokens${t.is_subagent?' ['+t.agent_name+']':''}</title>
    </rect>`;
    labels+=`<text x="${pad+w+4}" y="${y+barH-3}" font-size="10" fill="#8b949e">${t.output_tokens>0?t.output_tokens.toLocaleString():''}</text>`;
  });
  const legend=`<text x="${pad}" y="20" font-size="12" fill="#58a6ff">&#x25A0; Main Agent</text>
    <text x="${pad+120}" y="20" font-size="12" fill="${'var(--orange)'}">&#x25A0; Subagent</text>`;
  const html=`<div class="section-title">Output Tokens per Turn (${turns.length} turns)</div>
  <div class="timeline-wrap">
  <svg width="${svgW}" height="${svgH}" viewBox="0 0 ${svgW} ${svgH}">
    ${legend}${bars}${labels}
  </svg></div>`;
  document.getElementById('tab-timeline').innerHTML=html;
}

// ── Components ────────────────────────────────────────────────────
function renderComponents(){
  const cats=['subagent','skill','tool','system','main'];
  const catData={};
  cats.forEach(c=>{catData[c]=[];});
  DATA.components.forEach(c=>{
    if(catData[c.category])catData[c.category].push(c);
    else catData['main'].push(c);
  });
  let html='';
  cats.forEach(cat=>{
    const items=catData[cat].sort((a,b)=>b.tokens-a.tokens);
    if(!items.length)return;
    const maxT=items[0].tokens||1;
    html+=`<div class="section-title" style="margin-top:24px">${cat.charAt(0).toUpperCase()+cat.slice(1)} Components</div>`;
    items.forEach(c=>{
      const pct=Math.round(c.tokens/maxT*100);
      const colors={subagent:'blue',skill:'green',tool:'orange',system:'purple',main:'cyan'};
      html+=`<div class="bar-row">
        <div class="bar-label">${c.name.replace(/^(subagent|skill|tool):/,'')} ${c.detail?'<span style="color:var(--muted);font-size:10px">('+c.detail+')</span>':''}
          <span class="badge ${c.exact?'exact':'est'}">${c.exact?'exact':'est'}</span>
        </div>
        <div class="bar-track"><div class="bar-fill ${colors[cat]||'blue'}" style="width:${pct}%"></div></div>
        <div class="bar-val">${fmt(c.tokens,c.exact)} <span style="color:var(--muted)">${fmtCost(c.cost_usd)}</span></div>
      </div>`;
    });
  });
  html+='<br><div class="section-title">Full Components Table</div><table><tr><th>Name</th><th>Category</th><th>Tokens</th><th>Exact?</th><th>Cost (USD)</th></tr>';
  DATA.components.forEach(c=>{
    html+=`<tr><td>${c.name}</td><td>${badge(c.category)}</td><td>${fmt(c.tokens,c.exact)}</td><td>${c.exact?'<span class="badge exact">yes</span>':'<span class="badge est">est</span>'}</td><td>${fmtCost(c.cost_usd)}</td></tr>`;
  });
  html+='</table>';
  document.getElementById('tab-components').innerHTML=html;
}

// ── Top Consumers ────────────────────────────────────────────────
function renderTop(){
  const top=DATA.top_consumers;
  const maxT=top.length?top[0].tokens:1;
  let html='<div class="section-title">Top Token Consumers</div>';
  top.forEach((c,i)=>{
    const pct=Math.round(c.tokens/maxT*100);
    const colorMap={subagent:'#58a6ff',skill:'#3fb950',tool:'#f0883e',system:'#bc8cff',main:'#39d353'};
    const color=colorMap[c.category]||'#58a6ff';
    html+=`<div class="rank-item">
      <div class="rank-num">${i+1}</div>
      <div class="rank-name">
        <div>${c.name} ${badge(c.category)}</div>
        <div class="progress-bar"><div class="progress-fill" style="width:${pct}%;background:${color}"></div></div>
      </div>
      <div class="rank-tokens">${fmt(c.tokens,c.exact)}</div>
      <div class="rank-cost">${fmtCost(c.cost_usd)}</div>
    </div>`;
  });
  document.getElementById('tab-top').innerHTML=html;
}

// ── Init ─────────────────────────────────────────────────────────
function init(){
  DATA.duration_str='/*DURATION*/';
  renderOverview();renderContext();renderTimeline();renderComponents();renderTop();
}
init();
</script>
</body>
</html>
"""


def _to_serializable(obj):
    """Convert dataclass/list/dict to JSON-serializable form."""
    import dataclasses
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: _to_serializable(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, (list, tuple)):
        return [_to_serializable(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _to_serializable(v) for k, v in obj.items()}
    return obj


def render(result: AnalysisResult, output_path: str = "") -> str:
    """Render AnalysisResult to standalone HTML string. Optionally write to file."""
    from token_viz.analyzer import format_duration

    report_data = _to_serializable(result)
    duration_str = format_duration(result.duration_seconds)

    json_str = json.dumps(report_data, ensure_ascii=False)

    html = _HTML_TEMPLATE
    html = html.replace("/*SESSION_ID*/", result.session_id[:8] or "unknown")
    html = html.replace("/*MODEL*/", result.model)
    html = html.replace("/*DURATION*/", duration_str)
    html = html.replace("/*__REPORT_DATA__*/", json_str)

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

    return html
