(function () {
  const $ = (s) => document.querySelector(s);
  const NAMES = { SENSEX: "Sensex", NIFTY: "Nifty 50", BANKNIFTY: "Bank Nifty", FINNIFTY: "FinNifty", USDINR: "USD/INR", DXY: "Dollar Index" };
  const esc = (s = "") => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmt = (v, d = 0) => (v == null || isNaN(v) ? "–" : Number(v).toLocaleString("en-IN", { minimumFractionDigits: d, maximumFractionDigits: d }));
  const sgn = (v) => (v == null ? "" : (v > 0 ? "+" : "") + fmt(v, 2) + "%");
  const tone = (s) => (s === "bullish" ? "bull" : s === "bearish" ? "bear" : "neutral");
  const arrow = (t) => (t === "bull" ? "▲" : t === "bear" ? "▼" : "◆");
  const list = (a) => `<ul>${(a || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`;
  let ICT = null, PR = null, cur = null, chart = null;

  async function get(p) {
    try { const r = await fetch(`${p}?v=${Date.now()}`); return r.ok ? await r.json() : null; } catch { return null; }
  }

  function lvl(x, label) {
    if (!x) return `<div class="kv-i"><span>${esc(label)}</span><b>–</b></div>`;
    const price = x.low != null ? `${fmt(x.low)} – ${fmt(x.high)}` : fmt(x.price);
    return `<div class="kv-i"><span>${esc(label)}</span><b>${price}</b><small>${esc(x.name)} · ${sgn(x.dist)}</small></div>`;
  }

  function drawCard(I) {
    const D = I.draw, t = tone(D.direction);
    const st = ["ERL raid (manipulation)", "IRL rebalance (entry)", "Expansion to ERL (target)"];
    return `<div class="card hero ${t}">
      <div class="hero-head"><div>
        <div class="eyebrow">${NAMES[cur]} · close ${fmt(I.close, 2)} · ${esc(I.asof)} · daily ATR ${fmt(I.atr)}</div>
        <h1>Draw on liquidity: ${esc(D.headline)}</h1></div>
        <div class="verdict ${t}"><span>${arrow(t)}</span>${esc(D.direction)}</div></div>
      <div class="cycle">${st.map((s, i) => `<span class="${i === D.stage_idx ? "on" : ""}">${s}</span>`).join("<i>→</i>")}</div>
      <p class="stage">${esc(D.stage)}</p>
      <div class="kv">${lvl(D.target, D.target_label)}${lvl(D.entry, D.entry_label)}${lvl(D.invalidation, D.invalidation_label)}</div>
      <div class="col"><h4>Why</h4>${list(D.reasons)}</div></div>`;
  }

  function rangesCard(I) {
    const rows = I.ranges.map((r) => {
      const span = r.high - r.low || 1;
      const oL = ((r.ote_low - r.low) / span) * 100, oW = ((r.ote_high - r.ote_low) / span) * 100;
      const pos = Math.max(0, Math.min(100, r.pos));
      return `<div class="rng"><div class="rng-h"><b>${r.lookback}-day dealing range</b><span>${fmt(r.low)} – ${fmt(r.high)}</span></div>
        <div class="rbar"><span class="ote" style="left:${oL}%;width:${oW}%"></span><i class="eq"></i><b class="mk" style="left:${pos}%"></b></div>
        <div class="rng-f"><span>Discount</span><span>EQ ${fmt(r.eq)}</span><span>Premium</span></div>
        <p>${esc(r.note)}</p></div>`;
    }).join("");
    return `<div class="card"><h3>Equilibrium &amp; dealing ranges</h3>
      <p class="sub">IPDA look-backs. Buy below equilibrium, sell above it. Blue band = OTE (62–79% retracement) of the current leg. White marker = price.</p>${rows}</div>`;
  }

  function po3Card(I) {
    const p = I.po3 || {};
    const item = (k, lab) => p[k] ? `<div class="po3"><b>${lab}</b><span>O ${fmt(p[k].open)} · H ${fmt(p[k].high)} · L ${fmt(p[k].low)} · C ${fmt(p[k].close)}</span><p>${esc(p[k].note)}</p></div>` : "";
    return `<div class="card"><h3>Power of 3 &amp; weekly profile</h3>
      <p class="sub">Accumulation → manipulation (Judas move against the open) → distribution.</p>
      ${item("week", "This week")}${item("month", "This month")}
      <div class="po3"><b>Weekly profile</b><p>${esc(I.week_profile)}</p></div>
      <div class="po3"><b>Expiry</b><p>${esc(ICT.expiry)}</p></div></div>`;
  }

  function ladderCard(I) {
    let placed = false, rows = "";
    const nowRow = `<tr class="now"><td colspan="4">▶ Price ${fmt(I.close, 2)}</td></tr>`;
    for (const x of I.ladder) {
      if (!placed && x.price < I.close) { rows += nowRow; placed = true; }
      const z = x.low != null ? `${fmt(x.low)}–${fmt(x.high)}` : fmt(x.price);
      const k = x.kind.toLowerCase();
      rows += `<tr><td><span class="tag k-${k}">${x.kind}</span></td><td>${esc(x.label)}<small>${esc(x.status || "")}</small></td>
        <td class="num">${z}</td><td class="num ${x.dist >= 0 ? "up" : "down"}">${sgn(x.dist)}</td></tr>`;
    }
    if (!placed) rows += nowRow;
    return `<div class="card"><h3>Liquidity &amp; rebalance ladder</h3>
      <p class="sub">ERL = resting stops (targets). IRL = imbalances price returns to (entries). EQ = equilibrium. Within ±12% of price.</p>
      <div class="scroll"><table class="ladder">${rows}</table></div></div>`;
  }

  function smtCard() {
    const rel = (ICT.smt || []).filter((r) => r.a === cur || r.b === cur);
    const rows = (rel.length ? rel : ICT.smt || []).map((r) => `<tr>
      <td>${NAMES[r.a]} vs ${NAMES[r.b]}${r.corr < 0 ? " <small>(inverse)</small>" : ""}</td>
      <td>${esc(r.horizon)}</td><td><span class="tag ${tone(r.type)}">${esc(r.type)}</span></td>
      <td class="wrap">${esc(r.note)}</td></tr>`).join("");
    return `<div class="card"><h3>SMT divergence</h3>
      <p class="sub">When correlated markets disagree at a liquidity raid, smart money is taking the other side. Trade the stronger leg.</p>
      <div class="scroll"><table class="smt">${rows}</table></div></div>`;
  }

  function sigCard(I) {
    const ev = (I.events || []).slice().reverse().map((e) => `${e.date}: ${e.note}`);
    return `<div class="card"><h3>Institutional signature</h3><p class="sub">What FIIs did after the most recent major swing.</p>
      <p>${esc(I.signature || "Not enough NSE data yet.")}</p>
      <h3 style="margin-top:14px">Recent liquidity events (last 15 sessions)</h3>${ev.length ? list(ev) : "<p class='muted'>None</p>"}</div>`;
  }

  function drawChart(I) {
    if (chart) { chart.remove(); chart = null; }
    const el = $("#ictChart"), S = PR?.series?.[cur];
    if (!el || !S || !window.LightweightCharts) return;
    chart = LightweightCharts.createChart(el, {
      autoSize: true,
      layout: { background: { type: "solid", color: "transparent" }, textColor: "#8a96ad" },
      grid: { vertLines: { color: "rgba(148,163,184,.06)" }, horzLines: { color: "rgba(148,163,184,.06)" } },
      rightPriceScale: { borderVisible: false }, timeScale: { borderVisible: false },
    });
    const cs = chart.addCandlestickSeries({ upColor: "#22c55e", downColor: "#ef4444", wickUpColor: "#22c55e", wickDownColor: "#ef4444", borderVisible: false });
    const data = S.rows.map((r) => ({ time: r.t, open: r.o, high: r.h, low: r.l, close: r.c }));
    cs.setData(data);
    const L = (price, color, title, style = 2) => { if (price != null) cs.createPriceLine({ price, color, lineStyle: style, lineWidth: 1, title }); };
    const D = I.draw;
    const tc = D.direction === "bearish" ? "#ef4444" : "#22c55e";
    if (D.target) L(D.target.price, tc, D.direction === "two-sided" ? "BSL" : "Target");
    if (D.entry) { if (D.entry.low != null) { L(D.entry.high, "#60a5fa", "IRL"); L(D.entry.low, "#60a5fa", ""); } else L(D.entry.price, "#60a5fa", "EQ"); }
    if (D.invalidation) L(D.invalidation.price, "#f59e0b", D.direction === "two-sided" ? "SSL" : "Invalid");
    if (I.ranges[1]) L(I.ranges[1].eq, "#a78bfa", "EQ40", 1);
    chart.timeScale().setVisibleLogicalRange({ from: data.length - 160, to: data.length + 5 });
  }

  function render() {
    const I = ICT.instruments[cur];
    $("#ict").innerHTML = `
      <div class="sec-head"><h2>ICT liquidity map</h2>
        <p>Price is delivered from liquidity to imbalance and back: external range liquidity (ERL – old highs and lows, where stops rest)
        ↔ internal range liquidity (IRL – fair value gaps, order blocks, equilibrium). Daily data, updated every evening.</p></div>
      <div class="tabs" id="ictTabs">${Object.keys(ICT.instruments).map((k) => `<button data-k="${k}" class="${k === cur ? "on" : ""}">${NAMES[k]}</button>`).join("")}</div>
      ${drawCard(I)}
      <div class="ict-grid">${rangesCard(I)}${po3Card(I)}</div>
      <div class="ict-grid">${ladderCard(I)}<div>${smtCard()}${sigCard(I)}</div></div>
      <div class="card" style="margin-top:16px"><div class="row"><b>${NAMES[cur]} daily</b>
        <span class="legend"><span><i style="background:#22c55e"></i>Target</span><span><i style="background:#60a5fa"></i>IRL entry zone</span>
        <span><i style="background:#f59e0b"></i>Invalidation</span><span><i style="background:#a78bfa"></i>40-day equilibrium</span></span></div>
        <div id="ictChart" class="chart tall"></div></div>
      <details class="howto"><summary>How to read this</summary>
        <p>1. Start with the draw: where is the nearest unswept liquidity in the direction of structure? That is the target.</p>
        <p>2. Check the cycle stage. Right after ERL is taken, expect a retracement into IRL – that is where entries come, not at the highs.</p>
        <p>3. Use equilibrium: in a bullish draw, only buy below the dealing range's equilibrium (discount), ideally inside the OTE band or a fresh FVG.</p>
        <p>4. Confirm with SMT and the FII signature. Then drop to your intraday chart for the entry model (MSS + displacement + FVG).</p>
      </details>`;
    $("#ictTabs").onclick = (e) => { const b = e.target.closest("button"); if (b) { cur = b.dataset.k; render(); } };
    drawChart(I);
  }

  (async function init() {
    [ICT, PR] = await Promise.all([get("data/ict.json"), get("data/prices.json")]);
    const box = $("#ict");
    if (!box) return;
    if (!ICT || !ICT.instruments || !Object.keys(ICT.instruments).length) {
      box.innerHTML = "<div class='card muted'>ICT map not built yet – run the Colab cell.</div>";
      return;
    }
    cur = ICT.instruments[ICT.focus] ? ICT.focus : Object.keys(ICT.instruments)[0];
    render();
  })();
})();
