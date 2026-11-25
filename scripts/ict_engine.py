"""ICT engine on daily candles.

ERL: unswept swing highs/lows, relative equal highs/lows, previous period highs/lows.
IRL: daily + weekly fair value gaps, order blocks (with displacement + FVG), equilibrium.
Plus IPDA 20/40/60-day dealing ranges, structure, raids vs runs, Power of 3,
weekly profile, SMT divergence, FII signature and the draw on liquidity.
"""
import pandas as pd

from common import load, now_ist, save

FOCUS = ["SENSEX", "NIFTY", "BANKNIFTY", "FINNIFTY"]
NAMES = {"SENSEX": "Sensex", "NIFTY": "Nifty 50", "BANKNIFTY": "Bank Nifty", "FINNIFTY": "FinNifty",
         "USDINR": "USD/INR", "DXY": "Dollar Index"}
SMT_PAIRS = [("SENSEX", "NIFTY", 1), ("SENSEX", "BANKNIFTY", 1), ("SENSEX", "FINNIFTY", 1),
             ("NIFTY", "BANKNIFTY", 1), ("SENSEX", "USDINR", -1), ("SENSEX", "DXY", -1)]
HORIZONS = [("Short-term", 10, 30), ("Swing", 60, 190)]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
PERIODS = [("day", None), ("week", "W-FRI"), ("month", "ME"), ("quarter", "QE"), ("year", "YE")]
EXPIRY = ("Sensex weekly options expire on Thursday (BSE), Nifty 50 weekly on Tuesday (NSE). "
          "A holiday moves expiry to the previous trading day - check the exchange calendar.")


def frame(prices, key):
    s = (prices.get("series") or {}).get(key)
    if not s:
        return None
    df = pd.DataFrame(s["rows"])
    df["t"] = pd.to_datetime(df["t"])
    return df.set_index("t").sort_index()[["o", "h", "l", "c"]].astype(float)


def resample(df, rule):
    return df.resample(rule).agg({"o": "first", "h": "max", "l": "min", "c": "last"}).dropna()


def atr(df, n=20):
    pc = df["c"].shift()
    tr = pd.concat([df["h"] - df["l"], (df["h"] - pc).abs(), (df["l"] - pc).abs()], axis=1).max(axis=1)
    return float(tr.tail(n).mean())


def d(ts):
    return pd.Timestamp(ts).strftime("%d %b %Y")


def pct(level, close):
    return round((float(level) / close - 1) * 100, 2)


def r2(x):
    return round(float(x), 2)


def swings(df, n=2):
    H, L = df["h"].values, df["l"].values
    hs, ls = [], []
    for i in range(n, len(df) - n):
        if H[i] > H[i - n:i].max() and H[i] >= H[i + 1:i + n + 1].max():
            hs.append(i)
        if L[i] < L[i - n:i].min() and L[i] <= L[i + 1:i + n + 1].min():
            ls.append(i)
    return hs, ls


def structure(df):
    sub = df.tail(250)
    hs, ls = swings(sub)
    if len(hs) < 2 or len(ls) < 2:
        return {"state": "unclear", "note": "Not enough swings yet"}
    H, L = sub["h"].values, sub["l"].values
    h1, h2, l1, l2 = H[hs[-2]], H[hs[-1]], L[ls[-2]], L[ls[-1]]
    c = float(sub["c"].iloc[-1])
    if c > h2:
        state, note = "bullish", f"closed above the last swing high {h2:,.0f} (break of structure)"
    elif c < l2:
        state, note = "bearish", f"closed below the last swing low {l2:,.0f} (break of structure)"
    elif h2 > h1 and l2 > l1:
        state, note = "bullish", "higher highs and higher lows"
    elif h2 < h1 and l2 < l1:
        state, note = "bearish", "lower highs and lower lows"
    else:
        state, note = "ranging", "mixed swings - consolidation or transition"
    return {"state": state, "note": note, "swing_high": r2(h2), "swing_low": r2(l2),
            "swing_high_date": d(sub.index[hs[-1]]), "swing_low_date": d(sub.index[ls[-1]])}


def erl_pools(df, close, tol):
    sub = df.tail(260)
    H, L = sub["h"].values, sub["l"].values
    hs, ls = swings(sub)
    highs = [(H[i], d(sub.index[i])) for i in hs if H[i + 1:].max() <= H[i]]
    lows = [(L[i], d(sub.index[i])) for i in ls if L[i + 1:].min() >= L[i]]

    def group(levels, side):
        groups = []
        for p, dt in sorted(levels, key=lambda x: x[0]):
            if groups and abs(p - groups[-1]["price"]) <= tol:
                g = groups[-1]
                g["dates"].append(dt)
                g["price"] = max(g["price"], p) if side == "high" else min(g["price"], p)
            else:
                groups.append({"price": p, "dates": [dt]})
        res = []
        for g in groups:
            eq = len(g["dates"]) > 1
            base = ("Relative equal " + ("highs" if side == "high" else "lows")) if eq else ("Swing " + side)
            res.append({"name": f"{base} ({', '.join(g['dates'][-2:])})", "price": r2(g["price"]),
                        "side": side, "equal": eq})
        return res

    pools = group(highs, "high") + group(lows, "low")
    for name, rule in PERIODS:
        bars = df if rule is None else resample(df, rule)
        if len(bars) < 2:
            continue
        prev, cur = bars.iloc[-2], bars.iloc[-1]
        if cur["h"] <= prev["h"]:
            pools.append({"name": f"Prev {name} high", "price": r2(prev["h"]), "side": "high", "equal": False})
        if cur["l"] >= prev["l"]:
            pools.append({"name": f"Prev {name} low", "price": r2(prev["l"]), "side": "low", "equal": False})

    def dedupe(lst):
        out = []
        for p in lst:
            if out and abs(p["price"] - out[-1]["price"]) <= tol:
                out[-1]["name"] += " + " + p["name"]
                out[-1]["equal"] = out[-1]["equal"] or p["equal"]
            else:
                out.append(dict(p))
        return out

    above = dedupe(sorted([p for p in pools if p["side"] == "high" and p["price"] > close], key=lambda p: p["price"]))
    below = dedupe(sorted([p for p in pools if p["side"] == "low" and p["price"] < close], key=lambda p: -p["price"]))
    for p in above + below:
        p["dist"] = pct(p["price"], close)
    return above[:6], below[:6]


def fvgs(df, a, tf, lookback):
    sub = df.tail(lookback)
    O, H, L, C = (sub[k].values for k in ("o", "h", "l", "c"))
    out = []
    for i in range(1, len(sub) - 1):
        if L[i + 1] > H[i - 1]:
            side, bot, top = "bullish", H[i - 1], L[i + 1]
        elif H[i + 1] < L[i - 1]:
            side, bot, top = "bearish", H[i + 1], L[i - 1]
        else:
            continue
        if top - bot < 0.1 * a:
            continue
        ce = (top + bot) / 2
        aL, aH, aC = L[i + 2:], H[i + 2:], C[i + 2:]
        if side == "bullish":
            if len(aC) and aC.min() < bot:
                status = "inverted"
            elif len(aL) and aL.min() <= bot:
                status = "filled"
            elif len(aL) and aL.min() <= ce:
                status = "CE tapped"
            elif len(aL) and aL.min() <= top:
                status = "tapped"
            else:
                status = "open"
            hits = [k for k in range(len(aL)) if aL[k] <= top]
        else:
            if len(aC) and aC.max() > top:
                status = "inverted"
            elif len(aH) and aH.max() >= top:
                status = "filled"
            elif len(aH) and aH.max() >= ce:
                status = "CE tapped"
            elif len(aH) and aH.max() >= bot:
                status = "tapped"
            else:
                status = "open"
            hits = [k for k in range(len(aH)) if aH[k] >= bot]
        last_pos = i + 2 + hits[-1] if hits else None
        out.append({"tf": tf, "side": side, "low": r2(bot), "high": r2(top), "ce": r2(ce), "status": status,
                    "date": d(sub.index[i]),
                    "last_tap_date": d(sub.index[last_pos]) if hits else None,
                    "last_tap_ago": int(len(sub) - 1 - last_pos) if hits else None,
                    "displacement": bool(abs(C[i] - O[i]) >= 1.2 * a)})
    return out


def order_blocks(df, a, lookback=120):
    sub = df.tail(lookback)
    O, H, L, C = (sub[k].values for k in ("o", "h", "l", "c"))
    out = []
    for i in range(3, len(sub) - 1):
        body = C[i] - O[i]
        if abs(body) < 1.2 * a:
            continue
        bull = body > 0
        if bull and not L[i + 1] > H[i - 1]:
            continue
        if not bull and not H[i + 1] < L[i - 1]:
            continue
        j = next((k for k in range(i - 1, i - 4, -1) if (C[k] < O[k]) == bull), None)
        if j is None:
            continue
        lo, hi = (L[j], O[j]) if bull else (O[j], H[j])
        aL, aH, aC = L[i + 1:], H[i + 1:], C[i + 1:]
        if bull:
            if len(aC) and aC.min() < lo:
                continue
            status = "mitigated" if len(aL) and aL.min() <= hi else "fresh"
        else:
            if len(aC) and aC.max() > hi:
                continue
            status = "mitigated" if len(aH) and aH.max() >= lo else "fresh"
        out.append({"side": "bullish" if bull else "bearish", "low": r2(lo), "high": r2(hi),
                    "date": d(sub.index[j]), "status": status})
    return out[-4:]


def ranges(df, close):
    out = []
    for n in (20, 40, 60):
        w = df.tail(n)
        hi, lo = float(w["h"].max()), float(w["l"].min())
        up = w["l"].idxmin() < w["h"].idxmax()
        span = (hi - lo) or 1
        eq = (hi + lo) / 2
        pos = (close - lo) / span * 100
        if up:
            ol, oh, side = hi - 0.79 * span, hi - 0.62 * span, "buy"
        else:
            ol, oh, side = lo + 0.62 * span, lo + 0.79 * span, "sell"
        zone = "premium" if pos > 50 else "discount"
        out.append({"lookback": n, "high": r2(hi), "low": r2(lo), "eq": r2(eq), "pos": round(pos, 1),
                    "zone": zone, "leg": "up" if up else "down", "ote_low": r2(ol), "ote_high": r2(oh),
                    "note": f"{zone.capitalize()} ({pos:.0f}% of the range). Leg {'up' if up else 'down'}: "
                            f"{side} OTE {ol:,.0f}-{oh:,.0f}."})
    return out


def events(df, fv, lookback=15):
    H, L, C = df["h"].values, df["l"].values, df["c"].values
    n = len(df)
    ev = []
    for k in range(max(60, n - lookback), n):
        for side in ("high", "low"):
            for span in (60, 20):
                ref = H[k - span:k].max() if side == "high" else L[k - span:k].min()
                hit = H[k] > ref if side == "high" else L[k] < ref
                if not hit:
                    continue
                back = C[k] < ref if side == "high" else C[k] > ref
                kind = "raid" if back else "run"
                pool = "Buy-side" if side == "high" else "Sell-side"
                if kind == "raid":
                    note = (f"{pool} beyond the {span}-day {side} ({ref:,.0f}) was raided and price closed back inside - "
                            f"{'bearish' if side == 'high' else 'bullish'} manipulation")
                else:
                    note = (f"Price ran the {span}-day {side} ({ref:,.0f}) and closed beyond it - expansion "
                            f"{'higher' if side == 'high' else 'lower'}")
                ev.append({"ago": n - 1 - k, "date": d(df.index[k]), "kind": kind, "side": side,
                           "level": r2(ref), "name": f"{span}-day {side}", "note": note})
                break
    for f in fv:
        if f["last_tap_ago"] is not None and f["last_tap_ago"] < lookback and f["status"] != "inverted":
            ev.append({"ago": f["last_tap_ago"], "date": f["last_tap_date"], "kind": "irl", "side": f["side"],
                       "level": f["ce"], "name": f"{f['tf']} {f['side']} FVG",
                       "note": f"Price rebalanced into the {f['tf'].lower()} {f['side']} FVG "
                               f"{f['low']:,.0f}-{f['high']:,.0f} ({f['status']})"})
    seen = {}
    for e in sorted(ev, key=lambda e: -e["ago"]):
        seen[(e["kind"], e["side"], e["name"])] = e
    return sorted(seen.values(), key=lambda e: -e["ago"])[-8:]


def po3(df, rule, label):
    bars = resample(df, rule)
    if bars.empty:
        return None
    b = bars.iloc[-1]
    o, h, l, c = (float(b[k]) for k in ("o", "h", "l", "c"))
    rng = (h - l) or 1
    if c >= o:
        txt = (f"Bullish {label} so far: it first dipped {o - l:,.0f} below the open ({o:,.0f}) - manipulation done, "
               f"now in the expansion/distribution phase." if (o - l) / rng > 0.15 else
               f"Bullish {label} so far, but it has barely traded below the open ({o:,.0f}) - "
               f"a Judas dip below the open is still possible.")
    else:
        txt = (f"Bearish {label} so far: it first rallied {h - o:,.0f} above the open ({o:,.0f}) - manipulation done, "
               f"now in the expansion/distribution phase." if (h - o) / rng > 0.15 else
               f"Bearish {label} so far, but it has barely traded above the open ({o:,.0f}) - "
               f"a Judas rally above the open is still possible.")
    return {"open": r2(o), "high": r2(h), "low": r2(l), "close": r2(c), "note": txt}


def week_profile(df, a):
    last = df.index[-1]
    monday = (last - pd.Timedelta(days=last.weekday())).normalize()
    wk = df[df.index >= monday]
    if len(wk) < 2:
        return "Too early in the week to read a weekly profile."
    lo_d, hi_d = wk["l"].idxmin(), wk["h"].idxmax()
    o, c = wk["o"].iloc[0], wk["c"].iloc[-1]
    if wk["h"].max() - wk["l"].min() < 1.2 * a and len(wk) >= 3:
        return ("Tight week so far - consolidation profile. Watch Thursday/Friday for a raid of the intra-week "
                "high or low, then a reversal or expansion.")
    if c > o and lo_d != wk.index[-1] and lo_d.weekday() <= 2:
        day = DAYS[lo_d.weekday()]
        return (f"Low of the week printed {day} ({wk['l'].min():,.0f}) and price is above the weekly open - "
                f"fits the bullish '{day} low of the week' profile.")
    if c < o and hi_d != wk.index[-1] and hi_d.weekday() <= 2:
        day = DAYS[hi_d.weekday()]
        return (f"High of the week printed {day} ({wk['h'].max():,.0f}) and price is below the weekly open - "
                f"fits the bearish '{day} high of the week' profile.")
    return "No clean weekly profile yet."


def smt(frames):
    rows = []
    for a, b, corr in SMT_PAIRS:
        A, B = frames.get(a), frames.get(b)
        if A is None or B is None:
            continue
        j = A[["h", "l"]].join(B[["h", "l"]], how="inner", lsuffix="_a", rsuffix="_b")
        for hz, recent, prior in HORIZONS:
            if len(j) < recent + prior:
                continue
            r, p = j.iloc[-recent:], j.iloc[-(recent + prior):-recent]
            a_low = r["l_a"].min() < p["l_a"].min()
            a_high = r["h_a"].max() > p["h_a"].max()
            b_low = r["l_b"].min() < p["l_b"].min()
            b_high = r["h_b"].max() > p["h_b"].max()
            note = note_b = ""
            if corr == 1:
                bull, bear = a_low != b_low, a_high != b_high
                if bull:
                    weak, strong = (a, b) if a_low else (b, a)
                    note = (f"{NAMES[weak]} took its prior low, {NAMES[strong]} held - bullish SMT; "
                            f"{NAMES[strong]} is the stronger leg")
                if bear:
                    strong, weak = (a, b) if a_high else (b, a)
                    note_b = (f"{NAMES[strong]} made a new high, {NAMES[weak]} failed - bearish SMT; "
                              f"{NAMES[weak]} is the weaker leg")
            else:
                bull, bear = a_low != b_high, a_high != b_low
                note = (f"{NAMES[a]} {'took its prior low' if a_low else 'held its low'} while {NAMES[b]} "
                        f"{'made a new high' if b_high else 'did not make a new high'} - bullish SMT (no confirmation)")
                note_b = (f"{NAMES[a]} {'made a new high' if a_high else 'failed to make a new high'} while {NAMES[b]} "
                          f"{'made a new low' if b_low else 'did not make a new low'} - bearish SMT (no confirmation)")
            typ = "mixed" if bull and bear else "bullish" if bull else "bearish" if bear else "none"
            text = {"bullish": note, "bearish": note_b, "mixed": f"{note}; {note_b}"}.get(typ, "In sync - both confirm each other")
            rows.append({"a": a, "b": b, "corr": corr, "horizon": f"{hz} ({recent} vs prior {prior} sessions)",
                         "type": typ, "note": text})
    return rows


def smt_bias(key, rows):
    s = sum((1 if r["type"] == "bullish" else -1) for r in rows
            if key in (r["a"], r["b"]) and r["type"] in ("bullish", "bearish"))
    return (s > 0) - (s < 0)


def signature(df, poi):
    rows = [r for r in (poi.get("rows") or []) if r.get("FII")]
    if len(rows) < 20:
        return None
    s = pd.Series({pd.Timestamp(r["d"]): r["FII"]["fil"] - r["FII"]["fis"] for r in rows}).sort_index()
    w = df.tail(60)
    lo_d, hi_d = w["l"].idxmin(), w["h"].idxmax()
    ext, kind = (lo_d, "low") if lo_d > hi_d else (hi_d, "high")
    before, after = s[s.index <= ext], s[s.index >= ext]
    if before.empty or len(after) < 2:
        return None
    n = min(10, len(after) - 1)
    at, delta = before.iloc[-1], after.iloc[n] - before.iloc[-1]
    if kind == "low":
        verdict = ("accumulation signature - smart money bought back from the crowd at the low" if delta > 0
                   else "no accumulation yet - FIIs kept selling after the low")
    else:
        verdict = ("distribution signature - smart money sold into the crowd at the high" if delta < 0
                   else "no distribution yet - FIIs kept buying after the high")
    return (f"Most recent 60-day {kind}: {d(ext)}. FII index-futures net was {at:,.0f} contracts and changed "
            f"{delta:+,.0f} over the next {n} sessions - {verdict}.")


def draw_on_liquidity(close, sd, sw, ev, above, below, fv, obs, rngs, smt_b):
    r40 = rngs[1]
    score, reasons = 0, []
    for label, st in (("Daily", sd), ("Weekly", sw)):
        score += 1 if st["state"] == "bullish" else -1 if st["state"] == "bearish" else 0
        reasons.append(f"{label} structure {st['state']}: {st['note']}")
    erl = [e for e in ev if e["kind"] in ("raid", "run")]
    if erl:
        e = erl[-1]
        score += {("raid", "low"): 1, ("raid", "high"): -1, ("run", "high"): 1, ("run", "low"): -1}[(e["kind"], e["side"])]
        reasons.append(f"Last ERL event ({e['date']}): {e['note']}")
    if smt_b:
        score += smt_b
        reasons.append("SMT divergence with correlated markets " + ("favours upside" if smt_b > 0 else "favours downside"))
    reasons.append(f"Location: {r40['zone']} of the 40-day range, equilibrium {r40['eq']:,.0f}")
    direction = "bullish" if score >= 1 else "bearish" if score <= -1 else "two-sided"

    zones = [{"name": f"{f['tf']} {f['side']} FVG ({f['date']})", "side": f["side"], "low": f["low"], "high": f["high"]}
             for f in fv if f["status"] in ("open", "tapped", "CE tapped")]
    zones += [{"name": f"{o['side'].capitalize()} order block ({o['date']})", "side": o["side"],
               "low": o["low"], "high": o["high"]} for o in obs if o["status"] == "fresh"]

    def zone(side, below_price):
        c = [z for z in zones if z["side"] == side and (z["high"] < close if below_price else z["low"] > close)]
        if not c:
            return None
        z = max(c, key=lambda z: z["high"]) if below_price else min(c, key=lambda z: z["low"])
        return {**z, "dist": pct((z["low"] + z["high"]) / 2, close)}

    eq_level = {"name": "40-day equilibrium", "price": r40["eq"], "dist": pct(r40["eq"], close)}
    last = ev[-1] if ev else None
    k = (last["kind"], last["side"]) if last else None
    out = {"direction": direction, "reasons": reasons}
    if direction == "bullish":
        tgt = next((p for p in above[:3] if p["equal"]), above[0] if above else None)
        ent = zone("bullish", True) or (eq_level if r40["eq"] < close else None)
        sl = sd.get("swing_low")
        inv = ({"name": f"Daily swing low ({sd.get('swing_low_date')})", "price": sl, "dist": pct(sl, close)}
               if sl and sl < close else (below[0] if below else None))
        if k == ("raid", "low"):
            idx, stage = 0, ("Sell-side was just raided and price closed back inside (manipulation). Expect displacement "
                             "higher; the first entry is the rebalance of the gap it leaves.")
        elif k == ("irl", "bullish"):
            idx, stage = 1, "Price has rebalanced into a bullish imbalance (IRL) - the usual launch point toward external liquidity above."
        elif k == ("run", "high"):
            idx, stage = 2, ("Buy-side was just taken (ERL reached). After ERL, price normally seeks IRL: expect a "
                             "retracement into the entry zone before the next leg - do not chase.")
        else:
            idx, stage = (2 if close > r40["eq"] else 1), "Price is delivering between internal and external liquidity in a bullish context."
        head = f"buy-side at {tgt['price']:,.0f} ({tgt['name']})" if tgt else "price is above all mapped buy-side liquidity"
        out.update(target=tgt, entry=ent, invalidation=inv, stage_idx=idx, stage=stage, headline=head,
                   target_label="Target (ERL above)", entry_label="Entry zone (IRL below)", invalidation_label="Invalidation")
    elif direction == "bearish":
        tgt = next((p for p in below[:3] if p["equal"]), below[0] if below else None)
        ent = zone("bearish", False) or (eq_level if r40["eq"] > close else None)
        sh = sd.get("swing_high")
        inv = ({"name": f"Daily swing high ({sd.get('swing_high_date')})", "price": sh, "dist": pct(sh, close)}
               if sh and sh > close else (above[0] if above else None))
        if k == ("raid", "high"):
            idx, stage = 0, ("Buy-side was just raided and price closed back inside (manipulation). Expect displacement "
                             "lower; the first entry is the rebalance of the gap it leaves.")
        elif k == ("irl", "bearish"):
            idx, stage = 1, "Price has rebalanced into a bearish imbalance (IRL) - the usual launch point toward external liquidity below."
        elif k == ("run", "low"):
            idx, stage = 2, ("Sell-side was just taken (ERL reached). After ERL, price normally seeks IRL: expect a "
                             "retracement into the entry zone before the next leg - do not chase.")
        else:
            idx, stage = (2 if close < r40["eq"] else 1), "Price is delivering between internal and external liquidity in a bearish context."
        head = f"sell-side at {tgt['price']:,.0f} ({tgt['name']})" if tgt else "price is below all mapped sell-side liquidity"
        out.update(target=tgt, entry=ent, invalidation=inv, stage_idx=idx, stage=stage, headline=head,
                   target_label="Target (ERL below)", entry_label="Entry zone (IRL above)", invalidation_label="Invalidation")
    else:
        head = (f"two-sided between {below[0]['price']:,.0f} and {above[0]['price']:,.0f}" if above and below else "two-sided")
        out.update(target=above[0] if above else None, entry=eq_level, invalidation=below[0] if below else None,
                   stage_idx=-1, headline=head,
                   stage=("No clear draw: orders are building on both sides. Wait for one side to be raided and a close "
                          "back inside, then trade toward the other side."),
                   target_label="Buy-side above", entry_label="Equilibrium", invalidation_label="Sell-side below")
    return out


def build_ladder(close, above, below, fv, obs, rngs):
    L = []
    for p in above + below:
        L.append({"kind": "ERL", "label": p["name"], "price": p["price"],
                  "status": "relative equal - strong pool" if p["equal"] else "unswept", "dist": p["dist"]})
    for f in fv:
        far = abs(pct(f["ce"], close))
        if f["status"] in ("open", "tapped", "CE tapped") or (f["status"] == "inverted" and far <= 4):
            L.append({"kind": "IRL", "label": f"{f['tf']} {f['side']} FVG ({f['date']})", "price": f["ce"],
                      "low": f["low"], "high": f["high"], "status": f["status"], "dist": pct(f["ce"], close)})
    for o in obs:
        mid = (o["low"] + o["high"]) / 2
        L.append({"kind": "IRL", "label": f"{o['side'].capitalize()} order block ({o['date']})", "price": r2(mid),
                  "low": o["low"], "high": o["high"], "status": o["status"], "dist": pct(mid, close)})
    for r in rngs:
        L.append({"kind": "EQ", "label": f"{r['lookback']}-day equilibrium", "price": r["eq"], "status": "",
                  "dist": pct(r["eq"], close)})
    return sorted([x for x in L if abs(x["dist"]) <= 12], key=lambda x: -x["price"])


def analyse(key, df, poi, smt_rows):
    a = atr(df)
    close = float(df["c"].iloc[-1])
    wk = resample(df, "W-FRI")
    sd, sw = structure(df), structure(wk)
    above, below = erl_pools(df, close, 0.2 * a)
    fv = fvgs(df, a, "Daily", 120) + fvgs(wk, atr(wk), "Weekly", 60)
    obs = order_blocks(df, a)
    rngs = ranges(df, close)
    ev = events(df, [f for f in fv if f["tf"] == "Daily"])
    drw = draw_on_liquidity(close, sd, sw, ev, above, below, fv, obs, rngs, smt_bias(key, smt_rows))
    return {
        "name": NAMES[key], "close": r2(close), "asof": d(df.index[-1]), "atr": r2(a),
        "structure": {"daily": sd, "weekly": sw}, "ranges": rngs,
        "erl": {"above": above, "below": below},
        "fvgs": [f for f in fv if f["status"] != "filled" and abs(pct(f["ce"], close)) <= 12],
        "obs": obs, "events": ev,
        "po3": {"week": po3(df, "W-FRI", "week"), "month": po3(df, "ME", "month")},
        "week_profile": week_profile(df, a), "draw": drw,
        "ladder": build_ladder(close, above, below, fv, obs, rngs),
        "signature": signature(df, poi),
    }


def main():
    prices = load("prices.json", {}) or {}
    poi = load("participant_oi.json", {}) or {}
    frames = {k: frame(prices, k) for k in FOCUS + ["USDINR", "DXY"]}
    smt_rows = smt(frames)
    out = {"generated": now_ist(), "focus": "SENSEX", "expiry": EXPIRY, "smt": smt_rows, "instruments": {}}
    for key in FOCUS:
        df = frames.get(key)
        if df is None or len(df) < 260:
            print(f"{key}: no data, skipped")
            continue
        out["instruments"][key] = analyse(key, df, poi, smt_rows)
        dr = out["instruments"][key]["draw"]
        print(f"{key:9} {dr['direction']:10} {dr['headline']}")
    save("ict.json", out)


if __name__ == "__main__":
    main()
