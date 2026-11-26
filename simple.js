(function () {
  "use strict";
  const CFG = Object.assign({ brand: "Market Pulse", showTradeLevels: true, defaultView: "simple" }, window.APP_CONFIG || {});
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const esc = (s = "") => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const num = (v, d = 0) => (v == null || isNaN(v) ? "–" : Number(v).toLocaleString("en-IN", { minimumFractionDigits: d, maximumFractionDigits: d }));
  const lakh = (v) => { const a = Math.abs(v); return a >= 1e5 ? (a / 1e5).toLocaleString("en-IN", { maximumFractionDigits: 2 }) + " lakh" : num(a); };
  const sg = (v) => (v >= 0 ? "+" : "−");
  const pct = (v) => (v == null ? "" : (v > 0 ? "+" : "") + num(v, 2) + "%");
  const KEYS = ["SENSEX", "NIFTY", "BANKNIFTY"];
  const NAME = { SENSEX: "Sensex", NIFTY: "Nifty 50", BANKNIFTY: "Bank Nifty", FINNIFTY: "FinNifty", USDINR: "USD/INR", DXY: "Dollar Index" };
  const TFS = [["Yearly", "Yearly"], ["Quarterly", "Quarterly"], ["Monthly", "Monthly"], ["Weekly", "Weekly"], ["Daily", "Daily"]];
  const LBL = { Bullish: ["Bullish", "up"], Bearish: ["Bearish", "down"], Neutral: ["Neutral", "flat"] };
  const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} },
  };
  const D = {};
  let key = KEYS.includes(store.get("mp_key")) ? store.get("mp_key") : "SENSEX";
  let mode = ["simple", "pro"].includes(store.get("mp_mode")) ? store.get("mp_mode") : (CFG.defaultView === "pro" ? "pro" : "simple");
  let learn = false;
  let deferredInstall = null;

  async function get(p) {
    try { const r = await fetch(`${p}?v=${Date.now()}`); return r.ok ? await r.json() : null; } catch (e) { return null; }
  }
  const setH = () => document.documentElement.style.setProperty("--abh", $("#appbar").offsetHeight + "px");

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
      ? "For education and analysis only · Not trading advice · Data: CFTC, NSE, Yahoo Finance"
      : "Sirf education aur analysis ke liye · Trading advice nahi · Data: CFTC, NSE, Yahoo Finance";
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
    const b = document.querySelector(`#ictTabs button[data-k="${key}"]`);
    if (a && !a.classList.contains("on")) a.click();
    if (b && !b.classList.contains("on")) b.click();
    return !!(a && b);
  }
  function setKey(k) { key = k; store.set("mp_key", k); renderIdx(); renderSimple(); syncPro(); }
  function renderFresh() {
    const g = (D.ict && D.ict.generated) || (D.bias && D.bias.generated);
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

  /* ---------- Simple mode (easy Hinglish, English market terms) ---------- */
  function hero(b, s, px) {
    const v = s.verdict || "";
    const tone = /Bull/.test(v) ? "up" : /Bear/.test(v) ? "down" : "flat";
    const title = tone === "up" ? "Bullish bias" : tone === "down" ? "Bearish bias" : "Sideways — direction clear nahi";
    const lab = (t) => (b.timeframes[t] && b.timeframes[t].label) || "Neutral";
    const word = (arr) => { const u = arr.filter((x) => x === "Bullish").length, d = arr.filter((x) => x === "Bearish").length; return u > d ? "up" : d > u ? "down" : "flat"; };
    const big = word([lab("Yearly"), lab("Quarterly"), lab("Monthly")]), sh = word([lab("Weekly"), lab("Daily")]);
    const n = NAME[key];
    const S = {
      "up-up": `${n} ka big trend Bullish hai aur short-term bhi Bullish — dono same direction mein.`,
      "up-flat": `${n} ka big trend Bullish hai, lekin is week direction clear nahi. Jaldi entry ki zarurat nahi.`,
      "up-down": `${n} ka big trend Bullish hai, par short-term weak hai — yeh pullback ho sakta hai.`,
      "down-down": `${n} ka big trend Bearish hai aur short-term bhi weak hai.`,
      "down-flat": `${n} ka big trend Bearish hai, is week market sideways hai.`,
      "down-up": `${n} ka big trend Bearish hai, par short-term mein bounce aa raha hai — careful rahein.`,
      "flat-up": `${n} bade timeframe pe range mein hai, short-term thoda Bullish hai.`,
      "flat-down": `${n} bade timeframe pe range mein hai, short-term thoda Bearish hai.`,
      "flat-flat": `${n} abhi range mein hai — big trend aur short-term dono clear nahi.`,
    };
    return `<div class="s-card hero2 ${tone}">
      <div class="s-h"><span class="pulse ${tone}"></span>${esc(n)} · Today's view</div>
      <div class="big-verdict ${tone}">${title}</div>
      <div class="price-row"><span class="px">${num(px.close, 2)}</span>
        ${px.chg != null ? `<span class="chg ${px.chg >= 0 ? "up" : "down"}">${pct(px.chg)}</span>` : ""}
        <span class="asof">${esc(px.asof)} close</span></div>
      <p class="lead">${S[big + "-" + sh]}</p></div>`;
  }
  function trend(b) {
    const rows = TFS.map(([t, hi]) => {
      const x = b.timeframes[t]; if (!x) return "";
      const [w, c] = LBL[x.label] || LBL.Neutral;
      const conf = x.n ? Math.round((Math.abs(x.score) / x.n) * 100) : 0;
      return `<div class="tl-row"><div class="tl-name">${hi}</div><div class="meter ${c}"><i style="width:${Math.max(conf, 6)}%"></i></div><span class="chipx ${c}">${w}</span></div>`;
    }).join("");
    return `<div class="s-card"><div class="s-h">Trend meter</div>${rows}<p class="hint">Har timeframe pe multiple signals vote karte hain. Lambi bar = zyada signals same side.</p></div>`;
  }
  function where(I) {
    const r = I && I.ranges && I.ranges[1]; if (!r) return "";
    const pos = Math.max(0, Math.min(100, r.pos));
    let t;
    if (pos >= 75) t = "Price last 40 days ki range ke top ke paas hai — yaani <b>Premium zone</b>. Yahan fresh buy risky hai; pullback ka wait better hai.";
    else if (pos >= 50) t = "Price range ke <b>upper half</b> mein hai — thoda Premium. Big players Discount mein buy aur Premium mein sell karte hain.";
    else if (pos >= 25) t = "Price range ke <b>lower half</b> mein hai — thoda Discount.";
    else t = "Price range ke bottom ke paas hai — yaani <b>Discount zone</b>. Yahan se sell/short karna risky hai.";
    return `<div class="s-card"><div class="s-h">Price kahan hai? (Premium / Discount)</div>
      <div class="zbar"><i class="eq"></i><b class="mk" style="left:${pos}%"></b></div>
      <div class="zlab"><span>Discount</span><span>Equilibrium: ${num(r.eq)}</span><span>Premium</span></div>
      <p class="body">${t}</p><p class="hint">Range ${num(r.low)} – ${num(r.high)} (last 40 trading days). Beech ka level = Equilibrium.</p></div>`;
  }
  function who() {
    const rows = (D.poi && D.poi.rows) || []; if (rows.length < 21) return "";
    const net = (r, g) => (r[g] ? r[g].fil - r[g].fis : null);
    const last = rows[rows.length - 1], prev = rows[rows.length - 21];
    const f = net(last, "FII"), f0 = net(prev, "FII"), c = net(last, "Client"), c0 = net(prev, "Client");
    if (f == null || c == null || f0 == null || c0 == null) return "";
    const df = f - f0, dc = c - c0;
    let ft = f < 0 ? `FII (foreign institutions) abhi <b>net short</b> hain — ${lakh(f)} contracts ki bearish position.`
                   : `FII (foreign institutions) abhi <b>net long</b> hain — ${lakh(f)} contracts ki bullish position.`;
    ft += " " + (df > 0
      ? (f < 0 ? `Last 20 days mein unhone ${lakh(df)} contracts ke shorts <b>cover</b> kiye — bearish position kam kar rahe hain.` : `Last 20 days mein ${lakh(df)} contracts <b>aur buy</b> kiye.`)
      : (f < 0 ? `Last 20 days mein ${lakh(df)} contracts ke <b>naye shorts</b> add kiye — bearish position badha rahe hain.` : `Last 20 days mein ${lakh(df)} contracts ke longs <b>exit</b> kiye.`));
    const ct = dc < 0 ? `Retail traders ne last 20 days mein ${lakh(dc)} contracts <b>sell</b> kiye (longs kam kiye).`
                      : `Retail traders ne last 20 days mein ${lakh(dc)} contracts aur <b>buy</b> kiye.`;
    const smart = df > 0 ? ["Smart money: Buying", "up"] : ["Smart money: Selling", "down"];
    const combo = df > 0 && dc < 0 ? "Big players buy kar rahe hain aur retail sell — aisi rally usually healthy hoti hai."
                : df < 0 && dc > 0 ? "Big players sell kar rahe hain aur retail buy — yeh warning sign hai."
                : "Dono same side hain — koi khaas divergence nahi.";
    return `<div class="s-card"><div class="s-h">Big players kya kar rahe hain?</div>
      <span class="chipx ${smart[1]}">${smart[0]}</span>
      <div class="who">
        <div class="who-i"><div class="who-n">FII · net</div><div class="who-v ${f >= 0 ? "up" : "down"}">${sg(f)}${lakh(f)}</div><div class="who-d ${df >= 0 ? "up" : "down"}">20 days: ${sg(df)}${lakh(df)}</div></div>
        <div class="who-i"><div class="who-n">Retail · net</div><div class="who-v ${c >= 0 ? "up" : "down"}">${sg(c)}${lakh(c)}</div><div class="who-d ${dc >= 0 ? "up" : "down"}">20 days: ${sg(dc)}${lakh(dc)}</div></div>
      </div>
      <p class="body">${ft}</p><p class="body">${ct}</p><p class="body strong">${combo}</p>
      <p class="hint">Index futures contracts · NSE data ${esc(last.d)}</p></div>`;
  }
  function draw(I) {
    if (!I || !I.draw) return "";
    const d = I.draw, dir = d.direction;
    const tone = dir === "bullish" ? "up" : dir === "bearish" ? "down" : "flat";
    const ST = {
      bullish: ["Neeche ke stop-losses abhi sweep hue (manipulation). Ab upside move aa sakta hai.",
                "Price ne neeche ka FVG (gap) fill kar diya — yahin se aksar next upmove start hota hai.",
                "Upar ke stop-losses le liye gaye (target hit). Ab aksar pullback aata hai — chase karke buy mat karo."],
      bearish: ["Upar ke stop-losses abhi sweep hue (manipulation). Ab downside move aa sakta hai.",
                "Price ne upar ka FVG (gap) fill kar diya — yahin se aksar next downmove start hota hai.",
                "Neeche ke stop-losses le liye gaye (target hit). Ab aksar bounce aata hai — chase karke sell mat karo."],
    };
    const st = d.stage_idx >= 0 && ST[dir] ? ST[dir][d.stage_idx]
      : "Dono side orders build ho rahe hain. Jab ek side ke stop-losses sweep hon aur price wapas range mein aaye, tab direction clear hogi.";
    const title = dir === "bullish" ? "Upside target ki taraf" : dir === "bearish" ? "Downside target ki taraf" : "Abhi dono side open";
    let lv = "";
    if (CFG.showTradeLevels) {
      const box = (lab, x, sub) => (x ? `<div class="lv"><span>${lab}</span><b>${x.low != null ? `${num(x.low)}–${num(x.high)}` : num(x.price)}</b><small>${pct(x.dist)} · ${sub}</small></div>` : "");
      const L = dir === "two-sided"
        ? box("Upside liquidity", d.target, "buy stop-losses yahan") + box("Equilibrium", d.entry, "range ka center") + box("Downside liquidity", d.invalidation, "sell stop-losses yahan")
        : box("Target (liquidity)", d.target, "stop-losses yahan rest kar rahe hain")
          + box("Better entry zone", d.entry, dir === "bullish" ? "Discount area / FVG" : "Premium area / FVG")
          + box("Invalidation (view wrong)", d.invalidation, "iske beyond close = view wrong");
      lv = `<div class="lv3">${L}</div>`;
    }
    return `<div class="s-card"><div class="s-h">Market ka next target (liquidity)</div>
      <div class="big2 ${tone}">${title}</div><p class="body">${st}</p>${lv}
      <details class="why"><summary>Yeh kaise kaam karta hai?</summary>
        <p>Big players ko bade orders fill karne ke liye liquidity chahiye — yaani doosre traders ke stop-losses. Isliye market aksar purane high/low ke beyond liquidity lene jaata hai, phir fast move mein bane FVG (gap) ko fill karne wapas aata hai. Cycle: liquidity → FVG → liquidity.</p>
      </details></div>`;
  }
  function world() {
    const M = D.cot && D.cot.markets; if (!M) return "";
    const v = (k) => { const a = M[k] && M[k].idx && M[k].idx["52"]; return a ? a[a.length - 1] : null; };
    const items = [];
    const add = (k, hi, lo) => { const x = v(k); if (x == null) return; if (x >= 80) items.push(hi); else if (x <= 20) items.push(lo); };
    add("DXY", ["Dollar strong hone ke signals — India ke liye negative (FII outflow ho sakta hai).", "t-down"], ["Dollar weak hone ke signals — India ke liye positive (FII inflow aata hai).", "t-up"]);
    add("UST10Y", ["US bond yields girne ke signals — emerging markets ke liye positive.", "t-up"], ["US yields badhne ke signals — India pe pressure.", "t-down"]);
    add("MSCIEM", ["Emerging markets mein inflow ke signals — India ke liye positive.", "t-up"], ["Emerging markets se outflow ke signals.", "t-down"]);
    add("CRUDE", ["Crude oil upar jaane ke signals — rupee aur inflation pe pressure.", "t-down"], ["Crude girne ke signals — India ke liye positive.", "t-up"]);
    const MAP = { Supportive: ["Supportive", "up"], Mixed: ["Mixed", "flat"], Hostile: ["Negative", "down"] };
    const m = MAP[D.story && D.story.macro && D.story.macro.summary] || MAP.Mixed;
    const li = items.length ? items.map(([t, c]) => `<li class="${c}">${t}</li>`).join("") : `<li>Abhi kisi major global market mein extreme signal nahi hai.</li>`;
    return `<div class="s-card"><div class="s-h">Global mood</div><span class="chipx ${m[1]}">Global mood: ${m[0]}</span>
      <ul class="ticks">${li}</ul><p class="hint">CFTC report · big hedgers ki positioning · weekly update</p></div>`;
  }
  function alerts() {
    const out = [];
    const wd = new Date(Date.now() + 330 * 60000).getUTCDay();
    const exp = { SENSEX: [4, "Sensex weekly expiry (BSE)"], NIFTY: [2, "Nifty weekly expiry (NSE)"] }[key];
    if (exp) {
      if (wd === exp[0]) out.push(["t-warn", `Aaj ${exp[1]} hai — closing tak fast aur volatile moves ho sakte hain. Option premium tezi se decay hota hai.`]);
      else if ((wd + 1) % 7 === exp[0]) out.push(["t-warn", `Kal ${exp[1]} hai. (Holiday ho toh expiry ek din pehle.)`]);
    }
    const vr = D.prices && D.prices.series && D.prices.series.INDIAVIX && D.prices.series.INDIAVIX.rows;
    if (vr && vr.length) {
      const vx = vr[vr.length - 1].c;
      out.push(vx > 20 ? ["t-down", `India VIX ${num(vx, 1)} — fear high hai, options mehnge hain. Position size chhota rakho.`]
              : vx < 13 ? ["", `India VIX ${num(vx, 1)} — market calm hai, options saste hain par moves bhi chhote ho sakte hain.`]
              : ["", `India VIX ${num(vx, 1)} — normal range.`]);
    }
    ((D.ict && D.ict.smt) || []).filter((r) => (r.a === key || r.b === key) && (r.type === "bullish" || r.type === "bearish")).slice(0, 2).forEach((r) => {
      out.push(r.type === "bullish"
        ? ["t-up", r.corr < 0
            ? `SMT signal: ${NAME[r.a]} ki weakness ko ${NAME[r.b]} ne confirm nahi kiya (dono usually opposite chalte hain). Bullish sign ho sakta hai.`
            : `SMT signal: ${NAME[r.a]} aur ${NAME[r.b]} saath nahi chale — sell-side liquidity sirf ek index mein sweep hui. Smart money buying ka sign ho sakta hai.`]
        : ["t-down", r.corr < 0
            ? `SMT warning: ${NAME[r.a]} ki strength ko ${NAME[r.b]} ne confirm nahi kiya (dono usually opposite chalte hain). Bearish warning.`
            : `SMT warning: ${NAME[r.a]} aur ${NAME[r.b]} mein se ek ne new high banaya, doosre ne nahi — bearish warning.`]);
    });
    const rk = D.story && D.story.instruments && D.story.instruments[key] && D.story.instruments[key].risks;
    if (rk && rk.length) out.push(["", `${rk.length} signals is view ke against hain — details Pro mode mein.`]);
    if (!out.length) return "";
    return `<div class="s-card"><div class="s-h">Alerts</div><ul class="ticks">${out.map(([c, t]) => `<li class="${c}">${t}</li>`).join("")}</ul></div>`;
  }
  const DISC_HI = `<p class="disc">Yeh app sirf education aur market analysis ke liye hai — buy/sell advice nahi. Trading mein loss ho sakta hai; zarurat ho toh SEBI-registered advisor se baat karein.</p>`;
  const DISC_EN = `<p class="disc">For education and market analysis only — not investment advice or a recommendation to buy or sell. Trading involves risk of loss; consult a SEBI-registered adviser where appropriate.</p>`;

  function renderSimple() {
    const b = D.bias && D.bias.instruments && D.bias.instruments[key];
    const s = D.story && D.story.instruments && D.story.instruments[key];
    const I = D.ict && D.ict.instruments && D.ict.instruments[key];
    const el = $("#simple");
    if (!b || !s) { el.innerHTML = `<div class="s-card">Data abhi load nahi hua. Internet check karke refresh karein.</div>`; return; }
    const rows = (D.prices && D.prices.series && D.prices.series[key] && D.prices.series[key].rows) || [];
    const last = rows[rows.length - 1], prev = rows[rows.length - 2];
    const px = last ? { close: last.c, chg: prev ? (last.c / prev.c - 1) * 100 : null, asof: last.t } : { close: s.close, chg: null, asof: s.asof };
    el.innerHTML = hero(b, s, px) + `<div class="s-grid">${trend(b)}${where(I)}</div>` + draw(I)
      + `<div class="s-grid">${who()}${world()}</div>` + alerts() + (window.MP_EXTRA ? window.MP_EXTRA.simple(key) : "")
      + `<button class="cta" id="goPro">Full analysis dekho → Pro mode</button>` + DISC_HI;
    $("#goPro").onclick = () => setMode("pro");
  }

  /* ---------- Learn ---------- */
  const LEARN = {
    simple: {
      kicker: "Learn", title: "Smart money concepts, simple language mein",
      lead: "Is app ka goal: big players kya kar rahe hain aur market kis liquidity ki taraf ja raha hai — yeh clearly dikhana.",
      stepsH: "Kaise use karein — 4 steps",
      steps: ["<b>Simple</b> mode mein quick view padho — big trend kya hai, short-term kya hai.",
              "Check karo price <b>Discount</b> mein hai ya <b>Premium</b> mein. Premium mein fresh buy avoid karo, pullback ka wait karo.",
              "Big players (FII) aur retail ko compare karo — dono opposite hon toh smart money ki side socho.",
              "<b>Pro</b> mode mein ICT map, SMT aur levels confirm karo, phir apne chart pe entry dhoondo."],
      G: [["Liquidity (ERL)", "Purane highs ke upar aur lows ke neeche traders ke stop-losses hote hain. Big players ko bade orders fill karne ke liye yahi liquidity chahiye — isliye market aksar wahan tak jaata hai."],
          ["FVG / Imbalance (IRL)", "Fast move mein teen candles ke beech bana gap. Market aksar wapas aakar ise fill karta hai — yahi achhe entry zones bante hain."],
          ["Equilibrium, Premium, Discount", "Range ka 50% level = Equilibrium. Neeche = Discount (buy zone), upar = Premium (sell zone)."],
          ["Manipulation / Judas swing", "Real move se pehle opposite direction mein ek fake move jo stop-losses hunt karta hai. ICT 'Power of 3' ka middle step."],
          ["SMT divergence", "Do related index (jaise Sensex aur Bank Nifty) saath na chalein — ek new low banaye, doosra nahi — toh yeh smart money activity ka sign hota hai."],
          ["FII / DII / Retail / Pro", "FII = foreign institutions, DII = Indian mutual funds/insurance, Retail = normal traders, Pro = brokers ke prop desks. NSE roz shaam inki positions publish karta hai."],
          ["COT report", "US CFTC har week batata hai ki big hedgers dollar, bonds, crude mein kya positions le rahe hain. Extreme positioning ke baad aksar bada reversal aata hai."],
          ["India VIX", "Market ka fear meter. High VIX = bade moves expected aur options mehnge."],
          ["Expiry", "Sensex weekly options Thursday ko, Nifty Tuesday ko expire hote hain. Holiday ho toh ek din pehle."],
          ["Trend meter votes", "Har timeframe pe multiple signals vote karte hain. Zyada votes same side = zyada confidence."]],
      instH: "App install karein",
      inst: "Android (Chrome / Brave): ⋮ menu → <b>Install app</b> ya <b>Add to Home screen</b>.<br>iPhone (Safari): Share → <b>Add to Home Screen</b>.",
      btn: "Install karein", disc: DISC_HI,
    },
    pro: {
      kicker: "Learn", title: "The smart-money framework behind this dashboard",
      lead: "This dashboard maps where liquidity rests, which imbalances price is likely to rebalance, and who is positioned for the move.",
      stepsH: "How to use it - 4 steps",
      steps: ["Start in <b>Simple</b> for the one-screen read, then switch to <b>Pro</b>.",
              "<b>Story</b> and <b>Bias</b>: the top-down view from yearly to daily.",
              "<b>ICT Map</b> and <b>Intraday</b>: draw on liquidity, entry zone (IRL), invalidation, SMT, kill zones and setups.",
              "<b>Global</b>, <b>FII vs Retail</b> and <b>Backtest</b>: confirm who is driving the move and which tendencies actually hold."],
      G: [["External range liquidity (ERL)", "Resting stop orders above old highs and below old lows. Large players need this liquidity to fill size, so price is repeatedly drawn to it."],
          ["Fair value gap / IRL", "A three-candle imbalance left by a fast move. Price tends to return to rebalance it; these become entry zones."],
          ["Equilibrium, premium & discount", "The 50% level of a dealing range. Below it is discount (buy zone), above it is premium (sell zone)."],
          ["Power of 3 / Judas swing", "Accumulation, manipulation, distribution. The manipulation leg is a false move against the true direction that clears stops."],
          ["SMT divergence", "When correlated indices disagree at a liquidity raid (one makes a lower low, the other does not), it often marks smart-money accumulation or distribution."],
          ["Participant OI", "NSE's daily breakdown of index futures and options positions by FII, DII, Client and Pro - India's equivalent of the COT report."],
          ["COT report", "The CFTC's weekly report of positions held by commercials (hedgers) and speculators. Extreme commercial positioning often precedes major turns."],
          ["COT index", "Where the current commercial net position sits within its 26/52/156-week range, scaled 0-100. Above 80 or below 20 is extreme."],
          ["India VIX", "Expected 30-day volatility from Nifty options. High VIX means expensive options and wider ranges."],
          ["Expiry", "Sensex weekly options expire on Thursday (BSE), Nifty 50 on Tuesday (NSE). Holidays move expiry to the previous trading day."]],
      instH: "Install as an app",
      inst: "Android (Chrome / Brave): ⋮ menu → <b>Install app</b> or <b>Add to Home screen</b>.<br>iPhone (Safari): Share → <b>Add to Home Screen</b>.",
      btn: "Install now", disc: DISC_EN,
    },
  };
  function renderLearn() {
    const L = LEARN[mode];
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

  /* ---------- init ---------- */
  (async function init() {
    $("#brandName").textContent = CFG.brand;
    if (!CFG.showTradeLevels) document.body.classList.add("no-levels");
    window.addEventListener("resize", setH);
    $$(".mode button").forEach((b) => b.addEventListener("click", () => setMode(b.dataset.mode)));
    $("#learnBtn").addEventListener("click", () => { learn = !learn; apply(); });
    renderIdx(); apply(false); watchPsub();
    [D.bias, D.story, D.ict, D.poi, D.prices, D.cot] = await Promise.all(
      ["data/bias.json", "data/story.json", "data/ict.json", "data/participant_oi.json", "data/prices.json", "data/cot.json"].map(get));
    renderFresh(); renderSimple(); setH(); window.MP_RENDER = renderSimple;
    let tries = 0; const t = setInterval(() => { tries++; if (syncPro() || tries > 25) clearInterval(t); }, 300);
    if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
  })();
})();
