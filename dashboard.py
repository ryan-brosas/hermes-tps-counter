"""Dependency-free HTML dashboard for the TPS Counter API."""
from __future__ import annotations

DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>TPS Dashboard</title>
  <style>
    :root { color-scheme: dark; --bg: #0f172a; --panel: #111827; --muted: #94a3b8; --text: #e5e7eb; --accent: #38bdf8; --good: #22c55e; --warn: #f59e0b; --bad: #ef4444; --line: #1f2937; }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: radial-gradient(circle at top left, #172554 0, var(--bg) 42rem); color: var(--text); }
    header { padding: 1.25rem clamp(1rem, 3vw, 2rem); border-bottom: 1px solid var(--line); display: flex; gap: 1rem; justify-content: space-between; align-items: center; flex-wrap: wrap; }
    h1, h2 { margin: 0; line-height: 1.2; }
    h1 { font-size: clamp(1.45rem, 4vw, 2.35rem); }
    h2 { font-size: 1rem; color: #dbeafe; margin-bottom: .75rem; }
    main { padding: 1rem clamp(1rem, 3vw, 2rem) 2rem; display: grid; gap: 1rem; }
    .badge { border: 1px solid var(--line); border-radius: 999px; padding: .4rem .75rem; background: rgba(15, 23, 42, .72); font-size: .9rem; display: inline-flex; align-items: center; gap: .45rem; }
    .dot { width: .65rem; height: .65rem; border-radius: 999px; background: var(--warn); display: inline-block; }
    .connected .dot { background: var(--good); } .disconnected .dot { background: var(--bad); } .reconnecting .dot, .polling .dot { background: var(--warn); }
    .subtle { color: var(--muted); font-size: .92rem; }
    .grid { display: grid; gap: 1rem; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); }
    .panel { background: rgba(17, 24, 39, .86); border: 1px solid var(--line); border-radius: 1rem; padding: 1rem; box-shadow: 0 18px 50px rgba(0, 0, 0, .22); }
    .metric { display: flex; flex-direction: column; gap: .25rem; }
    .metric strong { font-size: clamp(1.35rem, 5vw, 2.15rem); color: #f8fafc; }
    .metric span { color: var(--muted); font-size: .9rem; }
    .two-col { display: grid; grid-template-columns: minmax(0, 1.3fr) minmax(280px, .7fr); gap: 1rem; }
    canvas { width: 100%; height: 150px; display: block; background: #020617; border: 1px solid #1e293b; border-radius: .75rem; }
    table { width: 100%; border-collapse: collapse; font-size: .92rem; }
    th, td { padding: .65rem .55rem; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }
    th { color: #bfdbfe; font-weight: 650; }
    td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
    .scroll { overflow-x: auto; }
    .empty { color: var(--muted); padding: 1rem 0; }
    footer { color: var(--muted); font-size: .86rem; padding: 0 clamp(1rem, 3vw, 2rem) 1.5rem; }
    @media (max-width: 840px) { .two-col { grid-template-columns: 1fr; } header { align-items: flex-start; } }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>TPS Dashboard</h1>
      <div class="subtle">Built-in real-time monitoring for Hermes TPS Counter</div>
    </div>
    <div id="connectionBadge" class="badge disconnected" role="status" aria-live="polite"><span class="dot" aria-hidden="true"></span><span id="connectionText">Disconnected</span></div>
  </header>
  <main>
    <section class="grid" aria-label="Aggregate TPS metrics">
      <div class="panel metric"><span>Overall TPS</span><strong id="overallTps">0.00</strong><span id="lastUpdated">Waiting for data</span></div>
      <div class="panel metric"><span>Total Calls</span><strong id="totalCalls">0</strong><span>Across tracked sessions</span></div>
      <div class="panel metric"><span>Total Tokens</span><strong id="totalTokens">0</strong><span>Input + output tokens</span></div>
      <div class="panel metric"><span>API Health</span><strong id="apiHealth">Unknown</strong><span id="diagnosticSummary">Diagnostics not loaded</span></div>
    </section>

    <section class="two-col">
      <div class="panel">
        <h2>Recent TPS Sparkline</h2>
        <canvas id="sparkline" width="900" height="180" aria-label="Recent TPS history sparkline"></canvas>
      </div>
      <div class="panel">
        <h2>Model / Provider Breakdown</h2>
        <div id="breakdown" class="empty">No model or provider data yet.</div>
      </div>
    </section>

    <section class="panel">
      <h2>Sessions</h2>
      <div class="scroll">
        <table aria-label="Session-level TPS stats">
          <thead><tr><th>Session</th><th class="num">Last TPS</th><th class="num">Avg TPS</th><th class="num">Peak TPS</th><th class="num">Calls</th><th class="num">Tokens</th><th>Updated</th></tr></thead>
          <tbody id="sessionsBody"><tr><td colspan="7" class="empty">No sessions loaded.</td></tr></tbody>
        </table>
      </div>
    </section>
  </main>
  <footer>Uses <code>/ws/tps</code> for real-time updates and falls back to REST polling via <code>/api/v1/summary</code>, <code>/api/v1/sessions</code>, <code>/api/v1/health</code>, and <code>/api/v1/health/diagnostics</code>.</footer>

  <script>
    (function () {
      'use strict';
      const state = { ws: null, reconnectAttempts: 0, pollTimer: null, history: [], sessions: new Map(), models: new Map(), providers: new Map() };
      const maxHistory = 30;
      const $ = (id) => document.getElementById(id);
      const fmt = (n, digits = 0) => Number(n || 0).toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: digits });
      const shortId = (id) => String(id || 'unknown').slice(0, 18);

      function setConnection(status, message) {
        const badge = $('connectionBadge');
        badge.className = 'badge ' + status;
        $('connectionText').textContent = message;
      }

      async function fetchJson(path) {
        const response = await fetch(path, { headers: { 'Accept': 'application/json' }, cache: 'no-store' });
        if (!response.ok) throw new Error(path + ' returned ' + response.status);
        return response.json();
      }

      function updateSummary(summary) {
        const tps = Number(summary?.average_tps || summary?.avg_tps || 0);
        $('overallTps').textContent = fmt(tps, 2);
        $('totalCalls').textContent = fmt(summary?.total_calls || 0);
        $('totalTokens').textContent = fmt(summary?.total_tokens || 0);
        pushHistory(tps);
      }

      function updateSessions(payload) {
        const sessions = Array.isArray(payload?.sessions) ? payload.sessions : [];
        for (const session of sessions) state.sessions.set(session.session_id || 'unknown', session);
        renderSessions();
      }

      function updateHealth(health, diagnostics) {
        $('apiHealth').textContent = health?.status || diagnostics?.status || 'Unknown';
        const components = diagnostics?.components || {};
        const bits = Object.keys(components).map((name) => name + ':' + (components[name]?.status || '?'));
        $('diagnosticSummary').textContent = bits.length ? bits.join(' · ') : 'DB: ' + (health?.db || 'unknown');
      }

      function updateFromTpsMessage(message) {
        if (message?.type && message.type !== 'tps_update') return;
        const data = message?.data || message || {};
        const sessionId = data.session_id || data.session || 'live';
        const lastTps = Number(data.last_tps || data.last_call_tps || data.tps || data.avg_tps || 0);
        const session = Object.assign({}, state.sessions.get(sessionId) || {}, data, {
          session_id: sessionId,
          last_call_tps: lastTps,
          avg_tps: Number(data.avg_tps || data.average_tps || lastTps || 0),
          peak_tps: Number(data.peak_tps || lastTps || 0),
          call_count: Number(data.call_count || data.calls || 0),
          total_input_tokens: Number(data.total_input_tokens || 0),
          total_output_tokens: Number(data.total_output_tokens || data.total_tokens || 0),
          updated_at: message?.timestamp || data.updated_at || new Date().toISOString()
        });
        state.sessions.set(sessionId, session);
        collectBreakdowns(data);
        pushHistory(lastTps);
        renderSessions();
        renderBreakdown();
        $('lastUpdated').textContent = 'Updated ' + new Date().toLocaleTimeString();
      }

      function collectBreakdowns(data) {
        mergeBreakdown(state.models, data?.models || data?.model_breakdown || {});
        mergeBreakdown(state.providers, data?.providers || data?.provider_breakdown || {});
        if (data?.model) state.models.set(data.model, normalizeBreakdown(data));
        if (data?.provider) state.providers.set(data.provider, normalizeBreakdown(data));
      }

      function normalizeBreakdown(item) {
        return { avg_tps: item?.avg_tps || item?.average_tps || item?.tps || 0, peak_tps: item?.peak_tps || 0, calls: item?.calls || item?.call_count || 0, total_output_tokens: item?.total_output_tokens || item?.output_tokens || 0 };
      }

      function mergeBreakdown(target, entries) {
        if (!entries || typeof entries !== 'object') return;
        for (const [name, value] of Object.entries(entries)) target.set(name, normalizeBreakdown(value || {}));
      }

      function renderSessions() {
        const body = $('sessionsBody');
        const rows = Array.from(state.sessions.values()).sort((a, b) => String(b.updated_at || '').localeCompare(String(a.updated_at || '')));
        if (!rows.length) { body.innerHTML = '<tr><td colspan="7" class="empty">No sessions loaded.</td></tr>'; return; }
        body.innerHTML = rows.map((s) => {
          const tokens = Number(s.total_tokens || 0) || Number(s.total_input_tokens || 0) + Number(s.total_output_tokens || 0);
          return '<tr><td title="' + escapeHtml(s.session_id) + '">' + escapeHtml(shortId(s.session_id)) + '</td>' +
            '<td class="num">' + fmt(s.last_call_tps || s.last_tps || 0, 2) + '</td>' +
            '<td class="num">' + fmt(s.avg_tps || 0, 2) + '</td>' +
            '<td class="num">' + fmt(s.peak_tps || 0, 2) + '</td>' +
            '<td class="num">' + fmt(s.call_count || s.calls || 0) + '</td>' +
            '<td class="num">' + fmt(tokens) + '</td>' +
            '<td>' + escapeHtml(s.updated_at || '') + '</td></tr>';
        }).join('');
      }

      function renderBreakdown() {
        const root = $('breakdown');
        const sections = [];
        if (state.models.size) sections.push(renderBreakdownTable('Models', state.models));
        if (state.providers.size) sections.push(renderBreakdownTable('Providers', state.providers));
        root.className = sections.length ? '' : 'empty';
        root.innerHTML = sections.length ? sections.join('') : 'No model or provider data yet.';
      }

      function renderBreakdownTable(title, map) {
        const rows = Array.from(map.entries()).map(([name, value]) => '<tr><td>' + escapeHtml(name) + '</td><td class="num">' + fmt(value.avg_tps, 2) + '</td><td class="num">' + fmt(value.peak_tps, 2) + '</td><td class="num">' + fmt(value.calls) + '</td></tr>').join('');
        return '<h3>' + title + '</h3><table><thead><tr><th>Name</th><th class="num">Avg TPS</th><th class="num">Peak</th><th class="num">Calls</th></tr></thead><tbody>' + rows + '</tbody></table>';
      }

      function pushHistory(value) {
        const n = Number(value || 0);
        state.history.push(n);
        while (state.history.length > maxHistory) state.history.shift();
        drawSparkline();
      }

      function drawSparkline() {
        const canvas = $('sparkline');
        const ctx = canvas.getContext('2d');
        const w = canvas.width, h = canvas.height;
        ctx.clearRect(0, 0, w, h);
        ctx.strokeStyle = '#1e293b'; ctx.lineWidth = 1;
        for (let i = 1; i < 4; i++) { ctx.beginPath(); ctx.moveTo(0, i * h / 4); ctx.lineTo(w, i * h / 4); ctx.stroke(); }
        if (!state.history.length) return;
        const max = Math.max(1, ...state.history);
        ctx.strokeStyle = '#38bdf8'; ctx.lineWidth = 4; ctx.beginPath();
        state.history.forEach((value, index) => {
          const x = state.history.length === 1 ? w : index * (w / (state.history.length - 1));
          const y = h - ((value / max) * (h - 20)) - 10;
          if (index === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        });
        ctx.stroke();
      }

      async function loadInitialState() {
        try {
          const [summary, sessions, health, diagnostics] = await Promise.allSettled([
            fetchJson('/api/v1/summary'), fetchJson('/api/v1/sessions'), fetchJson('/api/v1/health'), fetchJson('/api/v1/health/diagnostics')
          ]);
          if (summary.status === 'fulfilled') updateSummary(summary.value);
          if (sessions.status === 'fulfilled') updateSessions(sessions.value);
          updateHealth(health.value || {}, diagnostics.value || {});
          $('lastUpdated').textContent = 'Loaded ' + new Date().toLocaleTimeString();
        } catch (error) {
          $('diagnosticSummary').textContent = 'REST load failed: ' + error.message;
        }
      }

      function startPollingFallback() {
        if (state.pollTimer) return;
        setConnection('polling', 'Polling REST fallback');
        state.pollTimer = setInterval(loadInitialState, 5000);
      }

      function stopPollingFallback() {
        if (state.pollTimer) clearInterval(state.pollTimer);
        state.pollTimer = null;
      }

      function connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const url = protocol + '//' + window.location.host + '/ws/tps';
        setConnection(state.reconnectAttempts ? 'reconnecting' : 'disconnected', state.reconnectAttempts ? 'Reconnecting...' : 'Connecting...');
        try { state.ws = new WebSocket(url); } catch (error) { scheduleReconnect(); startPollingFallback(); return; }
        state.ws.onopen = () => { state.reconnectAttempts = 0; stopPollingFallback(); setConnection('connected', 'WebSocket connected'); };
        state.ws.onmessage = (event) => { try { updateFromTpsMessage(JSON.parse(event.data)); } catch (error) { console.warn('Invalid TPS update', error); } };
        state.ws.onerror = () => { setConnection('disconnected', 'WebSocket error'); };
        state.ws.onclose = () => { setConnection('disconnected', 'WebSocket disconnected'); startPollingFallback(); scheduleReconnect(); };
      }

      function scheduleReconnect() {
        state.reconnectAttempts += 1;
        const backoff = Math.min(30000, Math.pow(2, Math.min(state.reconnectAttempts - 1, 5)) * 1000);
        setConnection('reconnecting', 'Reconnecting in ' + Math.round(backoff / 1000) + 's');
        setTimeout(connectWebSocket, backoff);
      }

      function escapeHtml(value) {
        return String(value ?? '').replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
      }

      loadInitialState();
      connectWebSocket();
    }());
  </script>
</body>
</html>
"""
