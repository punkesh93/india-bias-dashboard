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
  const vcls = (v) => (v === "Holds" ? "up" : v === "Weak" ? "warn" : "down");
  const stcls = (s) => (s === "untouched" ? "flat" : s === "closed beyond" ? "up" : "warn");
  async function get(p) { try { const r = await fetch(`${p}?v=${Date.now()}`); return r.ok ? await r.json() : null; } catch (e) { return null; } }

  function renderIntraday() {
    const box = $("#intraday"); if (!box) return;
    const all = X.intra && X.intra.instruments;
    let k = keyNow(); if (all && !all[k]) k = "SENSEX";
    const I = all && all[k];
    const head = `<div class="sec-head"><h2>Intraday · ${NAME[k] || k}</h2><p>15-minute view of the latest session: kill zones, Judas swing, previous-day liquidity and MSS + FVG setups. Times in IST.</p></div>`;
    if (!I) { box.innerHTML = head + `<div class="card muted">Intraday data not built yet.</div>`; return; }
    const d = I.today, s = I.stats, S = s.setups;
    const zones = X.intra.zones.map((z) => {
      const m = [];
      if (d.high_zone === z.name) m.push(`<span class="zt up">High ${num(d.high)} · ${d.high_time}</span>`);
      if (d.low_zone === z.name) m.push(`<span class="zt down">Low ${num(d.low)} · ${d.low_time}</span>`);
      return `<div class="kzc ${m.length ? "hit" : ""}"><b>${esc(z.name)}</b><small>${z.from}–${z.to}</small>${m.join("")}</div>`;
    }).join("");
    const sb = X.intra.silver_bullet.map((w) => `${w.from}–${w.to}`).join(" and ");
    const rows = (I.setups_recent || []).slice().reverse().map((x) => `<tr><td>${esc(x.date.slice(5))}</td><td>${x.time}</td>
      <td><span class="tag ${tone(x.side)}">${x.side}</span></td><td>${esc(x.sweep)}</td><td>${num(x.fvg_low)}–${num(x.fvg_high)}</td>
      <td><span class="tag ${x.result === "win" ? "up" : x.result === "loss" ? "down" : "flat"}">${x.result}</span></td><td>${x.result === "no fill" ? "–" : x.r}</td></tr>`).join("");
    const stat = (l, v) => `<div class="stat"><span>${l}</span><b>${v == null ? "–" : v}</b></div>`;
    box.innerHTML = head + `
      <div class="ix-grid">
        <div class="card"><h3>Session recap · ${esc(d.date)}</h3>
          <div class="ohlc"><span>O <b>${num(d.open)}</b></span><span>H <b>${num(d.high)}</b></span><span>L <b>${num(d.low)}</b></span><span>C <b>${num(d.close)}</b></span></div>
          <div class="chips"><span class="tag ${tone(d.direction)}">${d.direction} day</span>
            <span class="tag ${stcls(d.pdh_status)}">PDH ${num(d.pdh)}: ${esc(d.pdh_status)}</span>
            <span class="tag ${stcls(d.pdl_status)}">PDL ${num(d.pdl)}: ${esc(d.pdl_status)}</span>
            ${d.judas ? `<span class="tag ${tone(d.judas)}">Judas swing (${d.judas})</span>` : ""}</div>
          <ul>${d.story.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>
        <div class="card"><h3>Kill zones</h3><div class="kz">${zones}</div>
          <p class="sub" style="margin-top:10px">Silver Bullet windows (adapted to IST): ${sb}. Check the statistics before relying on them.</p></div>
      </div>
      <div class="card" style="margin-top:12px"><div class="row"><b>Last 5 sessions · 15m</b>
        <span class="legend"><span><i style="background:#f59e0b"></i>Previous-day high / low</span><span><i style="background:#a78bfa"></i>Today's open</span></span></div>
        <div id="ixChart" class="chart tall"></div></div>
      <div class="ix-grid" style="margin-top:12px">
        <div class="card"><h3>MSS + FVG setups</h3><p class="sub">Liquidity sweep → market structure shift with displacement → entry on the FVG retrace. Stop beyond the sweep; target the opposite liquidity.</p>
          ${rows ? `<div class="scroll"><table class="ix-t"><tr><th>Date</th><th>Time</th><th>Side</th><th>Sweep</th><th>FVG</th><th>Result</th><th>R</th></tr>${rows}</table></div>` : `<p class="muted">No setups in the recent sessions.</p>`}</div>
        <div class="card"><h3>Last ${s.sessions} sessions · statistics</h3>
          ${stat("Day high formed in open kill zone", s.high_in_open_kz + "%")}${stat("Day low formed in open kill zone", s.low_in_open_kz + "%")}
          ${stat("High or low in open kill zone", s.extreme_in_open_kz + "%")}${stat("Judas-swing days", s.judas_days + "%")}
          ${stat("Previous-day high/low taken", s.pd_level_taken + "%")}${stat("…raided and closed back inside", s.pd_level_raided + "%")}
          ${stat("Setups found / filled", S.found + " / " + S.filled)}${stat("Win rate (filled)", S.win_rate == null ? "–" : S.win_rate + "%")}
          ${stat("Average R (filled)", S.avg_r)}${stat("Silver Bullet window: filled / win rate", S.sb_filled + " / " + (S.sb_win_rate == null ? "–" : S.sb_win_rate + "%"))}</div>
      </div>
      <div class="card" style="margin-top:12px"><h3>Next session levels</h3>
        <div class="ohlc"><span>New PDH <b>${num(I.next.pdh)}</b></span><span>New PDL <b>${num(I.next.pdl)}</b></span><span>Close <b>${num(I.next.prev_close)}</b></span></div>
        <p class="sub">Today's high and low become tomorrow's previous-day liquidity.</p></div>`;
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
    const all = X.bt && X.bt.instruments;
    let k = keyNow(); if (all && !all[k]) k = "SENSEX";
    const T = all && all[k];
    const head = `<div class="sec-head"><h2>Backtest · ${NAME[k] || k}</h2><p>Each ICT masterbook tendency tested on long index history. "Holds" = beats the random base rate by at least 2 standard errors; "Weak" = 1–2; otherwise "Doesn't hold". Past behaviour is no guarantee.</p></div>`;
    if (!T || !T.length) { box.innerHTML = head + `<div class="card muted">Backtest not built yet.</div>`; return; }
    box.innerHTML = head + `<div class="bt-grid">${T.map((t) => `<div class="card bt">
      <div class="bt-h"><b>${esc(t.title)}</b><span class="tag ${vcls(t.verdict)}">${esc(t.verdict)}</span></div>
      <p class="claim">Claim: ${esc(t.claim)}</p><p>${esc(t.summary)}</p>
      ${t.rows && t.rows.length ? `<div class="scroll"><table class="bt-t"><tr>${t.cols.map((c) => `<th>${esc(c)}</th>`).join("")}</tr>${t.rows.map((r) => `<tr>${r.map((v) => `<td>${esc(String(v))}</td>`).join("")}</tr>`).join("")}</table></div>` : ""}
      <p class="sub">${esc(t.sample)}</p></div>`).join("")}</div>`;
  }

  window.MP_EXTRA = {
    simple(key) {
      let html = "";
      const I = X.intra && X.intra.instruments && X.intra.instruments[key];
      if (I) html += `<div class="s-card"><div class="s-h">Aaj ka session (15-min)</div><ul class="ticks">${I.today.story_hi.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
        <p class="hint">Kal ke liye: upar ${num(I.next.pdh)} (aaj ka high), neeche ${num(I.next.pdl)} (aaj ka low) — yahan stop-loss jama honge.</p></div>`;
      const T = X.bt && X.bt.instruments && (X.bt.instruments[key] || X.bt.instruments.SENSEX);
      if (T && T.length) html += `<div class="s-card"><div class="s-h">Data ne kya sach nikala?</div><ul class="ticks">${T.map((t) =>
        `<li class="${t.verdict === "Holds" ? "t-up" : t.verdict === "Weak" ? "t-warn" : "t-down"}"><b>${esc(t.title_hi)}</b> — ${esc(t.hi)}</li>`).join("")}</ul>
        <p class="hint">Purane data pe test · aage bhi aisa hi ho, zaroori nahi.</p></div>`;
      return html;
    },
  };

  (async function () {
    [X.intra, X.bt] = await Promise.all([get("data/intraday.json"), get("data/backtest.json")]);
    renderIntraday(); renderBacktest();
    if (window.MP_RENDER) window.MP_RENDER();
    document.addEventListener("click", (e) => { if (e.target.closest("#idxbar button")) setTimeout(() => { renderIntraday(); renderBacktest(); }, 0); });
  })();
})();
