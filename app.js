const LC = LightweightCharts;
const $ = (s) => document.querySelector(s);
const TF = ["Yearly", "Quarterly", "Monthly", "Weekly", "Daily"];
const BIAS_COLOR = { Bullish: "#15803d", Bearish: "#b91c1c", Neutral: "#475569" };
const D = {};

async function load(path) {
  try {
    const r = await fetch(`${path}?v=${Date.now()}`);
    return r.ok ? await r.json() : null;
  } catch { return null; }
}

const fmt = (v, d = 0) => (v == null ? "–" : Number(v).toLocaleString("en-IN", { maximumFractionDigits: d }));
const uniq = (pts) => {
  const m = new Map();
  pts.forEach((p) => m.set(p.time, p));
  return [...m.values()].sort((a, b) => (a.time < b.time ? -1 : 1));
};

function chart(el) {
  return LC.createChart(el, {
    autoSize: true,
    layout: { background: { type: "solid", color: "#0f172a" }, textColor: "#cbd5e1" },
    grid: { vertLines: { color: "#1e293b" }, horzLines: { color: "#1e293b" } },
    rightPriceScale: { borderColor: "#334155" },
    leftPriceScale: { borderColor: "#334155" },
    timeScale: { borderColor: "#334155" },
  });
}

function renderStatus() {
  const lastPoi = D.poi?.rows?.at(-1)?.d;
  const items = [
    ["Bias", D.bias?.generated],
    ["COT", D.cot?.updated],
    ["NSE OI", D.poi?.updated ? `${D.poi.updated} (session ${lastPoi})` : null],
    ["Prices", D.prices?.updated],
  ];
  $("#status").innerHTML = items
    .map(([k, v]) => `<span class="${v ? "" : "warn"}">${k}: ${v ?? "missing"}</span>`).join("");
}

function renderMatrix() {
  const inst = D.bias?.instruments;
  if (!inst) { $("#matrix").innerHTML = "<tr><td>No bias.json yet. Run the Colab cell.</td></tr>"; return; }
  let h = `<tr><th></th>${TF.map((t) => `<th>${t}</th>`).join("")}</tr>`;
  for (const [k, v] of Object.entries(inst)) {
    h += `<tr><th>${k}</th>` + TF.map((t) => {
      const b = v.timeframes[t];
      if (!b) return "<td>–</td>";
      return `<td class="cell" data-k="${k}" data-t="${t}" style="background:${BIAS_COLOR[b.label]}">
        ${b.label}<small>${b.score > 0 ? "+" : ""}${b.score} / ${b.n}</small></td>`;
    }).join("") + "</tr>";
  }
  $("#matrix").innerHTML = h;
  $("#matrix").onclick = (e) => {
    const c = e.target.closest(".cell");
    if (c) showDetail(c.dataset.k, c.dataset.t);
  };
}

function showDetail(k, t) {
  const b = D.bias.instruments[k].timeframes[t];
  const rows = b.components.map((c) => `<tr>
      <td class="sig s${c.signal}">${c.signal > 0 ? "▲" : c.signal < 0 ? "▼" : "●"}</td>
      <td>${c.name}</td><td>${c.note}</td><td class="muted">${c.asof ?? ""}</td></tr>`).join("");
  $("#detail").classList.remove("muted");
  $("#detail").innerHTML = `<h3>${k} · ${t}: ${b.label} (${b.score > 0 ? "+" : ""}${b.score} of ${b.n} votes)</h3>
    <div class="scroll"><table>${rows}</table></div>`;
}

function setupCot() {
  const mk = D.cot?.markets;
  if (!mk) return;
  const cls = (v) => (v == null ? "" : v >= 80 ? "hi" : v <= 20 ? "lo" : "");
  let h = `<tr><th>Market</th><th>Report</th><th>Commercials</th><th>Large spec</th><th>Small spec</th>
    <th>Idx 26w</th><th>Idx 52w</th><th>Idx 156w</th><th>For India</th></tr>`;
  for (const m of Object.values(mk)) {
    const r = m.rows.at(-1);
    const ix = (n) => m.idx[n].at(-1);
    h += `<tr><td title="${m.market_name}">${m.label}</td><td>${r.d}</td>
      <td>${fmt(r.comm)}</td><td>${fmt(r.ls)}</td><td>${fmt(r.ss)}</td>
      ${["26", "52", "156"].map((n) => `<td class="${cls(ix(n))}">${fmt(ix(n))}</td>`).join("")}
      <td>${m.impact > 0 ? "Bullish = good" : m.impact < 0 ? "Bullish = bad" : "Context"}</td></tr>`;
  }
  $("#cotTable").innerHTML = h;

  const sel = $("#cotSel");
  sel.innerHTML = Object.entries(mk).map(([k, m]) => `<option value="${k}">${m.label}</option>`).join("");
  const net = chart($("#cotNet"));
  const idx = chart($("#cotIdx"));
  const sC = net.addLineSeries({ color: "#ef4444", lineWidth: 2 });
  const sL = net.addLineSeries({ color: "#22c55e", lineWidth: 1 });
  const sS = net.addLineSeries({ color: "#3b82f6", lineWidth: 1 });
  sC.createPriceLine({ price: 0, color: "#94a3b8", lineStyle: 2, title: "zero" });
  const sI = idx.addLineSeries({ color: "#ef4444", lineWidth: 2 });
  sI.createPriceLine({ price: 80, color: "#16a34a", lineStyle: 2, title: "80" });
  sI.createPriceLine({ price: 20, color: "#dc2626", lineStyle: 2, title: "20" });

  const draw = () => {
    const m = mk[sel.value];
    const lb = $("#cotLb").value;
    sC.setData(uniq(m.rows.map((r) => ({ time: r.d, value: r.comm }))));
    sL.setData(uniq(m.rows.map((r) => ({ time: r.d, value: r.ls }))));
    sS.setData(uniq(m.rows.map((r) => ({ time: r.d, value: r.ss }))));
    sI.setData(uniq(m.rows.map((r, i) => ({ time: r.d, value: m.idx[lb][i] })).filter((p) => p.value != null)));
    net.timeScale().fitContent();
    idx.timeScale().fitContent();
  };
  sel.onchange = draw;
  $("#cotLb").onchange = draw;
  draw();
}

function setupPoi() {
  const rows = D.poi?.rows;
  if (!rows?.length) { $("#poiChart").innerHTML = "<p class='muted pad'>No participant OI yet.</p>"; return; }
  const c = chart($("#poiChart"));
  c.applyOptions({ leftPriceScale: { visible: true } });
  const cols = { FII: "#f59e0b", DII: "#a855f7", Client: "#3b82f6", Pro: "#22c55e" };
  const ser = {};
  for (const [k, col] of Object.entries(cols)) ser[k] = c.addLineSeries({ color: col, lineWidth: 2 });
  ser.FII.createPriceLine({ price: 0, color: "#94a3b8", lineStyle: 2, title: "zero" });

  const nifty = c.addLineSeries({ color: "#e2e8f0", lineWidth: 1, priceScaleId: "left" });
  const first = rows[0].d;
  nifty.setData(uniq((D.prices?.series?.NIFTY?.rows || [])
    .filter((r) => r.t >= first).map((r) => ({ time: r.t, value: r.c }))));

  const val = (p, seg) => (seg === "fut" ? p.fil - p.fis : (p.icl - p.ics) - (p.ipl - p.ips));
  const draw = () => {
    const seg = $("#poiSeg").value;
    for (const k in ser) {
      ser[k].setData(uniq(rows.filter((r) => r[k]).map((r) => ({ time: r.d, value: val(r[k], seg) }))));
    }
    c.timeScale().fitContent();
  };
  $("#poiSeg").onchange = draw;
  draw();
}

function setupPrice() {
  const S = D.prices?.series;
  if (!S) return;
  const sel = $("#pxSel");
  sel.innerHTML = Object.keys(S).map((k) => `<option>${k}</option>`).join("");
  const c = chart($("#pxChart"));
  const cs = c.addCandlestickSeries({
    upColor: "#16a34a", downColor: "#dc2626", wickUpColor: "#16a34a", wickDownColor: "#dc2626", borderVisible: false,
  });
  let lines = [];
  const styles = { Weekly: ["#38bdf8", "PW"], Monthly: ["#f472b6", "PM"], Quarterly: ["#facc15", "PQ"] };

  const draw = () => {
    const k = sel.value;
    const data = uniq(S[k].rows.map((r) => ({ time: r.t, open: r.o, high: r.h, low: r.l, close: r.c })));
    cs.setData(data);
    lines.forEach((l) => cs.removePriceLine(l));
    lines = [];
    const lv = D.bias?.instruments?.[k]?.levels || {};
    for (const [tf, [col, tag]] of Object.entries(styles)) {
      const L = lv[tf];
      if (!L) continue;
      lines.push(cs.createPriceLine({ price: L.prev_high, color: col, lineStyle: 2, title: `${tag}H` }));
      lines.push(cs.createPriceLine({ price: L.prev_low, color: col, lineStyle: 2, title: `${tag}L` }));
    }
    c.timeScale().setVisibleLogicalRange({ from: data.length - 250, to: data.length + 5 });
  };
  sel.onchange = draw;
  draw();
}

(async function init() {
  [D.bias, D.cot, D.poi, D.prices] = await Promise.all(
    ["data/bias.json", "data/cot.json", "data/participant_oi.json", "data/prices.json"].map(load));
  renderStatus();
  renderMatrix();
  setupCot();
  setupPoi();
  setupPrice();
})();
