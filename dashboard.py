"""Self-contained HTML dashboard for real-time TPS monitoring.

Served at GET / by the FastAPI app. All CSS and JavaScript are inline —
no external scripts, stylesheets, fonts, or CDN dependencies.
"""

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TPS Dashboard</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#0f1117;--card:#1a1d27;--border:#2a2d3a;--text:#e4e4e7;--dim:#71717a;
--green:#22c55e;--red:#ef4444;--yellow:#eab308;--blue:#3b82f6;--accent:#6366f1}
body{font-family:system-ui,-apple-system,sans-serif;background:var(--bg);color:var(--text);
line-height:1.5;padding:1rem;max-width:1200px;margin:0 auto}
h1{font-size:1.5rem;font-weight:700;margin-bottom:.5rem;display:flex;align-items:center;gap:.5rem}
.status-badge{display:inline-block;width:10px;height:10px;border-radius:50%;flex-shrink:0}
.status-badge.ok{background:var(--green)}
.status-badge.disconnected{background:var(--red)}
.status-badge.reconnecting{background:var(--yellow);animation:pulse 1s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:.75rem;margin:1rem 0}
.card{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:1rem}
.card h2{font-size:.75rem;text-transform:uppercase;letter-spacing:.05em;color:var(--dim);margin-bottom:.25rem}
.card .value{font-size:1.75rem;font-weight:700;font-variant-numeric:tabular-nums}
.card .sub{font-size:.8rem;color:var(--dim);margin-top:.15rem}
.sparkline-wrap{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:1rem;margin:1rem 0}
.sparkline-wrap h2{font-size:.75rem;text-transform:uppercase;letter-spacing:.05em;color:var(--dim);margin-bottom:.5rem}
canvas{width:100%;height:80px;display:block}
table{width:100%;border-collapse:collapse;font-size:.85rem}
th,td{text-align:left;padding:.5rem .6rem;border-bottom:1px solid var(--border)}
th{color:var(--dim);font-weight:600;font-size:.75rem;text-transform:uppercase;letter-spacing:.03em}
td{font-variant-numeric:tabular-nums}
.session-table{background:var(--card);border:1px solid var(--border);border-radius:8px;overflow:auto;margin:1rem 0}
.section-title{font-size:1rem;font-weight:600;margin:1.5rem 0 .5rem}
.no-data{color:var(--dim);padding:1rem;text-align:center}
.conn-info{font-size:.8rem;color:var(--dim);margin-bottom:1rem}
</style>
</head>
<body>
<h1><span class="status-badge reconnecting" id="statusDot"></span> TPS Dashboard</h1>
<div class="conn-info" id="connInfo">Connecting&hellip;</div>

<div class="grid" id="summaryCards">
  <div class="card"><h2>Average TPS</h2><div class="value" id="avgTps">&mdash;</div><div class="sub" id="avgTpsSub"></div></div>
  <div class="card"><h2>Total Calls</h2><div class="value" id="totalCalls">&mdash;</div></div>
  <div class="card"><h2>Total Tokens</h2><div class="value" id="totalTokens">&mdash;</div></div>
  <div class="card"><h2>Active Sessions</h2><div class="value" id="totalSessions">&mdash;</div></div>
</div>

<div class="sparkline-wrap">
  <h2>Recent TPS (last 30 updates)</h2>
  <canvas id="sparkline" height="80"></canvas>
</div>

<div class="section-title">Sessions</div>
<div class="session-table">
  <table>
    <thead><tr><th>Session</th><th>Last TPS</th><th>Avg TPS</th><th>Peak TPS</th><th>Calls</th><th>Output Tokens</th></tr></thead>
    <tbody id="sessionBody"><tr><td colspan="6" class="no-data">No sessions yet</td></tr></tbody>
  </table>
</div>

<div class="section-title">Model Breakdown</div>
<div class="session-table">
  <table>
    <thead><tr><th>Model</th><th>Avg TPS</th><th>Peak TPS</th><th>Calls</th><th>Output Tokens</th></tr></thead>
    <tbody id="modelBody"><tr><td colspan="5" class="no-data">No model data yet</td></tr></tbody>
  </table>
</div>

<div class="section-title">Provider Breakdown</div>
<div class="session-table">
  <table>
    <thead><tr><th>Provider</th><th>Avg TPS</th><th>Peak TPS</th><th>Calls</th><th>Output Tokens</th></tr></thead>
    <tbody id="providerBody"><tr><td colspan="5" class="no-data">No provider data yet</td></tr></tbody>
  </table>
</div>

<div class="card" style="margin-top:1.5rem">
  <h2>API Health</h2>
  <div id="healthInfo" style="font-size:.85rem;color:var(--dim)">Loading&hellip;</div>
</div>

<script>
(function(){
  "use strict";

  // --- State ---
  var tpsHistory = [];
  var MAX_HISTORY = 30;
  var ws = null;
  var reconnectDelay = 1000;
  var MAX_RECONNECT = 30000;
  var pollTimer = null;
  var wsConnected = false;

  // --- Helpers ---
  function $(id){ return document.getElementById(id); }
  function fmt(n){
    if(n == null || isNaN(n)) return "\\u2014";
    if(n >= 1e6) return (n/1e6).toFixed(1)+"M";
    if(n >= 1e3) return (n/1e3).toFixed(1)+"K";
    return String(n);
  }
  function fmtTps(v){
    if(v == null || isNaN(v)) return "\\u2014";
    return v.toFixed(1)+" tok/s";
  }

  // --- Sparkline ---
  function drawSparkline(){
    var canvas = $("sparkline");
    if(!canvas) return;
    var ctx = canvas.getContext("2d");
    var dpr = window.devicePixelRatio || 1;
    var rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = 80 * dpr;
    ctx.scale(dpr, dpr);
    var w = rect.width, h = 80;
    ctx.clearRect(0,0,w,h);
    if(tpsHistory.length < 2){return;}
    var max = Math.max.apply(null, tpsHistory) || 1;
    var min = 0;
    var range = max - min || 1;
    var step = w / (MAX_HISTORY - 1);
    ctx.beginPath();
    ctx.strokeStyle = "#6366f1";
    ctx.lineWidth = 2;
    for(var i=0;i<tpsHistory.length;i++){
      var x = i * step;
      var y = h - ((tpsHistory[i] - min) / range) * (h - 8) - 4;
      if(i===0) ctx.moveTo(x,y); else ctx.lineTo(x,y);
    }
    ctx.stroke();
    // fill
    ctx.lineTo((tpsHistory.length-1)*step, h);
    ctx.lineTo(0, h);
    ctx.closePath();
    ctx.fillStyle = "rgba(99,102,241,0.1)";
    ctx.fill();
  }

  // --- Update summary ---
  function updateSummary(data){
    $("avgTps").textContent = fmtTps(data.average_tps);
    $("totalCalls").textContent = fmt(data.total_calls);
    $("totalTokens").textContent = fmt(data.total_tokens);
    $("totalSessions").textContent = fmt(data.total_sessions);
  }

  // --- Update sessions table ---
  function updateSessions(sessions){
    var tbody = $("sessionBody");
    if(!sessions || sessions.length === 0){
      tbody.innerHTML = '<tr><td colspan="6" class="no-data">No sessions yet</td></tr>';
      return;
    }
    tbody.innerHTML = sessions.map(function(s){
      return '<tr><td>'+esc(s.session_id)+'</td><td>'+fmtTps(s.last_call_tps)+'</td><td>'
        +fmtTps(s.avg_tps)+'</td><td>'+fmtTps(s.peak_tps)+'</td><td>'
        +fmt(s.call_count)+'</td><td>'+fmt(s.total_output_tokens)+'</td></tr>';
    }).join("");
  }

  // --- Update model/provider tables ---
  function updateBreakdown(tbodyId, data, labelKey){
    var tbody = $(tbodyId);
    if(!data || Object.keys(data).length === 0){
      tbody.innerHTML = '<tr><td colspan="5" class="no-data">No '+labelKey+' data yet</td></tr>';
      return;
    }
    tbody.innerHTML = Object.keys(data).map(function(k){
      var d = data[k];
      return '<tr><td>'+esc(k)+'</td><td>'+fmtTps(d.avg_tps)+'</td><td>'
        +fmtTps(d.peak_tps)+'</td><td>'+fmt(d.calls)+'</td><td>'
        +fmt(d.total_output_tokens)+'</td></tr>';
    }).join("");
  }

  function esc(s){var d=document.createElement("div");d.textContent=s;return d.innerHTML;}

  // --- Health ---
  function updateHealth(info){
    if(typeof info === "string"){$("healthInfo").textContent=info;return;}
    var parts = [];
    if(info.components){
      Object.keys(info.components).forEach(function(k){
        var c = info.components[k];
        parts.push(k+": "+c.status);
      });
    }
    $("healthInfo").textContent = parts.join(" | ") || info.status || "unknown";
  }

  // --- Connection status ---
  function setStatus(state, msg){
    var dot = $("statusDot");
    dot.className = "status-badge "+state;
    $("connInfo").textContent = msg;
  }

  // --- REST polling fallback ---
  function startPolling(){
    if(pollTimer) return;
    pollTimer = setInterval(function(){
      fetchSummary();
      fetchSessions();
    }, 5000);
  }
  function stopPolling(){
    if(pollTimer){clearInterval(pollTimer);pollTimer=null;}
  }

  // --- REST fetches ---
  function fetchSummary(){
    fetch("/api/v1/summary").then(function(r){return r.json();}).then(function(d){
      updateSummary(d);
      tpsHistory.push(d.average_tps || 0);
      if(tpsHistory.length > MAX_HISTORY) tpsHistory.shift();
      drawSparkline();
    }).catch(function(){});
  }
  function fetchSessions(){
    fetch("/api/v1/sessions").then(function(r){return r.json();}).then(function(d){
      updateSessions(d.sessions);
      // Collect model/provider from first session trend if available
      if(d.sessions && d.sessions.length > 0){
        fetchTrends(d.sessions[0].session_id);
      }
    }).catch(function(){});
  }
  function fetchTrends(sid){
    fetch("/api/v1/trends/"+encodeURIComponent(sid)).then(function(r){
      if(!r.ok) return null;
      return r.json();
    }).then(function(d){
      if(!d) return;
      updateBreakdown("modelBody", d.models, "model");
      updateBreakdown("providerBody", d.providers, "provider");
    }).catch(function(){});
  }
  function fetchHealth(){
    fetch("/api/v1/health/diagnostics").then(function(r){return r.json();}).then(function(d){
      updateHealth(d);
    }).catch(function(e){
      updateHealth("unreachable");
    });
  }

  // --- WebSocket ---
  function connectWS(){
    var proto = location.protocol === "https:" ? "wss:" : "ws:";
    var url = proto + "//" + location.host + "/ws/tps";
    try{ ws = new WebSocket(url); }catch(e){
      setStatus("disconnected","WebSocket error; using REST polling");
      startPolling();
      return;
    }
    ws.onopen = function(){
      wsConnected = true;
      reconnectDelay = 1000;
      setStatus("ok","Connected via WebSocket");
      stopPolling();
    };
    ws.onmessage = function(ev){
      try{
        var msg = JSON.parse(ev.data);
        if(msg.type === "tps_update" && msg.data){
          var d = msg.data;
          var tps = d.last_tps || d.avg_tps || 0;
          tpsHistory.push(tps);
          if(tpsHistory.length > MAX_HISTORY) tpsHistory.shift();
          drawSparkline();
          // Refresh summary + sessions periodically on WS data
          fetchSummary();
          fetchSessions();
        }
      }catch(e){}
    };
    ws.onclose = function(){
      wsConnected = false;
      setStatus("reconnecting","Reconnecting in "+Math.round(reconnectDelay/1000)+"s\u2026");
      startPolling();
      setTimeout(function(){ reconnectDelay = Math.min(reconnectDelay * 2, MAX_RECONNECT); connectWS(); }, reconnectDelay);
    };
    ws.onerror = function(){
      try{ws.close();}catch(e){}
    };
  }

  // --- Init ---
  fetchSummary();
  fetchSessions();
  fetchHealth();
  connectWS();

  // Refresh health every 30s
  setInterval(fetchHealth, 30000);
})();
</script>
</body>
</html>"""
