const LC = LightweightCharts;
const $ = (s) => document.querySelector(s);
const TF = ["Yearly", "Quarterly", "Monthly", "Weekly", "Daily"];
const TF_HINT = { Yearly: "Big picture", Quarterly: "Main swing", Monthly: "Position bias", Weekly: "Trade bias", Daily: "Session context" };
const NAMES = { NIFTY: "Nifty 50", SENSEX: "Sensex", BANKNIFTY: "Bank Nifty", USDINR: "USD / INR", INDIAVIX: "India VIX", DXY: "Dollar Index", US10Y: "US 10Y yield" };
const WHAT = { DXY: "a stronger US dollar", UST10Y: "higher bond prices (lower US yields)", MSCIEM: "rising emerging-market stocks", NASDAQ: "rising US tech stocks", SP500: "rising US stocks", CRUDE: "higher crude oil", GOLD: "higher gold" };
const ROLE = {
  FII: "Foreign funds - the closest thing to smart money in Indian F&O. Follow their direction.",
  Client: "Retail & HNI traders - usually wrong at extremes. Read contrarian.",
  Pro: "Broker prop desks - mostly option writers and arbitrage.",
  DII: "Mutual funds & insurers - mostly hedging their stock holdings.",
};
const D = {};
let current = "NIFTY";
let drawPrice = null;

async function load(path) {
  try {
    const r = await fetch(`${path}?v=${Date.now()}`);
    return r.ok ? await r.json() : null;
  } catch { return null; }
}

const esc = (s = "") => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (v, d = 0) => (v == null || isNaN(v) ? "–" : Number(v).toLocaleString("en-IN", { minimumFractionDigits: d, maximumFractionDigits: d }));
const sgn = (v, d = 0) => (v > 0 ? "+" : "") + fmt(v, d);
const tone = (l = "") => (/bull/i.test(l) ? "bull" : /bear/i.test(l) ? "bear" : "neutral");
const arrow = (t) => (t === "bull" ? "▲" : t === "bear" ? "▼" : "◆");
const list = (items) => `<ul>${(items || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`;
const uniq = (pts) => {
  const m = new Map();
  pts.forEach((p) => m.set(p.time, p));
  return [...m.values()].sort((a, b) => (a.time < b.time ? -1 : 1));
};

function chart(el) {
  return LC.createChart(el, {
    autoSize: true,
    layout: { background: { type: "solid", color: "transparent" }, textColor: "#8a96ad", fontFamily: "Inter, system-ui, sans-serif" },
    grid: { vertLines: { color: "rgba(148,163,184,.06)" }, horzLines: { color: "rgba(148,163,184,.06)" } },
    rightPriceScale: { borderVisible: false },
    leftPriceScale: { borderVisible: false },
    timeScale: { borderVisible: false },
  });
}

function renderUpdated() {
  const last = D.poi?.rows?.at(-1)?.d;
  const stale = last && (Date.now() - new Date(last)) / 864e5 > 4;
  const el = $("#updated");
  el.innerHTML = `<span class="dot ${stale ? "warn" : ""}"></span>Updated ${esc(D.bias?.generated ?? "–")}`;
  el.title = `COT: ${D.cot?.updated ?? "–"}\nNSE session: ${last ?? "–"}\nPrices: ${D.prices?.updated ?? "–"}`;
}

function renderTabs() {
  const keys = Object.keys(D.story?.instruments || {});
  $("#instTabs").innerHTML = keys.map((k) => `<button data-k="${k}" class="${k === current ? "on" : ""}">${NAMES[k] || k}</button>`).join("");
  $("#instTabs").onclick = (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    current = b.dataset.k;
    renderTabs();
    renderStory();
    if (drawPrice) drawPrice(current);
  };
}

function renderStory() {
  const s = D.story?.instruments?.[current];
  if (!s) { $("#story").innerHTML = `<div class="card muted">No story yet - run the Colab cell.</div>`; return; }
  const t = tone(s.verdict);
  const ai = D.story.ai?.[current];
  const mac = D.story.macro || { lines: [], summary: "–", tone: "neutral" };
  const lv = (s.levels || []).map((l) => `<tr class="${Math.abs(l.dist) < 0.4 ? "near" : ""}">
      <td>${esc(l.name)}</td><td class="num">${fmt(l.price, 2)}</td>
      <td class="num ${l.dist >= 0 ? "up" : "down"}">${sgn(l.dist, 2)}%</td></tr>`).join("");
  $("#story").innerHTML = `
    <div class="hero card ${t}">
      <div class="hero-head">
        <div>
          <div class="eyebrow">${esc(s.name)} · close ${fmt(s.close, 2)} · ${esc(s.asof)}</div>
          <h1>${esc(s.headline)}</h1>
        </div>
        <div class="verdict ${t}"><span>${arrow(t)}</span>${esc(s.verdict)}</div>
      </div>
      <div class="story3">
        <div class="col"><h4><i>1</i>Where it's coming from</h4>${list(s.coming_from)}</div>
        <div class="col"><h4><i>2</i>What it's doing</h4>${list(s.doing)}</div>
        <div class="col"><h4><i>3</i>What's next</h4>${list(s.next)}</div>
      </div>
      ${s.risks?.length ? `<div class="risks"><h4>⚠ What argues against it</h4>${list(s.risks)}</div>` : ""}
      ${ai ? `<div class="ai"><h4>AI commentary <small>${esc(ai.model)} · ${esc(ai.generated)}</small></h4><p>${esc(ai.text)}</p></div>` : ""}
    </div>
    <div class="split">
      <div class="card"><h3>Key levels</h3><p class="sub">Sorted by price. Highlighted = within 0.4% of the close.</p><table class="levels">${lv}</table></div>
      <div class="card"><h3>Global backdrop <span class="tag ${tone(mac.tone)}">${esc(mac.summary)}</span></h3>
        <p class="sub">Hedger positioning at 52-week extremes (CFTC).</p>${list(mac.lines)}
        ${mac.neutral?.length ? `<p class="sub">No signal: ${esc(mac.neutral.join(", "))}</p>` : ""}</div>
    </div>`;
}

function renderBias() {
  const inst = D.bias?.instruments;
  if (!inst) return;
  let h = `<div class="bgrid"><div></div>${TF.map((t) => `<div class="bh">${t}<small>${TF_HINT[t]}</small></div>`).join("")}`;
  for (const [k, v] of Object.entries(inst)) {
    h += `<div class="bname">${NAMES[k] || k}</div>`;
    for (const t of TF) {
      const b = v.timeframes[t];
      if (!b) { h += "<div></div>"; continue; }
      const tn = tone(b.label);
      const conf = b.n ? Math.round((Math.abs(b.score) / b.n) * 100) : 0;
      h += `<button class="bcell ${tn}" data-k="${k}" data-t="${t}">
        <span class="bl">${arrow(tn)} ${b.label}</span>
        <span class="bar"><i style="width:${conf}%"></i></span>
        <span class="bs">${b.score > 0 ? "+" : ""}${b.score} of ${b.n} votes</span></button>`;
    }
  }
  $("#biasGrid").innerHTML = h + "</div>";
  $("#biasGrid").onclick = (e) => {
    const c = e.target.closest(".bcell");
    if (c) showVotes(c.dataset.k, c.dataset.t);
  };
}

function showVotes(k, t) {
  const b = D.bias.instruments[k].timeframes[t];
  const box = $("#votes");
  box.classList.remove("hidden");
  box.innerHTML = `<div class="vhead"><h3>${NAMES[k] || k} · ${t} → <span class="${tone(b.label)}-t">${b.label}</span></h3><button class="x">✕</button></div>` +
    b.components.map((c) => {
      const tn = c.signal > 0 ? "bull" : c.signal < 0 ? "bear" : "neutral";
      const lab = c.signal > 0 ? "▲ Bullish" : c.signal < 0 ? "▼ Bearish" : "◆ Neutral";
      return `<div class="vote"><span class="vs ${tn}">${lab}</span><div><b>${esc(c.name)}</b><p>${esc(c.note)}</p></div><span class="muted small">${esc(c.asof || "")}</span></div>`;
    }).join("");
  box.querySelector(".x").onclick = () => box.classList.add("hidden");
  box.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function renderCotCards() {
  const mk = D.cot?.markets;
  if (!mk) return;
  $("#cotCards").innerHTML = Object.entries(mk).map(([k, m]) => {
    const v = m.idx["52"].at(-1);
    const r = m.rows.at(-1);
    const state = v == null ? "neutral" : v >= 80 ? "bull" : v <= 20 ? "bear" : "neutral";
    let effect = "Context only";
    if (m.impact !== 0) effect = state === "neutral" ? "No signal" : (state === "bull") === (m.impact > 0) ? "Good for India" : "Headwind for India";
    const et = effect.startsWith("Good") ? "bull" : effect.startsWith("Head") ? "bear" : "neutral";
    const txt = state === "bull" ? `Hedgers near their most bullish of the year - favours ${WHAT[k]}.`
      : state === "bear" ? `Hedgers near their most bearish of the year - leans against ${WHAT[k]}.`
      : "Hedgers are mid-range - no strong signal.";
    return `<div class="card cot">
      <div class="cot-head"><b>${esc(m.label)}</b><span class="tag ${et}">${effect}</span></div>
      <div class="gauge"><i style="left:${v ?? 50}%"></i></div>
      <div class="gl"><span>Max short</span><b>${fmt(v)} / 100</b><span>Max long</span></div>
      <p>${txt}</p>
      <div class="mini">26w ${fmt(m.idx["26"].at(-1))} · 52w ${fmt(v)} · 3y ${fmt(m.idx["156"].at(-1))} · report ${r.d}</div>
    </div>`;
  }).join("");
}

function setupCotChart() {
  const mk = D.cot?.markets;
  if (!mk) return;
  const sel = $("#cotSel");
  sel.innerHTML = Object.entries(mk).map(([k, m]) => `<option value="${k}">${esc(m.label)}</option>`).join("");
  const net = chart($("#cotNet"));
  const idx = chart($("#cotIdx"));
  const sC = net.addLineSeries({ color: "#ef4444", lineWidth: 2 });
  const sL = net.addLineSeries({ color: "#22c55e", lineWidth: 1 });
  const sS = net.addLineSeries({ color: "#3b82f6", lineWidth: 1 });
  sC.createPriceLine({ price: 0, color: "#64748b", lineStyle: 2, title: "zero" });
  const sI = idx.addLineSeries({ color: "#ef4444", lineWidth: 2 });
  sI.createPriceLine({ price: 80, color: "#22c55e", lineStyle: 2, title: "80" });
  sI.createPriceLine({ price: 20, color: "#ef4444", lineStyle: 2, title: "20" });
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

const poiVal = (p, seg) => (seg === "fut" ? p.fil - p.fis : (p.icl - p.ics) - (p.ipl - p.ips));

function renderPoiCards() {
  const rows = D.poi?.rows;
  if (!rows?.length) return;
  $("#poiCards").innerHTML = ["FII", "Client", "Pro", "DII"].map((g) => {
    const s = rows.filter((r) => r[g]).map((r) => poiVal(r[g], "fut"));
    if (s.length < 21) return "";
    const now = s.at(-1), d1 = now - s.at(-2), d5 = now - s.at(-6), d20 = now - s.at(-21);
    const c = (v) => (v >= 0 ? "up" : "down");
    return `<div class="card pcard">
      <div class="cot-head"><b>${g}</b><span class="tag ${now >= 0 ? "bull" : "bear"}">Net ${now >= 0 ? "long" : "short"}</span></div>
      <div class="big ${c(now)}">${sgn(now)}</div><div class="sub">index futures, contracts</div>
      <div class="chg"><span>1d <b class="${c(d1)}">${sgn(d1)}</b></span><span>5d <b class="${c(d5)}">${sgn(d5)}</b></span><span>20d <b class="${c(d20)}">${sgn(d20)}</b></span></div>
      <p>${ROLE[g]}</p></div>`;
  }).join("");
}

function setupPoiChart() {
  const rows = D.poi?.rows;
  if (!rows?.length) { $("#poiChart").innerHTML = "<p class='muted pad'>No participant OI yet.</p>"; return; }
  const c = chart($("#poiChart"));
  c.applyOptions({ leftPriceScale: { visible: true } });
  const cols = { FII: "#f59e0b", DII: "#a855f7", Client: "#3b82f6", Pro: "#22c55e" };
  const ser = {};
  for (const [k, col] of Object.entries(cols)) ser[k] = c.addLineSeries({ color: col, lineWidth: 2 });
  ser.FII.createPriceLine({ price: 0, color: "#64748b", lineStyle: 2, title: "zero" });
  const nifty = c.addLineSeries({ color: "rgba(226,232,240,.7)", lineWidth: 1, priceScaleId: "left" });
  const first = rows[0].d;
  nifty.setData(uniq((D.prices?.series?.NIFTY?.rows || []).filter((r) => r.t >= first).map((r) => ({ time: r.t, value: r.c }))));
  const draw = () => {
    const seg = $("#poiSeg").value;
    for (const k in ser) ser[k].setData(uniq(rows.filter((r) => r[k]).map((r) => ({ time: r.d, value: poiVal(r[k], seg) }))));
    c.timeScale().fitContent();
  };
  $("#poiSeg").onchange = draw;
  draw();
}

function setupPrice() {
  const S = D.prices?.series;
  if (!S) return;
  const sel = $("#pxSel");
  sel.innerHTML = Object.keys(S).map((k) => `<option value="${k}">${NAMES[k] || k}</option>`).join("");
  const c = chart($("#pxChart"));
  const cs = c.addCandlestickSeries({ upColor: "#22c55e", downColor: "#ef4444", wickUpColor: "#22c55e", wickDownColor: "#ef4444", borderVisible: false });
  const styles = { Weekly: ["#38bdf8", "PW"], Monthly: ["#f472b6", "PM"], Quarterly: ["#facc15", "PQ"] };
  let lines = [];
  drawPrice = (k) => {
    if (k && S[k]) sel.value = k;
    const key = sel.value;
    const data = uniq(S[key].rows.map((r) => ({ time: r.t, open: r.o, high: r.h, low: r.l, close: r.c })));
    cs.setData(data);
    lines.forEach((l) => cs.removePriceLine(l));
    lines = [];
    const lv = D.bias?.instruments?.[key]?.levels || {};
    for (const [tf, [col, tag]] of Object.entries(styles)) {
      const L = lv[tf];
      if (!L) continue;
      lines.push(cs.createPriceLine({ price: L.prev_high, color: col, lineStyle: 2, title: `${tag}H` }));
      lines.push(cs.createPriceLine({ price: L.prev_low, color: col, lineStyle: 2, title: `${tag}L` }));
    }
    c.timeScale().setVisibleLogicalRange({ from: data.length - 250, to: data.length + 5 });
  };
  sel.onchange = () => drawPrice();
  drawPrice(current);
}

(async function init() {
  [D.bias, D.cot, D.poi, D.prices, D.story] = await Promise.all(
    ["data/bias.json", "data/cot.json", "data/participant_oi.json", "data/prices.json", "data/story.json"].map(load));
  if (D.story?.instruments && !D.story.instruments[current]) current = Object.keys(D.story.instruments)[0];
  renderUpdated();
  renderTabs();
  renderStory();
  renderBias();
  renderCotCards();
  setupCotChart();
  renderPoiCards();
  setupPoiChart();
  setupPrice();
})();
