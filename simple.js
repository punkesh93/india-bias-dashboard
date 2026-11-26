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
  const TFS = [["Yearly", "Saal bhar"], ["Quarterly", "3 mahine"], ["Monthly", "Is mahine"], ["Weekly", "Is hafte"], ["Daily", "Aaj / kal"]];
  const LBL = { Bullish: ["Upar", "up"], Bearish: ["Neeche", "down"], Neutral: ["Saaf nahi", "flat"] };
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
      : "Sirf shiksha aur analysis ke liye · Trading advice nahi · Data: CFTC, NSE, Yahoo Finance";
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

  /* ---------- Simple mode (Hinglish) ---------- */
  function hero(b, s, px) {
    const v = s.verdict || "";
    const tone = /Bull/.test(v) ? "up" : /Bear/.test(v) ? "down" : "flat";
    const title = tone === "up" ? "Tezi ki taraf jhukav" : tone === "down" ? "Mandi ki taraf jhukav" : "Abhi koi saaf disha nahi";
    const lab = (t) => (b.timeframes[t] && b.timeframes[t].label) || "Neutral";
    const word = (arr) => { const u = arr.filter((x) => x === "Bullish").length, d = arr.filter((x) => x === "Bearish").length; return u > d ? "up" : d > u ? "down" : "flat"; };
    const big = word([lab("Yearly"), lab("Quarterly"), lab("Monthly")]), sh = word([lab("Weekly"), lab("Daily")]);
    const n = NAME[key];
    const S = {
      "up-up": `${n} ka bada trend bhi upar hai aur short-term bhi — dono ek hi disha mein hain.`,
      "up-flat": `${n} ka bada trend upar hai, lekin is hafte direction abhi clear nahi hai. Jaldbaazi ki zaroorat nahi.`,
      "up-down": `${n} ka bada trend upar hai, par short-term mein dabav hai — yeh ek pullback ho sakta hai.`,
      "down-down": `${n} ka bada trend neeche hai aur short-term bhi kamzor hai.`,
      "down-flat": `${n} ka bada trend neeche hai, is hafte market ruka hua hai.`,
      "down-up": `${n} ka bada trend neeche hai, par short-term mein bounce aa raha hai — dhyan se.`,
      "flat-up": `${n} bade timeframe pe range mein hai, short-term mein thodi tezi hai.`,
      "flat-down": `${n} bade timeframe pe range mein hai, short-term mein thoda dabav hai.`,
      "flat-flat": `${n} abhi range mein hai — na bada trend saaf hai, na short-term.`,
    };
    return `<div class="s-card hero2 ${tone}">
      <div class="s-h"><span class="pulse ${tone}"></span>${esc(n)} · aaj ka seedha jawab</div>
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
    return `<div class="s-card"><div class="s-h">Trend meter</div>${rows}<p class="hint">Har timeframe pe kai signals ka vote. Lambi patti = zyada signals ek hi taraf.</p></div>`;
  }
  function where(I) {
    const r = I && I.ranges && I.ranges[1]; if (!r) return "";
    const pos = Math.max(0, Math.min(100, r.pos));
    let t;
    if (pos >= 75) t = "Price pichhle 40 din ki range ke top ke paas hai — yaani <b>mehnga zone</b>. Yahan naya buy risky hai; dip ka intezaar behtar.";
    else if (pos >= 50) t = "Price range ke <b>upar wale aadhe</b> hisse mein hai — thoda mehnga. Bade players sasta kharidte hain, mehnga bechte hain.";
    else if (pos >= 25) t = "Price range ke <b>neeche wale aadhe</b> hisse mein hai — thoda sasta.";
    else t = "Price range ke bottom ke paas hai — yaani <b>sasta zone</b>. Yahan se bechna risky hai.";
    return `<div class="s-card"><div class="s-h">Price kahan hai?</div>
      <div class="zbar"><i class="eq"></i><b class="mk" style="left:${pos}%"></b></div>
      <div class="zlab"><span>Sasta</span><span>Beech: ${num(r.eq)}</span><span>Mehnga</span></div>
      <p class="body">${t}</p><p class="hint">Range ${num(r.low)} – ${num(r.high)} (40 trading din). "Beech" = equilibrium.</p></div>`;
  }
  function who() {
    const rows = (D.poi && D.poi.rows) || []; if (rows.length < 21) return "";
    const net = (r, g) => (r[g] ? r[g].fil - r[g].fis : null);
    const last = rows[rows.length - 1], prev = rows[rows.length - 21];
    const f = net(last, "FII"), f0 = net(prev, "FII"), c = net(last, "Client"), c0 = net(prev, "Client");
    if (f == null || c == null || f0 == null || c0 == null) return "";
    const df = f - f0, dc = c - c0;
    let ft = f < 0 ? `FII (videshi bade funds) abhi <b>net short</b> hain — ${lakh(f)} contracts ka mandi wala daav.`
                   : `FII (videshi bade funds) <b>net long</b> hain — ${lakh(f)} contracts ka tezi wala daav.`;
    ft += " " + (df > 0
      ? (f < 0 ? `20 din mein inhone ${lakh(df)} contracts ke short <b>cover kiye</b> — mandi ka daav ghata rahe hain.` : `20 din mein ${lakh(df)} contracts <b>aur khareede</b>.`)
      : (f < 0 ? `20 din mein ${lakh(df)} contracts ke <b>naye short</b> jode — mandi ka daav badha rahe hain.` : `20 din mein ${lakh(df)} contracts ke long <b>kam kiye</b>.`));
    const ct = dc < 0 ? `Retail traders ne 20 din mein ${lakh(dc)} contracts ki buying kam ki — crowd bech raha hai.`
                      : `Retail traders ne 20 din mein ${lakh(dc)} contracts aur khareede — crowd upar bhaag raha hai.`;
    const smart = df > 0 ? ["Smart money: kharidari ki taraf", "up"] : ["Smart money: bikvali ki taraf", "down"];
    const combo = df > 0 && dc < 0 ? "Bade players khareed rahe hain, crowd bech raha hai — aisi rally aksar healthy hoti hai."
                : df < 0 && dc > 0 ? "Bade players bech rahe hain, crowd khareed raha hai — savdhaani ka sign."
                : "Dono ek hi taraf chal rahe hain — koi khaas divergence nahi.";
    return `<div class="s-card"><div class="s-h">Bade players kya kar rahe hain?</div>
      <span class="chipx ${smart[1]}">${smart[0]}</span>
      <div class="who">
        <div class="who-i"><div class="who-n">FII · net</div><div class="who-v ${f >= 0 ? "up" : "down"}">${sg(f)}${lakh(f)}</div><div class="who-d ${df >= 0 ? "up" : "down"}">20 din: ${sg(df)}${lakh(df)}</div></div>
        <div class="who-i"><div class="who-n">Retail · net</div><div class="who-v ${c >= 0 ? "up" : "down"}">${sg(c)}${lakh(c)}</div><div class="who-d ${dc >= 0 ? "up" : "down"}">20 din: ${sg(dc)}${lakh(dc)}</div></div>
      </div>
      <p class="body">${ft}</p><p class="body">${ct}</p><p class="body strong">${combo}</p>
      <p class="hint">Index futures contracts · NSE data ${esc(last.d)}</p></div>`;
  }
  function draw(I) {
    if (!I || !I.draw) return "";
    const d = I.draw, dir = d.direction;
    const tone = dir === "bullish" ? "up" : dir === "bearish" ? "down" : "flat";
    const ST = {
      bullish: ["Neeche ke stop-loss abhi-abhi saaf hue (manipulation). Ab upar ki taraf tez move aa sakta hai.",
                "Price ne neeche ka gap (FVG) bhar diya — yahin se aksar agla upar ka move shuru hota hai.",
                "Upar ke stop-loss le liye gaye. Ab aksar thoda pullback aata hai — peechhe bhaag ke mat kharido."],
      bearish: ["Upar ke stop-loss abhi-abhi saaf hue (manipulation). Ab neeche ki taraf tez move aa sakta hai.",
                "Price ne upar ka gap (FVG) bhar diya — yahin se aksar agla neeche ka move shuru hota hai.",
                "Neeche ke stop-loss le liye gaye. Ab aksar thoda bounce aata hai — peechhe bhaag ke mat becho."],
    };
    const st = d.stage_idx >= 0 && ST[dir] ? ST[dir][d.stage_idx]
      : "Dono taraf orders jama ho rahe hain. Jab ek taraf ke stop-loss saaf hon aur price wapas range mein aaye, tab disha milegi.";
    const title = dir === "bullish" ? "Magnet: upar ki taraf" : dir === "bearish" ? "Magnet: neeche ki taraf" : "Magnet: abhi dono taraf";
    let lv = "";
    if (CFG.showTradeLevels) {
      const box = (lab, x, sub) => (x ? `<div class="lv"><span>${lab}</span><b>${x.low != null ? `${num(x.low)}–${num(x.high)}` : num(x.price)}</b><small>${pct(x.dist)} · ${sub}</small></div>` : "");
      const L = dir === "two-sided"
        ? box("Upar ki liquidity", d.target, "buy stop-loss jama") + box("Beech (equilibrium)", d.entry, "range ka center") + box("Neeche ki liquidity", d.invalidation, "sell stop-loss jama")
        : box(dir === "bullish" ? "Target · upar ka magnet" : "Target · neeche ka magnet", d.target, "yahan stop-loss jama hain")
          + box("Behtar entry zone", d.entry, dir === "bullish" ? "sasta area / gap" : "mehnga area / gap")
          + box("Galat hone ka level", d.invalidation, "iske paar close = view kamzor");
      lv = `<div class="lv3">${L}</div>`;
    }
    return `<div class="s-card"><div class="s-h">Paisa kahan khinch raha hai?</div>
      <div class="big2 ${tone}">${title}</div><p class="body">${st}</p>${lv}
      <details class="why"><summary>Yeh kaise kaam karta hai?</summary>
        <p>Bade players ko bade orders bharne ke liye doosron ke stop-loss chahiye hote hain. Isliye market aksar purane high/low ke paar jama stop-loss (liquidity) tak jaata hai, phir tez move mein chhode hue gaps (FVG) ko bharne wapas aata hai: liquidity → gap → liquidity.</p>
      </details></div>`;
  }
  function world() {
    const M = D.cot && D.cot.markets; if (!M) return "";
    const v = (k) => { const a = M[k] && M[k].idx && M[k].idx["52"]; return a ? a[a.length - 1] : null; };
    const items = [];
    const add = (k, hi, lo) => { const x = v(k); if (x == null) return; if (x >= 80) items.push(hi); else if (x <= 20) items.push(lo); };
    add("DXY", ["Dollar mazboot hone ke signals — India ke liye thoda negative.", "t-down"], ["Dollar kamzor hone ke signals — India ke liye achha (FII paisa aata hai).", "t-up"]);
    add("UST10Y", ["US bond yields girne ke signals — emerging markets ke liye achha.", "t-up"], ["US yields badhne ke signals — India pe dabav.", "t-down"]);
    add("MSCIEM", ["Emerging markets mein paisa aane ke signals — India ke liye achha.", "t-up"], ["Emerging markets se paisa nikalne ke signals.", "t-down"]);
    add("CRUDE", ["Crude oil mehnga hone ke signals — rupee aur mehngai pe dabav.", "t-down"], ["Crude sasta hone ke signals — India ke liye achha.", "t-up"]);
    const MAP = { Supportive: ["Saath de raha hai", "up"], Mixed: ["Mila-jula", "flat"], Hostile: ["Khilaf hai", "down"] };
    const m = MAP[D.story && D.story.macro && D.story.macro.summary] || MAP.Mixed;
    const li = items.length ? items.map(([t, c]) => `<li class="${c}">${t}</li>`).join("") : `<li>Abhi kisi bade global market mein extreme signal nahi hai.</li>`;
    return `<div class="s-card"><div class="s-h">Duniya ka mood</div><span class="chipx ${m[1]}">Global hawa: ${m[0]}</span>
      <ul class="ticks">${li}</ul><p class="hint">CFTC report se bade hedgers ki positioning · har hafte update</p></div>`;
  }
  function alerts() {
    const out = [];
    const wd = new Date(Date.now() + 330 * 60000).getUTCDay();
    const exp = { SENSEX: [4, "Sensex weekly expiry (BSE)"], NIFTY: [2, "Nifty weekly expiry (NSE)"] }[key];
    if (exp) {
      if (wd === exp[0]) out.push(["t-warn", `Aaj ${exp[1]} hai — din ke aakhir tak tez, ulte-seedhe moves ho sakte hain. Options ka premium tezi se ghatta hai.`]);
      else if ((wd + 1) % 7 === exp[0]) out.push(["t-warn", `Kal ${exp[1]} hai. (Chhutti ho toh expiry ek din pehle.)`]);
    }
    const vr = D.prices && D.prices.series && D.prices.series.INDIAVIX && D.prices.series.INDIAVIX.rows;
    if (vr && vr.length) {
      const vx = vr[vr.length - 1].c;
      out.push(vx > 20 ? ["t-down", `India VIX ${num(vx, 1)} — darr zyada hai, options mehnge. Position chhoti rakho.`]
              : vx < 13 ? ["", `India VIX ${num(vx, 1)} — market shaant hai, options saste par move chhote ho sakte hain.`]
              : ["", `India VIX ${num(vx, 1)} — normal range mein.`]);
    }
    ((D.ict && D.ict.smt) || []).filter((r) => (r.a === key || r.b === key) && (r.type === "bullish" || r.type === "bearish")).slice(0, 2).forEach((r) => {
      out.push(r.type === "bullish"
        ? ["t-up", r.corr < 0
            ? `SMT signal: ${NAME[r.a]} ki kamzori ko ${NAME[r.b]} ne confirm nahi kiya (dono aam taur pe ulte chalte hain). Neeche se kharidari ka sign ho sakta hai.`
            : `SMT signal: ${NAME[r.a]} aur ${NAME[r.b]} saath nahi chale — neeche ke stop-loss sirf ek mein saaf hue. Smart money ke neeche se kharidne ka sign ho sakta hai.`]
        : ["t-down", r.corr < 0
            ? `SMT warning: ${NAME[r.a]} ki tezi ko ${NAME[r.b]} ne confirm nahi kiya (dono aam taur pe ulte chalte hain). Upar kamzori ka sign.`
            : `SMT warning: ${NAME[r.a]} aur ${NAME[r.b]} mein se ek ne naya high banaya, doosre ne nahi — upar kamzori ka sign.`]);
    });
    const rk = D.story && D.story.instruments && D.story.instruments[key] && D.story.instruments[key].risks;
    if (rk && rk.length) out.push(["", `${rk.length} signals is view ke khilaf hain — detail Pro mode mein.`]);
    if (!out.length) return "";
    return `<div class="s-card"><div class="s-h">Dhyan rakho</div><ul class="ticks">${out.map(([c, t]) => `<li class="${c}">${t}</li>`).join("")}</ul></div>`;
  }
  const DISC_HI = `<p class="disc">Yeh app sirf shiksha aur market analysis ke liye hai — buy/sell ki salah nahi. Trading mein nuksaan ho sakta hai; zarurat ho toh SEBI-registered advisor se baat karo.</p>`;
  const DISC_EN = `<p class="disc">For education and market analysis only — not investment advice or a recommendation to buy or sell. Trading involves risk of loss; consult a SEBI-registered adviser where appropriate.</p>`;

  function renderSimple() {
    const b = D.bias && D.bias.instruments && D.bias.instruments[key];
    const s = D.story && D.story.instruments && D.story.instruments[key];
    const I = D.ict && D.ict.instruments && D.ict.instruments[key];
    const el = $("#simple");
    if (!b || !s) { el.innerHTML = `<div class="s-card">Data abhi load nahi hua. Internet check karke refresh karo.</div>`; return; }
    const rows = (D.prices && D.prices.series && D.prices.series[key] && D.prices.series[key].rows) || [];
    const last = rows[rows.length - 1], prev = rows[rows.length - 2];
    const px = last ? { close: last.c, chg: prev ? (last.c / prev.c - 1) * 100 : null, asof: last.t } : { close: s.close, chg: null, asof: s.asof };
    el.innerHTML = hero(b, s, px) + `<div class="s-grid">${trend(b)}${where(I)}</div>` + draw(I)
      + `<div class="s-grid">${who()}${world()}</div>` + alerts()
      + `<button class="cta" id="goPro">Pura analysis dekho → Pro mode</button>` + DISC_HI;
    $("#goPro").onclick = () => setMode("pro");
  }

  /* ---------- Learn (Hinglish in Simple, English in Pro) ---------- */
  const LEARN = {
    simple: {
      kicker: "Seekho", title: "Smart money ki bhasha, aasaan shabdon mein",
      lead: "Is app ka maqsad: bade players kya kar rahe hain, aur market kis liquidity ki taraf khinch raha hai — yeh saaf dikhana.",
      stepsH: "Kaise use karein — 4 steps",
      steps: ["<b>Simple</b> mein seedha jawab padho — bada trend kya hai, short-term kya hai.",
              "Dekho price <b>sasta</b> hai ya <b>mehnga</b>. Mehnge zone mein naya buy na karo, dip ka intezaar karo.",
              "Bade players (FII) aur crowd (retail) ko compare karo — dono ulte hon toh smart money ke saath socho.",
              "<b>Pro</b> mein ICT map, SMT aur levels confirm karo, phir apne chart pe entry dhoondho."],
      G: [["Liquidity (ERL)", "Purane high aur low ke upar-neeche traders ke stop-loss jama hote hain. Bade players ko bade orders bharne ke liye yahi liquidity chahiye — isliye market aksar wahan tak jaata hai."],
          ["Gap / FVG (IRL)", "Tez move mein teen candles ke beech chhoota hua khaali area. Market aksar wapas aake ise bharta hai — yahin achhe entry zones bante hain."],
          ["Equilibrium (beech)", "Range ka 50% level. Iske neeche = sasta (discount), upar = mehnga (premium). Sasta mein kharido, mehnge mein becho."],
          ["Manipulation / Judas swing", "Asli move se pehle ulti disha mein nakli jhatka jo stop-loss saaf karta hai — 'Power of 3' ka beech wala step."],
          ["SMT divergence", "Do milte-julte index (jaise Sensex aur Bank Nifty) saath na chalein — ek naya low banaye, doosra nahi — toh smart money ke chhupe kaam ka sign."],
          ["FII / DII / Retail / Pro", "FII = videshi bade funds, DII = desi mutual funds/insurance, Retail = aam traders, Pro = brokers ke trading desk. NSE roz shaam inki positions batata hai."],
          ["COT report", "America ka CFTC har hafte batata hai ki bade hedgers dollar, bonds, crude mein kya kar rahe hain. Extreme positioning ke baad bada mod aksar paas hota hai."],
          ["India VIX", "Market ka 'darr meter'. Zyada VIX = bade moves ki ummeed aur mehnge options."],
          ["Expiry", "Sensex weekly options Thursday ko, Nifty Tuesday ko expire hote hain. Chhutti ho toh ek din pehle."],
          ["Trend meter ke votes", "Har timeframe pe kai signals vote karte hain. Zyada votes ek taraf = zyada bharosa."]],
      instH: "App ki tarah install karo",
      inst: "Android (Chrome / Brave): ⋮ menu → <b>Install app</b> ya <b>Add to Home screen</b>.<br>iPhone (Safari): Share → <b>Add to Home Screen</b>.",
      btn: "Abhi install karo", disc: DISC_HI,
    },
    pro: {
      kicker: "Learn", title: "The smart-money framework behind this dashboard",
      lead: "This dashboard maps where liquidity rests, which imbalances price is likely to rebalance, and who is positioned for the move.",
      stepsH: "How to use it - 4 steps",
      steps: ["Start in <b>Simple</b> for the one-screen read, then switch to <b>Pro</b>.",
              "<b>Story</b> and <b>Bias</b>: the top-down view from yearly to daily.",
              "<b>ICT Map</b>: draw on liquidity, entry zone (IRL), invalidation, SMT and Power of 3.",
              "<b>Global</b> and <b>FII vs Retail</b>: confirm who is driving the move, then apply your intraday entry model."],
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
    renderFresh(); renderSimple(); setH();
    let tries = 0; const t = setInterval(() => { tries++; if (syncPro() || tries > 25) clearInterval(t); }, 300);
    if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
  })();
})();
