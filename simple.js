(function () {
  "use strict";
  const CFG = Object.assign({ brand: "Market Pulse", defaultView: "simple" }, window.APP_CONFIG || {});
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const esc = (s = "") => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const num = (v, d = 0) => (v == null || isNaN(v) ? "–" : Number(v).toLocaleString("en-IN", { minimumFractionDigits: d, maximumFractionDigits: d }));
  const lakh = (v) => { const a = Math.abs(v); return a >= 1e5 ? (a / 1e5).toLocaleString("en-IN", { maximumFractionDigits: 2 }) + " lakh" : num(a); };
  const sg = (v) => (v >= 0 ? "+" : "−");
  const pct = (v) => (v == null ? "" : (v > 0 ? "+" : "") + num(v, 2) + "%");
  const KEYS = ["SENSEX", "NIFTY", "BANKNIFTY"];
  const NAME = { SENSEX: "Sensex", NIFTY: "Nifty 50", BANKNIFTY: "Bank Nifty" };
  const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const STR = { above: ["Above prior high", "up"], below: ["Below prior low", "down"], inside: ["Inside prior range", "flat"] };
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} },
  };
  const D = {};
  let key = KEYS.includes(store.get("mp_key")) ? store.get("mp_key") : "SENSEX";
  let mode = ["simple", "pro"].includes(store.get("mp_mode")) ? store.get("mp_mode") : (CFG.defaultView === "pro" ? "pro" : "simple");
  let learn = false;
  let deferredInstall = null;
  async function get(p) { try { const r = await fetch(`${p}?v=${Date.now()}`); return r.ok ? await r.json() : null; } catch (e) { return null; } }
  const setH = () => document.documentElement.style.setProperty("--abh", $("#appbar").offsetHeight + "px");
  const S = () => (D.traps && D.traps.stats) || { first_hour: "78%", daily_rej: "71%", daily_brk: "26%", weekly_rej: "62%", weekly_brk: "33%",
    base: { since: 1997, 3: { up: 60, avg: 3.2 }, 6: { up: 67, avg: 6.8 }, 12: { up: 71, avg: 14.3 } }, fvg: { fill20: "43%", fill60: "49%" } };
  const TI = () => (D.traps && D.traps.instruments && D.traps.instruments[key]) || null;

  /* ---------- shell ---------- */
  function apply(scrollTop = true) {
    document.body.classList.toggle("mode-pro", mode === "pro");
    document.body.classList.toggle("learn-open", learn);
    $("#view-simple").classList.toggle("on", !learn && mode === "simple");
    $("#view-pro").classList.toggle("on", !learn && mode === "pro");
    $("#view-learn").classList.toggle("on", learn);
    $$(".mode button").forEach((b) => b.classList.toggle("on", b.dataset.mode === mode));
    $("#learnBtn").classList.toggle("on", learn);
    $("#foot").textContent = mode === "pro"
      ? "For education only · No buy/sell advice or forecasts · Data: NSE, BSE via Yahoo Finance, CFTC"
      : "Sirf education ke liye · Koi buy/sell advice ya prediction nahi · Data: NSE, BSE (Yahoo Finance), CFTC";
    renderLearn(); renderFresh();
    requestAnimationFrame(setH);
    if (scrollTop) window.scrollTo({ top: 0 });
    if (mode === "pro" && !learn) setTimeout(() => window.dispatchEvent(new Event("resize")), 80);
  }
  function setMode(m) { mode = m; learn = false; store.set("mp_mode", m); apply(); }
  function renderIdx() {
    const bar = $("#idxbar");
    bar.innerHTML = KEYS.map((k) => `<button class="idx ${k === key ? "on" : ""}" data-k="${k}">${NAME[k]}</button>`).join("");
    bar.onclick = (e) => { const b = e.target.closest("button[data-k]"); if (b) setKey(b.dataset.k); };
  }
  function syncPro() {
    const a = document.querySelector(`#instTabs button[data-k="${key}"]`);
    if (a && !a.classList.contains("on")) a.click();
    return !!a;
  }
  function setKey(k) { key = k; store.set("mp_key", k); renderIdx(); renderSimple(); syncPro(); }
  function renderFresh() {
    const g = (D.traps && D.traps.generated) || "";
    const box = $("#fresh"), el = $("#freshTxt");
    if (!g) { el.textContent = "–"; return; }
    const d = g.slice(0, 10), t = g.slice(11, 16);
    const today = new Date(Date.now() + 330 * 60000).toISOString().slice(0, 10);
    const days = Math.round((Date.parse(today) - Date.parse(d)) / 864e5);
    el.textContent = `${+d.slice(8, 10)} ${MON[+d.slice(5, 7) - 1]} · ${t}`;
    box.title = `Data updated ${g}`;
    box.classList.toggle("stale", days > 3);
  }
  function watchPsub() {
    if (!("IntersectionObserver" in window)) return;
    const links = $$(".psub a");
    const io = new IntersectionObserver((es) => es.forEach((e) => {
      if (e.isIntersecting) links.forEach((a) => a.classList.toggle("on", a.getAttribute("href") === "#" + e.target.id));
    }), { rootMargin: "-30% 0px -60% 0px" });
    links.forEach((a) => { const s = document.querySelector(a.getAttribute("href")); if (s) io.observe(s); });
  }

  /* ---------- Simple mode ---------- */
  function priceNow(T) {
    const rows = (D.prices && D.prices.series && D.prices.series[key] && D.prices.series[key].rows) || [];
    const l = rows[rows.length - 1], p = rows[rows.length - 2];
    return l ? { close: l.c, chg: p ? (l.c / p.c - 1) * 100 : null, asof: l.t } : { close: T.close, chg: null, asof: T.asof };
  }
  function hero(px) {
    return `<div class="s-card hero2 flat"><div class="s-h"><span class="pulse flat"></span>${esc(NAME[key])} · Market map</div>
      <div class="price-row"><span class="px">${num(px.close, 2)}</span>
        ${px.chg != null ? `<span class="chg ${px.chg >= 0 ? "up" : "down"}">${pct(px.chg)}</span>` : ""}
        <span class="asof">${esc(px.asof)} close</span></div>
      <p class="lead">Yeh app direction predict nahi karta. 90+ tests ke baad sirf wahi dikhata hai jo Indian data mein proven hai — liquidity kahan hai, traps kab bante hain, aur price range mein kahan hai.</p></div>`;
  }
  function trapDailyHi(d) {
    const s = S();
    if (!d) return "Intraday data abhi available nahi.";
    const side = d.side === "PDH" ? "high" : "low";
    const out = d.complete && d.side ? (d.back_inside ? " Aaj ka result: din range ke andar close hua ✓" : " Aaj ka result: din beyond close hua ✗") : "";
    if (d.kind === "pending") return `Aaj ka pehla ghanta (9:15–10:15) abhi complete nahi hua. Kal ka high ${num(d.pdh)} · low ${num(d.pdl)}.`;
    if (d.kind === "rejection") return `<b>Trap bana 🪤</b> — pehle ghante ne kal ka ${side} (${num(d.level)}) sweep karke wapas andar close kiya. Data: aise din <b>${s.daily_rej}</b> baar din range ke andar close hua (breakout hold hone par sirf ${s.daily_brk}).${out}`;
    if (d.kind === "held") return `<b>Breakout hold 🚀</b> — pehle ghante ne kal ka ${side} (${num(d.level)}) break karke beyond hold kiya. Trap nahi. Data: aise din sirf ${s.daily_brk} baar wapas andar close hua.${out}`;
    if (d.kind === "both") return "Pehle ghante ne kal ka high aur low dono tode — outside opening.";
    return `Pehla ghanta kal ki range (${num(d.pdl)} – ${num(d.pdh)}) ke andar raha — aaj koi opening trap nahi.`;
  }
  function trapWeeklyHi(w) {
    const s = S();
    if (!w) return "Weekly data abhi available nahi.";
    const side = w.side === "PWH" ? "high" : "low";
    const now = w.back_inside == null ? "" : ` Abhi price ${w.back_inside ? "range ke andar" : "range ke bahar"} hai.`;
    if (w.kind === "pending") return `Week ka pehla din abhi complete nahi hua. Last week: high ${num(w.pwh)} · low ${num(w.pwl)}.`;
    if (w.kind === "rejection") return `<b>Weekly trap active 🪤</b> — week ke pehle din ne last week ka ${side} (${num(w.level)}) sweep karke wapas andar close kiya. Data (since 2008): aise hafton mein <b>${s.weekly_rej}</b> baar week range ke andar close hua (hold hone par ${s.weekly_brk}).${now}`;
    if (w.kind === "held") return `<b>Weekly breakout hold 🚀</b> — last week ka ${side} (${num(w.level)}) toot ke hold hua. Trap nahi. Data: aise hafton mein sirf ${s.weekly_brk} baar wapas andar close.${now}`;
    if (w.kind === "both") return "Week ke pehle din ne last week ka high aur low dono tode.";
    return `Week ka pehla din last week ki range (${num(w.pwl)} – ${num(w.pwh)}) ke andar raha — is week koi trap nahi.`;
  }
  function trapCard(T) {
    return `<div class="s-card"><div class="s-h">Trap watch 🪤 (proven)</div>
      <p class="body"><b>Aaj (daily):</b> ${trapDailyHi(T.daily)}</p>
      <p class="body"><b>Is week:</b> ${trapWeeklyHi(T.weekly)}</p>
      <p class="hint">Trap = purane high/low ka sweep jo wapas andar close ho. Big players stop-losses lete hain, phir price range mein laut aata hai.</p></div>`;
  }
  function openingCard(T) {
    const s = S(), d = T.daily;
    const fh = d && d.fh_high != null ? `<p class="body">Aaj ka first hour: high <b>${num(d.fh_high)}</b> · low <b>${num(d.fh_low)}</b></p>` : "";
    return `<div class="s-card"><div class="s-h">Opening range (9:15–10:15)</div>
      <p class="body">Data (2 saal): <b>${s.first_hour}</b> din, din ka high ya low pehle ghante mein ban chuka hota hai.</p>${fh}
      <p class="hint">Isliye pehle ghante ka high/low mark karo — din ka ek extreme aksar wahi hota hai.</p></div>`;
  }
  function levelsCard(T) {
    const F = T.focus;
    if (!F) return "";
    const row = (x) => `<div class="lvl-row"><span class="nm">${esc(x.name)}${x.also ? ` <small>= ${esc(x.also.join(", "))}</small>` : ""}</span>
      <span><b>${num(x.price)}</b><small>${pct(x.dist)}</small></span></div>
      <div class="lvl-p"><span>Kal touch ~<b>${x.p1}%</b></span><span>5 din ~<b>${x.p5}%</b></span><span>20 din ~<b>${x.p20}%</b></span></div>`;
    const cur = `<div class="lvl-row cur"><span class="nm">Abhi (close)</span><b>${num(F.close, 2)}</b></div>`;
    return `<div class="s-card"><div class="s-h">Focus levels 🎯 (sirf yeh dekho)</div>${F.above.slice().reverse().map(row).join("")}${cur}${F.below.map(row).join("")}
      <p class="hint">Upar aur neeche ke sabse paas wale untouched liquidity levels — jo level already toot chuka, woh hata diya. Touch chance sirf volatility se (typical daily range ${F.adr_pct}%, data since 2008) — direction ka prediction nahi. Jo level touch ho, wahan dekho: sweep + rejection = trap 🪤, beyond hold = continuation zyada common.</p></div>`;
  }
  function structureCard(T) {
    const s = T.structure || {};
    const rows = ["Daily", "Weekly", "Monthly", "Quarterly", "Yearly"].filter((k) => s[k]).map((k) => {
      const [w, c] = STR[s[k].state] || STR.inside;
      return `<div class="tl-row"><div class="tl-name">${k}</div><div></div><span class="chipx ${c}">${w}</span></div>`;
    }).join("");
    return `<div class="s-card"><div class="s-h">Price structure</div>${rows}
      <p class="hint">Current period ka close vs previous period ka high/low. Sirf description — next move ka prediction nahi (tested).</p></div>`;
  }
  function bigCard(T) {
    const F = T.focus, s = S(), b = s.base;
    if (!F || !F.range1y) return "";
    const r = F.range1y, pos = Math.max(0, Math.min(100, r.pos));
    const where = pos >= 75 ? "range ke top ke paas" : pos >= 50 ? "upper half mein" : pos >= 25 ? "lower half mein" : "range ke bottom ke paas";
    const near = r.to_high < -r.to_low ? "upar (1-year high)" : "neeche (1-year low)";
    return `<div class="s-card"><div class="s-h">1-year range: iska matlab kya hai?</div>
      <div class="zbar"><i class="eq"></i><b class="mk" style="left:${pos}%"></b></div>
      <div class="zlab"><span>${num(r.low)}</span><span>${pos.toFixed(0)}%</span><span>${num(r.high)}</span></div>
      <ul class="ticks">
        <li><b>Upar:</b> 1-year high ${num(r.high)} sirf <b>${pct(r.to_high)}</b> door — 5 din mein touch ~${r.p_high5}%, 20 din mein ~${r.p_high20}%.</li>
        <li><b>Neeche:</b> 1-year low ${num(r.low)} <b>${pct(r.to_low)}</b> door — 20 din mein touch ~${r.p_low20}%.</li>
        <li><b>Aapke liye:</b> price ${where} hai, isliye paas wali badi liquidity ${near} hai. Range mein position khud buy/sell signal nahi (tested) — asli kaam us level pe price ka reaction dekhna hai.</li>
      </ul>
      <p class="hint">Long-term base: since ${b.since}, Sensex 12 months baad ${b["12"].up}% time upar.</p></div>`;
  }
  function posCard() {
    const rows = (D.poi && D.poi.rows) || []; if (rows.length < 21) return "";
    const net = (r, g) => (r[g] ? r[g].fil - r[g].fis : null);
    const a = rows[rows.length - 1], b = rows[rows.length - 21];
    const f = net(a, "FII"), f0 = net(b, "FII"), c = net(a, "Client"), c0 = net(b, "Client");
    if (f == null || c == null || f0 == null || c0 == null) return "";
    const df = f - f0, dc = c - c0;
    return `<div class="s-card"><div class="s-h">Positioning (context)</div>
      <div class="who">
        <div class="who-i"><div class="who-n">FII · net</div><div class="who-v ${f >= 0 ? "up" : "down"}">${sg(f)}${lakh(f)}</div><div class="who-d ${df >= 0 ? "up" : "down"}">20 days: ${sg(df)}${lakh(df)}</div></div>
        <div class="who-i"><div class="who-n">Retail · net</div><div class="who-v ${c >= 0 ? "up" : "down"}">${sg(c)}${lakh(c)}</div><div class="who-d ${dc >= 0 ? "up" : "down"}">20 days: ${sg(dc)}${lakh(dc)}</div></div>
      </div>
      <p class="hint">Index futures contracts · NSE ${esc(a.d)}. Context only — 2012–2026 ke test mein FII/retail positioning se next 5–20 din ka direction predict nahi hua.</p></div>`;
  }
  function notesCard() {
    const out = [];
    const wd = new Date(Date.now() + 330 * 60000).getUTCDay();
    const exp = { SENSEX: [4, "Sensex weekly expiry (BSE)"], NIFTY: [2, "Nifty weekly expiry (NSE)"] }[key];
    if (exp) {
      if (wd === exp[0]) out.push(`Aaj ${exp[1]} hai — option premium (time value) tezi se decay hota hai.`);
      else if ((wd + 1) % 7 === exp[0]) out.push(`Kal ${exp[1]} hai. (Holiday ho toh expiry ek din pehle.)`);
    }
    const vr = D.prices && D.prices.series && D.prices.series.INDIAVIX && D.prices.series.INDIAVIX.rows;
    if (vr && vr.length) out.push(`India VIX ${num(vr[vr.length - 1].c, 1)} — market ka fear meter.`);
    if (!out.length) return "";
    return `<div class="s-card"><div class="s-h">Notes</div><ul class="ticks">${out.map((t) => `<li>${t}</li>`).join("")}</ul></div>`;
  }
  function provenCard() {
    const all = (D.bt && D.bt.instruments) || {};
    const T = (all[key] && all[key].length ? all[key] : all.SENSEX) || [];
    const P = T.filter((t) => t.verdict === "Holds" || t.verdict === "Holds (strong)");
    if (!P.length) return "";
    return `<div class="s-card"><div class="s-h">Data se proven facts</div><ul class="ticks">${P.map((t) =>
      `<li class="t-up"><b>${esc(t.title)}</b> — ${esc(t.summary)}</li>`).join("")}</ul>
      <p class="hint">Sirf wahi dikhaya hai jo long-term Indian data pe test mein pass hua · future guarantee nahi.</p></div>`;
  }
  const DISC_HI = `<p class="disc">Yeh app sirf education ke liye hai — koi buy/sell advice, recommendation ya prediction nahi. Trading mein loss ho sakta hai; zarurat ho toh SEBI-registered advisor se baat karein.</p>`;
  const DISC_EN = `<p class="disc">For education only — not investment advice, a recommendation or a forecast. Trading involves risk of loss; consult a SEBI-registered adviser where appropriate.</p>`;

  function renderSimple() {
    const T = TI(), el = $("#simple");
    if (!T) { el.innerHTML = `<div class="s-card">Data abhi load nahi hua. Internet check karke refresh karein.</div>`; return; }
    el.innerHTML = hero(priceNow(T))
      + `<div class="s-grid">${trapCard(T)}${openingCard(T)}</div>`
      + levelsCard(T)
      + `<div class="s-grid">${structureCard(T)}${bigCard(T)}</div>`
      + `<div class="s-grid">${posCard()}${notesCard()}</div>`
      + provenCard()
      + `<button class="cta" id="goPro">Full map dekho → Pro mode</button>` + DISC_HI;
    $("#goPro").onclick = () => setMode("pro");
  }

  /* ---------- Learn ---------- */
  function learnData() {
    const s = S();
    return {
      simple: {
        kicker: "Learn", title: "Market map — simple language mein",
        lead: "Yeh app 90+ tests ke baad sirf wahi dikhata hai jo Indian data mein proven hai. Koi buy/sell ya direction prediction nahi — sirf liquidity, traps aur range.",
        stepsH: "Kaise use karein — 4 steps",
        steps: [`<b>Liquidity levels</b> dekho — kal, is week aur last week ke high/low pe stop-losses rest karte hain.`,
                `<b>9:15–10:15</b> pe dhyan do — ${s.first_hour} din, din ka high ya low pehle ghante mein ban jaata hai.`,
                `<b>Daily trap</b>: pehla ghanta kal ka high/low sweep karke wapas andar close kare → ${s.daily_rej} din range ke andar close (hold hone par sirf ${s.daily_brk}).`,
                `<b>Weekly trap</b>: week ka pehla din last week ka high/low sweep karke wapas close kare → ${s.weekly_rej} hafte range ke andar close (hold par ${s.weekly_brk}).`],
        G: [["Liquidity", "Purane highs ke upar aur lows ke neeche traders ke stop-losses hote hain. Big players ko bade orders ke liye yahi liquidity chahiye."],
            ["Sweep / Stop hunt", "Price kisi purane high/low ke thoda beyond jaakar stop-losses trigger karta hai."],
            ["Rejection close", "Sweep ke baad price wapas purani range ke andar close ho jaye — yahi trap hai."],
            ["Breakout hold", "Sweep ke baad price beyond hi close kare — yeh trap nahi, breakout hai."],
            ["Premium / Discount / Equilibrium", "Range ka 50% = Equilibrium. Upar Premium, neeche Discount. App mein yeh sirf position batata hai."],
            ["FVG", `Fast move mein teen candles ke beech gap. Indian data: sirf ${s.fvg.fill20} FVG 20 din mein fill hue — har FVG fill nahi hota.`],
            ["Opening range", `Pehla ghanta (9:15–10:15). ${s.first_hour} din, din ka high ya low yahin banta hai.`],
            ["FII / Retail", "Positioning context ke liye dikhaya hai. 2012–2026 ke test mein isse direction predict nahi hua."],
            ["India VIX", "Market ka fear meter. High VIX = bade moves expected aur options mehnge."],
            ["Buy/Sell signal kyun nahi?", "90+ tests mein koi mechanical direction signal costs ke baad reliably profitable nahi nikla. Isliye app facts dikhata hai — decision aapka."]],
        instH: "App install karein",
        inst: "Android (Chrome / Brave): ⋮ menu → <b>Install app</b> ya <b>Add to Home screen</b>.<br>iPhone (Safari): Share → <b>Add to Home Screen</b>.",
        btn: "Install karein", disc: DISC_HI,
      },
      pro: {
        kicker: "Learn", title: "A market map built only on what Indian data supports",
        lead: "More than 90 hypotheses were tested on Sensex, Nifty and Bank Nifty. Directional rules did not survive; range and liquidity-raid behaviour did. This app shows only the latter.",
        stepsH: "How to use it - 4 steps",
        steps: [`<b>Levels</b>: previous day/week/month highs and lows are where stops rest.`,
                `<b>Opening range</b>: the day's high or low formed in the first hour on ${s.first_hour} of sessions.`,
                `<b>Daily trap</b>: a first-hour sweep of PDH/PDL that closes back inside → day closed back inside ${s.daily_rej} (vs ${s.daily_brk} when the break held).`,
                `<b>Weekly trap</b>: a first-day sweep of last week's high/low that closes back inside → week closed back inside ${s.weekly_rej} (vs ${s.weekly_brk}).`],
        G: [["External range liquidity", "Resting stops above old highs and below old lows. Price repeatedly trades to them."],
            ["Liquidity raid (trap)", "A sweep beyond an old high/low that closes back inside. Proven on daily and weekly Indian data."],
            ["Breakout hold", "A sweep that closes beyond the level. Continuation was more common than reversal."],
            ["Equilibrium, premium & discount", "The 50% level of a dealing range. Shown as position only; long-horizon tests were consistent but not significant."],
            ["Fair value gap", `Three-candle imbalance. Nifty daily since 2008: ${s.fvg.fill20} filled within 20 days, ${s.fvg.fill60} within 60.`],
            ["Kill zone / opening range", `The first hour set the day's high or low on ${s.first_hour} of sessions.`],
            ["Participant OI & COT", "Shown as context. Tested 2012–2026 (FII/retail) and since 2006 (COT): no standalone directional edge."],
            ["What was rejected", "Weekday profiles, seasonality, expiry volatility, fib levels and projections, SMT stock screens, structure momentum and mechanical setups."],
            ["India VIX", "Expected 30-day volatility from Nifty options."],
            ["Expiry", "Sensex weekly options expire on Thursday (BSE), Nifty 50 on Tuesday (NSE). Holidays move expiry to the previous trading day."]],
        instH: "Install as an app",
        inst: "Android (Chrome / Brave): ⋮ menu → <b>Install app</b> or <b>Add to Home screen</b>.<br>iPhone (Safari): Share → <b>Add to Home Screen</b>.",
        btn: "Install now", disc: DISC_EN,
      },
    };
  }
  function renderLearn() {
    const L = learnData()[mode];
    $("#learn").innerHTML = `
      <div class="s-card hero2"><div class="s-h">${L.kicker}</div><div class="big-verdict flat">${L.title}</div><p class="lead">${L.lead}</p></div>
      <div class="s-card"><div class="s-h">${L.stepsH}</div><ol class="steps">${L.steps.map((x) => `<li>${x}</li>`).join("")}</ol></div>
      <div class="gl">${L.G.map(([h, p]) => `<div class="s-card"><h4>${h}</h4><p>${p}</p></div>`).join("")}</div>
      <div class="s-card" style="margin-top:12px"><div class="s-h">${L.instH}</div><p class="body">${L.inst}</p>
        <button class="cta installBtn" ${deferredInstall ? "" : "hidden"} style="margin-top:12px">${L.btn}</button></div>
      ${L.disc}`;
  }

  window.addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); deferredInstall = e; $$(".installBtn").forEach((b) => (b.hidden = false)); });
  document.addEventListener("click", async (e) => {
    const b = e.target.closest(".installBtn"); if (!b || !deferredInstall) return;
    deferredInstall.prompt(); try { await deferredInstall.userChoice; } catch (err) {}
    deferredInstall = null; $$(".installBtn").forEach((x) => (x.hidden = true));
  });

  (async function init() {
    $("#brandName").textContent = CFG.brand;
    document.body.classList.add("no-levels");
    window.addEventListener("resize", setH);
    $$(".mode button").forEach((b) => b.addEventListener("click", () => setMode(b.dataset.mode)));
    $("#learnBtn").addEventListener("click", () => { learn = !learn; apply(); });
    renderIdx(); apply(false); watchPsub();
    [D.traps, D.prices, D.poi, D.bt] = await Promise.all(
      ["data/traps.json", "data/prices.json", "data/participant_oi.json", "data/backtest.json"].map(get));
    renderFresh(); renderSimple(); renderLearn(); setH();
    let tries = 0; const t = setInterval(() => { tries++; if (syncPro() || tries > 25) clearInterval(t); }, 300);
    if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
  })();
})();
