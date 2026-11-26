(function () {
  "use strict";
  const $ = (s, r = document) => r.querySelector(s);
  const esc = (s = "") => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const num = (v, d = 0) => (v == null || isNaN(v) ? "–" : Number(v).toLocaleString("en-IN", { minimumFractionDigits: d, maximumFractionDigits: d }));
  const NAME = { SENSEX: "Sensex", NIFTY: "Nifty 50", BANKNIFTY: "Bank Nifty" };
  const X = { intra: null, bt: null };
  let chart = null;
  const keyNow = () => { try { return localStorage.getItem("mp_key") || "SENSEX"; } catch (e) { return "SENSEX"; } };
  const tone = (s) => (s === "bullish" ? "up" : s === "bearish" ? "down" : "flat");
  const stcls = (s) => (s === "untouched" ? "flat" : s === "closed beyond" ? "up" : "warn");
  async function get(p) { try { const r = await fetch(`${p}?v=${Date.now()}`); return r.ok ? await r.json() : null; } catch (e) { return null; } }
  const tests = (k) => (X.bt && X.bt.instruments && X.bt.instruments[k]) || [];
  const findTest = (id) => { for (const k of ["SENSEX", "NIFTY"]) { const t = tests(k).find((x) => x.id === id); if (t) return t; } return null; };
  const grab = (t, re) => { const m = t && t.summary && t.summary.match(re); return m ? m.slice(1) : null; };
  const SR = () => grab(findTest("sweep_rejection"), /inside (\d+%) of the time vs (\d+%)/);
  const FH = () => { const g = grab(findTest("first_hour"), /in (\d+%)/); return g ? g[0] : null; };

  function opening(I) {
    const day = I.today.date;
    const bars = I.bars.filter((b) => new Date(b.t * 1000).toISOString().slice(0, 10) === day);
    if (bars.length < 4) return null;
    const fh = bars.slice(0, 4);
    const hi = Math.max(...fh.map((b) => b.h)), lo = Math.min(...fh.map((b) => b.l)), cl = fh[3].c;
    const { pdh, pdl, close } = I.today;
    let side = null, kind = "inside";
    if (hi > pdh && lo < pdl) kind = "both";
    else if (hi > pdh) { side = "PDH"; kind = cl < pdh ? "rejection" : "held"; }
    else if (lo < pdl) { side = "PDL"; kind = cl > pdl ? "rejection" : "held"; }
    const level = side === "PDH" ? pdh : side === "PDL" ? pdl : null;
    const backInside = side === "PDH" ? close < pdh : side === "PDL" ? close > pdl : null;
    return { hi, lo, kind, side, level, backInside };
  }

  function renderIntraday() {
    const box = $("#intraday"); if (!box) return;
    const all = X.intra && X.intra.instruments;
    let k = keyNow(); if (all && !all[k]) k = "SENSEX";
    const I = all && all[k];
    const head = `<div class="sec-head"><h2>Intraday · ${NAME[k] || k}</h2><p>Latest session on 15-minute data, with only the statistics that passed testing. Times in IST.</p></div>`;
    if (!I) { box.innerHTML = head + `<div class="card muted">Intraday data not built yet.</div>`; return; }
    const d = I.today, s = I.stats, O = opening(I), sr = SR(), fh = FH();
    const zones = X.intra.zones.map((z) => {
      const m = [];
      if (d.high_zone === z.name) m.push(`<span class="zt up">High ${num(d.high)} · ${d.high_time}</span>`);
      if (d.low_zone === z.name) m.push(`<span class="zt down">Low ${num(d.low)} · ${d.low_time}</span>`);
      return `<div class="kzc ${m.length ? "hit" : ""}"><b>${esc(z.name)}</b><small>${z.from}–${z.to}</small>${m.join("")}</div>`;
    }).join("");
    let oc = "";
    if (O) {
      const sideTxt = O.side === "PDH" ? "high" : "low";
      const txt = O.kind === "rejection"
        ? `The first hour swept the previous-day ${sideTxt} (${num(O.level)}) and closed back inside — a rejection. Over 2 years, the day then closed back inside ${sr ? sr[0] : "~71%"} of the time.`
        : O.kind === "held"
        ? `The first hour broke the previous-day ${sideTxt} (${num(O.level)}) and held beyond. Over 2 years, the day closed back inside only ${sr ? sr[1] : "~26%"} of the time — continuation was more common.`
        : O.kind === "both" ? "The first hour traded beyond both the previous-day high and low — an outside opening."
        : "The first hour stayed inside the previous day's range — no opening sweep today.";
      const res = O.side ? `Outcome today: the session closed ${O.backInside ? "back inside" : "beyond"} the level.` : "";
      oc = `<div class="card"><h3>Opening context <span class="tag up">proven</span></h3>
        <div class="ohlc"><span>First-hour high <b>${num(O.hi)}</b></span><span>First-hour low <b>${num(O.lo)}</b></span></div>
        <p class="body">${esc(txt)}</p>${res ? `<p class="sub">${esc(res)}</p>` : ""}</div>`;
    }
    box.innerHTML = head + `
      <div class="ix-grid">
        <div class="card"><h3>Session recap · ${esc(d.date)}</h3>
          <div class="ohlc"><span>O <b>${num(d.open)}</b></span><span>H <b>${num(d.high)}</b></span><span>L <b>${num(d.low)}</b></span><span>C <b>${num(d.close)}</b></span></div>
          <div class="chips"><span class="tag ${tone(d.direction)}">${d.direction} day</span>
            <span class="tag ${stcls(d.pdh_status)}">PDH ${num(d.pdh)}: ${esc(d.pdh_status)}</span>
            <span class="tag ${stcls(d.pdl_status)}">PDL ${num(d.pdl)}: ${esc(d.pdl_status)}</span></div>
          <ul>${d.story.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>
        ${oc}
      </div>
      <div class="ix-grid" style="margin-top:12px">
        <div class="card"><h3>Kill zones <span class="tag up">proven</span></h3><div class="kz">${zones}</div>
          <p class="sub" style="margin-top:10px">Backtest (2 years): the day's high or low formed in the first hour on ${fh || "~78%"} of sessions. Last ${s.sessions} sessions (15-min): ${s.extreme_in_open_kz}%.</p></div>
        <div class="card"><h3>Next session levels</h3>
          <div class="ohlc"><span>New PDH <b>${num(I.next.pdh)}</b></span><span>New PDL <b>${num(I.next.pdl)}</b></span><span>Close <b>${num(I.next.prev_close)}</b></span></div>
          <p class="sub">Today's high and low become tomorrow's previous-day liquidity. Watch how the first hour treats them.</p></div>
      </div>
      <div class="card" style="margin-top:12px"><div class="row"><b>Last 5 sessions · 15m</b>
        <span class="legend"><span><i style="background:#f59e0b"></i>Previous-day high / low</span><span><i style="background:#a78bfa"></i>Today's open</span></span></div>
        <div id="ixChart" class="chart tall"></div></div>`;
    drawChart(I);
  }

  function drawChart(I) {
    if (chart) { chart.remove(); chart = null; }
    const el = $("#ixChart"); if (!el || !window.LightweightCharts) return;
    chart = LightweightCharts.createChart(el, {
      autoSize: true, layout: { background: { type: "solid", color: "transparent" }, textColor: "#8a96ad" },
      grid: { vertLines: { color: "rgba(148,163,184,.06)" }, horzLines: { color: "rgba(148,163,184,.06)" } },
      rightPriceScale: { borderVisible: false }, timeScale: { borderVisible: false, timeVisible: true, secondsVisible: false },
    });
    const cs = chart.addCandlestickSeries({ upColor: "#22c55e", downColor: "#ef4444", wickUpColor: "#22c55e", wickDownColor: "#ef4444", borderVisible: false });
    cs.setData(I.bars.map((b) => ({ time: b.t, open: b.o, high: b.h, low: b.l, close: b.c })));
    const L = (p, c, t) => cs.createPriceLine({ price: p, color: c, lineStyle: 2, lineWidth: 1, title: t });
    L(I.today.pdh, "#f59e0b", "PDH"); L(I.today.pdl, "#f59e0b", "PDL"); L(I.today.open, "#a78bfa", "Open");
    chart.timeScale().fitContent();
  }

  function renderBacktest() {
    const box = $("#backtest"); if (!box) return;
    let k = keyNow(); if (!tests(k).length) k = "SENSEX";
    const T = tests(k), P = T.filter((t) => t.verdict === "Holds");
    const head = `<div class="sec-head"><h2>Proven by data · ${NAME[k] || k}</h2><p>Only ideas that beat chance by at least 2 standard errors on long history are shown. ${T.length - P.length} other ideas were tested and did not hold, so they are left out.</p></div>`;
    if (!P.length) { box.innerHTML = head + `<div class="card muted">No idea has passed testing yet.</div>`; return; }
    box.innerHTML = head + `<div class="bt-grid">${P.map((t) => `<div class="card bt">
      <div class="bt-h"><b>${esc(t.title)}</b><span class="tag up">Proven</span></div>
      <p>${esc(t.summary)}</p>
      ${t.rows && t.rows.length ? `<div class="scroll"><table class="bt-t"><tr>${t.cols.map((c) => `<th>${esc(c)}</th>`).join("")}</tr>${t.rows.map((r) => `<tr>${r.map((v) => `<td>${esc(String(v))}</td>`).join("")}</tr>`).join("")}</table></div>` : ""}
      <p class="sub">${esc(t.sample)}</p></div>`).join("")}</div>`;
  }

  window.MP_EXTRA = {
    simple(key) {
      let html = "";
      const I = X.intra && X.intra.instruments && X.intra.instruments[key];
      if (I) {
        const d = I.today, O = opening(I), sr = SR();
        const st = { "untouched": "touch nahi hua", "closed beyond": "break hua aur beyond close hua",
                     "raided, closed back inside": "sweep hua par price wapas andar close hua (stop hunt)" };
        const L = [
          `${num(d.open)} pe open hua, ${num(d.close)} pe close hua — ${d.direction === "bullish" ? "Bullish" : "Bearish"} day.`,
          `Day high ${num(d.high)} (${d.high_time}, ${d.high_zone}) · Day low ${num(d.low)} (${d.low_time}, ${d.low_zone}).`,
          `Previous day high ${num(d.pdh)}: ${st[d.pdh_status] || d.pdh_status}.`,
          `Previous day low ${num(d.pdl)}: ${st[d.pdl_status] || d.pdl_status}.`,
        ];
        if (O && O.kind === "rejection") L.push(`Opening sweep: pehle ghante ne kal ka ${O.side === "PDH" ? "high" : "low"} (${num(O.level)}) sweep karke wapas andar close kiya (rejection). 2 saal ke data mein aise din ${sr ? sr[0] : "~71%"} baar din range ke andar close hua.`);
        if (O && O.kind === "held") L.push(`Opening break: pehle ghante ne kal ka ${O.side === "PDH" ? "high" : "low"} (${num(O.level)}) break karke beyond hold kiya. 2 saal ke data mein aise din sirf ${sr ? sr[1] : "~26%"} baar wapas andar close hua — continuation zyada common.`);
        if (O && O.kind === "inside") L.push("Pehla ghanta kal ki range ke andar raha — opening sweep nahi hua.");
        html += `<div class="s-card"><div class="s-h">Today's session (15-min)</div><ul class="ticks">${L.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
          <p class="hint">Kal ke key levels: upar ${num(I.next.pdh)} (aaj ka high), neeche ${num(I.next.pdl)} (aaj ka low) — yahan liquidity (stop-losses) hai.</p></div>`;
      }
      let T = tests(key); if (!T.length) T = tests("SENSEX");
      const P = T.filter((t) => t.verdict === "Holds");
      if (P.length) html += `<div class="s-card"><div class="s-h">Data se proven facts</div><ul class="ticks">${P.map((t) =>
        `<li class="t-up"><b>${esc(t.title)}</b> — ${esc(t.summary)}</li>`).join("")}</ul>
        <p class="hint">Sirf wahi dikhaya hai jo long-term data pe test mein pass hua · future guarantee nahi.</p></div>`;
      return html;
    },
  };

  (async function () {
    [X.intra, X.bt] = await Promise.all([get("data/intraday.json"), get("data/backtest.json")]);
    try { const sr = SR(); window.MP_STATS = { first_hour: FH(), rej: sr ? sr[0] : null, brk: sr ? sr[1] : null }; } catch (e) {}
    renderIntraday(); renderBacktest();
    if (window.MP_RENDER) window.MP_RENDER();
    document.addEventListener("click", (e) => { if (e.target.closest("#idxbar button")) setTimeout(() => { renderIntraday(); renderBacktest(); }, 0); });
  })();
})();
