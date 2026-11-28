(function () {
  "use strict";
  const $ = (s, r = document) => r.querySelector(s);
  const esc = (s = "") => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const num = (v, d = 0) => (v == null || isNaN(v) ? "–" : Number(v).toLocaleString("en-IN", { minimumFractionDigits: d, maximumFractionDigits: d }));
  const pct = (v) => (v == null ? "" : (v > 0 ? "+" : "") + num(v, 2) + "%");
  const KEYS = ["SENSEX", "NIFTY", "BANKNIFTY"];
  const NAME = { SENSEX: "Sensex", NIFTY: "Nifty 50", BANKNIFTY: "Bank Nifty" };
  const KL = { rejection: ["Trap (sweep + rejection)", "rej"], held: ["Breakout held", "held"], both: ["Outside", "none"], inside: ["No sweep", "none"], pending: ["Pending", "none"] };
  let T = null;
  const keyNow = () => { try { const k = localStorage.getItem("mp_key"); return KEYS.includes(k) ? k : "SENSEX"; } catch (e) { return "SENSEX"; } };
  async function get(p) { try { const r = await fetch(`${p}?v=${Date.now()}`); return r.ok ? await r.json() : null; } catch (e) { return null; } }

  function dailyText(d, s) {
    if (!d) return `<p class="muted">No intraday data.</p>`;
    const side = d.side === "PDH" ? "high" : "low", k = KL[d.kind] || KL.inside;
    let p;
    if (d.kind === "pending") p = "The first hour (09:15–10:15) is not complete yet.";
    else if (d.kind === "rejection") p = `The first hour swept the previous-day ${side} (${num(d.level)}) and closed back inside. Historically the day then closed back inside ${s.daily_rej} of the time (vs ${s.daily_brk} when the break held).`;
    else if (d.kind === "held") p = `The first hour broke the previous-day ${side} (${num(d.level)}) and held beyond. Historically the day closed back inside only ${s.daily_brk} of the time.`;
    else if (d.kind === "both") p = "The first hour traded beyond both the previous-day high and low.";
    else p = "The first hour stayed inside the previous day's range — no opening sweep.";
    const lv = `<div class="ohlc">${d.fh_high != null ? `<span>First hour <b>${num(d.fh_low)}–${num(d.fh_high)}</b></span>` : ""}<span>PDH <b>${num(d.pdh)}</b></span><span>PDL <b>${num(d.pdl)}</b></span></div>`;
    const out = d.complete && d.side ? `<p class="sub">Outcome: the session closed ${d.back_inside ? "back inside" : "beyond"} the level.</p>` : "";
    return `<span class="trap-k ${k[1]}">${k[0]}</span>${lv}<p class="body">${p}</p>${out}`;
  }
  function weeklyText(w, s) {
    if (!w) return `<p class="muted">No weekly data.</p>`;
    const side = w.side === "PWH" ? "high" : "low", k = KL[w.kind] || KL.inside;
    let p;
    if (w.kind === "pending") p = "The first day of the week is not complete yet.";
    else if (w.kind === "rejection") p = `The first day swept last week's ${side} (${num(w.level)}) and closed back inside. Since 2008 the week then closed back inside ${s.weekly_rej} of the time (vs ${s.weekly_brk} when the sweep held).`;
    else if (w.kind === "held") p = `The first day broke last week's ${side} (${num(w.level)}) and held beyond. Historically the week closed back inside only ${s.weekly_brk} of the time.`;
    else if (w.kind === "both") p = "The first day traded beyond both last week's high and low.";
    else p = "The first day stayed inside last week's range — no weekly sweep.";
    const now = w.back_inside == null ? "" : `<p class="sub">Now: price is ${w.back_inside ? "back inside" : "beyond"} the level (close ${num(w.close)}).</p>`;
    return `<span class="trap-k ${k[1]}">${k[0]}</span><div class="ohlc"><span>Last week high <b>${num(w.pwh)}</b></span><span>low <b>${num(w.pwl)}</b></span></div><p class="body">${p}</p>${now}`;
  }

  function renderTrap() {
    const box = $("#trapwatch"); if (!box) return;
    if (!T) { box.innerHTML = `<div class="sec-head"><h2>Trap Watch</h2></div><div class="card muted">Data not built yet.</div>`; return; }
    const k = keyNow(), I = T.instruments[k] || T.instruments.SENSEX, s = T.stats;
    const rows = KEYS.filter((x) => T.instruments[x]).map((x) => {
      const d = T.instruments[x].daily || {}, w = T.instruments[x].weekly || {};
      const a = KL[d.kind] || KL.pending, b = KL[w.kind] || KL.pending;
      return `<tr><td>${NAME[x]}</td><td><span class="trap-k ${a[1]}">${a[0]}</span></td><td><span class="trap-k ${b[1]}">${b[0]}</span></td></tr>`;
    }).join("");
    box.innerHTML = `<div class="sec-head"><h2>Trap Watch · ${NAME[k]}</h2><p>A sweep of the previous high/low that closes back inside is a liquidity raid. Proven on Indian data: daily (2 years) and weekly (since 2008). Descriptive statistics, not trade signals.</p></div>
      <div class="ix-grid">
        <div class="card"><h3>Daily trap · ${esc((I.daily || {}).date || "–")}</h3>${dailyText(I.daily, s)}</div>
        <div class="card"><h3>Weekly trap · week of ${esc((I.weekly || {}).week_start || "–")}</h3>${weeklyText(I.weekly, s)}</div>
      </div>
      <div class="card" style="margin-top:12px"><h3>All indices</h3>
        <div class="scroll"><table class="bt-t"><tr><th>Index</th><th>Today (first hour)</th><th>This week (first day)</th></tr>${rows}</table></div>
        <p class="sub">Historical: daily rejection → day closed back inside ${s.daily_rej} (vs ${s.daily_brk} when the break held). Weekly rejection → week closed back inside ${s.weekly_rej} (vs ${s.weekly_brk}). As trades, neither rule beat costs reliably — use them to read the range, not as entries.</p></div>`;
  }

  function renderLevels() {
    const box = $("#levels"); if (!box) return;
    if (!T) { box.innerHTML = ""; return; }
    const k = keyNow(), I = T.instruments[k] || T.instruments.SENSEX, s = T.stats, b = s.base, F = I.focus;
    const row = (x) => `<tr><td>${esc(x.name)}${x.also ? `<br><small class="muted">= ${esc(x.also.join(", "))}</small>` : ""}</td><td><b>${num(x.price)}</b></td><td>${pct(x.dist)}</td><td>${x.p1}%</td><td>${x.p5}%</td><td>${x.p20}%</td></tr>`;
    const focusT = F ? `<div class="scroll"><table class="bt-t"><tr><th>Level</th><th>Price</th><th>Distance</th><th>Next day</th><th>5 days</th><th>20 days</th></tr>
        ${F.above.slice().reverse().map(row).join("")}<tr class="cur-row"><td>Close</td><td><b>${num(F.close, 2)}</b></td><td colspan="4"></td></tr>${F.below.map(row).join("")}</table></div>
        <p class="sub">Nearest untouched liquidity on each side (levels already traded through are removed; duplicates merged). Touch chances come only from volatility — typical daily range ${F.adr_pct}% (${num(F.adr)} pts), measured on this index since 2008. They describe reach, not direction. When price reaches a level, watch for sweep + rejection (trap) vs hold beyond.</p>`
      : `<p class="muted">Not available.</p>`;
    const r = F && F.range1y;
    const near = r ? (r.to_high < -r.to_low ? "above — the 1-year high" : "below — the 1-year low") : "";
    const rangeC = r ? `<div class="zbar"><i class="eq"></i><b class="mk" style="left:${Math.max(0, Math.min(100, r.pos))}%"></b></div>
        <div class="zlab"><span>${num(r.low)}</span><span>${r.pos.toFixed(0)}% of 1-year range</span><span>${num(r.high)}</span></div>
        <ul class="plain">
          <li>1-year high ${num(r.high)} is <b>${pct(r.to_high)}</b> away: touched within 5 sessions ~${r.p_high5}%, within 20 sessions ~${r.p_high20}% (volatility-based).</li>
          <li>1-year low ${num(r.low)} is <b>${pct(r.to_low)}</b> away: within 20 sessions ~${r.p_low20}%.</li>
          <li><b>What it means:</b> the nearest major liquidity is ${near}. Range position alone did not predict direction in our tests — what matters is how price reacts when it reaches that level.</li>
        </ul>
        <p class="sub">Long-term base: Sensex higher 12 months later ${b["12"].up}% of the time since ${b.since}.</p>` : "";
    const st = I.structure || {};
    const SL = { above: ["Above prior high", "up"], below: ["Below prior low", "down"], inside: ["Inside prior range", "flat"] };
    const stRows = ["Daily", "Weekly", "Monthly", "Quarterly", "Yearly"].filter((x) => st[x]).map((x) => {
      const v = st[x], l = SL[v.state] || SL.inside;
      return `<tr><td>${x}</td><td>${num(v.close)}</td><td>${num(v.prev_high)}</td><td>${num(v.prev_low)}</td><td><span class="tag ${l[1]}">${l[0]}</span></td></tr>`;
    }).join("");
    const fvg = I.fvg || { above: [], below: [] };
    const fv = (arr) => arr.map((x) => `<tr><td><span class="tag ${x.type === "bullish" ? "up" : "down"}">${x.type}</span></td><td>${num(x.low)}–${num(x.high)}</td><td>${esc(x.date)}</td><td>${x.touched ? "yes" : "no"}</td><td>${pct(x.dist)}</td></tr>`).join("");
    box.innerHTML = `<div class="sec-head"><h2>Focus & structure · ${NAME[k]}</h2><p>Only the levels that matter now: the nearest untouched liquidity on each side, how far it is, and how often price reaches that far.</p></div>
      <div class="ix-grid">
        <div class="card"><h3>Focus levels 🎯</h3>${focusT}</div>
        <div class="card"><h3>1-year range — what it means</h3>${rangeC}</div>
      </div>
      <div class="ix-grid" style="margin-top:12px">
        <div class="card"><h3>Price structure</h3><div class="scroll"><table class="bt-t"><tr><th>Timeframe</th><th>Close</th><th>Prior high</th><th>Prior low</th><th>State</th></tr>${stRows}</table></div>
          <p class="sub">Description only — structure breaks did not predict the next period's direction in our tests.</p></div>
        <div class="card"><h3>Open daily FVGs</h3>${fvg.above.length || fvg.below.length
          ? `<div class="scroll"><table class="bt-t"><tr><th>Type</th><th>Zone</th><th>Formed</th><th>Touched</th><th>Distance</th></tr>${fv(fvg.above)}${fv(fvg.below)}</table></div>`
          : `<p class="muted">No open FVGs nearby.</p>`}
          <p class="sub">Nifty daily since 2008: ${s.fvg.fill20} of FVGs filled within 20 days, ${s.fvg.fill60} within 60. First touches showed no reliable support/resistance effect.</p></div>
      </div>`;
  }

  function labelContext() {
    document.querySelectorAll("section[id]").forEach((sec) => {
      if (sec.hidden || !/global|fii|oi|part|retail/i.test(sec.id) || sec.querySelector(".ctx-note")) return;
      const n = document.createElement("div");
      n.className = "ctx-note";
      n.textContent = "Context only — tested 2012–2026: FII, retail and COT positioning did not predict index direction on their own.";
      const h = sec.querySelector(".sec-head");
      if (h) h.after(n); else sec.prepend(n);
    });
  }

  function cleanPro() {
    document.querySelectorAll("#view-pro section").forEach((sec) => {
      const h = ((sec.querySelector("h2") || {}).textContent || "").toLowerCase();
      if (/today.?s story|how to read|bias matrix|ict map/.test(h) || /^(story|bias|guide|ict)/i.test(sec.id || "")) sec.hidden = true;
    });
    const ps = document.querySelector(".psub");
    if (!ps) return;
    ps.querySelectorAll("a").forEach((a) => { const t = document.querySelector(a.getAttribute("href")); if (!t || t.hidden) a.remove(); });
    ["#intraday", "#levels", "#trapwatch"].forEach((h) => { const a = ps.querySelector(`a[href="${h}"]`); if (a) ps.prepend(a); });
    const lv = ps.querySelector('a[href="#levels"]'); if (lv) lv.textContent = "Focus";
  }

  (async function () {
    T = await get("data/traps.json");
    cleanPro(); renderTrap(); renderLevels(); labelContext();
    [300, 1000, 2500, 6000].forEach((t) => setTimeout(() => { cleanPro(); labelContext(); }, t));
    document.addEventListener("click", (e) => { if (e.target.closest("#idxbar button")) setTimeout(() => { renderTrap(); renderLevels(); }, 0); });
  })();
})();
